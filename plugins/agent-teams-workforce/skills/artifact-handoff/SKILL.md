---
name: artifact-handoff
description: Shared file contracts for direct specialist sessions; producers and consumers read the same schemas and completion rules.
---

# Direct artifact handoff

Read [Epic contracts](epic-contracts.md) for the artifact assigned to this session, including its
fields, interpretation and completion criteria. JSON schemas are in [schemas/](schemas/).
Producers and reviewers use this same contract; a reviewer cannot add unstated requirements.

The brief contains only a bead id, labeled absolute input paths, an absolute output path, and a
one-line outcome. Read the named files yourself. Write the complete result to the exact output
path. Write only assigned outputs and, for architecture writers, the assigned draft views.
For a JSON output write one strict JSON value with unique keys; for a document write nonempty
UTF-8 Markdown. Do not paste file contents into a response. A final reply may name the result path.

Python validates the file against the schema, checks declared document citations, publishes the
canonical JSON, and records input/output fingerprints. The agent does not accept its own result,
write receipts, compute revision bindings, submit StructuredOutput, or run artifact checkpoint or
submission helpers. There is no machine mode or command-runner handoff in direct sessions.
A structurally valid artifact is not automatically a semantically correct one.

On a corrective pass, read the labeled validation-errors input and the existing output, repair the
specific findings and affected references, and preserve valid work. On interruption retain the
actual files; resumption continues those files. Do not fabricate completion for missing reasoning.
Named missing inputs or remaining uncertainties belong in the contract's existing evidence fields;
never add fields to a closed schema or return a success reference for absent work.
