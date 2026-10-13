# Routing a bead to elaboration

Failure handling: bounded transient retries and quota pauses remain. An ordinary item failure is recorded and excluded from selection for the current invocation; other eligible items continue. Setup, code, schema, and runtime type defects stop new dispatch, preserve the original diagnostic, and let current paid steps finish. Named within-step corrective passes remain bounded content work; failed runs do not dispatch repair or diagnosis agents.

Code: the driver's `<driver>/routing.py` (`route_elaboration`, `route`) and `<driver>/selection.py`;
the workflow `<plugin>/workflows/route-elaboration.js`; the policy `<plugin>/workflows/ROUTING.md`.
`<driver>` is the driver directory the `pipeline-contracts` skill defines: `DRIVER_DIR_PARTS` under
the control repository, defined once as `dirParts` in `schemas/driver-surface.schema.json` and
generated into `scripts/driver_surface_types.py`.

**Entry.** The only entry into the Epic pipeline is the driver's elaboration lane, which the owner
starts with `python3 ops/sdlc-automation/keeper.py` (CONTEXT 7.18). The driver routes with its own
`routing.route_elaboration` and never calls `route-elaboration.js`. The workflow is dispatched only
by the command `/work-bead`, which rules that a bead is elaboration work and then reports that the
driver's elaboration lane elaborates the Epic; it dispatches no elaboration.

## 1. Purpose

Rule, deterministically, whether a bead is elaboration work. An Epic, a Story or a feature routes
to `prd-to-spec`; every other kind is skipped with a reason naming where it belongs (a Task or an
infrastructure bead belongs to the build router, a Bug to triage by a person, `chore`, `docs`,
`research` and `spike` to no composite). The result is `{ bead, action, composite, reason,
ruledBy }`: `action` is `elaborate` or `skip`, `composite` is `prd-to-spec` or null, `ruledBy` is
always `deterministic`. No agent and no judgment are involved.

## 2. Produces and decides

After a run:
- The bead has exactly one verdict: `elaborate` (composite `prd-to-spec`) or `skip` (composite
  null), with a reason string.
- An Epic is `elaborate`.
- A Story is `elaborate`, and the caller elaborates the Story's parent **Epic**, never the Story:
  `prd-to-spec` takes an Epic. A Story with no Epic ancestor cannot be elaborated.
- A feature is `elaborate` only in the sense that it needs a PRD and an Epic first: the driver
  never dispatches `prd-to-spec` with a feature (`selection.select_only` skips it;
  `workitems.elaboration_args` refuses a bead with no PRD).
- A Bug, a Task, an infrastructure bead, a `chore`/`docs`/`research`/`spike` bead and any
  unrecognised kind are `skip`.
- Nothing is written anywhere.

## 3. Inputs

- One bead record: `id`, `type`, `labels`, and (for the reason text only) `parentType`,
  `parentId`, `ancestorTypes`, from the driver's `BeadIndex.routing_bead(id)`.
- The infrastructure vocabulary the `artifact-handoff` skill defines in
  `<plugin>/skills/artifact-handoff/schemas/infra-vocabulary.schema.json`, which `routing.py` loads
  as the generated `<plugin>/skills/artifact-handoff/scripts/infra_vocabulary.py` through
  `pluginversion.plugin_file` (`routing.INFRA_VOCABULARY_PARTS`), and which the workflow takes as
  its `infraVocabulary` argument.

Label matching applies only when the bead's `type` is not a known type (`by_label`): known types
are `task`, `bug`, `epic`, `story`, `feature`, `chore`, `docs`, `research`, `spike`, plus the
vocabulary's infrastructure types. Elaboration labels: `epic`; `story`; `feature`, `prd`,
`requirement`, `prd-to-spec`.

## 4. Outputs

- The verdict object, returned in memory (`routing.Route(bead_id, action, composite, reason,
  ruled_by)` in Python; the field names `bead, action, composite, reason, ruledBy` in the
  workflow's result).
- No files, no bead writes, no vault writes, no commits, no ledger events of its own (the driver
  records a skip through its normal `Skip` handling).

## 5. Steps

1. `deterministic`: `routing.route_elaboration(bead)` in `<driver>/routing.py`. Order of rules:
   elaboration kind (Epic, Story, feature by type or label) -> `elaborate` / `prd-to-spec`; then
   Bug -> skip; then Task or infrastructure type or label -> skip ("route through route-build");
   then out-of-pipeline types -> skip; else skip as unclassifiable.
2. `deterministic` (the driver, not this flow): a Story is mapped to its Epic ancestor before
   dispatch, in `selection.select_only` (a Story with an Epic ancestor is selected as that Epic;
   one without is skipped, naming the missing Epic).

There are no agent steps. `routing.route_elaboration` and `route-elaboration.js` apply the same
rules to the same inputs and return the same verdict for every bead kind; every elaboration
dispatch is routed by `selection._to_item` -> `routing.route`.

## 6. Checks

- Bug is never routed to a composite: without it a Bug would be dispatched to `prd-to-spec` or a
  build composite and produce beads or code from a report; nothing later stops a dispatched run.
- Label matching only for unknown types (`by_label`): without it a Task labelled `story` would be
  elaborated and its Tasks written again under a phantom Epic; nothing later catches that.

## 7. Failure causes

- Infrastructure vocabulary unavailable (the plugin is not installed, ships no
  `infra_vocabulary.py`, or the module lacks a name the driver reads): `routing.vocabulary_module()`
  raises `routing.InfraVocabularyUnavailableError`, which `routing.infra_vocabulary()`,
  `routing.infra_types()` and `routing.infra_labels()` propagate. Not retried (an unchanged plugin
  gives the same result).
- No other failure point: the router is a pure function over its input.

## 8. Where a run begins

The verdict is computed from the bead each time and nothing of it is saved.

## 9. Requirements that apply

- 7.18 Entry point: the only entry is the driver started by `keeper.py`; `/work-bead` and
  `/start-prd` dispatch no elaboration.
- 7.16 Hierarchy: a Bug is never routed to a composite (Claude Code never creates or works bug
  beads; bugs are for humans and a later triage process).
- 7.11 Deterministic over agentic: routing is code, no agent.
- 7.8 Owner selection filters: not implemented here. The filters (unscored Tasks, unmet Epic
  dependencies, the `bead_metadata.KEY_ELABORATION_STATE` key of
  `<plugin>/skills/beads-contract/schemas/bead-metadata.schema.json`) are in
  `<driver>/selection.py` and `elabstate.py`; the router only classifies the bead's kind.
- 7.9 Who gets asked what: a skip is reported, never put to the owner; a Bug's reason names
  triage by a person because only a person files and triages Bugs.

## 10. Open items

See QUESTIONS.md
