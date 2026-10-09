# Net-effect spec: `prd-validation` (Epic pipeline)

Step S01g. Scope: `prd-validation` only where the Epic pipeline (`prd-to-spec` and the workflows it
calls) calls it. **The Epic pipeline does not call it.** Every heading below except Purpose and Open
questions therefore reads "not called by the Epic pipeline".

## 1. Purpose

From `workflows/prd-validation.js` `meta.description`: a leaf mini in which one read-only analyst
session (agent `prd-validation-analyst`) inspects a PRD through seven lenses (requirement class,
ambiguity, completeness, conflict, constraints, domain boundaries, clarifications), plus an
informational BRD traceability mapping when `args.brd` is supplied; the script fails the PRD only on a
blocker finding, and treats a technical requirement as a major finding.

**It is not part of the Epic pipeline.** Evidence (run 2026-10-09 against the toolset repo at the
working tree, and the control repo):

- Child workflows called by `prd-to-spec.js`
  (`grep -o "settleWorkflow('agent-teams-workforce:[a-z-]*'" workflows/*.js`): `architecture`
  (line 1295), `repo-scoping` (1411), `trd-authoring` (1452), `prd-reconciliation` (1642),
  `spec-authoring` (1662), `task-decomposition` (1777). `prd-validation` is not among them.
- `architecture.js`, `repo-scoping.js`, `trd-authoring.js`, `prd-reconciliation.js`,
  `spec-authoring.js`, `task-decomposition.js` define `fableWorkflow` but make no child-workflow
  call (`grep -o "(settleWorkflow|fableWorkflow|workflow)\('agent-teams-workforce:[a-z0-9-]+'"` finds
  none in them).
- The literal `'agent-teams-workforce:prd-validation'` appears in no workflow, command or script
  (`grep -rn` over `workflows/`, `commands/`, `scripts/`). In `prd-to-spec.js` the string
  `prd-validation` appears only inside the embedded agent-contract table on line 22
  (`prd-validation-analyst`, `prd-validation-lead` entries), which is data, not a call.
- `agentType: 'agent-teams-workforce:prd-validation-analyst'` is dispatched only at
  `prd-validation.js:882`. No Epic workflow dispatches `prd-validation-analyst` directly
  (`grep` for the quoted agent name in the seven Epic workflow files returns nothing).
- The driver: `prd-validation` is not in `dispatch.py` `COMPOSITE_PHASES["prd-to-spec"]`
  (`architecture, repo-scoping, trd-authoring, prd-reconciliation, spec-authoring,
  task-decomposition`), and no driver `.py` source names it. The only driver hits are a stale
  compiled `__pycache__/dispatch.cpython-313.pyc` and historical `state/` files.
- History (`git log -S` on `prd-to-spec.js`): `7915a398` (2026-09-30) replaced the classify-only
  `prd-validation` dispatch with `depscore.py prd-parse`; `ff37924c` (2026-10-02) "prd-to-spec parses
  the PRD and leaves validation to the Ready gate"; `b42c43d5` (2026-10-09) removed `prd-parse` from
  `prd-to-spec.js` as well (`grep prd-parse workflows/prd-to-spec.js` returns nothing).
- The ledger (`ops/sdlc-automation/state/ledger.jsonl`) has 94 lines naming `prd-validation`, first
  2026-08-28, last 2026-10-03. The last is a `dispatched` event for `ssbd-guuuz` whose
  `extraArgs.resume.stale` carries `{"step": "prd-validation", "reason": "not a step of prd-to-spec;
  names no saved file"}`: a leftover entry in that Epic's `STEPS.md`, not a call.

The PRD gate the Epic pipeline relies on today is the owner setting `elaboration_state=ready` on the
Epic (`ops/sdlc-automation/elabstate.py` `candidacy`); see `<orch>/specs/epic/prd-to-spec.md`.

## 2. Produces and decides

Not called by the Epic pipeline.

## 3. Inputs

Not called by the Epic pipeline.

## 4. Outputs

Not called by the Epic pipeline.

## 5. Steps

Not called by the Epic pipeline. Agent accounting: `prd-validation-analyst` (the only agent
`prd-validation.js` dispatches) is not dispatched by any Epic flow, so the Python Epic pipeline has no
step for it. `prd-validation-lead` is manual-only per its own definition and no workflow dispatches it.

## 6. Checks kept / Checks dropped

Not called by the Epic pipeline. No check from `prd-validation.js` carries into the Epic flows.

## 7. Failure causes

Not called by the Epic pipeline.

## 8. Resume points

Not called by the Epic pipeline. One resume fact does affect the Epic flows: an Epic's working folder
can still list `prd-validation` in `STEPS.md` (seen for `ssbd-guuuz`), and today's
`artifactio.plan` reports it as a stale step that "names no saved file". See Open questions.

## 9. Owner rules that apply

Not called by the Epic pipeline. CONTEXT 7.11 (deterministic over agentic) and 7.9 (only owner facts
go to the owner) are why the PRD's readiness is the owner's `ready` ruling, not an agent session.

## 10. Open questions

1. **Leftover `prd-validation` step entries.** Some Epic working folders under
   `<control>/.claude/workflow-runs/artifacts/<bead>/STEPS.md` still list `prd-validation`. Should the
   Python resume logic ignore unknown step names, or should S05 remove them from the saved folders
   once? The sources do not say.
2. **Any PRD check before architecture?** Since `b42c43d5` the Epic pipeline runs no structural PRD
   check (neither `prd-validation` nor `depscore.py prd-parse`). Whether the Python pipeline needs a
   deterministic PRD parse (file readable, not superseded, requirements present) before the first
   agent step, or relies only on the owner's `ready` ruling, is for S02 or the owner to settle; it
   belongs in `<orch>/specs/epic/prd-to-spec.md` if kept.
3. **Fate of `prd-validation.js`.** Nothing in the Epic or Task pipelines, the commands, or the driver
   calls it. Whether S08 or S15 deletes it (and `prd-validation-analyst`), or it stays as a manual
   tool, is not settled by the sources.
