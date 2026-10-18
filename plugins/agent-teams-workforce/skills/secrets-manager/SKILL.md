---
name: secrets-manager
description: AWS Secrets Manager for secure secret storage and rotation. Use when storing credentials, configuring automatic rotation, managing secret versions, retrieving secrets in applications, or integrating with RDS.
last_updated: "2026-01-07"
doc_source: https://docs.aws.amazon.com/secretsmanager/latest/userguide/
---

# AWS Secrets Manager

AWS Secrets Manager helps protect access to applications, services, and IT resources. Store, retrieve, and automatically rotate credentials, API keys, and other secrets.

**You (the agent) never read a secret value**: no `get-secret-value` or `batch-get-secret-value` call through the CLI, the SDK, an MCP tool or any other means; see `aws-core:aws-secrets-manager`. **The code you write reads secrets at runtime.** In a SkillSpoke Lambda that is the Powertools Parameters utility (`parameters.get_secret`), which caches the value between invocations.

## Table of Contents

- [Core Concepts](#core-concepts)
- [Common Patterns](#common-patterns)
- [CLI Reference](#cli-reference)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)
- [References](#references)

## Core Concepts

### Secrets

Encrypted data stored in Secrets Manager. Can contain:
- Database credentials
- API keys
- OAuth tokens
- Any key-value pairs (up to 64 KB)

### Versions

Each secret can have multiple versions:
- **AWSCURRENT**: Current active version
- **AWSPENDING**: Version being rotated to
- **AWSPREVIOUS**: Previous version

### Rotation

Automatic credential rotation using Lambda functions. Built-in support for:
- Amazon RDS
- Amazon Redshift
- Amazon DocumentDB
- Custom secrets

## Common Patterns

### Create a Secret

**AWS CLI:**

```bash
# Create secret with JSON
aws secretsmanager create-secret \
  --name prod/myapp/database \
  --description "Production database credentials" \
  --secret-string '{"username":"admin","password":"MySecurePassword123!","host":"mydb.cluster-xyz.us-east-1.rds.amazonaws.com","port":5432,"database":"myapp"}'

# Create secret with binary data
aws secretsmanager create-secret \
  --name prod/myapp/certificate \
  --secret-binary fileb://certificate.pem
```

**boto3:**

```python
import boto3
import json

secrets = boto3.client("secretsmanager")

response = secrets.create_secret(
    Name="prod/myapp/database",
    Description="Production database credentials",
    SecretString=json.dumps({
        "username": "admin",
        "password": "MySecurePassword123!",
        "host": "mydb.cluster-xyz.us-east-1.rds.amazonaws.com",
        "port": 5432,
        "database": "myapp",
    }),
    Tags=[{"Key": "Environment", "Value": "production"}, {"Key": "Application", "Value": "myapp"}],
)
```

### Retrieve a Secret at Runtime (Lambda)

Application code in a SkillSpoke Lambda reads a secret with Powertools Parameters. The value is cached in the execution environment for `max_age` seconds, so the handler does not call Secrets Manager on every invocation, and a rotated value is picked up when the cache expires.

```python
from typing import Any

from aws_lambda_powertools.utilities import parameters
from aws_lambda_powertools.utilities.typing import LambdaContext

SECRET_NAME = "prod/myapp/database"  # from an environment variable in real code


def handler(event: dict, context: LambdaContext) -> dict:
    credentials: dict[str, Any] = parameters.get_secret(SECRET_NAME, transform="json", max_age=300)
    ...
```

The function's execution role needs `secretsmanager:GetSecretValue` on that secret (and `kms:Decrypt` when it uses a customer-managed key). Never log the value.

### Update a Secret

```bash
# Update secret value
aws secretsmanager update-secret \
  --secret-id prod/myapp/database \
  --secret-string '{"username":"admin","password":"NewPassword456!"}'

# Put new version with staging labels
aws secretsmanager put-secret-value \
  --secret-id prod/myapp/database \
  --secret-string '{"username":"admin","password":"NewPassword456!"}' \
  --version-stages AWSCURRENT
```

### Enable Rotation for RDS

```bash
aws secretsmanager rotate-secret \
  --secret-id prod/myapp/database \
  --rotation-lambda-arn arn:aws:lambda:us-east-1:123456789012:function:SecretsManagerRDSPostgreSQLRotation \
  --rotation-rules AutomaticallyAfterDays=30
```

### Create Secret with Rotation

```bash
# Use CloudFormation for RDS secret with rotation
aws cloudformation deploy \
  --template-file rds-secret.yaml \
  --stack-name rds-secret
```

```yaml
# rds-secret.yaml
AWSTemplateFormatVersion: '2010-09-09'
Resources:
  DBSecret:
    Type: AWS::SecretsManager::Secret
    Properties:
      Name: prod/myapp/database
      GenerateSecretString:
        SecretStringTemplate: '{"username": "admin"}'
        GenerateStringKey: password
        PasswordLength: 32
        ExcludeCharacters: '"@/\'

  DBSecretRotation:
    Type: AWS::SecretsManager::RotationSchedule
    Properties:
      SecretId: !Ref DBSecret
      RotationLambdaARN: !GetAtt RotationLambda.Arn
      RotationRules:
        AutomaticallyAfterDays: 30
```

## CLI Reference

### Secret Management

| Command | Description |
|---------|-------------|
| `aws secretsmanager create-secret` | Create secret |
| `aws secretsmanager describe-secret` | Get secret metadata |
| `aws secretsmanager update-secret` | Update secret |
| `aws secretsmanager delete-secret` | Delete secret |
| `aws secretsmanager restore-secret` | Restore deleted secret |
| `aws secretsmanager list-secrets` | List secrets |

### Versions

| Command | Description |
|---------|-------------|
| `aws secretsmanager put-secret-value` | Add new version |
| `aws secretsmanager list-secret-version-ids` | List versions |
| `aws secretsmanager update-secret-version-stage` | Move staging labels |

### Rotation

| Command | Description |
|---------|-------------|
| `aws secretsmanager rotate-secret` | Configure/trigger rotation |
| `aws secretsmanager cancel-rotate-secret` | Cancel rotation |

## Best Practices

### Secret Organization

- **Use hierarchical names**: `environment/application/secret-type`
- **Tag secrets** for organization and cost allocation
- **Separate by environment** (dev, staging, prod)

### Security

- **Use resource policies** to control access
- **Enable encryption** with customer-managed KMS keys
- **Rotate secrets** regularly (30-90 days)
- **Audit access** with CloudTrail
- **Use VPC endpoints** for private access

### Access Control

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/*",
      "Condition": {
        "StringEquals": {
          "secretsmanager:ResourceTag/Environment": "production"
        }
      }
    }
  ]
}
```

### Application Integration

- **Read secrets with Powertools Parameters** in Lambda code; it caches them to reduce API calls
- **Handle rotation** gracefully (on an authentication failure, fetch again with `force_fetch=True`)
- **Never log secrets**

## Troubleshooting

### AccessDeniedException

**Causes:**
- IAM policy missing `secretsmanager:GetSecretValue`
- Resource policy denying access
- KMS key policy missing permissions

**Debug:**

```bash
# Check secret resource policy
aws secretsmanager get-resource-policy --secret-id my-secret

# Check IAM permissions
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/my-role \
  --action-names secretsmanager:GetSecretValue \
  --resource-arns arn:aws:secretsmanager:us-east-1:123456789012:secret:my-secret
```

### Rotation Failed

**Debug:**

```bash
# Check rotation status
aws secretsmanager describe-secret --secret-id my-secret

# Check Lambda logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/SecretsManagerRotation \
  --filter-pattern "ERROR"
```

**Common causes:**
- Lambda timeout (increase to 30+ seconds)
- Network connectivity (VPC configuration)
- Database connection issues
- Wrong secret format

### Secret Not Found

```bash
# List secrets to find correct name
aws secretsmanager list-secrets \
  --filters Key=name,Values=myapp

# Check if deleted (within recovery window)
aws secretsmanager list-secrets \
  --include-planned-deletion
```

## References

- [Secrets Manager User Guide](https://docs.aws.amazon.com/secretsmanager/latest/userguide/)
- [Secrets Manager API Reference](https://docs.aws.amazon.com/secretsmanager/latest/apireference/)
- [Secrets Manager CLI Reference](https://docs.aws.amazon.com/cli/latest/reference/secretsmanager/)
- [boto3 Secrets Manager](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/secretsmanager.html)
