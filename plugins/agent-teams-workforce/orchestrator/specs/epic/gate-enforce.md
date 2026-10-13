# `gate-enforce` and the Epic pipeline

Failure handling: bounded transient retries and quota pauses remain. An ordinary item failure is recorded and excluded from selection for the current invocation; other eligible items continue. Setup, code, schema, and runtime type defects stop new dispatch, preserve the original diagnostic, and let current paid steps finish. Named within-step corrective passes remain bounded content work; failed runs do not dispatch repair or diagnosis agents.

## What it is

`workflows/gate-enforce.js` is a reusable phase gate for workflow scripts. It evaluates the
caller's deterministic checks against the artifact first and loops on a failed one with no model
turn; competitive criteria are recorded as flags; only constitutive criteria go to an independent
`phase-gate-enforcer`, which returns pass, loop or escalate. A gate with no constitutive criterion
passes on its checks alone. With `mode: 'exhaustion'` it asks the `advantage-evaluator` to rule
proceed or one directed revision on a gate whose loops are spent.

## The Epic pipeline does not run it

No step of an Epic's journal runs `gate-enforce`, and no Epic step starts `phase-gate-enforcer`,
`advantage-evaluator` or `constitutional-agent`. The driver names it in no module, and it is not a
composite the driver dispatches.

Review and approval inside elaboration are steps of the Epic's journal: the architecture reviewers
selected by rule, `architecture-team-lead` and `architecture-decider`
(`<orch>/specs/epic/architecture.md`), and the spec review with `spec-decider`
(`<orch>/specs/epic/spec-authoring.md`).

It therefore has no inputs, outputs, steps, checks or failure causes in the Epic pipeline.

## Open items

See QUESTIONS.md
