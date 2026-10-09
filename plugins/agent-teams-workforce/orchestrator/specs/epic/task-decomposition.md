# Net-effect spec: `task-decomposition`

Step S01e of the pipeline rewrite. Sources, in order of authority: the `meta.description` of
`<plugin>/workflows/task-decomposition.js`; the agent definition `<plugin>/agents/task-decomposer.md`
and the skills it loads (`subagent-contract`, `validation-protocol`, `beads-contract`,
`graphrag-lookup`, plus `wsjf` for sizing); CONTEXT section 7; and, for contracts only, the code of
`task-decomposition.js`, `prd-to-spec.js` (its caller), `scripts/portfolio/beadwrite.py`,
`scripts/portfolio/hierarchy.py`, `scripts/portfolio/depscore.py`, `scripts/portfolio/beadgraph.py`,
`scripts/shared-blocks/relay.js` and `<driver>/artifactio.py`.

Names used below:

- `<work>`: the Epic's working directory,
  `<control>/.claude/workflow-runs/artifacts/<epic-id>/` (`artifactio.working_dir`).
- `<slug>`: the Story's repository slug (the repository basename, suffixed `-2`, `-3` when two
  span repositories share a basename; assigned by the composite).
- `<root>`: the project root that recorded paths are relative to (`$SKILLSPOKE_ROOT`).
- "work item": a delta item that `recon-<slug>.json` marks `add`, `modify`, `remove` or `done`.
  A `done` item is a work item because code that already meets a requirement still gets a Task:
  the Task's Red step tests the requirement, and the build pipeline decides whether any code
  changes (CONTEXT 7.6, 7.19; the owner's answer 2 of 2026-10-09). Today's
  `hierarchy.WORK_STATUSES` lists only `add`, `modify`, `remove`; S04 widens it. Only a
  `planned-elsewhere` item is not a work item: another Epic's open bead plans it, and it becomes a
  `blocks` edge onto that bead.

## 1. Purpose

Decompose ONE repository's Spec into Tasks, and only Tasks, under the Story that Spec pairs with, in
that Story's single repository. A Task is build work (code, infrastructure or documentation); the
Spec's acceptance criteria are carried inside the build Tasks and become tests in each Task's Red
step, so no Task only writes tests. Tasks exist for every work item, `done` items included; work an
open Task of another Epic in the same repository already plans (a `planned-elsewhere` item, or an
`otherEpicTasks` entry) is not duplicated but becomes a `blocks` edge onto that Task. A missing
prerequisite the architecture's Closure found (for example a VPC, a security group or a Lambda
layer) is a work item like any other and gets a Task (CONTEXT 7.20). A `web-ui` Task carries in its
build contract the design source of the ui items it cites (`bundle`, `cds` or `none`) and, for
`bundle`/`cds`, its artifact (kind and slug). One maker session decomposes, sequences and sizes;
everything else (planning the build order, writing beads with their same-Story edges, the rerun
decision, coverage of items and sizes) is deterministic. Every Story gets at least one Task; there
is no "nothing to build" result (CONTEXT 7.6). Rerunning the flow keeps every existing Task when
nothing upstream changed, and replaces only the unstarted Tasks when something did.

## 2. Produces and decides

After a successful run, all of these are true:

1. `<work>/tasks-<slug>.json` exists, is the accepted decomposition, and its input record
   `<work>/tasks-<slug>.json.meta.json` holds the sha256 of every input that decides the rerun case
   (section 8) as they were when it was decomposed.
2. The rerun case was decided from fingerprints alone, and is one of `new` (no Task bead existed),
   `unchanged` (every recorded input hashes as recorded) or `replaced` (an input changed). There is
   no "can't tell" case (CONTEXT 7.5).
3. Case `unchanged`: no maker session ran; every existing Task bead is kept; only Task beads not yet
   written were created.
4. Case `replaced`: every unstarted Task bead under the Story that elaboration wrote was deleted;
   every started or closed one was kept and named to the maker as existing work; the full set was
   decomposed again around them.
5. Every Task in `tasks-<slug>.json` has a Task bead under the Story `story:<slug>` of the Epic,
   matched by `elab_key`, else by the delta items it cites, else by title, created or updated in
   place. No Task bead was closed. No started or closed Task bead was rewritten.
6. Each Task bead carries its build contract (description block and metadata, section 4), a valid
   job size (`wsjf_size_estimate`, `wsjf_size_low`, `wsjf_size_high`, `wsjf_size_confidence`), and
   all its `blocks` edges inside the Story: onto the Tasks of the same Story it depends on (maker
   edges plus the edges the delta's `requires` relations make inside this repository, cycles
   dropped); onto the bead that plans each `planned-elsewhere` item it needs; and onto each open
   Task of another Epic named in `blockedByExternal`. The edges are written with the Task, in
   build order, so every blocker exists when its dependent is written.
7. Every work item of `recon-<slug>.json` is cited in `requirementIds` by at least one Task
   (`recon-<slug>.json` itself is never edited by this flow). No item is recorded as needing no
   work: the `noWork` answer of today's corrective pass is a "nothing to build" record and is
   dropped (CONTEXT 7.6). Every required work item that `hierarchy.derive_prerequisites` finds
   without a Task is treated the same way. Every Task has a valid size. If after the one corrective pass any such item is still uncited, or any Task still
   has no valid size, the run failed at stage `uncited-items` naming them (CONTEXT 7.6).
8. The Story has at least one Task. An empty decomposition is not a result: it is a finding for
   the one corrective pass, and still empty after it, the run failed at stage `decompose`.

This flow does not decide the Epic's "done" state, does not write edges between Stories and does
not compute WSJF; the composite does all three after every Story is decomposed
(`prd-to-spec.md` steps 11 to 14). The sizes this flow writes are what that WSJF is computed from.

## 3. Inputs

From the caller (`prd-to-spec`, `decompArgs`), per Story:

| Input | Meaning |
|---|---|
| `epicId` | The Epic bead id. |
| `repoPath` | The Story's repository (absolute). Required. |
| `slug` | The Story's repository slug. |
| `story` | `{id, key, title}` of the Story bead `spec-authoring` wrote (`elab_key` `story:<slug>`). |
| `spec` | `{id, title, description, source}`: navigation text only (a summary); the contract is in the spec documents. |
| `specDocs` | `[{path, ref}]`: the three documents `spec-authoring` returns as `specPaths`: `<work>/spec-<slug>.md`, `<work>/spec-<slug>.data-model.md`, `<work>/spec-<slug>.criteria.md`; `ref` is the path relative to `<root>` that Tasks cite. There are no other spec artifact paths. |
| `detailingPath` | `<work>/recon-<slug>.json`. |
| `packagesDir` | `$ATW_DESIGN_PACKAGES_DIR`: the directory every cited cds bundle must sit in. Optional. |
| `pluginRoot` | Locates `<plugin>/skills/wsjf/SKILL.md` for the maker's sizing brief. |
| `upstreamChange` | Optional text: why the composite's resume found this step's saved files stale. Used only as the human-readable reason. |

Files read (all under `<work>` unless stated):

- `story-<slug>.json`: the Story's saved document (title, description, acceptance criteria,
  `decisionIds`; a Task citing no `decisionIds` inherits the Story's).
- `spec-<slug>.md`, `spec-<slug>.data-model.md`, `spec-<slug>.criteria.md`.
- `recon-<slug>.json`: `items[]` (`id`, `status`, `element`, `from`, `to`, surface, evidence,
  `plannedBy`) and `uiAuthority.uiItems[]` (`item`, `designSource`, `bundle`, `buildSpec`,
  `sections`, `artifact {kind, slug}`).
- every `recon-*.json` (the Epic-wide detailed items: id -> status, `plannedBy`, slug).
- `delta-items.json` (`depscore.py arch-delta --save`): `items[]` with `id`, `requires`, `kind`
  (`prerequisite`), `state` (`planned`) and `plannedBy`.
- cds bundles named by `uiAuthority` (`bundle.json`: `kind`, `slug`, `createdAt`, `buildSpec`).
- `tasks-<slug>.json` and `tasks-<slug>.json.meta.json` when they exist (rerun decision).

Beads read:

- The Epic's child Story whose metadata `elab_key` is `story:<slug>`.
- That Story's child beads of type `task`: `id`, `title`, `description`, `status`, `priority`,
  blockers, and metadata `elab_key`, `requirement_ids`, `build_state`.
- Open Tasks of other Epics built in the same repository (`beadwrite.other_epic_tasks`: Task not
  closed, metadata `repoPath`, else its Story's `repoPath`, equals `repoPath`; Epic is not this
  Epic): `id`, `title`, description head, `status`, `epic`.

## 4. Outputs

Files:

| Path | Format and key fields | Written by |
|---|---|---|
| `<work>/tasks-<slug>.context.json` | `existingTasks` (`elabKey`, `title`, description head, `status`, `requirementIds`) and `otherEpicTasks` (`id`, `title`, description head, `status`, `epic`), read from beads right before the maker runs; replaces the maker's use of `story-<slug>.written.json`. | step 5 |
| `<work>/candidates/tasks-<slug>.json` | The maker's output file, schema below. Validated once by step 7; not a resume point. | step 6 (agent) |
| `<work>/tasks-<slug>.json` | Accepted decomposition: `tasks[]` (`key`, `title`, `description`, `type`, `acceptanceCriteria[]`, `definitionOfDone[]`, `specPaths[]`, `specSections[]`, `requirementIds[]`, `decisionIds[]`, `reuses` (string or null), `blockedByExternal[]`, `surfaces` (list or null)), `testStrategy` (`pyramid`, `coverageThreshold`, `envMatrix[]`, `source`) or null, `rationale`, `edges[]` (`from`, `to`: local keys), `scores[]` (`key`, `jobSize`, `sizeLow`, `sizeHigh`, `sizeConfidence`, `rationale`), `notes`. Canonical JSON. | step 7 |
| `<work>/tasks-<slug>.json.meta.json` | `artifactio.record`: `artifact`, `path` (relative to `<root>`), `epic_id`, `phase` (`tasks:<slug>`), `sha256`, `bytes`, `created_at`, `updated_at`, `inputs[]` (`path`, `kind` `file`, `sha256`). | step 8, again in step 11 |
| `<work>/candidates/tasks-<slug>.correction.json` | The corrective maker's output file: `tasks[]` (same item schema, keys `N1`, `N2`, ...), `edges[]` (only into a new Task), `scores[]` (one per new Task, and one per saved Task key the brief named as unsized). No `noWork[]`. Validated once by step 10. | step 10 (agent) |
| `<work>/tasks-<slug>.correction.json` (+ `.meta.json`) | The accepted corrective answer, recorded with `artifactio.record` (inputs: `tasks-<slug>.json` as it was before the merge, `recon-<slug>.json`). Kept as evidence of the pass; its content reaches beads only through the amended `tasks-<slug>.json`. | step 10 |
| `<work>/tasks-<slug>.json` (amended) | `add-tasks` appends the accepted new Tasks under fresh keys `T<n>` past the highest saved key, with their edges and scores, and replaces the score of each saved Task the brief named as unsized. Saved Tasks are otherwise not changed. | step 11 |

Bead writes (all through the beads writer in `beadwrite.py`; every write keyed by `elab_key`):

- **Delete** (step 4, case `replaced` only): `bd delete <ids...> --force` for the unstarted Task
  beads defined in section 8.
- **Create** (step 9): `bd create --silent --type task --title <title> --description <text>
  --parent <story id> [--acceptance <criteria joined by newline>] --notes "repoPath: <repo>"
  --metadata <json> [--deps blocked-by:<id>,...]`.
- **Update** of an open, unstarted matched bead (step 9): one `bd update <id> [--title --description]
  [--set-metadata k=v ...]` for only the fields that differ; `bd dep add --file -` with JSON lines
  `{"issue_id", "depends_on_id", "type": "blocks"}` for missing blockers; `bd dep remove <id> <b>`
  for each same-Story blocker it no longer depends on. Blockers outside the Story are never removed.
- **Description** = `Repository: <repo> — work only in this repository.` + the Task's description
  + a `## Spec contract` block: spec path(s) relative to `<root>`, spec sections, requirement ids,
  surfaces (`unknown (none declared)` for null), test strategy line, Definition of Done, and for a
  `web-ui` Task its design source, cds artifact, cds bundle and cds build specs.
- **Metadata keys** (`beadwrite.task_metadata`): `elab_key`, `repoPath`, `wsjf_size_estimate`,
  `wsjf_size_low`, `wsjf_size_high`, `wsjf_size_confidence` (a valid score: all positive numbers,
  low <= size <= high, confidence <= 100; every Task has one after step 11), `wsjf_content_hash` (judging
  fingerprint of title, description and priority, only with sizes), `decision_ids`,
  `spec_sections`, `acceptance_criteria`, `definition_of_done`, `requirement_ids`, `surfaces`
  (JSON list, or `unknown`), `test_strategy` (JSON, or `unknown`), `cds_design_source`,
  `cds_artifact`, `cds_bundle_path`, `cds_build_specs`, `spec_path`, `spec_paths`,
  `spec_paths_verified`. List values are compact JSON.
- **`elab_key`** (`beadwrite._assign_keys`, in build order): the `reuses` key when no earlier Task
  took it; else `task:<slug>:items:<cited work item ids, naturally sorted, slugged, joined by +>`;
  a Task citing no work item gets `task:<slug>:<title slug>`; duplicates get `-2`, `-3`.

Vault writes: none. Git commits: none (`<work>` is untracked run state).

Returned to the caller (the composite's contract; field names kept so `prd-to-spec` and its spec
can rely on them): `ok`; `rerun` `{case, reason, changedInputs[], deleted[], kept[]}`; `repoPath`;
`story` `{id, elabKey}`; `tasks[]` `{key, elabKey, id, action (created|updated|unchanged|unchanged-started), title, dependsOn[], outsideBlockers[]}`;
`edges` `{added, removed, standing}`; `summary` `{created, updated, unchanged}`; `coverage`
`{uncitedBefore, uncitedAfter, unsizedBefore, unsizedAfter, added, resized, dropped, trimmed}` when
a corrective pass ran;
`warnings[]` (every normalization `plan-tasks` and `write-task` made); on failure `stage`
(`input`, `decompose`, `task-write`, `uncited-items`, `task-record`), `reason`, `uncitedItems`, and
`failure` `{stage, cause, repositories: [{repository, stage, cause, headline}]}`. The composite
records the `rerun` facts as its `task-rerun` run-ledger event and marks step `tasks:<slug>`
complete (`artifactio.py step`); see `<orch>/specs/epic/prd-to-spec.md` and
`<orch>/specs/epic/driver-contract.md` for which ledger events the driver receives.

## 5. Steps

Every step except 6 and 10 is deterministic Python in the orchestrator, calling the existing
library functions directly (no `depscore.py` subprocess, no relay, no command-runner session).

1. **Check the input** (deterministic). `repoPath` is non-empty and the Story `story:<slug>` exists
   under the Epic in beads. Otherwise fail at stage `input`, cause `other`.
2. **Fingerprint the inputs** (deterministic; `beadwrite.tasks_inputs` logic). Hash every input in
   section 8's set and compare with `tasks-<slug>.json.meta.json`. Result: `saved`, `changedInputs`
   (`{path, why}`), `unverified`, `unchanged` (saved, at least one recorded input, every one checked
   and equal).
3. **Decide the rerun case** (deterministic). `unchanged` -> skip to step 9. Otherwise go to step 4.
4. **Delete the unstarted Tasks** (deterministic; `beadwrite.replace_tasks`). Read the Story's
   Task beads; delete the unstarted ones (section 8) in one `bd delete --force`; keep the rest as
   `kept` (`id`, `title`, `elabKey`, `status`, `requirementIds`). Case is `replaced` when anything
   was deleted or kept, else `new`. Reason: `upstreamChange`, then each changed input, then "no
   tasks-<slug>.json is saved".
5. **Write the maker's context** (deterministic). Read beads once and write
   `tasks-<slug>.context.json`: `existingTasks` is `kept` from step 4 (empty in case `new`);
   `otherEpicTasks` from `other_epic_tasks`. This replaces
   reading `story-<slug>.written.json`, which `spec-authoring` wrote when it wrote the Story and
   which is stale whenever that step was reused.
6. **Decompose, sequence and size** (agent `task-decomposer`; model `fable`, effort `medium`, as the
   agent definition and the current dispatch set them; right for one authoring pass over the spec
   set and the repository code). One session. Input paths: `specDocs` (with their cite-as refs),
   `recon-<slug>.json`, `story-<slug>.json`, `tasks-<slug>.context.json`,
   `<plugin>/skills/wsjf/SKILL.md`, the repository `repoPath`. Brief (facts and expected outcome
   only): the three jobs (decompose into build Tasks with their contract fields and `testStrategy`;
   name the DAG edges; size each Task with `jobSize`, `sizeLow`, `sizeHigh`, `sizeConfidence`,
   one-line rationale); only work items make Tasks, each Task cites at least one, and every work
   item is cited; a `done` item gets a Task like any other, whose contract names the code on
   `main` the detailing cites as already meeting it, so its Red step tests that code and the
   build pipeline decides whether anything changes; a prerequisite item (a VPC, a security group,
   a Lambda layer, any element the delta's work rests on) gets a Task that builds it; work an
   `otherEpicTasks` Task or a `planned-elsewhere` bead already plans goes into `blockedByExternal`
   instead of a Task; `reuses` names the `elabKey` of the existing Task it is; in case `replaced`,
   the kept Tasks are existing work never to be duplicated; `surfaces` is a list or null; one
   artifact per `web-ui` Task; at least one Task. Output: the maker writes
   `<work>/candidates/tasks-<slug>.json` (the
   decomposition schema is named in the brief by path). No submission helper, no revision
   binding, no progress file. No parallelism: one maker per Story; the composite runs the Stories
   of an Epic in parallel. The session runs inside the session runner's section 2 guard
   (`driver-contract.md` §8).
7. **Accept the candidate** (deterministic, Python, once). Strict JSON (no duplicate keys) and
   schema-valid; write canonical `tasks-<slug>.json`. On rejection: one new maker session with the
   exact validation errors (CONTEXT 7.4, clarified instructions); a second rejection fails at stage
   `decompose`, cause `other`.
8. **Record the inputs** (deterministic; `artifactio.record` as a Python call, phase
   `tasks:<slug>`, inputs = section 8's set). A failure fails the run at stage `task-record`, cause
   `other`: without the record the next run cannot prove "unchanged" and would delete and
   re-decompose.
9. **Plan and write the Task beads** (deterministic; `beadwrite.plan_story_tasks` then
   `beadwrite.write_task` per Task in build order). Planning reads `story-<slug>.json`,
   `tasks-<slug>.json`, `recon-*.json`, `delta-items.json` and the bundles, runs no `bd`, and:
   makes repeated keys unique (`K`, `K-2`, ...; an edge on `K` applies to each copy; the n-th score
   on `K` to the n-th copy); drops edges that do not join two known Tasks; drops each edge that
   closes a cycle; derives in-repository `requires` edges and `planned-elsewhere` blockers
   (`hierarchy.derive_prerequisites`); settles each `web-ui` Task on one design source and one
   artifact (`hierarchy.check_cds_contract`); assigns `elab_key`s; computes `uncited` (work items no
   Task cites, plus every required work item `derive_prerequisites` reports without a Task, which
   today it only warns about) and `unsized` (Task keys with no valid score, which today
   `task_metadata` only skips), and their briefs. Planning stops before any write when `uncited`
   or `unsized` is non-empty and no corrective pass has run yet: step 10 runs first, so no Task is
   written without its size. Writing reads the Story's Task beads once, matches every Task
   (`_match_tasks`: `elab_key`, then most delta items in common, then title; a bead matches one
   Task at most; only beads whose `elab_key` starts `task:<slug>:` and that are not closed are
   candidates for the second and third rules), then per Task in build order: create, update an
   open unstarted bead where it differs, or leave a started/closed bead untouched
   (`unchanged-started`). Because Tasks are written in build order, every same-Story blocker is
   written before its dependent, so its edge is written with it. An external blocker that is a
   Task of this Story becomes a Story edge. A Task whose write fails fails the Story at stage
   `task-write` with the write's cause (the remaining Tasks are not written), so a successful run
   never leaves a Task without one of its edges; the rerun writes only what is missing.
10. **One corrective pass** (agent `task-decomposer`, model `fable`, effort `medium`), only when
    step 9's plan has uncited work items, unsized Tasks, or no Task at all. Input paths:
    `tasks-<slug>.json` (read-only), `recon-<slug>.json`, `specDocs`, `story-<slug>.json`, the
    repository, `<plugin>/skills/wsjf/SKILL.md`; the brief lists the uncited items exactly (`id`,
    `status`, `element`, `to`) and the unsized Task keys with what each score lacks. Output: the
    maker writes `<work>/candidates/tasks-<slug>.correction.json`; Python validates it once
    (strict JSON, schema), writes the accepted `tasks-<slug>.correction.json` and records it
    (section 4).
11. **Merge the corrective answer** (deterministic; `beadwrite.add_corrective_tasks`, changed so
    it no longer edits the detailing and no longer takes `noWork` answers). Take a new Task only
    when every work item it cites is uncited; give it a fresh `T<n>` key; when two new Tasks cite
    the same item the first keeps it, it is removed from the later ones' citations (`trimmed`), and
    a later Task left citing none of them is dropped (`dropped`); take edges only into a new Task;
    take a score for a new Task or for a saved Task key the brief named as unsized (`resized`), and
    only when it is valid; everything else is `rejected` with why. `recon-<slug>.json` and every
    other step's `.meta.json` are left untouched. Record the inputs again (step 8) and run step 9
    again. Items still uncited, Tasks still unsized, or a Story still without a Task fail the
    Story at stage `uncited-items` (or `decompose` for no Task), naming them, the answer file and
    the rejected answers. No further pass runs.
12. **Not in this flow: edges between Stories.** After every Story of the Epic is decomposed, the
    composite runs `depscore.py closure-edges` (`beadwrite.closure_task_edges`): for every saved
    Task building item X and every item Y that X requires and that ANOTHER repository's detailing
    marks as work, an edge from each Task of that Story building Y (ends named `S<i>-<key>`, `i` the
    repository's position in the span), and a warning for a required item no Task builds, that no
    repository details and the span ruling does not record as having no code, which fails the
    composite's step 11. It runs no `bd`. Its edges are written with the cross-Story edges by
    `write-all-task-edges`. Spec: `<orch>/specs/epic/prd-to-spec.md` steps 11 to 13.

Agents: `task-decomposer` is kept (steps 6 and 10). No other agent is dispatched. The
`workflow-command-runner` sessions the JS used for `tasks-inputs`, `replace-tasks`, the revision
fingerprint, candidate acceptance (probe and accept), `record`, `plan-tasks`, each `write-task`,
`add-tasks` and the correction's revision and acceptance are all replaced by the direct steps above.

## 6. Checks

**Kept**

- Candidate acceptance (strict JSON, schema), once, in Python: the planner normalizes instead of
  refusing, so a malformed shape (an edge list of strings, a duplicate JSON key) would silently
  drop dependencies or contract fields on the beads, and nothing after it looks at the raw shape.
- A required work item with no Task (`derive_prerequisites`) joins the uncited list: without it a
  `blocks` dependency with no builder reaches beads, and nothing later catches it (S01h finding
  24).
- Section 2 hard limit: the session runner's guard around both maker sessions
  (`driver-contract.md` §8); the `task-decomposer` holds Write.
- Unique keys, edges only between known Tasks, cycle edges dropped: without them build order is
  undefined and a cyclic `blocks` set in beads deadlocks the build lane; nothing later repairs it.
- Matching by `elab_key`, then cited items, then title, and never creating when a bead matches:
  without it a rerun writes duplicate Tasks to beads and both get built.
- A started or closed Task bead is never rewritten: without it work under build changes beneath
  the builder. Owner rule (CONTEXT 7.5: started and closed Tasks are kept).
- Deletion limited to unstarted, elaboration-written Tasks of this Story: hard limit (destructive
  operation; CONTEXT 6 sanctions exactly this deletion).
- The Story must exist before a Task is written, and `repoPath` must be non-empty: without them a
  Task lands in beads with no parent or no repository; checked once at step 1.
- Coverage (`uncited`) with one corrective pass, then failure at `uncited-items`: CONTEXT 7.6; a
  work item with no Task otherwise never gets built and `elaboration-finish` would see only that
  Tasks exist.
- Sizes (`unsized`) in the same corrective pass, then failure: CONTEXT 7.6 requires every Task's
  WSJF; a Task with no valid size stays unscored and is never selected for build (CONTEXT 7.8),
  and nothing in the Epic pipeline or the driver sizes it later.
- At least one Task per Story: CONTEXT 7.6 (no "nothing to build" outcome).
- A failed Task write fails the Story (step 9): without it the Epic could finish with a Task
  missing or missing an edge, and nothing later writes it.
- Recording the inputs (step 8) as a failing step: without the record, the next run treats the
  Story as changed and deletes its unstarted Tasks.
- Normalizations kept as recorded `warnings`, not gates: a Task citing no work item; two artifacts
  in one `web-ui` Task (first kept, others named in its description); several bundles (newest
  kept); an unknown design source (taken as `cds`).

**Dropped**

- The `writable` guard on artifact and beads descriptors: the Python call takes typed arguments.
- `dispatchInterruption`, `dispatchFailureCause` and `settleAgent` bookkeeping: they classify by
  matching error text, which CONTEXT 7.4 forbids; the session runner returns a structured cause.
- The relay: numbered relay files, `relayrun.py`, checksum-guarded commands and the receipt checks
  on relayed results; every call is direct.
- The candidate protocol of the sandbox: `artifactcontract.py submit`, the input-revision binding,
  `.progress.json` checkpoints, the "probe" and "recover" dance, the "revision binds the paths
  alone" fallback and the `.prev` copy. They exist because the sandbox cannot read files; Python
  reads the maker's output file and validates it once.
- `add-tasks` editing `recon-<slug>.json` and re-binding its sha256 in every `*.meta.json` under
  `<work>`: it rewrote another step's input records so their staleness checks could not see the
  change.
- The `noWork` answer (an uncited item recorded as needing no work, with a `file:line` reason): a
  "nothing to build" record per item, which CONTEXT 7.6 removes; such an item gets a Task.
- "A Story with nothing to build gets no Tasks and goes straight to deploy and verify" (the
  workflow's `meta.description`): CONTEXT 7.6.
- The `replay` argument: the fingerprint decision (step 2) covers it; a composite resume that
  finds `tasks:<slug>` fresh and this flow's `unchanged` case are the same fact.
- Rebuilding a Task list from the plan or the accepted file when no `write-task` result was relayed:
  Python has the real results.
- Logging the initial record failure and carrying on (`persistErrors`): replaced by the failing
  step 8.

## 7. Failure causes

| Failure point | Stage | Cause | Retry reasonable? |
|---|---|---|---|
| No `repoPath`, or no Story `story:<slug>` in beads | `input` | `other` | No: an upstream fault; the composite reports it. |
| `bd` lock held by another writer (beads read, delete, create, update, dep) | `decompose` (step 4), `task-write` (step 9) | `contention` (today `GraphError.cause`, chosen from `bd`'s standard error, which CONTEXT 7.4 does not accept as structured; the structured fact is an open item in QUESTIONS.md) | Yes: backoff from about 30 s, doubling, capped at 30 minutes (CONTEXT 7.4). Each attempt re-reads beads, so an applied write is updated, never created twice. |
| Beads server or connection failure | same | `bd-timeout` | Yes, same backoff. |
| Any other `bd` error | same | `other` | No. |
| Maker session: API error | `decompose` | `api` | Yes, through the owner's breaker (`breaker.py`). |
| Maker session: quota | `decompose` | `quota` | Yes, through the breaker. |
| Maker returned no candidate, or a candidate rejected twice | `decompose` | `other` | One retry with the validation errors (step 7); then no. |
| No Task after the corrective pass | `decompose` | `other` | No: incident-responder. |
| A Task write fails (step 9) | `task-write` | the write's cause | `bd-timeout`/`contention`: yes, with backoff; otherwise no. |
| Reading or writing a file in `<work>` (`OSError`, unreadable JSON) | `decompose`, `task-record` | `other` | No. |
| Corrective session: API / quota / no answer | `uncited-items` | `api` / `quota` / `other` | API and quota through the breaker; otherwise no. |
| Items still uncited, or Tasks still unsized, after the corrective pass | `uncited-items` | `other` | No: the incident-responder diagnoses it. |

The cause is always taken from the structured fact at the failure point (exit status, exception
type, the session runner's result; for `bd`, the fact S02 settles, QUESTIONS.md), never from
message text. `relay` has no
producer in this flow. When several Task writes fail, the result's cause is the first one's when
every cause is retryable (`contention`, `bd-timeout`, `api`, `quota`), else `other`.

## 8. Resume points

**Inputs whose fingerprints decide "unchanged"** (recorded in `tasks-<slug>.json.meta.json`, each
as `{path, kind: "file", sha256}`):

1. `<work>/spec-<slug>.md`
2. `<work>/spec-<slug>.data-model.md`
3. `<work>/spec-<slug>.criteria.md`
4. `<work>/story-<slug>.json`
5. `<work>/recon-<slug>.json` (the detailing; CONTEXT 7.5 names it, and the maker reads it)

The correction file is not an input: its accepted content is already merged into
`tasks-<slug>.json` (step 11). This list is the single source; `prd-to-spec.md` refers here. The PRD, the architecture and the
TRD are covered through these: the spec step reruns when its recorded inputs (`trd.md`,
`repo-scoping.json`, `recon-<slug>.json`, the PRD) change, which rewrites the spec files. "Unchanged" is true only when `tasks-<slug>.json` exists,
its record names at least one input, and every recorded input exists and hashes as recorded. An
input recorded without a hash, or not of kind `file`, makes the decision "changed" (never "can't
tell").

**How an unstarted Task is identified from bead fields** (`beadwrite.replace_tasks`): a child bead
of the Story whose metadata `elab_key` is `story:<slug>`, of type `task`, with

- metadata `elab_key` starting with `task:` (elaboration wrote it), and
- `status` in `{open, blocked, deferred}`, and
- no (empty) metadata `build_state`.

Every other Task under the Story is kept: any other status (`in_progress`, which the build lane's
claim sets; `closed`), a non-empty `build_state` (`red`, `green`, `deployed-unverified`, written by
the build lane on a failed build), or an `elab_key` not starting `task:` (not written by
elaboration). The edge cases are open items in QUESTIONS.md.

| Saved result | Fingerprinted by | A rerun after it redoes |
|---|---|---|
| `tasks-<slug>.json` + its `.meta.json` | section 8 inputs | Nothing upstream; case `unchanged`: plan and write only the missing or differing Task beads; no session. |
| Deletion of unstarted Tasks (step 4) | not saved (beads are the record) | If the run stops before step 8, the next run still sees "changed", deletes any unstarted Tasks again (none, or ones this run created), recomputes `kept`, and decomposes. |
| Task beads (step 9) | `elab_key` on each bead | Only beads missing or differing are written; started and closed ones are untouched. |
| `tasks-<slug>.correction.json` accepted + its `.meta.json` | `tasks-<slug>.json` as it was before the merge, `recon-<slug>.json` | The merge (idempotent: answers for items already cited or Tasks already sized are rejected) and the bead writes; no session. |
| `uncited-items` failure with unchanged inputs | the same accepted correction | Reproduces the failure without starting a session (CONTEXT 7.4: no retry with nothing changed). |

An interrupted maker session leaves at most a candidate file with no accepted result; the rerun
starts that session again (no partial candidate is trusted).

Restart cost: a rerun with unchanged inputs starts no agent session and makes one beads read plus
writes only for what is missing or differs.

## 9. Requirements that apply

- **7.5 Rerunning Task creation for a Story:** steps 2 to 4 and section 8. Unchanged inputs keep
  every Task and write only the missing ones; a changed input deletes the unstarted Tasks and
  recreates the set; started and closed Tasks are kept and named to the maker; the fingerprints
  decide, with no third case.
- **7.6 Done:** this flow delivers the per-Story half: at least one Task per Story; every work
  item, `done` items included, cited by a Task; every Task sized and written with its same-Story
  edges; one corrective pass naming the exact uncited items and unsized Tasks. There is no
  "nothing to build" result and no `noWork` record. The Epic-level rule, the edges between
  Stories and the WSJF arithmetic are the composite's (`prd-to-spec.md` steps 11 to 14), and run
  after the Tasks this flow writes exist.
- **7.4 Retries:** contention and `bd-timeout` with backoff; API and quota through the breaker; one
  retry of a rejected candidate with the validation errors; nothing reruns with nothing changed;
  causes are structured.
- **7.8 Selection filters:** every Task gets a valid size here, so the composite can compute its
  WSJF and the build lane can consider it.
- **7.10 Repositories:** the Story's single repository only; this flow creates and places no
  repository.
- **7.11 Deterministic over agentic:** only decomposition and the corrective answer are agent
  work; planning, writing, coverage, matching and the rerun decision are code.
- **7.14 Briefs:** the maker gets file paths and the expected outcome, never pasted data or
  theories.
- **7.16 Hierarchy:** every Task is written under its Story, which is under the Epic; this flow is
  the only creator of Tasks.
- **7.19 Existing code:** a `done` item gets a Task whose contract names the existing code; the
  build pipeline's Red step tests it and decides whether anything changes.
- **7.20 Missing prerequisites:** a prerequisite item gets a Task that builds it.
- **Hard limits (CONTEXT 6):** the only destructive operation is the sanctioned deletion of a
  Story's unstarted Tasks; no vault writes; nothing in `apps/marketing/`.
- **7.9:** no owner question arises in this flow.

## 10. Open items

See QUESTIONS.md
