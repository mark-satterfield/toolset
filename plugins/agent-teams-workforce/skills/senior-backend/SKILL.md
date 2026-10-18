---
name: "senior-backend"
description: Designs and implements SkillSpoke backend services - REST APIs on API Gateway REST API v1 with Python Lambda handlers on aws-lambda-powertools, DynamoDB and Aurora PostgreSQL data access, Cognito authentication, and security hardening. Use when the user asks to "design REST APIs", "optimize database queries", "implement authentication", "build microservices", "review backend code", "handle database migrations", or "load test APIs". Covers Python Lambda services, PostgreSQL optimization, API security, and backend architecture patterns.
---

# Senior Backend Engineer

Backend development patterns, API design, database optimization, and security practices for SkillSpoke's services.

## SkillSpoke's backend stack

Confirm against the architecture constraints and solution strategy (arc42 sections 2 and 4) in the `skillspoke-docs` vault.

- Every service Lambda is Python on `aws-lambda-powertools`, through `shared-chassis-lib`. Django, Flask and FastAPI are banned; Node.js backends (Express, Fastify, Koa, NestJS) are not SkillSpoke's.
- APIs are API Gateway REST API v1, spec-first: the OpenAPI specification exists before the handler code, and the API is built from it. HTTP API v2 is not used. GraphQL is not used.
- Data: DynamoDB (on-demand) or Aurora PostgreSQL Serverless v2 through the RDS Data API (see `aurora-postgresql`), each owned by one service. A service never imports another service's source and does not share its tables by default.
- Authentication: Amazon Cognito user pools; service-to-service calls use OAuth2 client credentials with one app client per calling service. SkillSpoke Lambdas call SkillSpoke APIs through `shared-apiClient-lib`.
- Infrastructure: CDK in Python (`aws-cdk-development`, `cdk-coding`); names from the naming command (`resource-naming`).
- Work between services goes through SkillSpoke events (`skillspoke-events`).

Load `python-coding` for every Python change.

---

## Quick Start

```bash
# Load test an API endpoint in AWS dev
python scripts/api_load_tester.py https://<api-id>.execute-api.us-east-1.amazonaws.com/dev/users --concurrency 5 --duration 30
```

---

## Tools Overview

### 1. API Scaffolder

`scripts/api_scaffolder.py` generates Express, Fastify or Koa route handlers. Those frameworks are not SkillSpoke's backend, so do not use its generated routes for SkillSpoke work; write the handlers with the Powertools event handler as shown in the API Design Workflow.

### 2. Database Migration Tool

`scripts/database_migration_tool.py` analyses a PostgreSQL schema over a direct connection string. SkillSpoke reaches Aurora PostgreSQL through the RDS Data API, with migrations and schema review as the `aurora-postgresql` skill states; use that skill's approach for SkillSpoke databases.

### 3. API Load Tester

Performs HTTP load testing with configurable concurrency, measuring latency percentiles and throughput.

**Input:** API endpoint URL and test configuration
**Output:** Performance report with latency distribution, error rates, throughput metrics

**Usage:**
```bash
# Basic load test
python scripts/api_load_tester.py https://<api-id>.execute-api.us-east-1.amazonaws.com/dev/users --concurrency 5 --duration 30

# Test with a header and body; read the token from an environment variable, never type it
python scripts/api_load_tester.py https://<api-id>.execute-api.us-east-1.amazonaws.com/dev/orders \
  --method POST \
  --header "Authorization: Bearer $ACCESS_TOKEN" \
  --body '{"product_id": 1, "quantity": 2}' \
  --concurrency 10 \
  --duration 60
```

Size a load test to the stated context (alpha: one dev account, at most five users), and run it only against AWS dev.

---

## Backend Development Workflows

### API Design Workflow

Use when designing a new API or refactoring existing endpoints.

**Step 1: Write the OpenAPI specification first**
```yaml
# openapi/api.yaml
openapi: 3.0.3
info:
  title: User Service API
  version: 1.0.0
paths:
  /users:
    get:
      summary: List users
      parameters:
        - name: "limit"
          in: query
          schema:
            type: integer
            default: 20
    post:
      summary: Create user
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CreateUser'
```

**Step 2: Build the REST API from the specification** in the service's Python CDK stack (`apigateway.SpecRestApi` with `ApiDefinition.from_asset`, a Cognito authorizer, and request validation from the specification's schemas).

**Step 3: Implement the handlers with the Powertools event handler**
```python
from http import HTTPStatus

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, Response, content_types
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic import BaseModel, EmailStr, Field

logger = Logger()
tracer = Tracer()
app = APIGatewayRestResolver(enable_validation=True)


class CreateUser(BaseModel):
    """Request body of POST /users, matching components/schemas/CreateUser."""

    email: EmailStr = Field(max_length=255)
    name: str = Field(min_length=1, max_length=100)


@app.post("/users")
@tracer.capture_method
def create_user(body: CreateUser) -> Response[dict[str, str]]:
    user = user_service.create(email=body.email, name=body.name)
    return Response(
        status_code=HTTPStatus.CREATED, content_type=content_types.APPLICATION_JSON, body={"id": user.user_id}
    )


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def handler(event: dict[str, object], context: LambdaContext) -> dict[str, object]:
    return app.resolve(event, context)
```

In a SkillSpoke service the chassis supplies the logger, tracer, metrics and idempotency wiring; use what `shared-chassis-lib` provides rather than re-creating it.

**Step 4: Validation** comes from the Pydantic models (`enable_validation=True`) and from API Gateway request validation against the specification; both reject a bad request with 4xx before business logic runs.

---

### Database Optimization Workflow

Use when queries are slow or database performance needs improvement. For DynamoDB, design the keys and indexes for the access patterns (`dynamodb` skill). For Aurora PostgreSQL (`aurora-postgresql` skill):

**Step 1: Identify slow queries**
```sql
-- Check query execution plans
EXPLAIN ANALYZE SELECT * FROM orders
WHERE user_id = 123
ORDER BY created_at DESC
LIMIT 10;

-- Look for: Seq Scan on a large table (bad), Index Scan (good)
```

**Step 2: Add the index in a migration**, reviewed and applied as the `aurora-postgresql` skill states, and verify the plan again.

---

### Security Hardening Workflow

Use when preparing an API for production or after a security review.

**Step 1: Authentication.** Every method has an authorizer: a Cognito user pool authorizer for seekers and employees, OAuth2 client credentials for service-to-service calls. Tokens are short-lived and validated by API Gateway or the chassis, never by hand-rolled JWT code with a shared secret.

**Step 2: Rate limiting, only where needed.** AWS WAF rate-based rules protect unauthenticated methods and account forms, and the chassis rate limiter protects identity endpoints only. Other services are not rate-limited; API Gateway stage throttling still bounds every API.

**Step 3: Validate all inputs** at the boundary with typed Pydantic models (as in the API Design Workflow), and reject what does not match.

**Step 4: Test the controls in AWS dev**
```bash
# Test input validation
python scripts/api_load_tester.py https://<api-id>.execute-api.us-east-1.amazonaws.com/dev/users \
  --method POST \
  --body '{"email": "not-an-email"}' \
  --expect-status 400
```

**Step 5: Security headers.** Set them at the edge with a CloudFront response headers policy (HSTS, content security policy, frame options) and on API responses where a header is response-specific.

---

## Reference Documentation

The references hold general backend knowledge; their Node.js, Express and GraphQL examples are background, and SkillSpoke writes the same patterns in Python on Powertools.

| File | Contains | Use When |
|------|----------|----------|
| `references/api_design_patterns.md` | REST conventions, versioning, error handling, pagination | Designing new APIs |
| `references/database_optimization_guide.md` | Indexing strategies, query optimization, N+1 solutions | Fixing slow queries |
| `references/backend_security_practices.md` | OWASP Top 10, auth patterns, input validation | Security hardening |

---

## Common Patterns Quick Reference

### REST API Response Format
```json
{
  "data": { "id": 1, "name": "John" },
  "meta": { "requestId": "abc-123" }
}
```

### Error Response Format
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid email format",
    "details": [{ "field": "email", "message": "must be valid email" }]
  },
  "meta": { "requestId": "abc-123" }
}
```

### HTTP Status Codes
| Code | Use Case |
|------|----------|
| 200 | Success (GET, PUT, PATCH) |
| 201 | Created (POST) |
| 204 | No Content (DELETE) |
| 400 | Validation error |
| 401 | Authentication required |
| 403 | Permission denied |
| 404 | Resource not found |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

### Database Index Strategy (PostgreSQL)
```sql
-- Single column (equality lookups)
CREATE INDEX idx_users_email ON users(email);

-- Composite (multi-column queries)
CREATE INDEX idx_orders_user_status ON orders(user_id, status);

-- Partial (filtered queries)
CREATE INDEX idx_orders_active ON orders(created_at) WHERE status = 'active';

-- Covering (avoid table lookup)
CREATE INDEX idx_users_email_name ON users(email) INCLUDE (name);
```
