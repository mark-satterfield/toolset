---
name: aws-cdk-development
description: AWS Cloud Development Kit (CDK) expert for building cloud infrastructure, in Python or TypeScript. Use when creating CDK stacks, defining CDK constructs, implementing infrastructure as code, or when the user mentions CDK, CloudFormation, IaC, cdk synth, cdk deploy, or wants to define AWS infrastructure programmatically. Covers CDK app structure, construct patterns, stack composition, and deployment workflows.
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

Name stacks and resources by the physical-name rule in `cdk-coding` (under "Structure"); it is stated only there.

### Lambda Function Development

The project's CDK language, its Lambda runtime and libraries, and any shared construct library it provides are in its architecture constraints and project instructions. Use the construct a project's shared construct library provides where it has one for the job. Otherwise, for a Python Lambda, use the stable `aws_lambda.Function` from `aws-cdk-lib` and bundle the dependencies with `Code.from_asset` and the runtime's bundling image. `@aws-cdk/aws-lambda-python-alpha` (`PythonFunction`) is an experimental alpha module outside `aws-cdk-lib`, with no stability guarantee; do not use it.

```python
from aws_cdk import BundlingOptions, aws_lambda as lambda_

UV_VERSION = uv_version  # the exact version the repository's [tool.uv] required-version names

lambda_.Function(
    self,
    "Handler",
    function_name=function_name,  # as the architecture names it
    runtime=lambda_.Runtime.PYTHON_3_14,
    architecture=lambda_.Architecture.ARM_64,
    handler="handlers.handler.handler",  # module path inside the copied package
    code=lambda_.Code.from_asset(
        function_dir,  # the smallest directory holding pyproject.toml, uv.lock and src/; all of it is mounted
        bundling=BundlingOptions(
            image=lambda_.Runtime.PYTHON_3_14.bundling_image,
            platform=lambda_.Architecture.ARM_64.docker_platform,  # the function's architecture
            environment={
                "UV_CACHE_DIR": "/tmp/uv-cache",
                # when the lock names a private index: "UV_INDEX": private_index_url (never build_args)
            },
            command=[
                "bash",
                "-c",
                " && ".join([
                    f"python -m pip install --quiet --target /tmp/uvtool uv=={UV_VERSION}",
                    # runtime packages only; add --no-emit-package for each layer-provided package
                    "/tmp/uvtool/bin/uv export --frozen --no-dev --no-default-groups"
                    " --no-emit-project -o /tmp/requirements.txt",
                    "/tmp/uvtool/bin/uv pip install --no-deps --only-binary :all:"
                    " --target /asset-output -r /tmp/requirements.txt",
                    "cp -r src/handlers /asset-output/",  # the handler package only
                    "find /asset-output -name __pycache__ -prune -exec rm -rf {} +",
                ]),
            ],
        ),
    ),
)
```

A `LayerVersion` is bundled from the layer's own project directory with the `BundlingOptions` above, with two changes: the install target is `/asset-output/python`, and no source package is copied. Its `compatible_runtimes` and `compatible_architectures` name the runtime and architecture it was built for.

Pin the runtime to the latest Python runtime Lambda supports (check with the AWS documentation tools) and use the same runtime for the bundling image and the function's architecture for its platform, so compiled dependencies match. Which packages the command installs, which it leaves to layers, and what it mounts and copies are decided by [python-lambda-packaging](../python-lambda-packaging/SKILL.md).

**Benefits**:
- Stable `aws-cdk-lib` API, with no alpha module to track
- Dependencies installed in a container that matches the Lambda runtime
- Consistent deployment patterns

### Pre-Deployment Validation

**cdk-nag**: where the project's hooks run cdk-nag on synth, do not add or run it; write constructs that pass the AwsSolutions and Serverless packs (load `cdk-coding`). Acknowledge an accepted finding with the cdk-nag 3 Validations API as `cdk-coding` describes under "Acknowledging a finding"; `NagSuppressions` and Aspects are the removed v2 API. `aws-core:aws-cdk` shows the cdk-nag 2 API (`Aspects.of(app).add(...)`, `NagSuppressions`); that guidance is superseded here.

Before deploying:

1. **Synth**: Ensure the app synthesizes
   ```bash
   cdk synth --profile dev
   ```

2. **Tests**: Run the repository's synth assertion tests (the test command the repository declares, for example `pytest`)

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

- One CDK app per service, with one stack per environment holding every resource the service owns; no separate data stack and no nested stacks to split a service
- Separate concerns into logical construct boundaries inside that stack
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
- "Which is the latest Python runtime Lambda supports?"
- "Verify a service is available in us-east-1"
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
- "How to configure Python bundling options for `Code.from_asset`?"
- "Best practices for CDK stack organization"
- "CDK construct for an on-demand DynamoDB table (`TableV2`)"

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
