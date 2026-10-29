---
name: artifact-handoff
description: Shared file contracts for direct specialist sessions; producers and consumers read the same schemas and completion rules.
---

# Direct artifact handoff

Find the artifact assigned to this session in [Epic contracts](epic-contracts.md) and read the
contract file it names in [schemas/](schemas/); that file's descriptions state the artifact's
fields, their meaning and when it is complete.
Producers and reviewers use this same contract; a reviewer cannot add unstated requirements.

The brief is [schemas/agent-brief.schema.json](schemas/agent-brief.schema.json): facts and
paths only, never a file's content, with the meaning of each input label. Read the named files
yourself. A file a step writes for an agent is checked against its contract file in
[schemas/](schemas/) before it is handed on. Write the complete result to the exact output
path. Write only assigned outputs.
For a JSON output write one strict JSON value with unique keys; for a document write nonempty
UTF-8 Markdown. Do not paste file contents into a response. A final reply may name the result path.

Python validates the file against the schema, checks declared document citations and records the
file in the step journal. The agent does not accept its own result, compute revision bindings,
submit StructuredOutput, or run artifact checkpoint or
submission helpers. There is no machine mode or command-runner handoff in direct sessions.
A structurally valid artifact is not automatically a semantically correct one.

On a corrective pass, read the labeled validation-errors input and the existing output, repair the
specific findings and affected references, and preserve valid work. On interruption retain the
actual files; resumption continues those files. Do not fabricate completion for missing reasoning.
Named missing inputs or remaining uncertainties belong in the contract's existing evidence fields;
never add fields to a closed schema or return a success reference for absent work.

## Generated contract types

Each schema in [schemas/](schemas/) is the one definition of its contract. Python code never
restates a key, type or allowed value: it imports the module that
`scripts/generate_contract_types.py` generates from the schema, and
`scripts/check_contract_types.py` fails when a generated module is stale. Run
`python3 scripts/generate_contract_types.py` after changing a schema.

| Schema | Generated module |
|---|---|
| `schemas/task-deps.schema.json` (Cross-Story Task dependencies) | `scripts/task_deps_contract.py` |

## Which agent writes which output

[agent-outputs.json](agent-outputs.json) pairs each file an agent writes with the schema (file
and `$defs` entry) it is checked against and the code that makes the pairing. The schema is the
one home of the output's shape: an agent definition, and a skill that states the output, point at
it and say only what goes in each field; the agent writes exactly the shape that schema defines,
and no other fields. `node scripts/check-agent-output-formats.mjs` (run by the pre-commit hook)
checks every pairing, and every structured-output schema a workflow dispatch hands the runtime,
against the agent definitions and those skills, and fails when a text calls a name a field that
the output does not define. A text names an output field only in backticks: the check fails on a
camelCase or snake_case name outside backticks that is a field of any schema or follows a write
instruction ("set fooBar"), on a plain word called a field ("add a confidence field"), on a
field of the output named in plain words in an instruction to put it on each object ("include
its source with each reason"), and on a single plain word put on each object that the output
does not define but another schema does ("give each reason a severity"). Every session an orchestrator flow launches with an `AgentLaunch`
must be named, by the function that builds it, in the `launches` of a pairing, so a new
validated output cannot be added without its pairing. A session any catalog agent may run (an
answer to the solutions architect's request) carries its contract in its brief: that pairing's
`pointer` is `brief`, and the check reads the schema and the rule in the code that writes the
brief instead of in each agent's definition.
