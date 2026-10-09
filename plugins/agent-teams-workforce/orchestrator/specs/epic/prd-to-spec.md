# Net-effect spec: `prd-to-spec` (the Epic pipeline's top level)

Sources, in order of authority: the `meta.description` of `<plugin>/workflows/prd-to-spec.js`;
the agent definition `<plugin>/agents/task-dependency-mapper.md` (the one agent this composite
dispatches itself); CONTEXT section 7; then, for contracts only, the code of `prd-to-spec.js`,
`<plugin>/scripts/portfolio/depscore.py` and `elaboration.py`, `<driver>/workitems.py`,
`<driver>/artifactio.py` and `<driver>/dispatch.py`. `<driver>` is
`$ATW_CONTROL_REPO/ops/sdlc-automation`.

This spec covers the composite's own steps and the contract at each phase boundary. Each phase it
calls has its own spec; this one does not restate them:

| Phase | Spec |
|---|---|
| Architecture | `<orch>/specs/epic/architecture.md` |
| Repo scoping | `<orch>/specs/epic/repo-scoping.md` |
| TRD authoring | `<orch>/specs/epic/trd-authoring.md` |
| Detailing (PRD reconciliation) | `<orch>/specs/epic/prd-reconciliation.md` |
| Spec authoring and the Story bead | `<orch>/specs/epic/spec-authoring.md` |
| Task decomposition, Task beads, the corrective pass, the rerun rule | `<orch>/specs/epic/task-decomposition.md` |
| WSJF scoring and dependency assessment (not called by this flow; see step 13) | `<orch>/specs/epic/wsjf-scoring.md`, `<orch>/specs/epic/dependency-assessment.md` |
| What the driver sends and reads back | `<orch>/specs/epic/driver-contract.md` |

`prd-validation` and `gate-enforce` are not called by `prd-to-spec`.

## 1. Purpose

Elaborate one existing, scored Epic and its PRD into Stories and Tasks written to beads. The flow
claims the Epic (`depscore.py elaboration-start`), runs the architecture phase for every PRD (never
skipped: a PRD the effective architecture already serves gets a "no change" result that says so),
holds the Epic for the owner only on business requirements no design can satisfy together or on
contradictory section 2 constraints, lists the build items from the approved target and delta,
rules the repository span from where the polyrepo-steward places those items, authors the TRD,
and per span repository details the items against `main`, authors one Spec and one Story, and
decomposes the Story into Tasks for its `add`/`modify`/`remove` items. It then derives the Task
edges between Stories, scores the Epic and its Tasks, and marks the Epic `elaboration_state=done`
(`depscore.py elaboration-finish --done`) once every span repository has its result, after which it
deletes the Epic's `target/<subject>/` (`depscore.py arch-target-remove`). A failed run returns
`ok:false` with `failure: { stage, cause, repositories[] }`; a transient cause releases the Epic for
a later rerun of only the failed steps, any other cause holds it for the incident-responder.

## 2. Produces and decides

After a successful run (`ok: true`, stage `finish`):
- The Epic bead carries `elaboration_state=done`, `elaboration_state_cause=decomposed-into-tasks`,
  `elaboration_state_at=<now>`, `elaboration_state_owner=""`. The Epic stays open (CONTEXT 7.6).
- The approved target for the Epic is integrated into the effective arc42 views (architecture
  phase), and `target/<subject>/` under `$ATW_ARCH_PATH` is deleted and the deletion committed in
  the vault repository.
- `delta-items.json` lists every build item (one per element the delta shows, then one
  `prerequisite` item per element the Closure found absent, stale or planned by an open bead, each
  with `requires`).
- The repository span is the distinct repositories the polyrepo-steward placed items in; no item is
  placed in the control repository or the repository holding the architecture.
- `trd.md` exists for the PRD.
- For every span repository: `recon-<slug>.json`, the spec documents, `story-<slug>.json`, one
  Story bead (keyed by `elab_key`), `tasks-<slug>.json`, and Task beads covering every `add`,
  `modify` and `remove` item of that repository, or a recorded "nothing to build".
- Task `blocks` edges between Stories are written: those the delta's `requires` relations make
  (`closure-edges`) and those the task-dependency-mapper derived (`task-deps.json`), with every
  edge that closes a cycle dropped.
- Story-to-Story `blocks` edges are rewritten from the Task edges (`story-edges`, run inside
  `elaboration-finish`).
- The Epic and every Task beneath it are rescored (WSJF arithmetic, Epic size rolled up from its
  Tasks).

Decisions the flow makes:
- **Refuse or claim** the Epic (`elaboration-start`).
- **Hold for the owner** (architecture `owner-concern`, or no architecture path configured).
- **Nothing to build**: the validated architecture assessment needs no implementation work and has
  no prerequisite, or the span names no repository. Then repo scoping, detailing, specs and Tasks
  produce nothing, and the Epic is still marked done.
- **Done or not done** (CONTEXT 7.6): done only when every span repository has its result.
- **Release or hold** a failed run's Epic, from `failure.cause`.

## 3. Inputs

From the driver (`<driver>/workitems.py` `elaboration_args`, `dispatch_context`,
`with_artifact_plan`; the full list is in `driver-contract.md`):
- `prd`: `{ id, title, path }`; `id` is the PRD file stem; `path` is the PRD file under
  `$ATW_PRD_DIR`. The JavaScript also accepts inline `body`/`content`; the driver never sends it.
- `epic`: `{ id, key, type: "epic", title, prdRef }`.
- `owner`: the run's owner token (the dispatch execution id); `reclaim: true` when the Epic is
  `in_progress` under a token whose run is not live (`itemownership`).
- `beadsRepoPath`: the control repository, where beads runs (`beadsio.main_repo_path()`).
- `archPath`: `$ATW_ARCH_PATH` (folder holding `arc42/`, `target/`, `built/`).
- `trdPath`: where the TRD is filed in the vault, when one exists for the PRD.
- `designSystem.packagesDir`: `$ATW_DESIGN_PACKAGES_DIR`, the owner's single-artifact cds bundles.
- `pluginRoot`: the installed plugin root (`pluginversion.running_dir()`).
- `artifactScript`: `$ATW_ARTIFACT_SCRIPT` (`<driver>/artifactio.py`); `projectRoot` /
  `skillspokeRoot`: `$SKILLSPOKE_ROOT`.
- `resume`: `artifactio.dispatch_resume(artifactio.plan(<epic>))`: `{ root, dir, epicId,
  completed[], stale[{step, what, reason}], names? }`.
- Optional and passed through to phases: `architectureSubject`, `maxArchitectureRounds`,
  `dependencies`, `accessPatterns`, `spec`.

Bead fields read (by `depscore.py`, not by the flow): the Epic's `issue_type`, status, metadata
`elaboration_state`, `elaboration_state_owner`, `elaboration_state_at`, `wsjf_ubv`, `wsjf_tc`,
`wsjf_confidence`, `wsjf`; all Tasks beneath the Epic and their edges (scoring, story edges).

Vault: the PRD file; `$ATW_ARCH_PATH/arc42/` (effective views, section 2
`02-architecture-constraints/` read-only); `$ATW_ARCH_PATH/target/<subject>/` (target, `delta/`,
`baseline.json`, `closure.json`).

Repositories: each span repository's `main` (read by the detailing phase).

Working directory: `<control>/.claude/workflow-runs/artifacts/<epic-id>/` (`artifactio.working_dir`;
`<epic-id>` sanitised by `artifactio.safe_key`).

## 4. Outputs

Files in `<work>` = `.claude/workflow-runs/artifacts/<epic-id>/` (each recorded file gets a
`<name>.meta.json` from `artifactio.py record` with the sha256 of its inputs):

| File | Written by | Format, key fields |
|---|---|---|
| `architecture/...` (`survey.json`, `survey.md`, `decision.md`, `decision.json`, `target.json`, `architecture-update.json`, ...) | architecture phase | see `architecture.md` |
| `delta-items.json` | step 6, `depscore.py arch-delta --save` | `{ ok, refusals[], architectureChange: none\|new\|partial, note, deltaExists, baselineValidated, implementationComplete, implementationWork, views[], items[{ id, element, views[], kind, state, requires[] }] }` |
| `repo-scoping.json` | repo-scoping phase | `{ placements[{ repoPath, itemIds[], frontend }], noCode[{ itemId, reason }], spanRationale, createdRepos[] }` (shape owned by `repo-scoping.md`) |
| `trd.md` | trd-authoring phase | Markdown |
| `recon-<slug>.json` | detailing phase | see `prd-reconciliation.md` |
| `spec-<slug>.md`, `spec-<slug>.data-model.md`, `spec-<slug>.criteria.md`, `story-<slug>.json` | spec-authoring phase | see `spec-authoring.md` |
| `tasks-<slug>.json` | task-decomposition phase | see `task-decomposition.md` |
| `candidates/task-deps.json` | agent, step 11 | `{ edges[{ from, to, kind: data\|contract\|infrastructure\|event-flow, reason }], acyclic, cycle[] }`; Task keys as `S<i>-<local key>` |
| `task-deps.json` | step 11, accepted copy of the candidate | same shape |
| `task-edges/all.json` | step 12, `depscore.py write-all-task-edges --out` | the write summary |
| `STEPS.md` | each step on success, `artifactio.complete_step(<work>, <step>)` | one completed step id per line |
| `run.json` (new; replaces the `RUN-JOURNAL` log lines) | step 16 | the run record (see step 16) |

`<slug>` is the span repository's basename with characters outside `[A-Za-z0-9._-]` replaced by
`_`, suffixed `-2`, `-3` when two span repositories share a basename, assigned in span order. The
Story key is `S<i>` for the `i`-th span repository (1-based). Task keys across Stories are
`S<i>-<local key>`.

Bead writes made by this flow's own steps (all through `depscore.py` or the beads-contract CLI,
run in `beadsRepoPath`):

| Step | Command | Writes |
|---|---|---|
| 2 | `depscore.py elaboration-start --epic <id> --owner <token> [--reclaim]` | Epic metadata `elaboration_state=in_progress`, `elaboration_state_at`, `elaboration_state_cause=elaboration-started`, `elaboration_state_owner=<token>` |
| 12 | `depscore.py write-all-task-edges --epic <id> --dir <work> --repos <span> --out <work>/task-edges/all.json` | `blocks` edges between Tasks of different Stories |
| 13 | `depscore.py elaboration-finish --epic <id> --owner <token> [--done]` | WSJF values on the Epic and its Tasks; with `--done`: `elaboration_state=done`, `elaboration_state_cause=decomposed-into-tasks`, `elaboration_state_at`, `elaboration_state_owner=""`; then Story `blocks` edges (`story-edges`) |
| 15a | `depscore.py elaboration-release --epic <id> --owner <token>` | `elaboration_state_owner=""` when it is still this run's token; state stays `in_progress` |
| 15b | `beads-contract.py -C <beadsRepoPath> metadata set <id> elaboration_state= elaboration_state_cause=awaiting-human-action elaboration_state_owner=` | the owner/incident hold |

Story beads (`depscore.py write-story`) and Task beads (`depscore.py write-task`, `replace-tasks`)
are written by the spec-authoring and task-decomposition phases; see their specs. Every Story and
Task write is keyed by `elab_key`, so a rerun updates the bead that exists.

Vault writes by this flow's own steps: step 14 deletes `$ATW_ARCH_PATH/target/<subject>/` and
commits the deletion in the vault repository with the message `docs(architecture): remove the
<subject> target once the Specs and Tasks made from its delta are written`. The architecture and
TRD phases write the vault as their specs say.

Return value (handback; which fields the driver reads is settled in `driver-contract.md`):
`{ ok, stage, beadId, headline, detailPath, hierarchy{ epic, stories[{ key, id, elabKey, repoPath,
title }], tasks[{ key, id, elabKey, parentStoryId, title, dependsOn[] }] }, repoSpan[],
targetRemoval{ removed, commit, reason }, beadsEmitted, lifecycle{ owner, start, finish, release?,
held?, heldCause?, holdWrite?, done }, storyEdges?, crossStoryDependencies, closureEdges,
createdRepos?, degraded, artifacts{ dir, epicId, phases, filing }, refusal?, failure?,
requiredHumanActions? }`.

## 5. Steps

Every step below that the JavaScript ran through `relay.js` / `relayrun.py` / the
`workflow-command-runner` agent is a direct call from Python (a subprocess with argv, no shell, or
an in-process function). No step starts an agent session except step 11 and the phases' own agent
steps.

1. `deterministic` **Inputs.** Validate the typed arguments: Epic id present, `beadsRepoPath`
   present, PRD path readable, plugin root known (the orchestrator's own install; no resolver
   runs). Failure: stage `input` or `epic-lifecycle`, cause `other`, no bead touched.
2. `deterministic` **Claim the Epic.** `depscore.py elaboration-start --epic <id> --owner <token>
   [--reclaim]`. Result `{ ok, refusal{ code, reason }, owner, previousState, warnings[] }`.
   Refusal codes: `not-an-open-epic`, `epic-done`, `epic-owned`. A refusal returns `ok:false`,
   stage `epic-lifecycle`, `refusal` set, and touches nothing else (the driver holds the Epic until
   it changes, `lane.py`). On `ok`, record `owner` as this run's token.
3. `deterministic` **Rule saved work.** Fingerprint every step's recorded inputs against its
   `<name>.meta.json` (`artifactio.plan` / `hashed_inputs`); a step is reusable when its files exist
   and every recorded input hashes as recorded. Each reused or stale step is a ledger event
   (`reused` / `stale` with the reason). See section 8.
4. `phase` **Architecture** (`architecture.md`). Skipped only when its saved result is reusable
   (`depscore.py saved-target --art-dir <work>` returns `found:true` with a `targetDir`). Inputs:
   PRD path, Epic id, `archPath`, `subject`, repo path, `maxRounds`, `<work>/architecture/`.
   Boundary contract out: `{ ok, subject, targetDir, deltaDir, decisionPath, targetPath,
   architectureUpdatePath, architectureUpdate.touched, stage?, reason?, requiredHumanActions? }`.
5. `deterministic` **Owner hold on architecture.** When the architecture result is `stage:
   owner-concern` (two business requirements no design satisfies together, or contradictory or
   unsatisfiable section 2 constraints), or `stage: input` because no architecture path is
   configured: run the hold write (step 15b), write the owner's question to the owner inbox
   (`ownerinbox.py`, `$ATW_OWNER_INBOX`), and return `ok:false`, stage `requires-human-action`,
   `requiredHumanActions` (the architecture's own, plus the restore step: `elabmark.py
   --set=in_progress --bead=<id> --apply` once settled). Any other architecture failure is
   `failure.stage = architecture` and goes to step 15.
6. `deterministic` **List the build items.** `depscore.py arch-delta --delta-dir <targetDir>/delta
   --save <work>/delta-items.json`. Always recomputed (it reads only the target and writes
   nothing else). An item list with `refusals` is carried on with the items it lists. Derive:
   `architectureChange` (`none`, `new`, `partial`, CONTEXT 7.7), `deltaDir` (empty when
   `deltaExists:false`), the items, and **noImplementationWork** =
   `baselineValidated && implementationComplete && implementationWork == 0` and no item of kind
   `prerequisite`.
7. In parallel:
   - 7a. `phase` **Repo scoping** (`repo-scoping.md`), unless reusable or **noImplementationWork**
     (then the span is empty and every item is recorded as `noCode` with the reason "the validated
     architecture assessment requires no implementation work"). Inputs: PRD path, `decision.md`,
     `target.json`, `delta-items.json`, Epic key and title, `avoidRepos` (step 8 only). Boundary
     contract out: `{ ok, repos[], placements[{ repoPath, itemIds[], frontend }], noCode[],
     createdRepos[], spanRationale }`. A reused span is read with `depscore.py saved-span
     --art-dir <work>`; any delta item it does not place is added to `noCode` ("the saved placement
     does not place it").
   - 7b. `phase` **TRD authoring** (`trd-authoring.md`), unless reusable. Inputs: PRD, the delta
     (subject, `targetDir`, `deltaDir`, `architectureChange`, note, items), `survey.json`,
     `archPath`, `trdPath`, `<work>/trd.md`. Boundary contract out: `{ ok, trdPath, filingPath,
     trd{ trdPath, summary } }`.
8. `deterministic` **Misplacement check.** A placement is misplaced when its `repoPath` is the
   control repository (`beadsRepoPath`) or contains `archPath`. When any is misplaced, run 7a once
   more with `avoidRepos` = the misplaced placements and their reasons (a fresh steward run, not the
   saved span). If misplacements remain: see Open question 1 (the JavaScript fails the run at
   stage `repo-scoping`; the meta description says the items are left unplaced). The span is the
   distinct `repoPath`s of the placements, in placement order. An empty span means
   **nothingToBuild**.
9. Per span repository, in parallel across repositories, in this order within one repository:
   - 9a. `phase` **Detailing** (`prd-reconciliation.md`). Inputs: the items placed in that
     repository, the delta (`targetDir`, `deltaDir`, `architectureChange`, note), `survey.json`,
     PRD, the repository, `uiRepo` (any placement in it has `frontend:true`),
     `designSystem.packagesDir`/`mocksDir`/`shellsDir`, `<work>/recon-<slug>.json`. Boundary
     contract out (`depscore.py recon-facts`): `{ ok, reconPath, work[], idle[{ id, status,
     plannedBy? }], uiWork[{ id, designSource: bundle|cds|none, bundle, buildSpec, sections[] }],
     dependenciesCurrent, dependencyFindings }`. A failed detailing blocks that repository's Spec;
     the repository fails at stage `detailing` (or the phase's own stage).
   - 9b. `phase` **Spec authoring** (`spec-authoring.md`). Inputs: `trd.md`, `trd.summary`, the
     delta, `recon-<slug>.json` (the phase reads the item list from the file; the composite passes
     only the path and the ids of work and idle items), the UI items, the repository, the Story key
     `S<i>`, the Epic, `beadsRepoPath`, the depscore script. The phase writes the Story bead with
     `depscore.py write-story --epic --dir --slug --repo`. Boundary contract out: `{ ok, story{ id,
     key, elabKey, title }, decisionIds[], apiSpec, dataModelSpec, eventContracts, errorSpec
     (each with artifactPaths[]), summary{ created, updated } }`. A result without `story` is a
     failure.
10. Per Story, in parallel: `phase` **Task decomposition** (`task-decomposition.md`). Inputs: the
    spec documents (`spec-<slug>.md`, `.data-model.md`, `.criteria.md` plus any `artifactPaths`
    the spec phase returned), `recon-<slug>.json` path, `story-<slug>.json`, the Story `{ id, key,
    title }`, `beadsRepoPath`, `designSystem.packagesDir`, and `upstreamChange` (the stale reason
    of `tasks:<slug>` from step 3, when there is one). The phase owns the rerun rule (CONTEXT 7.5),
    the Task bead writes and the one corrective pass for uncited items (CONTEXT 7.6). Boundary
    contract out: `{ ok, tasks[{ key, id, elabKey, action, title, dependsOn[] }], summary{ created,
    updated }, rerun?{ case, reason, deleted[], kept[] }, stage?, uncitedItems?, failure? }`. A
    `rerun` is recorded as ledger event `task-rerun` with its case and reason. A failure at stage
    `uncited-items` carries the items no Task cites after the corrective pass.
11. `agent` **Cross-Story Task dependencies.** Runs only when two or more Stories have Tasks, and
    `task-deps.json` is not reusable.
    - Agent: `task-dependency-mapper` (`<plugin>/agents/task-dependency-mapper.md`).
    - Input paths: each Story's `<work>/tasks-<slug>.json`; a short listing of each Story's Task
      keys, titles and same-Story edges (keys and titles only; descriptions stay in the files); the
      `closure-edges` edges from step 12a as "these stand, do not return them".
    - Output file: `<work>/candidates/task-deps.json` (shape in section 4), validated against that
      schema and copied to `<work>/task-deps.json` by Python (`jsonartifact.py` acceptance becomes
      an in-process validate-and-write), then recorded with its input sha256s
      (`artifactio.record`, inputs = the `tasks-<slug>.json` files).
    - Model and effort as used today: frontmatter `model: fable`, call `effort: medium`
      (frontmatter also `effort: medium`); the shared `fable` block switches to `opus` on
      recovery. Medium effort fits a bounded read-and-relate job; whether `fable` is the right
      model is Open question 4.
    - Runs alone (after every Story's decomposition).
12. `deterministic` **Write the Task edges between Stories.**
    - 12a. Before step 11: `depscore.py closure-edges --dir <work> --repos <span>` returns
      `{ edges[{ from, to, reason }], summary.warnings }`: the edges the delta's `requires`
      relations make, and warnings for a required item with no Task, no open bead and not done
      (reported, not a failure).
    - 12b. `depscore.py write-all-task-edges --epic <id> --dir <work> --repos <span> --out
      <work>/task-edges/all.json`: reads `task-deps.json` and the closure edges, drops any edge
      that closes a cycle, writes the `blocks` edges. Result `summary{ blockers{ to: [from] },
      added, removed, standing, rejected }`. Runs when `task-deps.json` exists (fresh or reused).
13. `deterministic` **Finish.** **done** = **nothingToBuild**, or no repository failed in steps 9
    and 10. Run `depscore.py elaboration-finish --epic <id> --owner <token> [--done]`. Result `{ ok,
    lifecycle (non-null when marked done), summary{ tasksScored, epicsWritten, tasksWritten,
    unscored, done }, storyEdges{ ok, added[], removed[], unchanged, refusedStories[], reason,
    conflicts[], cycles[], error? } }`. Scoring runs whether or not the Epic is done. This flow
    calls no WSJF judging and no dependency-assessment workflow: Epic and Task WSJF judgments
    (sizes, values) come from the task-decomposition phase and the earlier Epic scoring; finish
    only runs the arithmetic.
14. `deterministic` **Remove the target**, only when step 13 marked the Epic done and `archPath`
    is set: `depscore.py arch-target-remove --arch-root <archPath> --target-dir <targetDir>
    --message "<message in section 4>"`. Result `{ ok, removed, commit, refusals[] }`. A refusal
    is reported in `targetRemoval.reason`; it does not fail the run.
15. `deterministic` **Release or hold** (on every exit after step 2 succeeded, unless step 13
    marked the Epic done or step 5 already held it):
    - 15a. The run succeeded, or failed with a transient cause (`api`, `quota`, `bd-timeout`,
      `contention`; `relay` while it still has a producer): `depscore.py elaboration-release`.
      The Epic stays `in_progress` with no owner; the driver redispatches after its backoff, and
      the rerun redoes only the failed steps (section 8).
    - 15b. Any other cause: the hold write (`beads-contract.py metadata set ... elaboration_state=
      elaboration_state_cause=awaiting-human-action elaboration_state_owner=`), and
      `requiredHumanActions` names the incident-responder diagnosis and the restore step. A hold
      write that fails with `bd-timeout` or `contention` is retried with backoff (30 s, doubling,
      cap 30 min, CONTEXT 7.4); any other failure is recorded in `lifecycle.holdWrite`. Once a hold
      was attempted, the Epic is never released, even when every hold write failed.
16. `deterministic` **Record the run.** Write `<work>/run.json` (the record the JavaScript emitted
    as `RUN-JOURNAL` log lines: composite, Epic, PRD id, outcome, per-phase status and decision,
    the reused/stale/task-rerun events, partial results on failure), append the ledger events the
    driver reads (`driver-contract.md` names them), and return the handback with `detailPath` =
    that file.

Parallelism summary: 7a with 7b; 9 across repositories; 10 across Stories; 11 alone. Each agent
session is started by the phase that owns it, with its definition, file paths and an output file.

Relay and command-runner calls of the JavaScript, each mapped:

| JavaScript relay label | Becomes |
|---|---|
| `resolve-plugin-root-<n>` (inline Python, up to 3 attempts) | dropped; the orchestrator knows its install |
| `epic:start` | step 2, subprocess `depscore.py elaboration-start` |
| `replay:read-saved-target` | step 4, `depscore.py saved-target` (or the same function in-process) |
| `resume:recheck-<step>` (`artifactio.py plan`) | step 3, in-process fingerprint check |
| `steps:record:<step>` (`artifactio.py step`) | in-process `artifactio.complete_step` after each step |
| `arch:delta` | step 6, `depscore.py arch-delta --save` |
| `replay:read-saved-span` | step 7a, `depscore.py saved-span` |
| `epic:hold` | step 15b, `beads-contract.py metadata set` |
| `beads:closure-edges` | step 12a, `depscore.py closure-edges` |
| `sequence:inputs` (`artifactRevision`) | step 11, in-process sha256 of the input files |
| `sequence:accept-cross-story` (`jsonartifact.py` acceptance) | step 11, in-process schema validation and write |
| `sequence:record` (`artifactio.py record`) | step 11, in-process `artifactio.record` |
| `beads:write-all-task-edges` | step 12b, `depscore.py write-all-task-edges` |
| `epic:finish` | step 13, `depscore.py elaboration-finish` |
| `arch:target-remove` | step 14, `depscore.py arch-target-remove` |
| `epic:release` | step 15a, `depscore.py elaboration-release` |

## 6. Checks kept / Checks dropped

**Checks kept**
- `elaboration-start` refusals (`not-an-open-epic`, `epic-done`, `epic-owned`): without them two
  runs write the same Epic's beads at once, or a done Epic's Tasks are rewritten; the manual door
  bypasses driver selection, so nothing earlier always catches it.
- Misplacement (control repository, architecture repository): without it Stories and Tasks are
  written against the control or vault repository and the build lane commits product code there;
  nothing later checks a Task's repository against this rule.
- The done rule (CONTEXT 7.6): without it the Epic is marked done with a repository missing its
  Story or Tasks, and selection never elaborates it again.
- Target removal only after done: without it `target/<subject>/` (the input of every rerun step)
  is deleted while steps still need it.
- Cycle drop in `write-all-task-edges` (inside `depscore.py`): a cycle in `blocks` edges makes
  every Task on it unbuildable, and nothing later breaks it.
- Schema validation of `candidates/task-deps.json` before it is written: a malformed edge (unknown
  key, wrong kind) reaches beads otherwise; `write-all-task-edges` validates keys too, so this may
  be merged into that one check (S02).
- Section 2 hard limit: enforced inside the architecture phase (`depscore.py arch-constraints` /
  `arch-constraints-restore`, see `architecture.md`); this flow writes nothing under arc42.
- Hold attempted means never released: without it a held Epic is released, redispatched and fails
  the same way again; nothing later stops the loop.

**Checks dropped**
- Plugin-root resolution and its three attempts: the orchestrator runs from its install.
- `!hasText(emitTarget)` "no tracker" refusal and the PRD body-or-path check: typed arguments from
  the driver; the PRD path is checked once in step 1.
- "Architecture result names no target directory": `arch-delta` fails on a missing directory, and
  the architecture flow returns a typed result.
- The upstream-rerun recheck in `resumeFresh` (a step is reused while its upstream steps were
  reused, else the inputs are rechecked through a relay): replaced by checking each step's own
  recorded input fingerprints directly (section 8); the result is the same with no chain logic.
- The control-repository check applied separately to a saved span: merged into step 8, which
  applies to saved and fresh spans alike.
- Bounded dispatch policy (`dispatchInterruption`, `settleWorkflow`, `settleAgent`,
  `dispatchRetry`, the 5 s x 3^n backoff): replaced by the runner's structured session result and
  the driver's `breaker.py` (CONTEXT 7.4).
- `dispatchFailureCause` text matching on error messages: forbidden (CONTEXT 7.4); causes come
  from structured facts.
- `RUN-JOURNAL` chunking into 4000-character log lines: the run record is a file (step 16).
- `EXPECTED_PHASES` entries `PRD`, `Epic`, `PRD Parse` and `Run Ledger` as phases: `PRD Parse` was
  never entered; the others do no work. Phase names for the dashboard are settled in
  `driver-contract.md`.
- The fixed 10/30/90 s hold-write backoff: replaced by the CONTEXT 7.4 backoff.
- The `degraded` flag and the `DEGRADED:` headline text: kept only if `driver-contract.md` shows
  the driver reads them; otherwise dropped.

## 7. Failure causes

| Failure point | Stage | Cause | Retry reasonable? |
|---|---|---|---|
| Typed input missing (Epic id, beads repo, PRD path) | `input` / `epic-lifecycle` | `other` | No: the same input fails the same way. |
| `elaboration-start` refusal | `epic-lifecycle` (+ `refusal.code`) | none (a refusal, not a failure) | No; the driver holds until the bead changes. |
| `depscore.py` / `bd` exit with a `bd` lock or timeout | the step's stage | `bd-timeout` or `contention`, from the field the script's JSON result carries | Yes, backoff 30 s doubling, cap 30 min. |
| An agent session ends on an API error or quota | the phase's stage | `api` / `quota`, from the session's structured result (stream event / exit status), never from text | Yes, through `breaker.py`. |
| Architecture `owner-concern` / no architecture path | `requires-human-action` | `other` | No: held for the owner. |
| Other architecture failure | `architecture` | the phase's `failure.cause` | Per that cause. |
| Repo scoping fails, or misplaces twice | `repo-scoping` | the phase's cause, else `other` | Per cause; a misplacement twice is `other`. |
| TRD authoring fails | `trd-authoring` | the phase's cause | Per cause. |
| One repository's detailing or spec fails | per repository: `detailing` / `spec-authoring` / the phase's stage; run: `repositories-incomplete` | per repository from its phase's `failure.cause`; the run's cause is transient only when every failed repository's is | Transient: yes, rerun only the failed steps. Otherwise: incident-responder. |
| One Story's decomposition fails (incl. `uncited-items` after the one corrective pass) | per repository: the phase's stage; run: `repositories-incomplete` | as above; `uncited-items` is `other` | `uncited-items`: no, it already had its one corrective pass. |
| No repository produced a Spec, or no Story produced Tasks (and not nothingToBuild) | `repositories-incomplete` | combined, as above | as above. |
| `closure-edges` does not run | none (logged) | `other` | No. |
| task-dependency-mapper ends without an accepted file | none; `crossStoryDependencies.reason` set, the run continues | the session's cause | Transient: yes, on the next dispatch (the step is not recorded). Otherwise no. |
| `write-all-task-edges` fails | none; reason recorded | from its result | Contention: yes. |
| `elaboration-finish` fails | the Epic is not done; the run is `ok:true` today with a "scoring did not run" headline (Open question 3) | from its result | Contention: yes. |
| `arch-target-remove` refused | none; `targetRemoval.reason` | `other` | No. |
| Hold write fails | recorded in `lifecycle.holdWrite` | `bd-timeout` / `contention` / `other` | `bd-timeout`/`contention`: yes, with backoff; else no. |
| Unexpected exception | the current phase's name | `other` | No: incident-responder. |

Every failure returns `failure: { stage, cause, repositories: [{ repository, stage, cause,
headline }] }`. `relay` is produced today only by relay plumbing; after the rewrite nothing in this
flow produces it (Open question 2).

## 8. Resume points

A step is reused when its saved files exist and every input recorded in their `.meta.json` hashes
as recorded now. A reused step starts no agent session. Step ids are those of
`artifactio.STEP_ORDER`, recorded in `STEPS.md`.

| Step id | Saved files | Inputs that fingerprint it | A rerun after it redoes |
|---|---|---|---|
| (claim) | none | none | step 2 again; idempotent: the same owner token resumes an `in_progress` Epic |
| `architecture` | `architecture/` deliverables incl. `target.json` (see `architecture.md` for its inner resume points: `survey.*`, `plans/`, `candidates/`, `target-check.json`, `arc42-revision.json`) | PRD file; the arc42 revision (`arc42-revision.json`) | nothing in architecture; steps 6 onward as their own fingerprints decide |
| (items) | `delta-items.json` | none: recomputed every run from `target/<subject>/` | always recomputed; costs no session |
| `repo-scoping` | `repo-scoping.json` | PRD; `architecture/decision.md`; `architecture/target.json` | nothing when unchanged |
| `trd` | `trd.md` | PRD; `decision.md`; `target.json`; `architecture-update.json`; `survey.json`; `target/<subject>/`; arc42 section 2 folder; the effective views of the delta's elements (`arch-views:`) | nothing when unchanged |
| `recon:<slug>` | `recon-<slug>.json` | PRD; `target.json`; `repo-scoping.json`; `survey.json`; the repository's `main` commit (`git-main:<repo>`, stale only when a file the detailing cites changed) | nothing when unchanged |
| `spec:<slug>` | `spec-<slug>.md`, `.data-model.md`, `.criteria.md`, `story-<slug>.json` | `trd.md`; `repo-scoping.json`; `recon-<slug>.json`; PRD | `depscore.py write-story` from the saved files (idempotent by `elab_key`), no agent |
| `tasks:<slug>` | `tasks-<slug>.json` | the spec documents; `story-<slug>.json` | the missing Task beads only (CONTEXT 7.5 rule, owned by `task-decomposition.md`) |
| `task-deps` | `task-deps.json` | every `tasks-<slug>.json` | `write-all-task-edges` from the saved file, no agent |
| (finish) | none | none | `elaboration-finish` again; idempotent |
| (target removal) | none | none | `arch-target-remove` again; `removed:false` when already gone |

A failed repository's steps are not recorded, so the next dispatch redoes exactly those. A stale
step's files are set aside by the driver (`artifactio.set_aside_stale`) before the dispatch. The
saved architecture surveys of `ssbd-mb689`, `ssbd-hdqid` and `ssbd-guuuz` (CONTEXT 7.13) are reused
through the `architecture` resume point when their inputs are unchanged.

## 9. Owner rules that apply

- **7.4 Retries:** structured causes only (section 7); transient causes release the Epic for a
  later rerun of the failed steps; succeeded steps are never redone (section 8); the same step with
  nothing changed is not retried but diagnosed (hold for the incident-responder).
- **7.5 Rerunning Task creation:** delegated to the task-decomposition phase; this flow passes the
  stale reason (`upstreamChange`) and records `task-rerun`.
- **7.6 Done:** step 13's done rule; the one corrective pass is inside the task-decomposition
  phase, and its leftover `uncitedItems` fail that repository. "Epic closed" is never used: done is
  `elaboration_state=done` and the Epic stays open.
- **7.7 Three-case architecture model:** `architectureChange` (`none`, `new`, `partial`) from
  `arch-delta` drives `deltaDir`; every case yields build items (view items and/or
  `implementationWork` gaps), so something always reaches the TRD and the Tasks unless the
  validated assessment says no implementation work.
- **7.9 Who gets asked what:** only `owner-concern` and the missing architecture path go to the
  owner (inbox); every other failure goes to the incident-responder.
- **7.10 Repositories:** the polyrepo-steward places items and creates repositories; the control
  repository and the architecture repository are never placement targets.
- **7.11 Deterministic over agentic:** only step 11 and the phases' reasoning steps are agents.
- **7.13 Saved work:** the architecture resume point reuses the existing surveys.
- **Hard limits (CONTEXT 6):** no arc42 section 2 writes (architecture phase); no destructive
  operations beyond the target folder removal after done, and the unstarted-Task deletion inside
  task decomposition.

## 10. Open questions

1. **Misplacement after the second steward run.** The meta description says a placement in the
   control or architecture repository "goes back to the steward once, and is then left unplaced";
   the code fails the run at stage `repo-scoping` instead. Which is intended? If "left unplaced",
   are those items recorded as `noCode`?
2. **The `relay` cause.** After the rewrite this flow has no relay. Keep `relay` in
   `failurecause.py` for other producers, or drop it (S02).
3. **`elaboration-finish` failure.** Today a failed finish leaves the Epic not done but returns
   `ok:true` (headline "Scoring did not run"). Should it be a failure with its structured cause, so
   the Epic is released for a retry? The done rule suggests yes.
4. **task-dependency-mapper model.** Frontmatter says `model: fable` with an `opus` switch on
   recovery; CONTEXT does not settle which model this bounded edge-mapping job should use.
5. **Owner inbox writer.** Does the flow write the owner's question to `$ATW_OWNER_INBOX`
   itself, or does the driver write it from `requiredHumanActions` as today? `driver-contract.md`
   and S02 settle it.
6. **Task-deps when one Story is reused and another changed.** The `task-deps` step is
   fingerprinted by all `tasks-<slug>.json` files; when one Story's Tasks are recreated, all
   cross-Story edges are derived again. Acceptable, or derive only the edges touching the changed
   Story?
7. **Inline PRD text.** The JavaScript accepts `prd.body`; the driver never sends it. Drop it, or
   keep it for the `/start-prd` door (depends on whether that door survives, as for
   `route-elaboration`).
8. **Closure-edge warnings.** A required item with no Task, no open bead and not done is only
   logged. It is wrong output in beads (a dependency with no builder) that nothing later catches;
   should it fail the repository or be fed into the corrective pass?
