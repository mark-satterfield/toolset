# senior-data-engineer reference

## Workflows

### Workflow 1: Building a Batch ETL Pipeline

**Scenario:** Extract data from PostgreSQL, transform with dbt, load to Snowflake.

#### Step 1: Define Source Schema

```sql
-- Document source tables
SELECT
    table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'source_schema'
ORDER BY table_name, ordinal_position;
```

#### Step 2: Generate Extraction Config

```bash
python scripts/pipeline_orchestrator.py generate \
  --type airflow \
  --source postgres \
  --tables orders,customers,products \
  --mode incremental \
  --watermark updated_at \
  --output dags/extract_source.py
```

#### Step 3: Create dbt Models

```sql
-- models/staging/stg_orders.sql
WITH source AS (
    SELECT * FROM {{ source('postgres', 'orders') }}
),

renamed AS (
    SELECT
        order_id,
        customer_id,
        order_date,
        total_amount,
        status,
        _extracted_at
    FROM source
    WHERE order_date >= DATEADD(day, -3, CURRENT_DATE)
)

SELECT * FROM renamed
```

```sql
-- models/marts/fct_orders.sql
{{
    config(
        materialized='incremental',
        unique_key='order_id',
        cluster_by=['order_date']
    )
}}

SELECT
    o.order_id,
    o.customer_id,
    c.customer_segment,
    o.order_date,
    o.total_amount,
    o.status
FROM {{ ref('stg_orders') }} o
LEFT JOIN {{ ref('dim_customers') }} c
    ON o.customer_id = c.customer_id

{% if is_incremental() %}
WHERE o._extracted_at > (SELECT MAX(_extracted_at) FROM {{ this }})
{% endif %}
```

#### Step 4: Configure Data Quality Tests

```yaml
# models/marts/schema.yml
version: 2

models:
  - name: "fct-orders"
    description: "Order fact table"
    columns:
      - name: "order-id"
        tests:
          - unique
          - not_null
      - name: "total-amount"
        tests:
          - not_null
          - dbt_utils.accepted_range:
              min_value: 0
              max_value: 1000000
      - name: "order-date"
        tests:
          - not_null
          - dbt_utils.recency:
              datepart: day
              field: order_date
              interval: 1
```

#### Step 5: Create Airflow DAG

```python
# dags/daily_etl.py
from airflow import DAG
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago
from datetime import timedelta

default_args = {
    "owner": "data-team",
    "depends_on_past": False,
    "email_on_failure": True,
    "email": ["data-alerts@company.com"],
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    "daily_etl_pipeline",
    default_args=default_args,
    description="Daily ETL from PostgreSQL to Snowflake",
    schedule_interval="0 5 * * *",
    start_date=days_ago(1),
    catchup=False,
    tags=["etl", "daily"],
) as dag:
    extract = BashOperator(
        task_id="extract_source_data",
        bash_command="python /opt/airflow/scripts/extract.py --date {{ ds }}",
    )

    transform = BashOperator(
        task_id="run_dbt_models",
        bash_command="cd /opt/airflow/dbt && dbt run --select marts.*",
    )

    test = BashOperator(
        task_id="run_dbt_tests",
        bash_command="cd /opt/airflow/dbt && dbt test --select marts.*",
    )

    notify = BashOperator(
        task_id="send_notification",
        bash_command="python /opt/airflow/scripts/notify.py --status success",
        trigger_rule="all_success",
    )

    extract >> transform >> test >> notify
```

#### Step 6: Validate Pipeline

```bash
# Test locally
dbt run --select stg_orders fct_orders
dbt test --select fct_orders

# Validate data quality
python scripts/data_quality_validator.py validate \
  --table fct_orders \
  --checks all \
  --output reports/quality_report.json
```

---

### Workflow 2: Implementing Real-Time Streaming

**Scenario:** Stream high-volume records through Kinesis Data Streams, process them with a Python Lambda, and land them in an Apache Iceberg table on S3 through Amazon Data Firehose. For the project's business events use EventBridge instead, as the project's event standard defines (the project instructions name it; load it before you design, specify, review or implement anything that produces, routes or receives an event); for changes to a service's own table use DynamoDB Streams with the same Lambda pattern.

#### Step 1: Define the Record Schema

Validate every record at the boundary with a typed model (Powertools parser with Pydantic):

```python
from datetime import datetime

from pydantic import BaseModel


class UserActivity(BaseModel):
    """One activity record on the stream; carries identifiers, never seeker content."""

    activity_id: str
    user_id: str
    activity_type: str
    occurred_at: datetime
```

#### Step 2: Define the Stream, Consumer and Delivery in CDK

Names come from the project's naming command (the `resource-naming` skill).

```python
from aws_cdk import Duration, aws_kinesis as kinesis, aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as sources, aws_sqs as sqs

stream = kinesis.Stream(
    self,
    "ActivityStream",
    stream_name=stream_name,  # from the naming command
    stream_mode=kinesis.StreamMode.ON_DEMAND,
    encryption=kinesis.StreamEncryption.MANAGED,
    retention_period=Duration.hours(24),
)

failures = sqs.Queue(self, "ActivityFailures", queue_name=failure_queue_name, enforce_ssl=True)

consumer.add_event_source(
    sources.KinesisEventSource(
        stream,
        starting_position=lambda_.StartingPosition.TRIM_HORIZON,
        batch_size=100,
        bisect_batch_on_error=True,
        retry_attempts=3,
        report_batch_item_failures=True,
        on_failure=sources.SqsDlq(failures),
    )
)
```

Land the raw records with an Amazon Data Firehose stream whose source is the Kinesis stream and whose destination is the Iceberg table (Firehose delivers exactly once to Iceberg tables and needs the AWS Glue Data Catalog).

#### Step 3: Implement the Consumer

```python
from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.batch import BatchProcessor, EventType, process_partial_response
from aws_lambda_powertools.utilities.data_classes.kinesis_stream_event import KinesisStreamRecord
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()
metrics = Metrics()
processor = BatchProcessor(event_type=EventType.KinesisDataStreams)


def record_handler(record: KinesisStreamRecord) -> None:
    activity = UserActivity.model_validate_json(record.kinesis.data_as_text())
    apply_activity(activity)  # idempotent: delivery is at least once
    metrics.add_metric(name="ActivitiesProcessed", unit=MetricUnit.Count, value=1)


@metrics.log_metrics
@logger.inject_lambda_context
def handler(event: dict[str, object], context: LambdaContext) -> dict[str, object]:
    return process_partial_response(event=event, record_handler=record_handler, processor=processor, context=context)
```

#### Step 4: Handle Late Data and Errors

- Partial batch responses retry only the failed records; bisect on error isolates a poison record, and after the retry attempts it goes to the on-failure destination with its shard ID and sequence numbers.
- Late records are applied by event time, not arrival time: keep the newest version per key with a conditional write, and let windowed aggregates in the Iceberg table be recomputed by Athena.
- For windowed aggregation in the consumer, use the event source mapping's tumbling window; for stateful processing beyond that, use Amazon Managed Service for Apache Flink (an hourly-billed application, justified only by a stated need).

#### Step 5: Monitor Stream Health

Alarm in CloudWatch on the consumer's `IteratorAge` (how far behind the stream it is), the on-failure queue's depth, Lambda errors and throttles, and the Firehose delivery metrics; trace the consumer with X-Ray. The `cloudwatch` skill has the alarm patterns.

---

### Workflow 3: Data Quality Framework Setup

**Scenario:** Implement comprehensive data quality monitoring with Great Expectations.

#### Step 1: Initialize Great Expectations

```bash
# Install and initialize
pip install great_expectations

great_expectations init

# Connect to data source
great_expectations datasource new
```

#### Step 2: Create Expectation Suite

```python
# expectations/orders_suite.py
import great_expectations as gx

context = gx.get_context()

# Create expectation suite
suite = context.add_expectation_suite("orders_quality_suite")

# Add expectations
validator = context.get_validator(
    batch_request={
        "datasource_name": "warehouse",
        "data_asset_name": "orders",
    },
    expectation_suite_name="orders_quality_suite",
)

# Schema expectations
validator.expect_table_columns_to_match_ordered_list(
    column_list=["order_id", "customer_id", "order_date", "total_amount", "status", "created_at"]
)

# Completeness expectations
validator.expect_column_values_to_not_be_null("order_id")
validator.expect_column_values_to_not_be_null("customer_id")
validator.expect_column_values_to_not_be_null("order_date")

# Uniqueness expectations
validator.expect_column_values_to_be_unique("order_id")

# Range expectations
validator.expect_column_values_to_be_between("total_amount", min_value=0, max_value=1000000)

# Categorical expectations
validator.expect_column_values_to_be_in_set("status", ["pending", "confirmed", "shipped", "delivered", "cancelled"])

# Freshness expectation
validator.expect_column_max_to_be_between(
    "order_date", min_value={"$PARAMETER": "now - timedelta(days=1)"}, max_value={"$PARAMETER": "now"}
)

# Referential integrity
validator.expect_column_values_to_be_in_set("customer_id", value_set={"$PARAMETER": "valid_customer_ids"})

validator.save_expectation_suite(discard_failed_expectations=False)
```

#### Step 3: Create Data Quality Checks with dbt

```yaml
# models/marts/schema.yml
version: 2

models:
  - name: "fct-orders"
    description: "Order fact table with data quality checks"

    tests:
      # Row count check
      - dbt_utils.equal_rowcount:
          compare_model: ref('stg_orders')

      # Freshness check
      - dbt_utils.recency:
          datepart: hour
          field: created_at
          interval: 24

    columns:
      - name: "order-id"
        description: "Unique order identifier"
        tests:
          - unique
          - not_null
          - relationships:
              to: ref('dim_orders')
              field: order_id

      - name: "total-amount"
        tests:
          - not_null
          - dbt_utils.accepted_range:
              min_value: 0
              max_value: 1000000
              inclusive: true
          - dbt_expectations.expect_column_values_to_be_between:
              min_value: 0
              row_condition: "status != 'cancelled'"

      - name: "customer-id"
        tests:
          - not_null
          - relationships:
              to: ref('dim_customers')
              field: customer_id
              severity: warn
```

#### Step 4: Implement Data Contracts

```yaml
# contracts/orders_contract.yaml
contract:
  name: "orders-data-contract"
  version: "1.0.0"
  owner: data-team@company.com

schema:
  type: object
  properties:
    order_id:
      type: string
      format: uuid
      description: "Unique order identifier"
    customer_id:
      type: string
      not_null: true
    order_date:
      type: date
      not_null: true
    total_amount:
      type: decimal
      precision: 10
      scale: 2
      minimum: 0
    status:
      type: string
      enum: ["pending", "confirmed", "shipped", "delivered", "cancelled"]

sla:
  freshness:
    max_delay_hours: 1
  completeness:
    min_percentage: 99.9
  accuracy:
    duplicate_tolerance: 0.01

consumers:
  - name: "analytics-team"
    usage: "Daily reporting dashboards"
  - name: "ml-team"
    usage: "Churn prediction model"
```

#### Step 5: Set Up Quality Monitoring Dashboard

```python
# monitoring/quality_dashboard.py
from datetime import datetime, timedelta
import pandas as pd

def generate_quality_report(connection, table_name: "str-dict"
    """Generate comprehensive data quality report."""

    report = {
        "table": table_name,
        "timestamp": datetime.now().isoformat(),
        "checks": {}
    }

    # Row count check
    row_count = connection.execute(
        f"SELECT COUNT(*) FROM {table_name}"
    ).fetchone()[0]
    report["checks"]["row_count"] = {
        "value": row_count,
        "status": "pass" if row_count > 0 else "fail"
    }

    # Freshness check
    max_date = connection.execute(
        f"SELECT MAX(created_at) FROM {table_name}"
    ).fetchone()[0]
    hours_old = (datetime.now() - max_date).total_seconds() / 3600
    report["checks"]["freshness"] = {
        "max_timestamp": max_date.isoformat(),
        "hours_old": round(hours_old, 2),
        "status": "pass" if hours_old < 24 else "fail"
    }

    # Null rate check
    null_query = f"""
    SELECT
        SUM(CASE WHEN order_id IS NULL THEN 1 ELSE 0 END) as null_order_id,
        SUM(CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END) as null_customer_id,
        COUNT(*) as total
    FROM {table_name}
    """
    null_result = connection.execute(null_query).fetchone()
    report["checks"]["null_rates"] = {
        "order_id": null_result[0] / null_result[2] if null_result[2] > 0 else 0,
        "customer_id": null_result[1] / null_result[2] if null_result[2] > 0 else 0,
        "status": "pass" if null_result[0] == 0 and null_result[1] == 0 else "fail"
    }

    # Duplicate check
    dup_query = f"""
    SELECT COUNT(*) - COUNT(DISTINCT order_id) as duplicates
    FROM {table_name}
    """
    duplicates = connection.execute(dup_query).fetchone()[0]
    report["checks"]["duplicates"] = {
        "count": duplicates,
        "status": "pass" if duplicates == 0 else "fail"
    }

    # Overall status
    all_passed = all(
        check["status"] == "pass"
        for check in report["checks"].values()
    )
    report["overall_status"] = "pass" if all_passed else "fail"

    return report
```

---
