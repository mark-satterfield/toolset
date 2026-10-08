---
name: resource-naming
description: >-
  Generates and checks the name of every named cloud resource and code artifact from the
  project's own naming rules, so no agent composes a name by hand. Use whenever you name,
  rename or review the name of a CDK stack, Lambda function, DynamoDB table or cache table,
  S3 bucket, API Gateway API, IAM role, CloudWatch log group, Step Functions state machine,
  EventBridge bus, rule or schema, SQS queue or dead-letter queue, Secrets Manager secret,
  SSM parameter, VPC, subnet, security group, KMS alias, Cognito user pool or app client,
  Powertools service name or metrics namespace, environment variable, Python module file,
  CDK stack file or Lambda config file. Run `atw-naming name ...` to get the name and
  `atw-naming check ...` to verify an existing one; never type a name from memory or by
  copying a neighbour.
allowed-tools: [Bash]
---

# Resource Naming

Every name a covered item carries comes out of the naming script. The rules are the
project's, kept in one config file the project owns (`.resource-naming.yaml`); the script
only applies them, deterministically. This skill holds no project rule: run `atw-naming list`
to see the project's resource types, patterns and domain table.

## The rule

- **Always call the script.** Get the name with `atw-naming name`, put exactly what it prints
  into the code (CDK `stack_name`, `function_name`, `table_name`, SSM parameter names, the
  Powertools `service`, file names), and verify any existing or hand-edited name with
  `atw-naming check`.
- **Never hand-compose a name**, never "fix up" a printed name, and never copy a name from a
  neighbouring stack as the pattern. A name the script refuses is wrong, however it reads.
- When the script refuses an input, change the input (a camelCase one-token domain, an
  action without redundant words such as `handler`), not the name.
- **Name the project.** Every name starts with the prefix of the project the resource
  belongs to, so `name` requires `--project` (the projects are in `atw-naming list`); there is
  no default project. Pass `--team` for a resource of an internal (employee-facing)
  application: `team` goes right after the prefix. A project with categories accepts only
  their `{type}` values.
- Language-native conventions still apply to code identifiers the config does not cover:
  Python classes in PascalCase, functions and variables in snake_case, TypeScript in
  camelCase. The config's file-name and env-var types cover file names and environment
  variable names.
- A resource type the config does not list is not covered: report it in your result as a
  gap in the naming config instead of inventing a pattern.

## Commands

`atw-naming` is on the Bash tool's `PATH` (it runs
`${CLAUDE_PLUGIN_ROOT}/skills/resource-naming/scripts/naming.py`, which needs PyYAML).

```bash
atw-naming list                                   # projects, resource types, patterns, flags, domains
atw-naming name stack --project <project> --domain careerProfile --type service
atw-naming name stack --project <project> --team --domain web --type infra
atw-naming name lambda --project <project> --domain careerProfile --action scoreMatch
atw-naming name ssm --project <project> --namespace careerProfile --resource-type dynamodb --resource-name table
atw-naming check stack <name>                     # exit 0, or non-zero with reasons
atw-naming check stack <name> --project <project> # also require that project's prefix
atw-naming where                                  # which config file is in use
```

Each `{segment}` in a pattern is a flag of the same name in kebab-case (`{resourceType}` is
`--resource-type`); a segment in `[...]` is optional; a `flag` segment (`--team`) takes no
value. `name` refuses a missing or unknown `--project` and missing, extra or invalid
segments; `check` accepts any project's prefix unless `--project` is given. Exit codes: 0 ok; 1 the name or an input breaks a rule (the reasons are on
stderr); 2 no config, an invalid config or an unknown resource type.

## Where the config comes from

In order: `--config PATH`; `$RESOURCE_NAMING_CONFIG`; `$ATW_CONTROL_REPO/.resource-naming.yaml`
(the control repository, which is how a fleet repository or a worktree outside the control
repository finds it); else the first `.resource-naming.yaml` in the working directory or any
directory above it. With none, the script exits 2 and lists every place it tried. There are
no built-in defaults: a missing config is reported, never guessed around.

## Config format

```yaml
projects:                     # the umbrella each resource belongs to; --project names one
  <project-id>:
    prefix: <camelCase one token>     # starts every name; lowercased where AWS requires
    repo_prefix: <prefix of its repositories>
    metrics_namespace: <Name>         # optional; default the prefix with a capital first letter
    categories: {<category>: [<type>, ...]}   # optional; restricts {type}
forbidden_substrings: [...]   # spellings never valid anywhere (case-insensitive)
forbidden_tokens: [...]       # words no name may contain (e.g. environment names)
permitted_suffixes: [...]     # the only literal endings an AWS resource pattern may have
type_words: [...]             # words for a kind of resource; no aws name may contain one (permitted suffixes exempt)
segments:                     # style: camelCase|PascalCase|lowercase|kebab|region|az|accountId, enum, or flag
  team: {flag: team}          # value-less --team; patterns place it as [-{team}] after {project}
  domain: {style: camelCase}
  action: {style: camelCase, reject_words: [handler]}
domains:                      # reference table; a name containing an `avoid` term fails
  - {name: <Label>, external: <kebab>, internal: <camelCase>, avoid: [...]}
resources:
  <type>: {description: ..., pattern: "...", category: aws|code, min_length: N, max_length: N, type_words: [...]}
```

Pattern grammar: `{segment}` is caller-supplied; `{segment|lower|kebab|snake|upper_snake}`
transforms it; `[...]` is optional; `{project}`, `{projectLower}` and `{metricsNamespace}` come
from the project named by `--project`; everything else is literal.
