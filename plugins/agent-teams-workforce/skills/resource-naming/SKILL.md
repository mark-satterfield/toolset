---
name: resource-naming
description: >-
  Builds, converts and checks the name of every named cloud resource and code artifact with the
  project's naming command, so no agent composes a name by hand. Use whenever you name, rename
  or review the name of a repository, CDK stack or stack file, Lambda function, DynamoDB table,
  S3 bucket, API Gateway API, IAM role, log group, state machine, EventBridge bus, rule or
  schema, SQS queue, secret, SSM parameter, VPC, subnet, security group, KMS alias, Cognito
  user pool or app client, Powertools service or metrics namespace, environment variable,
  Python module, package or distribution, or any other name the project's naming standard
  covers. Find the command with `printenv ATW_NAMING_COMMAND`, then run it (`<command> name
  build ...`, `name convert ...`, `name check ...`); never type a name from memory or by
  copying a neighbour.
allowed-tools: [Bash]
---

# Resource Naming

The plugin holds no naming rule. Every name comes from the project's naming command: the
executable the project names in the environment variable `ATW_NAMING_COMMAND`, which
implements the `resource-naming` command line of the project's naming standard. The command
is the only thing that knows the patterns, the token forms and the lists the standard closes;
this skill only says how to call it.

## Find the command

Run `printenv ATW_NAMING_COMMAND`. It prints the command (a name on `PATH` or an absolute
path); run that command by what it printed, with the arguments below, as one Bash call. When
it prints nothing, no naming command is configured: no name can be made or checked. Say so in
your result and leave the name unmade; never compose one by hand instead.

## The rule

- **Always call the command.** Get every name from it and put exactly what it prints into the
  code (CDK `stack_name`, `function_name`, `table_name`, SSM parameter names, the Powertools
  `service`, file names). Check any existing or hand-edited name with `name check`.
- **Never hand-compose a name**, never "fix up" a printed name, and never copy a name from a
  neighbouring stack as the pattern. A name the command refuses is wrong, however it reads.
- **Trust what it returns.** A name the command built, converted or swapped is correct, and a
  check that reported valid is final; do not check it again.
- When the command refuses an input, read the violations it lists and change the input (the
  words of a token, the token you gave), not the name.
- A kind of name the command does not know is not covered: report it in your result as a gap
  in the naming standard instead of inventing a pattern.
- Language-native conventions still apply to code identifiers the standard does not name:
  Python classes in PascalCase, functions and variables in snake_case, TypeScript in camelCase.

## Commands

`<command>` below is what `printenv ATW_NAMING_COMMAND` printed. Every command takes one
output option: none (text for people), `-q` (only the result; for a check, only the exit
status), `-v` (also how the result was reached, on stderr for a produced value) or `--json`
(one JSON document on stdout). Programs and scripts use `--json` and the exit status, never
the text, which may be reworded.

| To | Run |
|---|---|
| list the kinds, each with its pattern | `<command> name build --help` |
| see the tokens one kind takes | `<command> name build <kind> --help` |
| build a name from its tokens | `<command> name build <kind> --<role> <value> ...` |
| turn an existing name into a name of another kind | `<command> name convert <name> --to <kind> [--from <kind>] [--with <role>=<value> ...]` |
| replace one token of an existing name | `<command> name swap <name> --set <role>=<value> ... [--kind <kind>]` |
| check a name as a kind | `<command> name check <name> --kind <kind> [--expect <role>=<value> ...]` |
| list the kinds a name is valid as | `<command> name identify <name>` |
| check a repository name | `<command> name check-repository <name>` |
| get the stack, stack file and Python names a repository name determines | `<command> name repository-names <repository>` |
| build, check or convert one token | `<command> token build\|check\|convert ...` (`<command> token build --help`) |

Token values may be given in any normal form (`"career profile"`, `career-profile`,
`careerProfile`); quote a value that holds spaces. For example:

```bash
<command> name build cdk-stack --project Acme --domain "career profile" --type service -q
<command> name convert Acme-dataAccess-lib --to python-distribution -q
<command> name convert acme-image-service --to lambda-function --with action=resize -q
<command> name check acme-careerProfile-service --kind cdk-stack
<command> name repository-names Acme-careerProfile-service --json
```

When a name can be read as more than one kind and the readings give different results,
`name convert` stops and prints one `name build` command per result: run the one you mean, or
give `--from <kind>`.

Exit status: 0 the value was produced, or the name is valid; 1 refused or invalid (the
violations say which rules); 2 a usage error (unknown command, kind, role or option); 70 an
internal error of the command.

## Plugin scripts

The plugin's Python scripts call the command through `scripts/naming_command.py` in this
skill, which reads `ATW_NAMING_COMMAND`, adds `--json`, and reads the document and the exit
status. It holds no naming rule either.
