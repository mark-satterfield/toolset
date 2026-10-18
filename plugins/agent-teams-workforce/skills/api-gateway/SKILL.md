---
name: api-gateway
description: AWS API Gateway REST API (v1) management. Use when creating APIs, configuring integrations, setting up authorization, managing stages, implementing rate limiting, or troubleshooting API issues.
last_updated: "2026-01-07"
doc_source: https://docs.aws.amazon.com/apigateway/latest/developerguide/
---

# AWS API Gateway

Amazon API Gateway is a fully managed service for creating, publishing, and securing APIs at any scale.

**SkillSpoke uses REST APIs (API Gateway v1, the `apigateway` API) only. HTTP APIs (v2, `apigatewayv2`) are banned** by SkillSpoke standing rule 4. Every API, authorizer, CLI call and CDK construct in this skill is the REST API kind; a WebSocket API is used only where a requirement names it.

## Table of Contents

- [Core Concepts](#core-concepts)
- [Common Patterns](#common-patterns)
- [CLI Reference](#cli-reference)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)
- [References](#references)

## Core Concepts

### API Types

| Type | Description | Use Case |
|------|-------------|----------|
| **REST API** | Full-featured: Cognito user pools authorizers, usage plans, WAF, request validation | Every SkillSpoke API |
| **WebSocket API** | Bidirectional communication | Only where a requirement names real-time bidirectional traffic |

### Key Components

- **Resources**: URL paths (/users, /orders/{id})
- **Methods**: HTTP verbs (GET, POST, PUT, DELETE)
- **Integrations**: Backend connections (Lambda, HTTP, AWS services)
- **Stages**: Deployment environments (dev, prod)

### Integration Types

| Type | Description |
|------|-------------|
| **Lambda Proxy** | Pass-through to Lambda (recommended) |
| **Lambda Custom** | Transform request/response |
| **HTTP Proxy** | Pass-through to HTTP endpoint |
| **AWS Service** | Direct integration with AWS services |
| **Mock** | Return static response |

## Common Patterns

### Create REST API with Lambda Proxy

```bash
# Create REST API
aws apigateway create-rest-api \
  --name my-rest-api \
  --endpoint-configuration types=REGIONAL

API_ID=abc123

# Get root resource ID
ROOT_ID=$(aws apigateway get-resources --rest-api-id $API_ID --query 'items[0].id' --output text)

# Create resource
aws apigateway create-resource \
  --rest-api-id $API_ID \
  --parent-id $ROOT_ID \
  --path-part items

RESOURCE_ID=xyz789

# Create method
aws apigateway put-method \
  --rest-api-id $API_ID \
  --resource-id $RESOURCE_ID \
  --http-method GET \
  --authorization-type NONE

# Create Lambda integration
aws apigateway put-integration \
  --rest-api-id $API_ID \
  --resource-id $RESOURCE_ID \
  --http-method GET \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:123456789012:function:MyFunction/invocations

# Deploy to stage
aws apigateway create-deployment \
  --rest-api-id $API_ID \
  --stage-name prod
```

### Lambda Handler for API Gateway

SkillSpoke Lambdas use `aws-lambda-powertools` only. The REST API proxy event (payload format 1.0) is resolved with `APIGatewayRestResolver`:

```python
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.typing import LambdaContext

app = APIGatewayRestResolver()


@app.get("/items")
def list_items() -> dict[str, str]:
    return {"message": "Success", "path": app.current_event.path}


def handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)
```

### Configure CORS

```bash
# Enable CORS on resource
aws apigateway put-method \
  --rest-api-id $API_ID \
  --resource-id $RESOURCE_ID \
  --http-method OPTIONS \
  --authorization-type NONE

aws apigateway put-integration \
  --rest-api-id $API_ID \
  --resource-id $RESOURCE_ID \
  --http-method OPTIONS \
  --type MOCK \
  --request-templates '{"application/json": "{\"statusCode\": 200}"}'

aws apigateway put-method-response \
  --rest-api-id $API_ID \
  --resource-id $RESOURCE_ID \
  --http-method OPTIONS \
  --status-code 200 \
  --response-parameters '{
    "method.response.header.Access-Control-Allow-Headers": true,
    "method.response.header.Access-Control-Allow-Methods": true,
    "method.response.header.Access-Control-Allow-Origin": true
  }'

aws apigateway put-integration-response \
  --rest-api-id $API_ID \
  --resource-id $RESOURCE_ID \
  --http-method OPTIONS \
  --status-code 200 \
  --response-parameters '{
    "method.response.header.Access-Control-Allow-Headers": "'\''Content-Type,Authorization'\''",
    "method.response.header.Access-Control-Allow-Methods": "'\''GET,POST,PUT,DELETE,OPTIONS'\''",
    "method.response.header.Access-Control-Allow-Origin": "'\''*'\''"
  }'
```

### Cognito User Pools Authorization

A REST API verifies Cognito tokens with a Cognito user pools authorizer, so handler code does not verify them.

```bash
aws apigateway create-authorizer \
  --rest-api-id $API_ID \
  --name cognito-authorizer \
  --type COGNITO_USER_POOLS \
  --provider-arns arn:aws:cognito-idp:us-east-1:123456789012:userpool/us-east-1_abc123 \
  --identity-source 'method.request.header.Authorization'
```

## CLI Reference

### REST API (apigateway)

| Command | Description |
|---------|-------------|
| `aws apigateway create-rest-api` | Create API |
| `aws apigateway get-rest-apis` | List APIs |
| `aws apigateway create-resource` | Create resource |
| `aws apigateway put-method` | Create method |
| `aws apigateway put-integration` | Create integration |
| `aws apigateway create-deployment` | Deploy API |

## Best Practices

### Performance

- **Enable stage caching only for a stated latency need**: the API Gateway cache is billed per hour while it is enabled, whether or not it serves requests, so at alpha scale it is opt-in, not a default
- **Use regional endpoints** unless global distribution needed
- **Implement pagination** for list endpoints

### Security

- **Use authorization** on all endpoints
- **Enable WAF** for REST APIs
- **Use API keys** for rate limiting (not authentication)
- **Enable access logging**
- **Use HTTPS only**

### Reliability

- **Set up throttling** to protect backends
- **Configure timeout** appropriately
- **Use canary deployments** for updates
- **Monitor with CloudWatch**

## Troubleshooting

### 403 Forbidden

**Causes:**
- Missing authorization
- Invalid API key
- WAF blocking
- Resource policy denying

**Debug:**

```bash
# Check API key
aws apigateway get-api-key --api-key abc123 --include-value

# Check authorizer
aws apigateway get-authorizer --rest-api-id abc123 --authorizer-id xyz789
```

### 502 Bad Gateway

**Causes:**
- Lambda error
- Integration timeout
- Invalid response format

**Lambda response format:**

```python
# Correct format
return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"message": "success"})}

# Wrong - missing statusCode
return {"message": "success"}
```

### 504 Gateway Timeout

**Causes:**
- Backend timeout (Lambda max 29 seconds for REST API)
- Integration timeout too short

**Solutions:**
- Increase Lambda timeout
- Use async processing for long operations
- Increase the integration timeout (29 s by default for REST APIs)

### CORS Errors

**Debug:**
- Check OPTIONS method exists
- Verify headers in response
- Check origin matches allowed origins

## References

- [API Gateway Developer Guide](https://docs.aws.amazon.com/apigateway/latest/developerguide/)
- [API Gateway REST API Reference](https://docs.aws.amazon.com/apigateway/latest/api/)
- [API Gateway CLI Reference](https://docs.aws.amazon.com/cli/latest/reference/apigateway/)
- [boto3 API Gateway](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/apigateway.html)
