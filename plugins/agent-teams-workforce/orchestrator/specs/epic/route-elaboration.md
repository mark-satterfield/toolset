# Net-effect spec: `route-elaboration`

Source: `<plugin>/workflows/route-elaboration.js` (`meta.description`), the plugin command
`<plugin>/commands/work-bead.md` (its only caller), `<plugin>/workflows/ROUTING.md`, and the
driver's `<driver>/routing.py` and `<driver>/selection.py`. `<driver>` is
`$ATW_CONTROL_REPO/ops/sdlc-automation`.

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
- A feature is `elaborate` only in the sense that it needs a PRD and an Epic first: no door
  dispatches `prd-to-spec` with a feature (the driver's `selection.select_only` skips it, naming
  `/agent-teams-workforce:start-prd`; `workitems.elaboration_args` refuses a bead with no PRD).
- A Bug, a Task, an infrastructure bead, a `chore`/`docs`/`research`/`spike` bead and any
  unrecognised kind are `skip`.
- Nothing is written anywhere.

## 3. Inputs

- One bead record: `id`, `type`, `labels`, and (for the reason text only) `parentType`,
  `parentId`, `ancestorTypes`. Callers read it with `atw-bd show <id> --json` (the command) or
  from the driver's `BeadIndex.routing_bead(id)` (the driver).
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
2. `deterministic` (caller, not this flow): a Story is mapped to its Epic ancestor before
   dispatch. The driver does this in `selection.select_only` (a Story with an Epic ancestor is
   selected as that Epic; one without is skipped, naming the missing Epic). The `/work-bead`
   command does it in its step 5.

There are no agent steps. The JavaScript's one phase (`Classify`) and its `log` line are not
carried over.

**Is `<driver>/routing.py` already covering it? Yes.** `routing.route_elaboration` applies the
same rules to the same inputs and returns the same verdict for every bead kind, and `routing.route`
sends Epic/Story/feature beads to it. The driver never calls `route-elaboration.js`: every
elaboration dispatch is routed by `selection._to_item` -> `routing.route`. The only caller of the
JavaScript is the plugin command `commands/work-bead.md` (step 3, "ELABORATION work"), the manual
door.

**Is it still needed? Not as a workflow.** Its logic already exists in Python and is the one the
pipeline uses. The rewrite keeps one router (`routing.route_elaboration`) and no
`route-elaboration` flow. `route-elaboration.js` becomes deletable once `/work-bead` routes
through the Python router, or loses its elaboration branch (merged question Q12 and Open question
1). Differences between the two today, which
the Python version settles:
- Infrastructure kinds: the JavaScript hardcodes `infra`/`infrastructure`; `routing.py` reads
  `infra-vocabulary.json`. The vocabulary is the one source.
- Story reason text: `routing.py` says a Story run "reconciles the Story with its Spec and emits
  the Task beads parented to it", which is not what happens; the JavaScript's reason (the Story is
  elaborated through its parent Epic) is correct. The verdict is the same; only the reason text
  differs. Fix the text when `routing.py` is next edited (S05 or S08).

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
- `humanInitiated` (named in `ROUTING.md` step 3): no code reads it; drop it from the command text.

## 7. Failure causes

- Infrastructure vocabulary unreadable or empty: `routing.infra_vocabulary` logs once to stderr and
  routes with no infrastructure types or labels. Cause `other`; not retried (an unchanged file
  gives the same result). It cannot misroute elaboration work: Epic/Story/feature rules do not use
  the vocabulary.
- No other failure point: the router is a pure function over its input.

## 8. Resume points

None. The verdict is recomputed from the bead each time; it costs nothing and saves nothing.

## 9. Owner rules that apply

- 7.11 Deterministic over agentic: routing is code, no agent.
- 7.8 Owner selection filters: not implemented here. The filters (unscored Tasks, unmet Epic
  dependencies, the mobile Epics `ssbd-cb6i4`, `ssbd-kfihs`, `ssbd-mx3vn` left without
  `elaboration_state`) stay in `<driver>/selection.py` and `elabstate.py`; the router only
  classifies the bead's kind.
- 7.9 Who gets asked what: a skip is reported, never put to the owner; a Bug's reason names
  triage by a person because only a person files and triages Bugs.

## 10. Open questions

**Q12 [owner] (merged; also asked in `prd-to-spec.md`). Which manual doors into the Epic
pipeline survive?** Today three exist besides the driver: the `/work-bead` command's elaboration
branch (step 3, "ELABORATION work", and step 5), the `/start-prd` command, and the inline PRD text
(`prd.body`) those doors could pass. If the owner wants manual elaboration, each surviving door
needs a Python entry point that routes and starts the `prd-to-spec` flow (which applies the
selection filters of CONTEXT 7.8 at its entry, `prd-to-spec.md` step 2); if not, the branches go and S08
deletes `route-elaboration.js`. Where the router then lives is Open question 1.

1. **[S02] Where the router lives** (after Q12). `routing.py` is in the driver (control
   repository) and imports `pluginversion`; the `/work-bead` command runs from the installed plugin
   and cannot import the driver. Either the router moves into `<orch>` and the driver imports it
   from the installed plugin, or the command calls a driver CLI.
2. **[S02] Feature verdict.** Both routers return `elaborate` for a feature, yet no door can
   dispatch one (it has no Epic or PRD yet). Returning `skip` with "needs `/start-prd`" would match
   what happens. Change the verdict?
