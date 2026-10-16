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
