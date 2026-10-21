---
name: "senior-devops"
description: DevOps skill for CI/CD, infrastructure automation and deployment of serverless services on AWS - GitHub Actions checks, CDK in Python deployed to the development account, packages published to CodeArtifact, Lambda deployments with aliases and CodeDeploy, and CloudWatch monitoring. Use when setting up pipelines, deploying applications, managing infrastructure, implementing monitoring, or optimizing deployment processes.
---

# Senior Devops

DevOps practice for serverless services on AWS, with infrastructure as CDK in Python and CI on GitHub Actions.

## The delivery stack

The project's delivery stack, its shared libraries, its environments and which of them are deployed are stated in its architecture constraints and project instructions; read them first. This skill describes a delivery stack of this shape:

- **Infrastructure as code:** AWS CDK in Python (`aws-cdk-development`, `cdk-coding`), through the project's shared CDK library where it has one, rather than Terraform or raw CloudFormation. A service is one CDK app with one stack per environment; values cross stacks through SSM Parameter Store; names come from the naming command (`resource-naming`).
- **Compute:** Python Lambdas on `aws-lambda-powertools`, deployed as CDK assets. A project that runs no ECS, EKS or Kubernetes workloads builds no container images for services (an AgentCore Runtime agent is the exception, packaged as the `aws-agentic-ai` skill states).
- **Packages:** shared libraries are published to AWS CodeArtifact as versioned packages; services consume them as packages, never as source.
- **Environments:** each environment is its own AWS account; deploy only to the environments the project instructions say are deployed.
- **CI:** GitHub Actions runs the repository's checks on pull requests; work that goes through pull requests opens them with the project's PR command.
- **Monitoring:** CloudWatch metrics, logs and alarms, X-Ray and ADOT, and the observability events the project's event standard defines.

What a repository publishes and deploys is answered by the `polyrepo-steward` (the `deploy-mechanism` workflow), from the repository's own declarations.

## Core Capabilities

### 1. Pipeline Generator

`scripts/pipeline_generator.py` scaffolds GitHub Actions or CircleCI configurations. On GitHub Actions, a generated workflow is a starting point that must run the repository's own declared checks.

**Example — GitHub Actions checks for a Python CDK service:**
```yaml
# .github/workflows/ci.yml
name: CI
on:
  pull_request:
    branches: [main]

permissions:
  contents: read

jobs:
  checks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.14'
      - run: pip install -r requirements-dev.txt
      - run: ruff check .
      - run: ruff format --check .
      - run: mypy --strict .
      - run: pytest
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
      - run: npx aws-cdk synth
```

Pin action versions as the repository's existing workflows do, and use the repository's declared commands (its `AGENTS.md`, `CLAUDE.md` or Taskfile) rather than these placeholders. Deployment to AWS dev is not run from CI by default.

**Usage:**
```bash
python scripts/pipeline_generator.py <project-path> --platform=github --stages=build,test
```

### 2. Infrastructure as Code

Infrastructure is CDK in Python. `scripts/terraform_scaffolder.py` generates Terraform modules; do not use its output where the project's infrastructure is CDK.

```bash
# Synthesize and review the change before deploying
cdk synth --profile dev
cdk diff --profile dev <stack-name>

# Deploy to AWS dev
cdk deploy --profile dev <stack-name>

# Verify the stack reached CREATE_COMPLETE or UPDATE_COMPLETE
aws cloudformation describe-stacks --profile dev --stack-name <stack-name> --query 'Stacks[0].StackStatus'
```

### 3. Deployment Strategies for Lambda

A Lambda change can shift traffic gradually with an alias and AWS CodeDeploy, which rolls back automatically when a CloudWatch alarm fires:

```python
from aws_cdk import aws_codedeploy as codedeploy, aws_lambda as lambda_

alias = lambda_.Alias(self, "LiveAlias", alias_name="live", version=handler.current_version)

codedeploy.LambdaDeploymentGroup(
    self,
    "DeploymentGroup",
    alias=alias,
    deployment_config=codedeploy.LambdaDeploymentConfig.CANARY_10PERCENT_5MINUTES,
    alarms=[errors_alarm],
)
```

At small scale (the development context the project instructions state), an all-at-once deploy with a smoke test is usually enough; add canary shifting when a stated availability requirement needs it, and record the choice. `scripts/deployment_manager.py` targets container deployments (Kubernetes blue/green), which a Lambda-only project does not run.

## Resources

The references hold general DevOps knowledge; their Terraform, Docker, ECS and Kubernetes examples are background; follow this file where they differ.

- Pattern Reference: `references/cicd_pipeline_guide.md` — CI/CD patterns, best practices, anti-patterns
- Workflow Guide: `references/infrastructure_as_code.md` — IaC processes, optimization, troubleshooting
- Technical Guide: `references/deployment_strategies.md` — deployment strategies, security considerations, scalability
- Tool Scripts: `scripts/` directory

## Development Workflow

### 1. Infrastructure Changes

```bash
# Synthesize and run the repository's synth assertion tests
cdk synth --profile dev
pytest

# Review the diff, then deploy to AWS dev
cdk diff --profile dev <stack-name>
cdk deploy --profile dev <stack-name>
```

### 2. Package Publication

A shared library publishes a new version to CodeArtifact with the publish command its repository declares. How a library is versioned and how a consumer pins it and picks up a published version are the project's rules (its `AGENTS.md`); where the project states none, never edit a pin, a lock file or a library version to reach a version that is not yet published.

### 3. Rollback

A failed CloudFormation update rolls back on its own. To undo a deployed change, revert the commit and deploy again; with a CodeDeploy deployment group, a firing alarm shifts traffic back to the previous Lambda version.

```bash
# See why a deploy failed
aws cloudformation describe-stack-events --profile dev --stack-name <stack-name> --query 'StackEvents[?contains(ResourceStatus, `FAILED`)]'
```

## Troubleshooting

Check the troubleshooting section in `references/deployment_strategies.md` for general patterns, and `aws-core:aws-cdk` and `aws-core:aws-cloudformation` for CDK and stack failures.
