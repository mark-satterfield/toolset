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
- "work item": a build item `repo-scoping` placed in the Story's repository: the `itemIds` of
  every `placements[]` entry of `<work>/repo-scoping.json` whose `repoPath` is `repoPath`, joined
  to `<work>/delta-items.json` for `element`, `views`, `requires` and, for a prerequisite, `kind`.
  Every placed item is a work item and carries no status: elaboration does not judge whether code
  for it exists or already meets anything (CONTEXT 7.23); the Task says what to build and how, and
  the build pipeline's tests decide whether any code changes (CONTEXT 7.6, 7.19). How today's
  `hierarchy` and `beadwrite` planning, which reads the removed detailing file, comes to read the
  placed items is QUESTIONS.md item 32d.

## 1. Purpose

Decompose ONE repository's Spec into Tasks, and only Tasks, under the Story that Spec pairs with, in
that Story's single repository. A Task is an activity, the "how": it says what to build in this
repository and how to build it (for example "in repository xyz, for service abx, write Lambda abc
that does lm"); the requirements, the "what", stay in the PRD and the TRD, and the spec documents
carry their technical detail, which the Task cites (CONTEXT 7.24). A Task is build work (code,
infrastructure or documentation); the Task's Red step writes tests from the PRD, the TRD, the
Story, the spec documents and the Task, so no Task only writes tests. Every work item gets a Task
in this Epic (CONTEXT 7.23, 7.25); where an open Task of another Epic in the same repository (an
`otherEpicTasks` entry) overlaps, the Task also gets a `blocks` edge onto it (`blockedByExternal`),
so the overlapping work is built in order. The edge is added to the Task; it never replaces it. A
missing prerequisite the
architecture's Closure found (for example a VPC, a security group or a Lambda layer) is a work
item like any other and gets a Task (CONTEXT 7.20). A `web-ui` Task carries in its build contract
the design source of the ui items it cites (`bundle`, `cds` or `none`, from
`spec-<slug>.ui.json`) and, for `bundle`/`cds`, its artifact (kind and slug). One maker session
decomposes, sequences and sizes;
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
   dropped); and onto each open Task of another Epic named in `blockedByExternal`. The edges are
   written with the Task, in build order, so every blocker exists when its dependent is written.
7. Every work item is cited in `requirementIds` by at least one Task (no input file is edited by
   this flow). No item is recorded as needing no work: the `noWork` answer of today's corrective
   pass is a "nothing to build" record and is dropped (CONTEXT 7.6). Every required work item that `hierarchy.derive_prerequisites` finds
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
| `specPaths` | the three absolute paths `spec-authoring` returns as `specPaths`: `<work>/spec-<slug>.md`, `<work>/spec-<slug>.data-model.md`, `<work>/spec-<slug>.criteria.md`. This flow computes `specDocs` = `[{path, ref}]` from them in step 1, `ref` being the path relative to `<root>` that Tasks cite. There are no other spec artifact paths. |
| `scopingPath` | `<work>/repo-scoping.json` (the placed items). |
| `itemsPath` | `<work>/delta-items.json` (the build items' elements, views and `requires`). |
| `uiPath` | `<work>/spec-<slug>.ui.json` from `spec-authoring`, or null when the repository holds no UI. |
| `packagesDir` | `$ATW_DESIGN_PACKAGES_DIR`: the directory every cited cds bundle must sit in. Optional. |
| `pluginRoot` | Locates `<plugin>/skills/wsjf/SKILL.md` for the maker's sizing brief. |
| `upstreamChange` | Optional text: why the composite's resume found this step's saved files stale. Used only as the human-readable reason. |

Files read (all under `<work>` unless stated):

- `story-<slug>.json`: the Story's saved document (title, description, acceptance criteria,
  `decisionIds`; a Task citing no `decisionIds` inherits the Story's).
- `spec-<slug>.md`, `spec-<slug>.data-model.md`, `spec-<slug>.criteria.md`.
- `repo-scoping.json`: `placements[]` (`repoPath`, `itemIds`) for every repository of the span
  (the Epic-wide map from item id to repository), and `noCode[]`.
- `delta-items.json` (`depscore.py arch-delta --save`): `items[]` with `id`, `element`, `views`,
  `requires` and `kind` (`prerequisite`).
- `spec-<slug>.ui.json` when it exists: `uiItems[]` (`item`, `designSource`, `bundle`,
  `buildSpec`, `sections`, `artifact {kind, slug}`).
- cds bundles named by `spec-<slug>.ui.json` (`bundle.json`: `kind`, `slug`, `createdAt`,
  `buildSpec`).
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
| `<work>/tasks-<slug>.items.json` | The Story's work items: `items[]` (`id`, `element`, `views`, `requires`, `kind`), from `repo-scoping.json` and `delta-items.json`. | step 5 |
| `<work>/candidates/tasks-<slug>.json` | The maker's output file, schema below. Validated once by step 7; not a resume point. | step 6 (agent) |
| `<work>/tasks-<slug>.json` | Accepted decomposition: `tasks[]` (`key`, `title`, `description` (the activity), `type`, `acceptanceCriteria[]` and `definitionOfDone[]` (references to criterion and DoD ids in `spec-<slug>.criteria.md`, not requirement text; CONTEXT 7.24), `specPaths[]`, `specSections[]`, `requirementIds[]`, `decisionIds[]`, `reuses` (string or null), `blockedByExternal[]`, `surfaces` (list or null)), `testStrategy` (`pyramid`, `coverageThreshold`, `envMatrix[]`, `source`) or null, `rationale`, `edges[]` (`from`, `to`: local keys), `scores[]` (`key`, `jobSize`, `sizeLow`, `sizeHigh`, `sizeConfidence`, `rationale`), `notes`. Canonical JSON. | step 7 |
| `<work>/tasks-<slug>.json.meta.json` | `artifactio.record`: `artifact`, `path` (relative to `<root>`), `epic_id`, `phase` (`tasks:<slug>`), `sha256`, `bytes`, `created_at`, `updated_at`, `inputs[]` (`path`, `kind` `file`, `sha256`). | step 8, again in step 11 |
| `<work>/candidates/tasks-<slug>.correction.json` | The corrective maker's output file: `tasks[]` (same item schema, keys `N1`, `N2`, ...), `edges[]` (only into a new Task), `scores[]` (one per new Task, and one per saved Task key the brief named as unsized). No `noWork[]`. Validated once by step 10. | step 10 (agent) |
| `<work>/tasks-<slug>.correction.json` (+ `.meta.json`) | The accepted corrective answer, recorded with `artifactio.record` (inputs: `tasks-<slug>.json` as it was before the merge, `repo-scoping.json`, `delta-items.json`). Kept as evidence of the pass; its content reaches beads only through the amended `tasks-<slug>.json`. | step 10 |
| `<work>/tasks-<slug>.json` (amended) | `add-tasks` appends the accepted new Tasks under fresh keys `T<n>` past the highest saved key, with their edges and scores, and replaces the score of each saved Task the brief named as unsized. Saved Tasks are otherwise not changed. | step 11 |

Bead writes (all through the beads writer in `beadwrite.py`; every write keyed by `elab_key`):

- **Delete** (step 4, case `replaced` only): `bd delete <ids...> --force` for the unstarted Task
  beads defined in section 8.
- **Create** (step 9): `bd create --silent --type task --title <title> --description <text>
  --parent <story id> [--acceptance <criterion ids joined by newline>] --notes "repoPath: <repo>"
  --metadata <json> [--deps blocked-by:<id>,...]`.
- **Update** of an open, unstarted matched bead (step 9): one `bd update <id> [--title --description]
  [--set-metadata k=v ...]` for only the fields that differ; `bd dep add --file -` with JSON lines
  `{"issue_id", "depends_on_id", "type": "blocks"}` for missing blockers; `bd dep remove <id> <b>`
  for each same-Story blocker it no longer depends on. Blockers outside the Story are never removed.
- **Description** = `Repository: <repo> — work only in this repository.` + the Task's description
  (the activity: what to build and how)
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
   under the Epic in beads. Otherwise fail at stage `input`, cause `other`. Compute `specDocs`
   (`[{path, ref}]`) from `specPaths`.
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
   which is stale whenever that step was reused. Also write the work items to
   `tasks-<slug>.items.json` (from `repo-scoping.json` and `delta-items.json`), so the maker reads
   one short file by path.
6. **Decompose, sequence and size** (agent `task-decomposer`; model `fable`, effort `medium`, as the
   agent definition and the current dispatch set them; right for one authoring pass over the spec
   set). One session. Input paths: `specDocs` (with their cite-as refs), the work items (written
   by Python to `<work>/tasks-<slug>.items.json`: `id`, `element`, `views`, `requires`, `kind`),
   `spec-<slug>.ui.json` when it exists, `story-<slug>.json`, `tasks-<slug>.context.json`,
   `<plugin>/skills/wsjf/SKILL.md`, the repository `repoPath` (where the Tasks' work goes). Brief
   (facts and expected outcome
   only): the three jobs (decompose into build Tasks with their contract fields and `testStrategy`;
   name the DAG edges; size each Task with `jobSize`, `sizeLow`, `sizeHigh`, `sizeConfidence`,
   one-line rationale); only work items make Tasks, each Task cites at least one, and every work
   item is cited; each Task is an activity that says what to build in this repository and how,
   and cites the spec sections and views that hold the requirements it serves, without restating
   them as its own requirements (CONTEXT 7.24); do not judge whether code for an item already
   exists or meets anything: every work item gets its Task, and the build pipeline's tests decide
   what already works (CONTEXT 7.19, 7.23); a prerequisite item (a VPC, a security group, a Lambda
   layer, any element the delta's work rests on) gets a Task that builds it; where an
   `otherEpicTasks` Task overlaps a Task, name it in that Task's `blockedByExternal` (an edge in
   addition to the Task, never instead of it); a Task's `acceptanceCriteria` and
   `definitionOfDone` are references to criterion and DoD ids in `spec-<slug>.criteria.md`, never
   new requirement text; `reuses`
   names the `elabKey` of the existing Task it is; in case `replaced`,
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
   `tasks-<slug>.json`, `repo-scoping.json`, `delta-items.json`, `spec-<slug>.ui.json` and the
   bundles, runs no `bd`, and:
   makes repeated keys unique (`K`, `K-2`, ...; an edge on `K` applies to each copy; the n-th score
   on `K` to the n-th copy); drops edges that do not join two known Tasks; drops each edge that
   closes a cycle; derives in-repository `requires` edges
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
    `tasks-<slug>.json` (read-only), `tasks-<slug>.items.json`, `specDocs`, `story-<slug>.json`,
    the repository, `<plugin>/skills/wsjf/SKILL.md`; the brief lists the uncited items exactly
    (`id`, `element`, `views`) and the unsized Task keys with what each score lacks. Output: the
    maker writes `<work>/candidates/tasks-<slug>.correction.json`; Python validates it once
    (strict JSON, schema), writes the accepted `tasks-<slug>.correction.json` and records it
    (section 4).
11. **Merge the corrective answer** (deterministic; `beadwrite.add_corrective_tasks`, changed so
    it edits no other step's file and no longer takes `noWork` answers). Take a new Task only
    when every work item it cites is uncited; give it a fresh `T<n>` key; when two new Tasks cite
    the same item the first keeps it, it is removed from the later ones' citations (`trimmed`), and
    a later Task left citing none of them is dropped (`dropped`); take edges only into a new Task;
    take a score for a new Task or for a saved Task key the brief named as unsized (`resized`), and
    only when it is valid; everything else is `rejected` with why. Every other step's file and
    `.meta.json` are left untouched. Record the inputs again (step 8) and run step 9
    again. Items still uncited, Tasks still unsized, or a Story still without a Task fail the
    Story at stage `uncited-items` (or `decompose` for no Task), naming them, the answer file and
    the rejected answers. No further pass runs.
12. **Not in this flow: edges between Stories.** After every Story of the Epic is decomposed, the
    composite runs `depscore.py closure-edges` (`beadwrite.closure_task_edges`): for every saved
    Task building item X and every item Y that X requires and that `repo-scoping.json` places in
    ANOTHER repository, an edge from each Task of that Story building Y (ends named `S<i>-<key>`,
    `i` the repository's position in the span), no edge and no warning for a required element the
    Closure lists in `satisfied[]` (built per the element status matrix), and a warning for a
    required item that no Task builds, that the span ruling does not record as having no code and
    that the Closure does not list as satisfied, which fails the
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
- `add-tasks` editing the detailing file (`recon-<slug>.json`) and re-binding its sha256 in every
  `*.meta.json` under `<work>`: it rewrote another step's input records so their staleness checks
  could not see the change. The detailing step itself is removed (CONTEXT 7.10).
- Work-item statuses (add, modify, remove, "done") and the `planned-elsewhere` blocker onto
  another Epic's bead: they came from the removed detailing step (`prd-reconciliation`), which
  judged existing code; elaboration does not (CONTEXT 7.23). Every placed item is a work item and
  gets a Task in this Epic; an overlapping open Task of another Epic in the same repository adds a
  `blocks` edge (`blockedByExternal`) to that Task and never replaces it.
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
5. `<work>/repo-scoping.json` (the placed items; the maker reads them)
6. `<work>/delta-items.json` (the items' elements, views and `requires`)
7. `<work>/spec-<slug>.ui.json`, when the repository holds UI (the design sources the Tasks carry)

The correction file and `tasks-<slug>.items.json` are not inputs: the first's accepted content is
already merged into `tasks-<slug>.json` (step 11), and the second is derived from inputs 5 and 6.
This list is the single source; `prd-to-spec.md` refers here. The PRD, the architecture and the
TRD are covered through these: the spec step reruns when its recorded inputs (`trd.md`,
`repo-scoping.json`, `delta-items.json`, the PRD) change, which rewrites the spec files. "Unchanged" is true only when `tasks-<slug>.json` exists,
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
| `tasks-<slug>.correction.json` accepted + its `.meta.json` | `tasks-<slug>.json` as it was before the merge, `repo-scoping.json`, `delta-items.json` | The merge (idempotent: answers for items already cited or Tasks already sized are rejected) and the bead writes; no session. |
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
  item (every placed item) cited by a Task; every Task sized and written with its same-Story
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
- **7.19, 7.23 Existing code:** this flow does not judge existing code; every placed item gets a
  Task, and the build pipeline's Red step and TDD loop decide whether anything changes.
- **7.24 Tasks are activities:** each Task says what to build in its repository and how, and cites
  the spec sections and views holding the requirements; the requirements stay in the PRD and TRD.
- **7.20 Missing prerequisites:** a prerequisite item gets a Task that builds it.
- **Hard limits (CONTEXT 6):** the only destructive operation is the sanctioned deletion of a
  Story's unstarted Tasks; no vault writes; nothing in `apps/marketing/`.
- **7.9:** no owner question arises in this flow.

## 10. Open items

See QUESTIONS.md
