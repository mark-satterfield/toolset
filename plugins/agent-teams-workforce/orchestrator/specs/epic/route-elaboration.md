# Net-effect spec: `route-elaboration`

Failure handling: bounded transient retries and quota pauses remain. An ordinary item failure is recorded and excluded from selection for the current invocation; other eligible items continue. Setup, code, schema, and runtime type defects stop new dispatch, preserve the original diagnostic, and let current paid steps finish. Named within-step corrective passes remain bounded content work; failed runs do not dispatch repair or diagnosis agents.

Source: `<plugin>/workflows/route-elaboration.js` (`meta.description`), `<plugin>/workflows/ROUTING.md`,
and the driver's `<driver>/routing.py` and `<driver>/selection.py`. `<driver>` is
`$ATW_CONTROL_REPO/ops/sdlc-automation`.

**Entry.** The only entry into the Epic pipeline is the driver's elaboration lane, which the owner
starts with `python3 ops/sdlc-automation/keeper.py` (CONTEXT 7.18). There is no `/work-bead` entry
and no `/start-prd` entry: S08 deletes both plugin commands. Today the JavaScript's only caller is
`/work-bead`, so with that command gone `route-elaboration.js` has no caller and S08 deletes it;
the driver's `routing.route_elaboration` is the one router.

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
  never dispatches `prd-to-spec` with a feature (`selection.select_only` skips it, today naming
  `/agent-teams-workforce:start-prd`, a command S08 deletes, so the skip reason must stop naming
  it; `workitems.elaboration_args` refuses a bead with no PRD).
- A Bug, a Task, an infrastructure bead, a `chore`/`docs`/`research`/`spike` bead and any
  unrecognised kind are `skip`.
- Nothing is written anywhere.

## 3. Inputs

- One bead record: `id`, `type`, `labels`, and (for the reason text only) `parentType`,
  `parentId`, `ancestorTypes`, from the driver's `BeadIndex.routing_bead(id)`.
- The infrastructure vocabulary `<plugin>/scripts/infra-vocabulary.json` (`types`, `labels`),
  which `routing.py` reads through `pluginversion.plugin_file`. The JavaScript hardcodes
  `infra`/`infrastructure` instead.

Label matching applies only when the bead's `type` is not a known type (`by_label`): known types
are `task`, `bug`, `epic`, `story`, `feature`, `chore`, `docs`, `research`, `spike`, plus the
vocabulary's infrastructure types. Elaboration labels: `epic`; `story`; `feature`, `prd`,
`requirement`, `prd-to-spec`.

## 4. Outputs

- The verdict object, returned in memory (`routing.Route(bead_id, action, composite, reason,
  ruled_by)` in Python; the field names `bead, action, composite, reason, ruledBy` in the
  JavaScript result).
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

There are no agent steps. The JavaScript's one phase (`Classify`) and its `log` line are not
carried over.

**Is `<driver>/routing.py` already covering it? Yes.** `routing.route_elaboration` applies the
same rules to the same inputs and returns the same verdict for every bead kind, and `routing.route`
sends Epic/Story/feature beads to it. The driver never calls `route-elaboration.js`: every
elaboration dispatch is routed by `selection._to_item` -> `routing.route`.

**Is it still needed? No.** Its logic already exists in Python, in the driver, and is the one the
pipeline uses. The rewrite keeps one router (`routing.route_elaboration`, where it is) and no
`route-elaboration` flow; S08 deletes `route-elaboration.js` with the `/work-bead` command that was
its only caller (CONTEXT 7.18). Differences between the two today, which the Python version
settles:
- Infrastructure kinds: the JavaScript hardcodes `infra`/`infrastructure`; `routing.py` reads
  `infra-vocabulary.json`. The vocabulary is the one source.
- Story reason text: `routing.py` says a Story run "reconciles the Story with its Spec and emits
  the Task beads parented to it", which is not what happens; the JavaScript's reason (the Story is
  elaborated through its parent Epic) is correct. The verdict is the same; only the reason text
  differs. See QUESTIONS.md item 48.

## 6. Checks kept / Checks dropped

**Checks kept**
- Bug is never routed to a composite: without it a Bug would be dispatched to `prd-to-spec` or a
  build composite and produce beads or code from a report; nothing later stops a dispatched run.
- Label matching only for unknown types (`by_label`): without it a Task labelled `story` would be
  elaborated and its Tasks written again under a phantom Epic; nothing later catches that.

**Checks dropped**
- The JavaScript's argument parsing (`typeof args === 'string'` -> `JSON.parse`): a sandbox
  artifact; the Python function takes a dict.
- The JavaScript's own copy of the rules: replaced by the single Python router.
- `humanInitiated` (named in `ROUTING.md` step 3): no code reads it; it goes with the deleted
  `/work-bead` command.

## 7. Failure causes

- Infrastructure vocabulary unreadable or empty: `routing.infra_vocabulary` logs once to stderr and
  routes with no infrastructure types or labels. Cause `other`; not retried (an unchanged file
  gives the same result). It cannot misroute elaboration work: Epic/Story/feature rules do not use
  the vocabulary.
- No other failure point: the router is a pure function over its input.

## 8. Resume points

None. The verdict is recomputed from the bead each time; it costs nothing and saves nothing.

## 9. Requirements that apply

- 7.18 Entry point: the only entry is the driver started by `keeper.py`; no `/work-bead` or
  `/start-prd` entry exists or is added.
- 7.16 Hierarchy: a Bug is never routed to a composite (Claude Code never creates or works bug
  beads; bugs are for humans and a later triage process).
- 7.11 Deterministic over agentic: routing is code, no agent.
- 7.8 Owner selection filters: not implemented here. The filters (unscored Tasks, unmet Epic
  dependencies, the mobile Epics `ssbd-cb6i4`, `ssbd-kfihs`, `ssbd-mx3vn` left without
  `elaboration_state`) stay in `<driver>/selection.py` and `elabstate.py`; the router only
  classifies the bead's kind.
- 7.9 Who gets asked what: a skip is reported, never put to the owner; a Bug's reason names
  triage by a person because only a person files and triages Bugs.

## 10. Open items

See QUESTIONS.md
