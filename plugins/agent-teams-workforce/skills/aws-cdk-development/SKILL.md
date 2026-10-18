---
name: aws-cdk-development
description: AWS Cloud Development Kit (CDK) expert for building cloud infrastructure with TypeScript/Python. Use when creating CDK stacks, defining CDK constructs, implementing infrastructure as code, or when the user mentions CDK, CloudFormation, IaC, cdk synth, cdk deploy, or wants to define AWS infrastructure programmatically. Covers CDK app structure, construct patterns, stack composition, and deployment workflows.
context: fork
skills:
  - aws-mcp-setup
allowed-tools:
  - mcp__cdk__*
  - mcp__aws-mcp__*
  - mcp__awsdocs__*
  - Bash(cdk *)
  - Bash(npm *)
  - Bash(npx *)
  - Bash(aws cloudformation *)
  - Bash(aws sts get-caller-identity)
hooks:
  PreToolUse:
    - matcher: Bash(cdk deploy*)
      command: aws sts get-caller-identity --query Account --output text
      once: true
---

# AWS CDK Development

This skill provides comprehensive guidance for developing AWS infrastructure using the Cloud Development Kit (CDK), with integrated MCP servers for accessing latest AWS knowledge and CDK utilities.

## AWS Documentation Requirement

Always verify AWS facts using MCP tools (`mcp__aws-mcp__*` or `mcp__*awsdocs*__*`) before answering. The `aws-mcp-setup` dependency is auto-loaded — if MCP tools are unavailable, guide the user through that skill's setup flow.

## Integrated MCP Servers

This skill includes the CDK MCP server automatically configured with the plugin:

### AWS CDK MCP Server
**When to use**: For CDK-specific guidance and utilities
- Get CDK construct recommendations
- Retrieve CDK best practices
- Access CDK pattern suggestions
- Validate CDK configurations
- Get help with CDK-specific APIs

**Important**: Leverage this server for CDK construct guidance and advanced CDK operations.

## When to Use This Skill

Use this skill when:
- Creating new CDK stacks or constructs
- Refactoring existing CDK infrastructure
- Implementing Lambda functions within CDK
- Following AWS CDK best practices
- Validating CDK stack configurations before deployment
- Verifying AWS service capabilities and regional availability

## Core CDK Principles

### Resource Naming

Use the resource-naming skill: the project's naming command (`printenv ATW_NAMING_COMMAND` prints it) gives every stack and resource name (`name build <kind> ...`), and `name check <name> --kind <kind>` verifies one. Never compose a name by hand. When the project configures no naming command (`printenv ATW_NAMING_COMMAND` prints nothing), let CDK generate names.

### Lambda Function Development

Use the appropriate Lambda construct based on runtime:

**TypeScript/JavaScript**: Use `@aws-cdk/aws-lambda-nodejs`
```typescript
import { NodejsFunction } from 'aws-cdk-lib/aws-lambda-nodejs';

new NodejsFunction(this, 'MyFunction', {
  entry: 'lambda/handler.ts',
  handler: 'handler',
  // Automatically handles bundling, dependencies, and transpilation
});
```

**Python**: Use `@aws-cdk/aws-lambda-python`
```typescript
import { PythonFunction } from '@aws-cdk/aws-lambda-python-alpha';

new PythonFunction(this, 'MyFunction', {
  entry: 'lambda',
  index: 'handler.py',
  handler: 'handler',
  // Automatically handles dependencies and packaging
});
```

**Benefits**:
- Automatic bundling and dependency management
- Transpilation handled automatically
- No manual packaging required
- Consistent deployment patterns

### Pre-Deployment Validation

**cdk-nag**: where the project's hooks run cdk-nag on synth, do not add or run it; write constructs that pass the AwsSolutions and Serverless packs (load `cdk-coding`). Acknowledge an accepted finding with the cdk-nag 3 Validations API as `cdk-coding` describes under "Acknowledging a finding"; `NagSuppressions` and Aspects are the removed v2 API. `aws-core:aws-cdk` shows the cdk-nag 2 API (`Aspects.of(app).add(...)`, `NagSuppressions`); that guidance is superseded here.

Before deploying:

1. **Build**: Ensure compilation succeeds
   ```bash
   npm run build  # or language-specific build command
   ```

2. **Tests**: Run unit and integration tests
   ```bash
   npm test  # or pytest, mvn test, etc.
   ```

3. **Validation Script**: Meta-level checks
   ```bash
   ./scripts/validate-stack.sh
   ```

The validation script checks:
- Language detection
- Template size and resource count analysis
- Synthesis success verification
- (Note: Detailed anti-pattern checks are handled by cdk-nag)

## Workflow Guidelines

### Development Workflow

1. **Design**: Plan infrastructure resources and relationships
2. **Verify AWS Services**: Use AWS Documentation MCP to confirm service availability and features
   - Check regional availability for all required services
   - Verify service limits and quotas
   - Confirm latest API specifications
3. **Implement**: Write CDK constructs following best practices
   - Use CDK MCP server for construct recommendations
   - Reference CDK best practices via MCP tools
4. **Validate**: Run pre-deployment checks (see above)
5. **Synthesize**: Generate CloudFormation templates
6. **Review**: Examine synthesized templates for correctness
7. **Deploy**: Deploy to target environment
8. **Verify**: Confirm resources are created correctly

### Stack Organization

- Use nested stacks for complex applications
- Separate concerns into logical construct boundaries
- Share values between stacks through SSM Parameter Store (the producing stack writes the parameter, the consuming stack reads it at deploy time); never CloudFormation exports or passing constructs across stacks (see `cdk-coding`)
- Use CDK context for environment-specific configuration

### Testing Strategy

- Unit test individual constructs
- Integration test stack synthesis
- Snapshot test CloudFormation templates
- Validate resource properties and relationships

## Using MCP Servers Effectively

### When to Use AWS Documentation MCP

**Always verify before implementing**:
- New AWS service features or configurations
- Service availability in target regions
- API parameter specifications
- Service limits and quotas
- Security best practices for AWS services

**Example scenarios**:
- "Check if Lambda supports Python 3.13 runtime"
- "Verify DynamoDB is available in eu-south-2"
- "What are the current Lambda timeout limits?"
- "Get latest S3 encryption options"

### When to Use CDK MCP Server

**Leverage for CDK-specific guidance**:
- CDK construct selection and usage
- CDK API parameter options
- CDK best practice patterns
- Construct property configurations
- CDK-specific optimizations

**Example scenarios**:
- "What's the recommended CDK construct for API Gateway REST API?"
- "How to configure NodejsFunction bundling options?"
- "Best practices for CDK stack organization"
- "CDK construct for DynamoDB with auto-scaling"

### MCP Usage Best Practices

1. **Verify First**: Always check AWS Documentation MCP before implementing new features
2. **Regional Validation**: Check service availability in target deployment regions
3. **CDK Guidance**: Use CDK MCP for construct-specific recommendations
4. **Stay Current**: MCP servers provide latest information beyond knowledge cutoff
5. **Combine Sources**: Use both skill patterns and MCP servers for comprehensive guidance

## CDK Patterns Reference

For detailed CDK patterns, anti-patterns, and architectural guidance, refer to the comprehensive reference:

**File**: `references/cdk-patterns.md`

This reference includes:
- Common CDK patterns and their use cases
- Anti-patterns to avoid
- Security best practices
- Cost optimization strategies
- Performance considerations

## Additional Resources

- **Validation Script**: `scripts/validate-stack.sh` - Pre-deployment validation
- **CDK Patterns**: `references/cdk-patterns.md` - Detailed pattern library
- **AWS Documentation MCP**: Integrated for latest AWS information
- **CDK MCP Server**: Integrated for CDK-specific guidance

## GitHub Actions Integration

When GitHub Actions workflow files exist in the repository, ensure all checks defined in `.github/workflows/` pass before committing. This prevents CI/CD failures and maintains code quality standards.
