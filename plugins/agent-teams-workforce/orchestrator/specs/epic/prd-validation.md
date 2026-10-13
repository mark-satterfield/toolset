# `prd-validation` and the Epic pipeline

Failure handling: bounded transient retries and quota pauses remain. An ordinary item failure is recorded and excluded from selection for the current invocation; other eligible items continue. Setup, code, schema, and runtime type defects stop new dispatch, preserve the original diagnostic, and let current paid steps finish. Named within-step corrective passes remain bounded content work; failed runs do not dispatch repair or diagnosis agents.

## What it is

`workflows/prd-validation.js` is a leaf workflow in which one read-only analyst session (agent
`prd-validation-analyst`) inspects a PRD through seven lenses (requirement class, ambiguity,
completeness, conflict, constraints, domain boundaries, clarifications), with an informational
BRD traceability mapping when `args.brd` is supplied. The script fails the PRD only on a blocker
finding, and treats a technical requirement as a major finding. It runs on its own, when a person
dispatches it.

## The Epic pipeline does not run it

No step of an Epic's journal runs `prd-validation` or starts `prd-validation-analyst`.
`prd-validation-lead` is manual-only by its own definition, and nothing starts it. The driver
names the workflow in no module.

Elaboration assumes the PRD is validated. The PRD gate the Epic pipeline relies on is the Epic's
elaboration state: the driver selects an Epic only when that state is ready, or in progress with
no live run owning it (`<driver>/elabstate.py` `candidacy`; see
`<orch>/specs/epic/driver-contract.md` §2). `prd-to-spec` makes no PRD check of its own beyond
reading the file (CONTEXT 7.17).

It therefore has no inputs, outputs, steps, checks or failure causes in the Epic pipeline.

## Requirements that apply

CONTEXT 7.17: validating an Epic and its PRD is not part of elaboration. CONTEXT 7.18: the only
entry into the pipeline is `keeper.py`.

## Open items

See QUESTIONS.md
