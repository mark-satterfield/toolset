---
name: "senior-data-engineer"
description: Data engineering skill for building scalable data pipelines, ETL/ELT systems, and data infrastructure. Expertise in Python and SQL on AWS serverless data services (EventBridge, DynamoDB Streams, Kinesis, Firehose, Glue, Athena, Iceberg on S3), with general knowledge of Spark, Airflow, dbt and Kafka. Includes data modeling, pipeline orchestration, data quality, and DataOps. Use when designing data architectures, building data pipelines, optimizing data workflows, implementing data governance, or troubleshooting data issues.
---

# Senior Data Engineer

Production-grade data engineering skill for building scalable, reliable data systems.

## Table of Contents

1. [Trigger Phrases](#trigger-phrases)
2. [Quick Start](#quick-start)
3. [Workflows](#workflows)
   - [Building a Batch ETL Pipeline](#workflow-1-building-a-batch-etl-pipeline)
   - [Implementing Real-Time Streaming](#workflow-2-implementing-real-time-streaming)
   - [Data Quality Framework Setup](#workflow-3-data-quality-framework-setup)
4. [Architecture Decision Framework](#architecture-decision-framework)
5. [Tech Stack](#tech-stack)
6. [Reference Documentation](#reference-documentation)
7. [Troubleshooting](#troubleshooting)

---

## Trigger Phrases

Activate this skill when you see:

**Pipeline Design:**
- "Design a data pipeline for..."
- "Build an ETL/ELT process..."
- "How should I ingest data from..."
- "Set up data extraction from..."

**Architecture:**
- "Should I use batch or streaming?"
- "Lambda vs Kappa architecture"
- "How to handle late-arriving data"
- "Design a data lakehouse"

**Data Modeling:**
- "Create a dimensional model..."
- "Star schema vs snowflake"
- "Implement slowly changing dimensions"
- "Design a data vault"

**Data Quality:**
- "Add data validation to..."
- "Set up data quality checks"
- "Monitor data freshness"
- "Implement data contracts"

**Performance:**
- "Optimize this Spark job"
- "Query is running slow"
- "Reduce pipeline execution time"
- "Tune Airflow DAG"

---

## Quick Start

### Core Tools

```bash
# Generate pipeline orchestration config
python scripts/pipeline_orchestrator.py generate \
  --type airflow \
  --source postgres \
  --destination snowflake \
  --schedule "0 5 * * *"

# Validate data quality
python scripts/data_quality_validator.py validate \
  --input data/sales.parquet \
  --schema schemas/sales.json \
  --checks freshness,completeness,uniqueness

# Optimize ETL performance
python scripts/etl_performance_optimizer.py analyze \
  --query queries/daily_aggregation.sql \
  --engine spark \
  --recommend
```

---

## Workflows
→ See references/workflows.md for details

## Architecture Decision Framework

Use this framework to choose the right approach for your data pipeline. SkillSpoke runs on AWS serverless services, owned per service and built in Python CDK: Python Lambdas on `aws-lambda-powertools`, DynamoDB and Aurora PostgreSQL Serverless v2 (through the RDS Data API), S3, SkillSpoke events through the events service onto the one EventBridge bus, and CloudWatch, X-Ray and ADOT for observability. At alpha scale (one dev account, at most five users), prefer per-request services over always-on clusters unless a stated need justifies the floor cost.

### Batch vs Streaming

| Criteria | Batch | Streaming |
|----------|-------|-----------|
| **Latency requirement** | Hours to days | Seconds to minutes |
| **Data volume** | Large historical datasets | Continuous event streams |
| **Processing complexity** | Complex transformations, ML | Simple aggregations, filtering |
| **Cost sensitivity** | More cost-effective | Higher infrastructure cost |
| **Error handling** | Easier to reprocess | Requires careful design |

**Decision Tree (AWS services SkillSpoke uses):**
```
Is real-time insight required?
├── Yes → Use streaming
│   ├── Reacting to a SkillSpoke business or system event?
│   │   └── EventBridge: publish through the central event API; the target's
│   │       stack owns the routing rule, its SQS queue or Lambda target and DLQ
│   ├── Reacting to changes in a service's own DynamoDB table?
│   │   └── DynamoDB Streams → Lambda event source mapping (Powertools batch
│   │       processing, bisect on error, on-failure destination)
│   ├── High-volume ordered records (clickstream, logs) to process or land?
│   │   └── Kinesis Data Streams (on-demand) → Lambda, or → Amazon Data Firehose
│   │       to S3 / Apache Iceberg tables (Firehose delivers exactly once to Iceberg)
│   └── Stateful stream processing with exactly-once state (joins, sessions)?
│       └── Amazon Managed Service for Apache Flink over Kinesis; a running
│           application is billed per hour, so justify it with a stated need
└── No → Use batch
    ├── Small or moderate volume → scheduled Lambda (EventBridge Scheduler) or
    │   Step Functions over S3 / DynamoDB / Aurora, SQL in Athena
    └── Large volume (> ~1 TB daily) → AWS Glue (Spark) jobs or Athena CTAS
        into Iceberg on S3
```

Every consumer is idempotent (delivery is at least once), and every stream consumer has an on-failure destination or DLQ. Kafka (including Amazon MSK) is not part of SkillSpoke's stack: an MSK cluster is always-on capacity, and EventBridge, Kinesis and DynamoDB Streams cover SkillSpoke's streaming needs. Use the Kafka material in the references only when the task is explicitly about an external Kafka source.

Cost facts to weigh (confirm current prices with the AWS documentation tools): Kinesis Data Streams in On-demand Standard mode charges per GB written and read plus an hourly charge for each stream; Firehose charges per GB ingested; Managed Service for Apache Flink charges per running application hour; EventBridge custom-bus events and Lambda are charged per request.

### Lambda vs Kappa Architecture

| Aspect | Lambda | Kappa |
|--------|--------|-------|
| **Complexity** | Two codebases (batch + stream) | Single codebase |
| **Maintenance** | Higher (sync batch/stream logic) | Lower |
| **Reprocessing** | Native batch layer | Replay from source |
| **Use case** | ML training + real-time serving | Pure event-driven |

**When to choose Lambda:**
- Need to train ML models on historical data
- Complex batch transformations not feasible in streaming
- Existing batch infrastructure

**When to choose Kappa:**
- Event-sourced architecture
- All processing can be expressed as stream operations
- Starting fresh without legacy systems

SkillSpoke does not use EventBridge archive or replay; replay for a Kappa design comes from the stream's retention (Kinesis) or from the data a service keeps in S3.

### Data Warehouse vs Data Lakehouse

| Feature | Warehouse (Amazon Redshift Serverless) | Lakehouse (Iceberg on S3 / S3 Tables, queried with Athena) |
|---------|-------------------------------|---------------------------|
| **Best for** | BI, SQL analytics | ML, unstructured data |
| **Storage cost** | Higher (managed storage) | Lower (open formats) |
| **Flexibility** | Schema-on-write | Schema-on-read |
| **Performance** | Excellent for SQL | Good, improving |
| **Pricing** | Per RPU-second while queries run | Per TB scanned (Athena) plus S3 storage |

---

## Tech Stack

The AWS services SkillSpoke uses come first in each row; the rest are general knowledge for reading other systems, not choices for SkillSpoke.

| Category | SkillSpoke (AWS) | Other systems you may meet |
|----------|------------------|----------------------------|
| **Languages** | Python, SQL | Scala |
| **Orchestration** | Step Functions, EventBridge Scheduler, Lambda durable functions | Airflow (MWAA), Prefect, Dagster |
| **Transformation** | Lambda, AWS Glue (Spark), Athena SQL | dbt, Spark, Flink |
| **Streaming** | EventBridge (through the events service), DynamoDB Streams, Kinesis Data Streams, Amazon Data Firehose | Kafka, Pub/Sub |
| **Storage** | S3, Apache Iceberg / S3 Tables, DynamoDB, Aurora PostgreSQL Serverless v2 | GCS, Delta Lake |
| **Warehouses** | Athena, Redshift Serverless | Snowflake, BigQuery, Databricks |
| **Quality** | Validation at the boundary in Python (Pydantic), AWS Glue Data Quality | Great Expectations, dbt tests |
| **Monitoring** | CloudWatch metrics, logs and alarms, X-Ray, ADOT, SkillSpoke observability events | Prometheus, Grafana, Datadog |

---

## Reference Documentation

The references hold general data-engineering knowledge. Their examples use Airflow, dbt, Kafka, Spark, Snowflake and Prometheus; in SkillSpoke, map each to the AWS service in the Tech Stack table above, and follow this file where they differ.

### 1. Data Pipeline Architecture
See `references/data_pipeline_architecture.md` for:
- Lambda vs Kappa architecture patterns
- Batch processing with Spark and Airflow
- Stream processing patterns (shown with Kafka and Flink)
- Exactly-once semantics implementation
- Error handling and dead letter queues

### 2. Data Modeling Patterns
See `references/data_modeling_patterns.md` for:
- Dimensional modeling (Star/Snowflake)
- Slowly Changing Dimensions (SCD Types 1-6)
- Data Vault modeling
- dbt best practices
- Partitioning and clustering

### 3. DataOps Best Practices
See `references/dataops_best_practices.md` for:
- Data testing frameworks
- Data contracts and schema validation
- CI/CD for data pipelines
- Observability and lineage
- Incident response

---

## Troubleshooting
→ See references/troubleshooting.md for details

