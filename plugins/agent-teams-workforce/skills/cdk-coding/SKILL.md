---
name: cdk-coding
description: How to write AWS CDK apps, stacks and constructs (Python or TypeScript) that pass the cdk-nag AwsSolutions and Serverless packs and the language checks the first time — app, stack and construct structure, typed props, L2 constructs over L1, least privilege through grants and scoped statements, encryption, TLS, logging, tracing, dead-letter handling and retention on by default, acknowledging an accepted finding with the cdk-nag 3 Validations API, deterministic synthesis, deploy-time references between stacks, and assertion tests. Use whenever writing, editing, refactoring, reviewing or testing CDK infrastructure code, together with the coding skill of the language the app is written in.
user-invocable: true
---

# AWS CDK: secure and deterministic by construction

Write every construct so that it would pass a security review and the cdk-nag rule packs the day it is written.
A CDK app is code that produces infrastructure: what it leaves out (an encryption setting, a log, a dead-letter
queue, a scoped permission) becomes a gap in a running system. Write the secure, observable form first; the checks
confirm it and never correct it.

These rules apply to every piece of CDK code an agent writes, changes or reviews. A reviewer judges CDK code
against them.

**Load the language skill too.** CDK code is also Python or TypeScript code: load `python-coding` for a Python app
and `typescript-coding` for a TypeScript app, and follow both skills. This skill covers what is specific to CDK.

## How to read this skill

- Every rule has one form: the instruction, then the reason, then at most one example.
- Examples are in Python, because that is the language most CDK apps here are written in. The TypeScript form uses
  the same construct and property names in camelCase (`enforceSsl`, `grantReadData`).
- An example illustrates its rule; the rule covers every case its text describes, not only the case shown.
- Examples are shortened: imports and docstrings are trimmed unless the rule is about them. Code you write carries
  them in full, as the language skill requires.
- A rule id in parentheses, such as (AwsSolutions-S10), names the cdk-nag rule that checks the same thing. The id is
  there so a finding can be traced to its rule here; the rule is the reason to write the code this way, not the id.

## Habits to replace on sight

| Do not | Do instead | Section |
|---|---|---|
| `actions=["s3:*"]`, `resources=["*"]` | The construct's grant method, or named actions on named ARNs | Permissions |
| `ManagedPolicy.from_aws_managed_policy_name(...)` on a role | Grants, or a customer managed policy scoped to the resources | Permissions |
| A bucket, queue or topic with default properties | Encryption, TLS-only access, logging and dead-letter handling set explicitly | Data and messaging |
| A Lambda function with default memory, timeout, tracing and logs | Explicit memory, timeout, tracing, log retention and failure destination | Compute |
| `NagSuppressions.add_resource_suppressions(...)` | `Validations.of(construct).acknowledge(Acknowledgment(...))` per finding | Acknowledging a finding |
| A boto3 call, `from_lookup` or `os.environ` branch inside a stack | Values passed in as props, or resolved at deploy time | Deterministic synthesis |
| `CfnOutput(export_name=...)` with `Fn.import_value` in another stack | An SSM parameter written by the producer and read by the consumer | Values shared between stacks |

## Structure

- Keep the app entry point (`app.py`, `bin/<app>.ts`) to one job: create the `App`, read the configuration the app
  needs, create the stacks with their props, and call `app.synth()`. It holds no resources and no logic. The reason:
  everything an entry point defines is untestable without running the whole app.
- Give each stack one deployment lifecycle: resources that are deployed, updated and torn down together. Stateful
  resources (tables, buckets, user pools, keys) sit in a stack that is rarely replaced, apart from the compute that
  changes often. The reason: a failed or rolled-back deployment of fast-changing code never puts stored data at risk.
- Put each reusable unit of infrastructure in a `Construct` subclass, not in a stack method. A stack composes
  constructs; a construct encapsulates one capability (an API with its log group and authorizer, a function with its
  role, alarms and dead-letter queue). The reason: a construct is reused and tested on its own, a stack method is not.
- Treat construct ids as permanent. The logical id of every CloudFormation resource is derived from the construct
  path, so renaming an id or moving a construct to another parent replaces the resource; for a table or a bucket that
  means a new, empty one. Choose ids that name the thing (`"OrdersTable"`, not `"Table1"`), and never change the id of a
  deployed stateful resource without a migration plan.
- Give each construct and stack its configuration as typed props, never through module globals or environment reads
  inside the construct. In Python, a frozen dataclass or keyword-only typed parameters; in TypeScript, a
  `readonly` props interface named `<Construct>Props`.

  Instead of:

  ```python
  class OrdersApi(Construct):
      def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:
          super().__init__(scope, construct_id)
          self.stage_name = os.environ.get("STAGE", "dev")
  ```

  Write:

  ```python
  @dataclass(frozen=True)
  class OrdersApiProps:
      """Configuration of the orders API."""

      stage_name: str
      orders_table: dynamodb.ITable


  class OrdersApi(Construct):
      """The orders REST API, its handler and its access logs."""

      def __init__(self, scope: Construct, construct_id: str, *, props: OrdersApiProps) -> None:
          """Create the API from its props."""
          super().__init__(scope, construct_id)
          self._props: OrdersApiProps = props
  ```

- Accept the interface type of a resource in props (`dynamodb.ITable`, `s3.IBucket`, `iam.IRole`), not the concrete
  class. The reason: a construct that accepts the interface works with an imported resource as well as one created
  in the same app, and the caller decides which.
- Let CloudFormation generate physical names unless a name is required by something outside the app. A hard-coded
  physical name blocks any change that needs replacement (the new resource cannot take the old name while the old
  one exists) and collides across environments. When a physical name is required, write the one the architecture, the task or its spec
  gives; where none of them records it, build it with the project's naming tool or skill when one exists (for
  example `resource-naming`), never by hand.
- When the project has a shared construct library (a wrapped function, API or table with the project's defaults
  already applied), build from it instead of from the raw construct. The reason: the library already carries the
  decisions this skill describes, and a second copy drifts.

## Constructs: L2 over L1

- Use the L2 construct (`s3.Bucket`, `lambda_.Function`, `apigateway.RestApi`) for every resource that has one. An L2
  sets safe defaults, wires permissions through grants and exposes typed properties; an L1 (`Cfn*`) is the raw
  CloudFormation resource with none of that.
- Use an L1 only for a resource or property that has no L2 form. Wrap it in a construct with typed props so the rest
  of the app never sees the raw resource.
- Prefer a property of the L2 over an escape hatch. When an escape hatch (`node.default_child`,
  `add_property_override`) is the only way, apply it inside the construct that owns the resource. A raw override is
  written after cdk-nag reads the construct tree, so cdk-nag can report a finding the override has already fixed;
  acknowledge that finding with the reason "remediated through property override" (Acknowledging a finding).

## Permissions

- Grant access through the resource's grant methods: `table.grant_read_data(fn)`, `bucket.grant_read(fn)`,
  `queue.grant_send_messages(fn)`, or the resource's `grants` property where the construct library version provides
  one. Choose the narrowest method that covers the need (`grant_read`, not `grant_read_write`). The reason: a grant
  writes the exact actions on the exact resource ARNs, so the policy is least privilege by construction (AWS
  Well-Architected, Security pillar: grant least privilege).
- When no grant method covers the need, write a `PolicyStatement` with named actions and named resource ARNs.
  A wildcard action (`s3:*`) or a wildcard resource (`*`) is a finding (AwsSolutions-IAM5,
  Serverless-StarPermissions), because it grants everything the service adds in future too.

  Instead of:

  ```python
  handler.add_to_role_policy(iam.PolicyStatement(actions=["dynamodb:*"], resources=["*"]))
  ```

  Write:

  ```python
  orders_table.grant_read_write_data(handler)
  ```

- Where a service accepts only `*` as the resource for an action (for example X-Ray `PutTraceSegments`, CloudWatch
  `PutMetricData`), write that one action with `*`, scope it with a condition where the service supports one, and
  acknowledge the specific finding (`AwsSolutions-IAM5[Resource::*]`) with that reason.
- Never attach AWS managed policies to a role (AwsSolutions-IAM4). Most of them are broad by design
  (`AWSLambdaBasicExecutionRole` allows writing to every log group in the account). Give the role exactly what it uses:
  a function's log group and its grant come from the function construct; anything else is a grant or a scoped
  statement.
- Give each function its own role. A shared role carries the union of every function's permissions, so every
  function holds permissions it does not use.
- Require authentication on every API method and function URL (AwsSolutions-APIG4, AwsSolutions-COG4): a Cognito
  user pool authorizer, a Lambda authorizer or IAM auth. A method that must be public carries an acknowledgement that
  says why it is public.

## Data and messaging

Every rule in this section follows the Security pillar's data protection practice: protect data at rest and in
transit, and keep a record of access.

- S3 buckets: block all public access (`block_public_access=s3.BlockPublicAccess.BLOCK_ALL`, AwsSolutions-S2),
  require TLS (`enforce_ssl=True`, AwsSolutions-S10), encrypt (`encryption=s3.BucketEncryption.S3_MANAGED` or KMS),
  turn on server access logging to a separate log bucket (`server_access_logs_bucket=...`, AwsSolutions-S1), and
  turn on versioning for any bucket whose objects are not reproducible. The access log bucket itself carries the same
  settings, except that it does not log to itself; acknowledge its AwsSolutions-S1 finding with that reason.

  Instead of:

  ```python
  uploads_bucket = s3.Bucket(self, "UploadsBucket")
  ```

  Write:

  ```python
  uploads_bucket = s3.Bucket(
      self,
      "UploadsBucket",
      block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
      encryption=s3.BucketEncryption.S3_MANAGED,
      enforce_ssl=True,
      versioned=True,
      server_access_logs_bucket=access_logs_bucket,
      server_access_logs_prefix="uploads/",
      removal_policy=RemovalPolicy.RETAIN,
  )
  ```

- SQS queues: encrypt (`encryption=sqs.QueueEncryption.SQS_MANAGED` or KMS, AwsSolutions-SQS2), require TLS
  (`enforce_ssl=True`, AwsSolutions-SQS4), and give every queue that is not itself a dead-letter queue a dead-letter
  queue (`dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=..., queue=...)`, AwsSolutions-SQS3,
  Serverless-SQSRedrivePolicy). The reason: a message that keeps failing otherwise blocks or loops until it expires,
  and is then lost without a trace.
- SNS topics: encrypt with a KMS key (`master_key=...`) and require TLS (`enforce_ssl=True`, AwsSolutions-SNS3); give
  every subscription a dead-letter queue (`dead_letter_queue=...`, Serverless-SNSRedrivePolicy).
- EventBridge rules: give each target a dead-letter queue and a retry policy (Serverless-EventBusDLQ).
- DynamoDB tables: turn on point-in-time recovery (AwsSolutions-DDB3), use on-demand billing unless the project has
  decided otherwise for a measured load, and set `removal_policy=RemovalPolicy.RETAIN` and deletion protection on a
  table that holds data that cannot be recreated.
- KMS keys: turn on rotation (`enable_key_rotation=True`, AwsSolutions-KMS5).
- Secrets Manager secrets: schedule rotation (AwsSolutions-SMG4) when the secret is a credential the app can rotate;
  for a secret issued by a third party that cannot be rotated from AWS, acknowledge the finding with that reason.
  Never put a secret value in code, in context, in an environment variable or in a parameter: the function reads it
  from the secret at run time and holds a grant to read it.
- Log groups: create the log group explicitly with a retention period (`logs.RetentionDays...`,
  Serverless-CloudWatchLogGroupRetentionPeriod). The reason: a log group created implicitly by a service keeps logs
  forever and is not removed with the stack.
- Stateful resources: set `removal_policy` explicitly on every resource that stores data. `RETAIN` (or `SNAPSHOT`
  where supported) for data that cannot be recreated; `DESTROY` only for data that can, and only where the
  environment's teardown needs it.

## Compute

- Lambda functions: use the latest runtime of the language (AwsSolutions-L1, Serverless-LambdaLatestVersion), set
  `memory_size` and `timeout` explicitly (Serverless-LambdaDefaultMemorySize, Serverless-LambdaFunctionDefaultTimeout),
  turn on active tracing (`tracing=lambda_.Tracing.ACTIVE`, Serverless-LambdaTracing), give the function an explicit
  log group with retention, and give it somewhere for failures to go: a dead-letter queue (`dead_letter_queue=...`,
  Serverless-LambdaDLQ) and, for asynchronous invocation, an on-failure destination
  (Serverless-LambdaAsyncFailureDestination). The reason for each: the defaults (128 MB, 3 seconds, no tracing,
  logs kept forever, failed events dropped) are rarely right and hide failures.

  Instead of:

  ```python
  handler = lambda_.Function(
      self,
      "OrdersHandler",
      runtime=lambda_.Runtime.PYTHON_3_12,
      handler="handler.main",
      code=lambda_.Code.from_asset(str(HANDLER_ROOT)),
  )
  ```

  Write:

  ```python
  handler = lambda_.Function(
      self,
      "OrdersHandler",
      runtime=lambda_.Runtime.PYTHON_3_14,
      handler="handler.main",
      code=lambda_.Code.from_asset(str(HANDLER_ROOT)),
      memory_size=512,
      timeout=Duration.seconds(10),
      tracing=lambda_.Tracing.ACTIVE,
      log_group=handler_log_group,
      dead_letter_queue=handler_dead_letter_queue,
      on_failure=destinations.SqsDestination(handler_dead_letter_queue),
  )
  ```

  The runtime shown is an example; use the newest runtime the installed CDK version offers for the language.
- Event source mappings (SQS, Kinesis, DynamoDB streams): set an on-failure destination
  (Serverless-LambdaEventSourceMappingDestination), set the batch size and, for SQS, a queue visibility timeout of at
  least six times the function timeout, so a message is not delivered again while it is still being processed.
- Step Functions state machines: log `ALL` events to a log group with retention (AwsSolutions-SF1) and turn on
  tracing (AwsSolutions-SF2, Serverless-StepFunctionStateMachineXray).

## APIs and identity

- API Gateway REST APIs: turn on access logging in a structured (JSON) format to a log group with retention
  (AwsSolutions-APIG1, Serverless-APIGWAccessLogging, Serverless-APIGWStructuredLogging), execution logging for all
  methods (AwsSolutions-APIG6), tracing (Serverless-APIGWXrayEnabled), stage throttling limits chosen for the API
  (Serverless-APIGWDefaultThrottling), and a request validator (AwsSolutions-APIG2). The reason: without access logs no
  one can tell who called the API, and without throttling one client can exhaust the account's capacity.
- Associate a WAFv2 web ACL with every public API stage (AwsSolutions-APIG3). When the project has decided a stage
  goes without one, acknowledge the finding with that decision as the reason.
- Cognito user pools: set a password policy of at least 8 characters with upper case, digits and symbols
  (AwsSolutions-COG1), require MFA (AwsSolutions-COG2), and choose the feature plan the project has decided
  (AwsSolutions-COG8). An identity pool allows unauthenticated identities only with an acknowledgement that says why
  (AwsSolutions-COG7).

## Acknowledging a finding

- Fix the construct first. Acknowledge a finding only when the rule does not fit this resource for a reason you can
  state: a service that accepts only `*`, a project decision recorded elsewhere, a property fixed through an override.
  An acknowledgement is a recorded exception, not a way to make a check pass.
- Acknowledge with the cdk-nag 3 API, which is CDK's own `Validations`:

  ```python
  from aws_cdk import Acknowledgment, Validations

  Validations.of(handler_role).acknowledge(
      Acknowledgment(
          id="AwsSolutions-IAM5[Resource::*]",
          reason="X-Ray accepts trace segments only on Resource '*'.",
      ),
  )
  ```

  `NagSuppressions`, `NagPackSuppression` and the `Aspects`-based registration are the cdk-nag 2 API, removed in
  cdk-nag 3; never write them. When the project wraps this call in a helper, use the helper.
- Acknowledge each finding by its full id. A granular rule reports one finding per offending action or resource in
  the form `RuleId[FindingId]` (`AwsSolutions-IAM5[Action::s3:*]`, `AwsSolutions-IAM4[Policy::arn:...]`), and cdk-nag 3
  matches each one separately; acknowledging the bare rule id does not cover them.
- Acknowledge on the narrowest construct that owns the finding (the role, the bucket), never on the stack or the
  app. An acknowledgement applies to every child of the construct it is placed on, so a broad one hides future
  findings no one has reviewed.
- Write the reason as evidence a reviewer can check: what the resource needs and why the rule does not apply. "Needed"
  or "false positive" is not a reason.

## Deterministic synthesis

The same code and the same context must always synthesize the same template (CDK best practice: "determinism is key
to successful AWS CDK deployments").

- Never call an AWS SDK, the network or any other external system from a stack or construct. Synthesis must have no
  side effects and need no credentials. A value that must come from AWS is resolved at deploy time
  (`ssm.StringParameter.value_for_string_parameter`, a CloudFormation dynamic reference) or, when it truly is needed
  at synth, through a context provider (`from_lookup`) whose result is committed in `cdk.context.json`.
- Commit `cdk.context.json` whenever the app uses a lookup. Without it each synth runs the lookup again, needs
  credentials, and can return a different value (a new Availability Zone, a newer machine image) that replaces
  resources.
- Never branch a stack on the machine it runs on: no `os.environ` reads, no `datetime.now()`, no random values, no
  reading files outside the repository inside constructs. Configuration enters through the entry point (context or a
  configuration file in the repository) and reaches constructs as props.
- Give every stack an explicit environment (`env=Environment(account=..., region=...)`) from the entry point's
  configuration. An environment-agnostic stack cannot use lookups and resolves some properties differently. The
  account and region are values known only at deploy time: the entry point takes them from the deploy (for example
  `CDK_DEFAULT_ACCOUNT` and `CDK_DEFAULT_REGION`, which the CDK CLI sets from the profile it deploys with), never
  from a literal in the code.

## Values shared between stacks

- Pass a value between stacks through an SSM parameter: the producing stack writes it
  (`ssm.StringParameter(self, ..., parameter_name=..., string_value=...)`) and the consuming stack reads it at deploy
  time (`ssm.StringParameter.value_for_string_parameter(self, parameter_name)`). Follow the project's rule where it
  states another mechanism.
- Never share values with CloudFormation exports (`CfnOutput(export_name=...)`, `Fn.import_value`, or passing a
  construct from one stack to another, which makes CDK create exports). The reason: an export locks the producing
  stack; it cannot change or remove the exported value while any stack imports it, so a routine change in one stack
  blocks on the other.

## Tests

- Test each stack and construct with fine-grained assertions on the synthesized template: `Template.from_stack(stack)`
  with `has_resource_properties`, `resource_count_is` and `Match`. Assert the properties this skill requires (TLS
  enforcement, encryption, tracing, the dead-letter queue, the exact policy actions), not only that a resource exists.
  The reason: these tests catch a removed security setting in seconds, before any deployment.
- Prefer fine-grained assertions over snapshot tests. A snapshot fails on every harmless change and is updated
  without being read, so it stops guarding anything.

## The safety net

Where the repository's hooks synthesize the app with the cdk-nag AwsSolutions and Serverless packs after each edit
and at commit, every finding they report is fixed in the construct (or acknowledged as this skill describes) before
the work is finished; do not add cdk-nag to the app or run it yourself. Where no hook runs it, synthesize the app with
those packs before finishing. The target is that the hook reports nothing, because the code above was written to pass.
