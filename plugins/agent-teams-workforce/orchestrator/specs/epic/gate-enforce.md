# Net-effect spec: `gate-enforce` (Epic pipeline)

Step S01g. Scope: `gate-enforce` only at its call sites in the Epic pipeline (`prd-to-spec` and the
workflows it calls). **The Epic pipeline has no call site.** Every heading below except Purpose and
Open questions therefore reads "not called by the Epic pipeline". Its call sites in `bug-fix.js` belong
to the Task pipeline (S09).

## 1. Purpose

From `workflows/gate-enforce.js` `meta.description`: a reusable phase gate. It evaluates the caller's
deterministic checks against the artifact first and loops on a failed one with no model turn;
competitive criteria are recorded as flags; only constitutive criteria go to an independent
`phase-gate-enforcer`, which returns pass / loop / escalate. A gate with no constitutive criterion
passes on its checks alone. With `mode: 'exhaustion'` it asks the `advantage-evaluator` to rule proceed
or one directed revision on a gate whose loops are spent.

**It is not part of the Epic pipeline.** Evidence (run 2026-10-09 against the toolset repo at the
working tree, and the control repo):

- Every child-workflow call in the plugin
  (`grep -rn -o "(settleWorkflow|fableWorkflow|workflow)\('agent-teams-workforce:[a-z0-9-]+'" workflows/`):
  `gate-enforce` is called only from `bug-fix.js` lines 1359, 1504 and 1534. `prd-to-spec.js` calls
  `architecture`, `repo-scoping`, `trd-authoring`, `prd-reconciliation`, `spec-authoring`,
  `task-decomposition`; those six make no child-workflow call.
- `gate-enforce.js` dispatches `agent-teams-workforce:advantage-evaluator` (line 281) and
  `agent-teams-workforce:phase-gate-enforcer` (line 432). No Epic workflow dispatches either agent
  directly (`grep` for the quoted names `phase-gate-enforcer`, `advantage-evaluator`,
  `constitutional-agent` in `prd-to-spec.js`, `architecture.js`, `repo-scoping.js`,
  `trd-authoring.js`, `prd-reconciliation.js`, `spec-authoring.js`, `task-decomposition.js` returns
  nothing; the only hit in `prd-to-spec.js` is the embedded agent-contract table on line 22).
- The driver: no driver `.py` source names `gate-enforce`; it is not a composite in `dispatch.py`.
- History (`git log -S "agent-teams-workforce:gate-enforce'"` on `prd-to-spec.js`): the calls were
  changed in `c24e8eb6` (2026-08-06), `c493869e` (2026-09-22), `e55d89b6` (2026-09-23), `804750aa`
  (2026-09-26) and removed by `db2ee0d8` (2026-09-28, "remove unproven checks and narrative comments
  from SDLC workflows").
- The ledger has 38 lines naming `gate-enforce`, composites `prd-to-spec` and `bug-fix`, the last on
  2026-09-23: historical.

Review and approval inside the Epic flows are done by the flows' own reviewer and decider agents
(for example `architecture-decider`, `architecture-conformance-reviewer`, `openapi-contract-reviewer`,
`spec-decider`); those belong to `<orch>/specs/epic/architecture.md`,
`<orch>/specs/epic/spec-authoring.md` and the other Epic specs, not to this one.

## 2. Produces and decides

Not called by the Epic pipeline.

## 3. Inputs

Not called by the Epic pipeline.

## 4. Outputs

Not called by the Epic pipeline.

## 5. Steps

Not called by the Epic pipeline. Agent accounting: `phase-gate-enforcer` and `advantage-evaluator`
(the agents `gate-enforce.js` dispatches) have no step in the Python Epic pipeline. Their use in
`bug-fix` is specified under S09.

## 6. Checks kept / Checks dropped

Not called by the Epic pipeline.

## 7. Failure causes

Not called by the Epic pipeline.

## 8. Resume points

Not called by the Epic pipeline.

## 9. Owner rules that apply

Not called by the Epic pipeline.

## 10. Open questions

- Driver `verdict` events without a gate (in the Epic pipeline they come from reviewers and
  deciders, not from `gate-enforce`): merged question Q15 in `<orch>/specs/epic/driver-contract.md`.
