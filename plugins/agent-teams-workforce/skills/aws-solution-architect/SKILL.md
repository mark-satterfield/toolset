---
name: "aws-solution-architect"
description: Design AWS architectures for SkillSpoke using serverless, event-driven patterns, expressed as CDK in Python. Use when asked to design serverless architecture, choose AWS services, estimate or optimize AWS costs, set up CI/CD, or plan infrastructure as code. Covers Lambda, API Gateway REST API v1, DynamoDB, Aurora PostgreSQL Serverless v2, EventBridge, Step Functions, Cognito, and cost optimization at alpha scale.
---

# AWS Solution Architect

Design scalable, cost-effective AWS architectures for SkillSpoke, with the infrastructure written as CDK in Python.

## SkillSpoke's stack

Confirm against the architecture constraints (arc42 section 2) and the solution strategy (arc42 section 4) in the `skillspoke-docs` vault before relying on these; where they differ, the vault wins.

- **Compute:** AWS Lambda, Python, `aws-lambda-powertools` through `shared-chassis-lib`. Django, Flask and FastAPI are banned. Agents run on Amazon Bedrock AgentCore Runtime.
- **APIs:** API Gateway REST API v1, spec-first in OpenAPI; HTTP API v2 is not used. Live push uses the API Gateway WebSocket API.
- **Infrastructure:** AWS CDK in Python through `shared-cdk-lib`. A service is one CDK app with one stack per environment holding every resource it owns. Values cross stacks only through SSM Parameter Store, never CloudFormation exports and imports. No raw CloudFormation templates, SAM templates or Terraform.
- **Persistence:** chosen per data set and owned per service: DynamoDB (on-demand), Aurora PostgreSQL Serverless v2 through the RDS Data API (with pgvector; see the `aurora-postgresql` skill), or versioned S3. Services do not share tables by default.
- **Integration:** SkillSpoke events go through the central event API of the events service onto the single EventBridge bus; the stack of a rule's target owns the rule (see the `skillspoke-events` skill). Synchronous REST only where a user-facing read needs another context's data immediately.
- **Identity:** Amazon Cognito, one user pool per trust domain; service-to-service calls use OAuth2 client credentials.
- **Email:** Amazon SES. **AI:** Amazon Bedrock. **Observability:** CloudWatch, X-Ray and ADOT, plus SkillSpoke observability events.
- **Network:** everything that can sit inside the environment VPC does, reached through VPC endpoints; the only internet path is the egress tier of the Egress Boundary service.
- **Names:** every resource name comes from the project's naming command (the `resource-naming` skill).
- **Scale:** alpha (one dev account, at most five users). Prefer per-request pricing (Lambda, DynamoDB on-demand, Aurora Serverless v2 able to scale to 0 ACUs) over always-on capacity (ECS services, provisioned RDS instances, ElastiCache nodes, NAT Gateways) unless a stated need justifies the monthly floor.

---

## Workflow

### Step 1: Gather Requirements

Collect the specifications from the Epic, its PRD and the effective architecture:

```
- What the capability does and which bounded context owns it
- Access patterns and the data each needs
- Latency and availability requirements (SLA, RPO/RTO)
- Compliance and personal-data requirements
- Expected load, stated (do not invent a scale figure; ask when a decision needs one)
```

### Step 2: Design Architecture

Choose the pattern from SkillSpoke's stack:
- **Serverless API:** API Gateway REST API v1 (from the OpenAPI specification) + Python Lambda + DynamoDB or Aurora PostgreSQL Serverless v2
- **Event-Driven Service:** a routing rule on the SkillSpoke bus + SQS + Python Lambda, with Step Functions or Lambda durable functions for orchestration inside the service
- **Web front end:** Next.js on the CDS design system behind CloudFront and AWS WAF

`scripts/architecture_designer.py` can list generic patterns from a requirements file. It also offers patterns outside SkillSpoke's stack (ECS Fargate three-tier, AppSync GraphQL, ElastiCache); treat those as not applicable unless the owner has stated a need for them.

See `references/architecture_patterns.md` for detailed pattern specifications; its CloudFormation and TypeScript examples show the shape of each pattern, and SkillSpoke writes the same resources in Python CDK.

**Validation checkpoint:** Confirm the design meets the architecture constraints and the requirement before Step 3.

### Step 3: Write the Infrastructure as CDK in Python

Write the service's stack in Python CDK with the `aws-cdk-development` and `cdk-coding` skills, using the constructs `shared-cdk-lib` provides. A minimal service core:

```python
from aws_cdk import Stack, aws_apigateway as apigateway, aws_dynamodb as dynamodb, aws_lambda as lambda_
from constructs import Construct


class ServiceStack(Stack):
    """One service's stack: every resource the service owns."""

    def __init__(self, scope: Construct, construct_id: str, *, names: ServiceNames, **kwargs: object) -> None:
        super().__init__(scope, construct_id, **kwargs)
        table = dynamodb.TableV2(
            self,
            "Table",
            table_name=names.table,
            partition_key=dynamodb.Attribute(name="pk", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="sk", type=dynamodb.AttributeType.STRING),
            billing=dynamodb.Billing.on_demand(),
        )
        handler = lambda_.Function(
            self,
            "ApiHandler",
            function_name=names.function,
            runtime=lambda_.Runtime.PYTHON_3_14,
            handler="handler.handler",
            code=lambda_.Code.from_asset("src"),
            tracing=lambda_.Tracing.ACTIVE,
            environment={"TABLE_NAME": table.table_name},
        )
        table.grant_read_write_data(handler)
        apigateway.SpecRestApi(
            self,
            "Api",
            rest_api_name=names.rest_api,
            api_definition=apigateway.ApiDefinition.from_asset("openapi/api.yaml"),
        )
```

`ServiceNames` stands for the names the naming command produced. `scripts/serverless_stack.py` generates a raw CloudFormation/SAM template; SkillSpoke does not deploy raw CloudFormation, so do not use its output as infrastructure.

### Step 4: Review Costs

Estimate the monthly cost of the design at the stated load with the AWS Pricing Calculator figures (confirm current prices with the AWS documentation tools), and state the floor cost of any always-on resource. `scripts/cost_optimizer.py` analyses an inventory of existing resources:

```bash
python scripts/cost_optimizer.py --resources current_setup.json --monthly-spend 200
```

Output includes:
- Monthly cost breakdown by service
- Right-sizing recommendations
- Idle resource removal
- Potential monthly savings

Savings Plans and reserved capacity apply only to steady, committed usage; they are not a default at alpha scale.

### Step 5: Deploy

Deploy to AWS dev with CDK:

```bash
cdk deploy --profile dev <stack-name>
```

### Step 6: Validate and Handle Failures

Verify the deployment and its monitoring:

```bash
aws cloudformation describe-stacks --profile dev --stack-name <stack-name>
```

**If the deploy fails:**

1. Read the failure reason:
   ```bash
   aws cloudformation describe-stack-events --profile dev --stack-name <stack-name> --query 'StackEvents[?contains(ResourceStatus, `FAILED`)]'
   ```
2. Review CloudWatch Logs for the Lambda errors.
3. Fix the CDK code, synth, and redeploy with `cdk deploy`.

**Common failure causes:**
- IAM permission errors → check the grants and role trust policies in the CDK code
- Resource limit exceeded → request a quota increase through Service Quotas
- A name refused by the service → build it again with the naming command

---

## Tools

### architecture_designer.py

Lists generic architecture patterns for a requirements file.

```bash
python scripts/architecture_designer.py --input requirements.json --output design.json
```

**Input:** JSON with app type, scale, budget, compliance needs
**Output:** Recommended pattern, service stack, cost estimate, pros/cons. Patterns outside SkillSpoke's stack are not applicable without a stated need.

### serverless_stack.py

Generates a generic raw CloudFormation/SAM template. Not used for SkillSpoke infrastructure, which is CDK in Python.

### cost_optimizer.py

Analyzes costs of an existing inventory and recommends optimizations.

```bash
python scripts/cost_optimizer.py --resources inventory.json --monthly-spend 200
```

**Output:** Recommendations for:
- Idle resource removal
- Instance right-sizing
- Reserved capacity purchases (steady committed usage only)
- Storage tier transitions
- NAT Gateway alternatives (VPC endpoints)

---

## Input Requirements

Provide these details for architecture design:

| Requirement | Description | Example |
|-------------|-------------|---------|
| Capability | What is being built and its bounded context | Job-search results publishing |
| Expected load | Stated users and requests/sec | Alpha: at most five users |
| Budget | Monthly AWS limit | Stated by the owner |
| Compliance | Regulatory and personal-data needs | GDPR |
| Availability | Uptime requirements | 99.9% SLA, 1hr RPO |

---

## Output Formats

### Architecture Design

- Pattern recommendation with rationale, against the architecture constraints
- Service diagram as Mermaid
- Monthly cost estimate and trade-offs

### Infrastructure as Code

- **CDK in Python** through `shared-cdk-lib`, with names from the naming command

### Cost Analysis

- Current spend breakdown with optimization recommendations
- Priority action list (high/medium/low)

---

## Reference Documentation

| Document | Contents |
|----------|----------|
| `references/architecture_patterns.md` | Generic patterns: serverless, microservices, three-tier, data processing, GraphQL, multi-region. Only the serverless and event-driven patterns fit SkillSpoke's stack; the examples are CloudFormation and TypeScript, and SkillSpoke writes them in Python CDK |
| `references/service_selection.md` | Decision matrices for compute, database, storage, messaging; SkillSpoke's choices are fixed in the stack above |
| `references/best_practices.md` | Serverless design, cost optimization, security hardening, scalability |
