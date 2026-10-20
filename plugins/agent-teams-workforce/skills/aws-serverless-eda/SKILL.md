---
name: aws-serverless-eda
description: AWS serverless and event-driven architecture expert based on the Well-Architected Framework, applied to SkillSpoke's stack (Python Lambdas on aws-lambda-powertools, API Gateway REST API v1, DynamoDB, CDK in Python, SkillSpoke events through the events service onto EventBridge). Use when building serverless APIs, Lambda functions, REST APIs, microservices, or async workflows. Covers Lambda, API Gateway REST API v1 and the WebSocket API, DynamoDB, Step Functions, EventBridge, SQS, SNS, and serverless patterns. Essential when user mentions serverless, Lambda, API Gateway, event-driven, async processing, queues, pub/sub, or wants to build scalable serverless applications with AWS best practices.
context: fork
skills:
  - aws-mcp-setup
  - aws-cdk-development
allowed-tools:
  - mcp__aws-mcp__*
  - mcp__awsdocs__*
  - mcp__cdk__*
  - Bash(sam local *)
  - Bash(aws lambda *)
  - Bash(aws apigateway *)
  - Bash(aws apigatewayv2 *)
  - Bash(aws dynamodb *)
  - Bash(aws stepfunctions *)
  - Bash(aws events *)
  - Bash(aws sqs *)
  - Bash(aws sns *)
  - Bash(aws sts get-caller-identity)
---

# AWS Serverless & Event-Driven Architecture

This skill provides guidance for building serverless applications and event-driven architectures on AWS based on Well-Architected Framework principles, in SkillSpoke's stack:

- Every service Lambda is Python on `aws-lambda-powertools`, through `shared-chassis-lib`. Django, Flask and FastAPI are banned.
- APIs are API Gateway REST API v1, spec-first in OpenAPI; HTTP API v2 is not used. Live push uses the API Gateway WebSocket API (the `apigatewayv2` CLI covers WebSocket APIs; it is never used to create an HTTP API).
- Infrastructure is CDK in Python, one CDK app per service with one stack per environment holding every resource the service owns. Values cross stacks only through SSM Parameter Store, never CloudFormation exports and imports.
- SkillSpoke events are published only through the central event API of the events service, which puts them on the single bus; a routing rule is owned by the stack of its target. Load the `skillspoke-events` skill for anything that produces, routes or receives a SkillSpoke event.
- Every name comes from the project's naming command (the `resource-naming` skill).
- Alpha scale (one dev account, at most five users): per-request pricing (Lambda, DynamoDB on-demand) over always-on capacity unless a stated need justifies it.

## AWS Documentation Requirement

Always verify AWS facts using MCP tools (`mcp__aws-mcp__*` or `mcp__*awsdocs*__*`) before answering. The `aws-mcp-setup` dependency is auto-loaded — if MCP tools are unavailable, guide the user through that skill's setup flow.

## Serverless MCP Servers

This skill leverages the CDK MCP server (provided via `aws-cdk-development` dependency) and AWS Documentation MCP for serverless guidance.

> **Note**: The following AWS MCP servers are available separately via the Full AWS MCP Server (see `aws-mcp-setup` skill) and are not bundled with this plugin:
> - AWS Serverless MCP — SAM CLI local testing (SkillSpoke deploys with CDK, not `sam deploy`)
> - AWS Lambda Tool MCP — Direct Lambda invocation
> - AWS Step Functions MCP — Workflow orchestration
> - Amazon SNS/SQS MCP — Messaging and queue management

## When to Use This Skill

Use this skill when:
- Building serverless applications with Lambda
- Designing event-driven architectures
- Implementing microservices patterns
- Creating asynchronous processing workflows
- Orchestrating multi-service transactions
- Building real-time data processing pipelines
- Implementing saga patterns for distributed transactions
- Designing for scale and resilience

## AWS Well-Architected Serverless Design Principles

### 1. Speedy, Simple, Singular

**Functions should be concise and single-purpose**

```python
from aws_lambda_powertools.utilities.typing import LambdaContext


# GOOD - single purpose, focused function
def process_order(event: dict[str, object], context: LambdaContext) -> dict[str, object]:
    order = validate_order(event)
    save_order(order)
    publish_order_created(order)  # through the central event API
    return {"statusCode": 200, "body": json.dumps({"orderId": order.order_id})}


# BAD - one function handles orders, inventory, payments, shipping...
```

**Keep functions environmentally efficient and cost-aware**:
- Minimize cold start times
- Optimize memory allocation
- Use provisioned concurrency only when a measured latency need justifies its always-on cost
- Leverage connection reuse (create SDK clients at module scope)

### 2. Think Concurrent Requests, Not Total Requests

**Design for concurrency, not volume**

Lambda scales horizontally - design considerations should focus on:
- Concurrent execution limits
- Downstream service throttling
- Shared resource contention
- Connection pool sizing

```python
from aws_cdk import aws_dynamodb as dynamodb

# On-demand capacity scales with concurrent load and costs nothing when idle.
table = dynamodb.TableV2(
    self,
    "Table",
    table_name=table_name,  # from the naming command
    partition_key=dynamodb.Attribute(name="pk", type=dynamodb.AttributeType.STRING),
    billing=dynamodb.Billing.on_demand(),
)
```

Provisioned capacity with auto-scaling is cheaper only for steady, predictable traffic high enough to keep the provisioned units busy; at SkillSpoke's alpha scale it is a monthly floor that low usage does not reduce. Choose it only for a stated, measured need (see the `dynamodb` skill).

### 3. Share Nothing

**Function runtime environments are short-lived**

```python
# BAD - relying on the local file system between invocations
def handler(event: dict[str, object], context: LambdaContext) -> None:
    Path("/tmp/data.json").write_text(json.dumps(data))  # lost when the environment is recycled


# GOOD - persistent storage
s3 = boto3.client("s3")


def handler(event: dict[str, object], context: LambdaContext) -> None:
    s3.put_object(Bucket=os.environ["BUCKET_NAME"], Key="data.json", Body=json.dumps(data))
```

**State management**:
- Use DynamoDB for persistent state and for the session record
- Use Step Functions or Lambda durable functions for workflow state (see principle 5)
- Use S3 for file storage and for large results
- ElastiCache is deployed only when a measured need appears; it is not the session store and not the idempotency store

### 4. Assume No Hardware Affinity

**Applications must be hardware-agnostic**

Infrastructure can change without notice:
- Lambda functions can run on different hardware
- No assumption about underlying infrastructure

**Design for portability**:
- Read configuration at run time (environment variables for deploy-time values, SSM Parameter Store and runtime configuration for values that change)
- Avoid hardware-specific optimizations
- Test across different environments

### 5. Orchestrate with State Machines, Not Function Chaining

**Orchestrate with Step Functions or Lambda durable functions, never Lambda-to-Lambda chaining**

Choose on the workload (https://docs.aws.amazon.com/lambda/latest/dg/durable-step-functions.html):
- **Lambda durable functions** when the workflow is code-first and tightly coupled with the business logic of a Lambda function, with fine-grained steps, retries and checkpoints inside that function.
- **Step Functions** when the workflow orchestrates across AWS services (native integrations with no Lambda in between), needs a visual or auditable definition, or spans several services or teams.

Coordination between SkillSpoke services is by events, not a central state machine: a state machine orchestrates work inside one service, and rollback across services uses compensating events.

Record which one you chose and why in your result.

```python
from aws_cdk import aws_stepfunctions as sfn

# BAD - one Lambda invoking the next with lambda_client.invoke(...)

# GOOD - Step Functions orchestration inside one service
state_machine = sfn.StateMachine(
    self,
    "OrderWorkflow",
    state_machine_name=state_machine_name,  # from the naming command
    definition_body=sfn.DefinitionBody.from_chainable(
        validate_order.next(process_payment).next(ship_order).next(send_confirmation)
    ),
)
```

**Benefits of Step Functions**:
- Visual workflow representation
- Built-in error handling and retries
- Execution history and debugging
- Parallel and sequential execution
- Service integrations without code

### 6. Use Events to Trigger Transactions

**Event-driven over synchronous request/response**

```python
from aws_cdk import aws_s3 as s3, aws_s3_notifications as s3n

# Pattern: a resource event inside the service
bucket.add_event_notification(
    s3.EventType.OBJECT_CREATED,
    s3n.LambdaDestination(process_function),
    s3.NotificationKeyFilter(prefix="uploads/"),
)
```

Between services, a SkillSpoke event is published through the central event API (never with a direct `PutEvents` from the producer), and the stack that owns the target owns the routing rule on the bus, with the target's retry policy and DLQ. The bus name and ARN are read from the SSM parameters `shared-events-infra` publishes. The `skillspoke-events` skill holds the rule, its event pattern and the target's obligations.

**Benefits**:
- Loose coupling between services
- Asynchronous processing
- Better fault tolerance
- Independent scaling

### 7. Design for Failures and Duplicates

**Operations must be idempotent**

Delivery is at least once, so every operation that creates or changes something is idempotent. Never check for a record and then write it as two calls: two concurrent deliveries both see no record and both process. Use the Powertools idempotency utility with its DynamoDB persistence layer (through the chassis), which claims the key with a conditional write before the work runs. Each service that needs it owns an on-demand idempotency table with TTL in its own stack (attribute `id` as partition key, TTL on `expiration`). Reads are never made idempotent.

```python
import os

from aws_lambda_powertools.utilities.batch import BatchProcessor, EventType, process_partial_response
from aws_lambda_powertools.utilities.data_classes.sqs_event import SQSRecord
from aws_lambda_powertools.utilities.idempotency import (
    DynamoDBPersistenceLayer,
    IdempotencyConfig,
    idempotent_function,
)
from aws_lambda_powertools.utilities.typing import LambdaContext

persistence = DynamoDBPersistenceLayer(table_name=os.environ["IDEMPOTENCY_TABLE_NAME"])
config = IdempotencyConfig(event_key_jmespath="orderId")
processor = BatchProcessor(event_type=EventType.SQS)


@idempotent_function(data_keyword_argument="order", config=config, persistence_store=persistence)
def process_order(order: dict[str, str]) -> dict[str, str]:
    ...  # create or change something; return a small result (an ID or a status)
    return {"orderId": order["orderId"], "status": "processed"}


def record_handler(record: SQSRecord) -> None:
    process_order(order=record.json_body)


def handler(event: dict[str, object], context: LambdaContext) -> dict[str, object]:
    config.register_lambda_context(context)
    return process_partial_response(event=event, record_handler=record_handler, processor=processor, context=context)
```

Where the operation itself is a single DynamoDB write, a conditional write (`ConditionExpression="attribute_not_exists(pk)"`, treating `ConditionalCheckFailedException` as "already done") is idempotent on its own and needs no idempotency table.

**Retries come from the SDK, not from a hand-written loop**: the AWS SDK already retries with exponential backoff and jitter, and a loop around an SDK call multiplies the attempts. Configure the client's retry mode instead: standard mode unless you have a specific reason to choose another (https://docs.aws.amazon.com/sdkref/latest/guide/feature-retry-behavior.html); adaptive mode only for a client throttled against a single resource. Retries of a failed event belong to the event source (SQS redelivery, EventBridge retry policy) with a DLQ, which is why the handler must be idempotent.

## Architecture Patterns

For detailed implementation patterns with full code examples, see the reference documentation:

### Event-Driven Architecture Patterns
**File**: `references/eda-patterns.md`
- Event Router with EventBridge (rule-based routing; SkillSpoke events go through the events service onto the one bus)
- Queue-Based Processing with SQS (standard/FIFO, DLQ, Lambda consumers)
- Pub/Sub Fan-Out with SNS + SQS (multi-consumer, filtering)
- Saga Pattern with Step Functions (distributed transactions, compensating actions)
- Event Sourcing with DynamoDB Streams (append-only event store, projections)

### Serverless Architecture Patterns
**File**: `references/serverless-patterns.md`
- API-Driven Microservices (REST API v1 + Lambda backend)
- Stream Processing with Kinesis (real-time, batch windowing, bisect on error)
- Async Task Processing with SQS (background jobs, concurrency control)
- Scheduled Jobs with EventBridge Scheduler (cron/rate schedules)
- Webhook Processing (signature validation, async queue forwarding)

The reference files hold some TypeScript examples; SkillSpoke writes the same constructs in Python CDK and the handlers in Python.

> **Important**: How CDK code names resources (`rest_api_name`, `function_name`, `table_name`, `queue_name`, state machine and stack names, SSM parameter names) is the physical-name rule of the `cdk-coding` skill. When `printenv ATW_NAMING_COMMAND` prints nothing, say so in your result and leave the name unmade.

## Best Practices

### Error Handling

**Report partial batch failures** so only the failed records are retried (enable `report_batch_item_failures` on the event source mapping). Powertools `process_partial_response` (shown in principle 7) builds the `batchItemFailures` response:

```python
from aws_cdk import aws_lambda_event_sources as sources

function.add_event_source(sources.SqsEventSource(queue, report_batch_item_failures=True))
```

### Dead Letter Queues

**Always configure DLQs for error handling**:

```python
from aws_cdk import Duration, aws_cloudwatch as cloudwatch, aws_sqs as sqs

dlq = sqs.Queue(
    self,
    "Dlq",
    queue_name=dlq_name,  # from the naming command
    retention_period=Duration.days(14),
    encryption=sqs.QueueEncryption.KMS_MANAGED,
    enforce_ssl=True,
)

queue = sqs.Queue(
    self,
    "Queue",
    queue_name=queue_name,  # from the naming command
    dead_letter_queue=sqs.DeadLetterQueue(queue=dlq, max_receive_count=3),
    encryption=sqs.QueueEncryption.KMS_MANAGED,
    enforce_ssl=True,
)

cloudwatch.Alarm(
    self,
    "DlqAlarm",
    metric=dlq.metric_approximate_number_of_messages_visible(),
    threshold=1,
    evaluation_periods=1,
    alarm_description="Messages in DLQ require attention",
)
```

### Observability

**Enable tracing and monitoring** (CloudWatch, X-Ray, ADOT):

```python
from aws_cdk import aws_lambda as lambda_

lambda_.Function(
    self,
    "Function",
    function_name=function_name,  # from the naming command
    runtime=lambda_.Runtime.PYTHON_3_14,
    handler="handler.handler",
    code=lambda_.Code.from_asset("src"),
    tracing=lambda_.Tracing.ACTIVE,  # X-Ray tracing
    environment={
        "POWERTOOLS_SERVICE_NAME": powertools_service,  # from the naming command
        "POWERTOOLS_METRICS_NAMESPACE": metrics_namespace,  # from the naming command
        "POWERTOOLS_LOG_LEVEL": "INFO",
    },
)
```

Packaging Python dependencies and the shared constructs every stack uses come from `shared-cdk-lib`; see the `aws-cdk-development` and `cdk-coding` skills.

## Using MCP Servers Effectively

Use the CDK MCP server (via `aws-cdk-development` dependency) for construct recommendations and CDK-specific guidance when building serverless infrastructure.

Use AWS Documentation MCP to verify service features, regional availability, and API specifications before implementing.

## Additional Resources

This skill includes comprehensive reference documentation based on AWS best practices:

- **Serverless Patterns**: `references/serverless-patterns.md`
  - Core serverless architectures and API patterns
  - Data processing and integration patterns
  - Orchestration with Step Functions
  - Anti-patterns to avoid

- **Event-Driven Architecture Patterns**: `references/eda-patterns.md`
  - Event routing and processing patterns
  - Event sourcing and saga patterns
  - Idempotency and error handling
  - Message ordering and deduplication

- **Security Best Practices**: `references/security-best-practices.md`
  - Shared responsibility model
  - IAM least privilege patterns
  - Data protection and encryption
  - Network security with VPC

- **Observability Best Practices**: `references/observability-best-practices.md`
  - Three pillars: metrics, logs, traces
  - Structured logging with Lambda Powertools
  - X-Ray distributed tracing
  - CloudWatch alarms and dashboards

- **Performance Optimization**: `references/performance-optimization.md`
  - Cold start optimization techniques
  - Memory and CPU optimization
  - Package size reduction
  - Provisioned concurrency patterns

- **Deployment Best Practices**: `references/deployment-best-practices.md`
  - CI/CD pipeline design
  - Testing strategies (unit, integration, load)
  - Deployment strategies (canary, blue/green)
  - Rollback and safety mechanisms

**External Resources**:
- **AWS Well-Architected Serverless Lens**: https://docs.aws.amazon.com/wellarchitected/latest/serverless-applications-lens/
- **ServerlessLand.com**: Pre-built serverless patterns
- **AWS Serverless Workshops**: https://serverlessland.com/learn?type=Workshops

For detailed implementation patterns, anti-patterns, and code examples, refer to the comprehensive references in the skill directory.
