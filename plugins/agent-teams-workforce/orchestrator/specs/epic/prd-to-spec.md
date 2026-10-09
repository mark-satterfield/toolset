# Net-effect spec: `prd-to-spec` (the Epic pipeline's top level)

Sources, in order of authority: the `meta.description` of `<plugin>/workflows/prd-to-spec.js`;
the agent definition `<plugin>/agents/task-dependency-mapper.md` (the one agent this composite
dispatches itself); CONTEXT section 7; then, for contracts only, the code of `prd-to-spec.js`,
`<plugin>/scripts/portfolio/depscore.py`, `elaboration.py` and `resumefacts.py`,
`<driver>/workitems.py`, `<driver>/artifactio.py`, `<driver>/dispatch.py` and `<driver>/lane.py`.
`<driver>` is `$ATW_CONTROL_REPO/ops/sdlc-automation`.

This spec covers the composite's own steps and names each phase's contract by reference. Each phase
it calls has its own spec, which is the single source of that phase's inputs, outputs, result
fields and reuse decision; this one does not restate them:

| Phase | Spec |
|---|---|
| Architecture | `<orch>/specs/epic/architecture.md` |
| Repo scoping (span, placement checks, the no-implementation short cut) | `<orch>/specs/epic/repo-scoping.md` |
| TRD authoring | `<orch>/specs/epic/trd-authoring.md` |
| Detailing (PRD reconciliation) | `<orch>/specs/epic/prd-reconciliation.md` |
| Spec authoring and the Story bead | `<orch>/specs/epic/spec-authoring.md` |
| Task decomposition, Task beads, the corrective pass, the rerun rule | `<orch>/specs/epic/task-decomposition.md` |
| WSJF scoring and dependency assessment (not called by this flow; see step 14) | `<orch>/specs/epic/wsjf-scoring.md`, `<orch>/specs/epic/dependency-assessment.md` |
| What the driver sends and reads back; the session runner's shared rules | `<orch>/specs/epic/driver-contract.md` |
| Every artifact and bead write across the Epic flows | `<orch>/specs/epic/INDEX.md` |

`prd-validation` and `gate-enforce` are not called by `prd-to-spec`.

## 1. Purpose

Elaborate one existing, scored Epic and its PRD into Stories and Tasks written to beads. The flow
claims the Epic (`depscore.py elaboration-start`), runs the architecture phase for every PRD (never
skipped: a PRD the effective architecture already serves gets a "no change" result that says so),
returns owner facts to the driver only on business requirements no design can satisfy together, on
contradictory section 2 constraints, or on a missing architecture path, lists the build items from
the approved target and delta, has the repo-scoping phase rule the repository span from where the
polyrepo-steward places those items, authors the TRD, and per span repository details the items
against `main`, authors one Spec and one Story, and decomposes the Story into Tasks for its
`add`/`modify`/`remove` items. It then derives the Task edges between Stories, scores the Epic and
its Tasks, and marks the Epic `elaboration_state=done` (`depscore.py elaboration-finish --done`)
once every span repository has its result, after which it deletes the Epic's `target/<subject>/`
(`depscore.py arch-target-remove`). A failed run returns `ok:false` with `failure: { stage, cause,
repositories[] }` and releases the Epic; the driver backs off a transient cause and opens an
incident for any other.

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
- The repository span is the one the repo-scoping phase returned (its checks: every item placed
  exactly once, nothing in the control, architecture or marketing repositories).
- `trd.md` exists for the PRD.
- For every span repository: `recon-<slug>.json`, the spec documents, `story-<slug>.json`, one
  Story bead (keyed by `elab_key`), `tasks-<slug>.json`, and Task beads covering every `add`,
  `modify` and `remove` item of that repository, or a recorded "nothing to build" (the record is
  Open question 4).
- Task `blocks` edges between Stories are written: those the delta's `requires` relations make
  (`closure-edges`) and those the task-dependency-mapper derived (`task-deps.json`), with every
  edge that closes a cycle dropped.
- Story-to-Story `blocks` edges are rewritten from the Task edges (`story-edges`, run inside
  `elaboration-finish`).
- The Epic and every Task beneath it are rescored (WSJF arithmetic, Epic size rolled up from its
  Tasks).

Decisions the flow makes:
- **Refuse or claim** the Epic (step 2 selection filters, step 3 `elaboration-start`).
- **Return owner facts** (architecture `owner-concern` or `no-arch-path`): the flow returns
  `requiredHumanActions`; the driver holds the Epic and writes the owner inbox.
- **Nothing to build**: the span repo-scoping returns names no repository (its no-implementation
  short cut, or every item recorded as having no code here). Then detailing, specs and Tasks produce
  nothing, and the Epic is still marked done.
- **Done or not done** (CONTEXT 7.6): done only when every span repository has its result.
- **Transient or not** for a failed run's `failure.cause`; the driver acts on it (section 7).

## 3. Inputs

From the driver (`<driver>/workitems.py` `elaboration_args`, `dispatch_context`,
`with_artifact_plan`; the full list is in `driver-contract.md` §3):
- `prd`: `{ id, title, path }`; `id` is the PRD file stem; `path` is the PRD file under
  `$ATW_PRD_DIR`. The JavaScript also accepts inline `body`/`content`; the driver never sends it
  (Open question 3).
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
- `resume`: `artifactio.dispatch_resume(artifactio.plan(<epic>))`. Whether the driver keeps
  computing it once each phase rules its own reuse is merged question Q6 in `driver-contract.md`.
- Optional and passed through to phases: `architectureSubject`, `maxArchitectureRounds`,
  `dependencies`, `accessPatterns`, `spec` (the driver sends none of them today; Open question 3
  covers the last three).

Bead fields read (by `depscore.py` and `<driver>/elabstate.py`, not by the flow's own code): the
Epic's `issue_type`, status, metadata `elaboration_state`, `elaboration_state_cause`,
`elaboration_state_owner`, `elaboration_state_at`, `wsjf_ubv`, `wsjf_tc`, `wsjf_confidence`,
`wsjf`; its `tracks`/`blocks` prerequisites (step 2); all Tasks beneath the Epic and their edges
(scoring, story edges).

Vault: the PRD file; `$ATW_ARCH_PATH/arc42/` (effective views, section 2
`02-architecture-constraints/` read-only); `$ATW_ARCH_PATH/target/<subject>/` (target, `delta/`,
`baseline.json`, `closure.json`).

Repositories: each span repository's `main` (read by the detailing phase).

Working directory: `<control>/.claude/workflow-runs/artifacts/<epic-id>/` (`artifactio.working_dir`;
`<epic-id>` sanitised by `artifactio.safe_key`). Called `<work>` below.

## 4. Outputs

Files in `<work>` (each recorded file gets a `<name>.meta.json` from `artifactio.record`, the one
input-record format of every Epic flow):

| File | Written by | Format, key fields |
|---|---|---|
| `architecture/...` | architecture phase | see `architecture.md` §4 |
| `delta-items.json` | step 7, `depscore.py arch-delta --save` | `{ ok, refusals[], architectureChange: none\|new\|partial, note, deltaExists, baselineValidated, implementationComplete, implementationWork, views[], items[{ id, element, views[], kind, state, requires[] }] }` |
| `repo-scoping.json` (+ inventory, candidate) | repo-scoping phase | see `repo-scoping.md` §4 |
| `trd.md` | trd-authoring phase | see `trd-authoring.md` §4 |
| `recon-<slug>.json` (+ `.bundles.json`) | detailing phase | see `prd-reconciliation.md` Outputs |
| `spec-<slug>.md`, `spec-<slug>.data-model.md`, `spec-<slug>.criteria.md`, `story-<slug>.json` (+ draft) | spec-authoring phase | see `spec-authoring.md` Outputs |
| `tasks-<slug>.json` (+ context, candidate, correction) | task-decomposition phase | see `task-decomposition.md` §4 |
| `closure-edges.json` | step 11, `depscore.py closure-edges --out` | `{ edges[{ from, to, reason }], summary.warnings }` |
| `candidates/task-deps.json` | agent, step 12 | `{ edges[{ from, to, kind: data\|contract\|infrastructure\|event-flow, reason }], acyclic, cycle[] }`; Task keys as `S<i>-<local key>` |
| `task-deps.json` (+ `.meta.json`) | step 12, accepted copy of the candidate | same shape |
| `task-edges/all.json` | step 13, `depscore.py write-all-task-edges --out` | the write summary |
| `STEPS.md` | each step on success, `artifactio.complete_step(<work>, <step>)` | one completed step id per line |
| `run.json` (new; replaces the `RUN-JOURNAL` log lines) | step 17 | the run record (see step 17) |

`<slug>` is the span repository's basename with characters outside `[A-Za-z0-9._-]` replaced by
`_`, suffixed `-2`, `-3` when two span repositories share a basename, assigned in span order. The
Story key is `S<i>` for the `i`-th span repository (1-based). Task keys across Stories are
`S<i>-<local key>`.

Bead writes made by this flow's own steps (all through `depscore.py`, run in `beadsRepoPath`):

| Step | Command | Writes |
|---|---|---|
| 3 | `depscore.py elaboration-start --epic <id> --owner <token> [--reclaim]` | Epic metadata `elaboration_state=in_progress`, `elaboration_state_at`, `elaboration_state_cause=elaboration-started`, `elaboration_state_owner=<token>` |
| 13 | `depscore.py write-all-task-edges --epic <id> --dir <work> --repos <span> --out <work>/task-edges/all.json` | `blocks` edges between Tasks of different Stories |
| 14 | `depscore.py elaboration-finish --epic <id> --owner <token> [--done]` | WSJF values on the Epic and its Tasks; with `--done`: `elaboration_state=done`, `elaboration_state_cause=decomposed-into-tasks`, `elaboration_state_at`, `elaboration_state_owner=""`; then Story `blocks` edges and `story_*` keys (`story-edges`) |
| 16 | `depscore.py elaboration-release --epic <id> --owner <token>` | `elaboration_state_owner=""` when it is still this run's token; state stays `in_progress` |

The flow writes no hold. The person hold (`elabstate.hold_for_person`) and the owner inbox entry
(`ownerinbox` through the lane's `human_log`) are written by the driver from `requiredHumanActions`
(`<driver>/lane.py` `_person_needed`); see `driver-contract.md` §4.

Story beads (`depscore.py write-story`), Task beads (`write-task`, `replace-tasks`) and the
Epic's TRD metadata (`beads-contract.py metadata set`) are written by the phases; see their specs
and `INDEX.md`. Every Story and Task write is keyed by `elab_key`, so a rerun updates the bead
that exists.

Vault writes by this flow's own steps: step 15 deletes `$ATW_ARCH_PATH/target/<subject>/` and
commits the deletion in the vault repository with the message `docs(architecture): remove the
<subject> target once the Specs and Tasks made from its delta are written`. The architecture phase
writes the vault as its spec says.

Return value (handback; which fields the driver reads is settled in `driver-contract.md` §4):
`{ ok, stage, beadId, headline, detailPath, hierarchy{ epic, stories[{ key, id, elabKey, repoPath,
title }], tasks[{ key, id, elabKey, parentStoryId, title, dependsOn[] }] }, repoSpan[],
targetRemoval{ removed, commit, reason }, beadsEmitted, lifecycle{ owner, start, finish, release?,
done }, storyEdges?, crossStoryDependencies, closureEdges, createdRepos?, artifacts{ dir, epicId,
phases, filing }, refusal?, failure?, requiredHumanActions? }`.

## 5. Steps

Every step below that the JavaScript ran through `relay.js` / `relayrun.py` / the
`workflow-command-runner` agent is a direct call from Python (a subprocess with argv, no shell, or
an in-process function). No step starts an agent session except step 12 and the phases' own agent
steps. Every agent session, in this flow and in every phase, runs inside the session runner's
section 2 guard (`driver-contract.md` §8).

1. `deterministic` **Inputs.** Validate the typed arguments: Epic id present, `beadsRepoPath`
   present, PRD path readable, plugin root known (the orchestrator's own install; no resolver
   runs). Failure: stage `input`, cause `other`, no bead touched.
2. `deterministic` **Selection filters (CONTEXT 7.8).** In-process, with the driver's own functions
   (`elabstate.candidacy`, `elabstate.unmet_blockers`, `BeadIndex.wsjf_of`), refuse an Epic that
   driver selection would not pick: `elaboration_state` empty (the mobile Epics `ssbd-cb6i4`,
   `ssbd-kfihs`, `ssbd-mx3vn`, and an Epic held `awaiting-human-action`) or `done`; no `wsjf`; an
   unmet Epic prerequisite. The refusal codes are the driver's existing `WAIT_CODES` and
   `PERSON_CODES` (`epic-authoring`, `epic-unscored`, `upstream-not-elaborated`, `epic-done`,
   `epic-state-unknown`). A refusal returns `ok:false`, stage `epic-lifecycle`, `refusal` set, and
   touches nothing. For a driver dispatch this repeats selection; it matters for any door that does
   not go through selection (merged question Q12 in `route-elaboration.md`).
3. `deterministic` **Claim the Epic.** `depscore.py elaboration-start --epic <id> --owner <token>
   [--reclaim]`. Result `{ ok, refusal{ code, reason }, owner, previousState, warnings[] }`.
   Refusal codes: `not-an-open-epic`, `epic-done`, `epic-owned`. A refusal returns `ok:false`,
   stage `epic-lifecycle`, `refusal` set, and touches nothing else (the driver holds the Epic until
   it changes, `lane.py`). On `ok`, record `owner` as this run's token.
4. `deterministic` **Saved work.** No composite-level ruling. Each phase rules its own reuse at its
   start, from its own recorded inputs, as its spec's resume section says; the composite records a
   ledger event `reused` or `stale` (with the reason) for each phase from the phase's result. See
   section 8.
5. `phase` **Architecture** (`architecture.md`). Skipped only when the saved result is complete and
   current: `depscore.py saved-target --art-dir <work>` (`resumefacts.saved_target`) returns
   `found:true` with a `targetDir`, `ok:true` (survey current, arc42 revision unchanged) **and**
   `closureSaved:true`. Otherwise the architecture flow runs; its own resume points make a call on
   saved work cheap. Inputs and result: `architecture.md` §3 and §2 item 11.
6. `deterministic` **Owner facts from architecture.** When the architecture result is `stage:
   owner-concern` (two business requirements no design satisfies together, or contradictory or
   unsatisfiable section 2 constraints) or `stage: no-arch-path` (no architecture root configured):
   return `ok:false`, stage `requires-human-action`, `requiredHumanActions` = the architecture's.
   The flow writes no hold and no inbox entry: the driver holds the Epic and records the owner's
   question in the owner inbox from `requiredHumanActions` (CONTEXT 7.9). Any other architecture
   failure is `failure.stage = architecture` and goes to step 16.
7. `deterministic` **List the build items.** `depscore.py arch-delta --delta-dir <targetDir>/delta
   --save <work>/delta-items.json`. Always recomputed (it reads only the target and writes
   nothing else). An item list with `refusals` is carried on with the items it lists. Derive
   `architectureChange` (`none`, `new`, `partial`, CONTEXT 7.7) and `deltaDir` (empty when
   `deltaExists:false`).
8. In parallel:
   - 8a. `phase` **Repo scoping** (`repo-scoping.md`). The composite passes the `delta-items.json`
     path, the `arch-delta` result fields and the Epic; the phase owns the no-implementation short
     cut, its own reuse, the placement checks and the one corrective pass, and returns the span as
     final (`repo-scoping.md` §4, flow result). An empty span means **nothingToBuild**.
   - 8b. `phase` **TRD authoring** (`trd-authoring.md`). The composite passes the PRD, the
     `arch-delta` result fields and the architecture paths; the result is `{ ok, trdPath,
     filingPath, decisionIds }` (`trd-authoring.md` §4). No summary is passed on: spec authoring
     reads the TRD by path.
9. Per span repository, in parallel across repositories, in this order within one repository:
   - 9a. `phase` **Detailing** (`prd-reconciliation.md`). The composite passes the repository, its
     placed items, `uiRepo`, the `arch-delta` result fields and `designSystem`; the result is the
     facts list in `prd-reconciliation.md` (Produces and decides), including `uiWork[]` with
     `artifact`. A failed detailing blocks that repository's Spec; the repository fails at the
     phase's stage.
   - 9b. `phase` **Spec authoring** (`spec-authoring.md`). The composite passes `trd.md` (path
     only), the detailing facts, the repository, the Story key `S<i>` and the Epic; the phase writes
     the Story bead. The result is the one in `spec-authoring.md` (Produces and decides): `story`,
     `specPaths`, `decisionIds`, `summary`. A result without `story` is a failure.
10. Per Story, in parallel: `phase` **Task decomposition** (`task-decomposition.md`). The composite
    passes `specPaths` from 9b, the `recon-<slug>.json` path, the Story `{ id, key, title }`,
    `beadsRepoPath`, `designSystem.packagesDir` and the stale reason of `tasks:<slug>` when the
    phase reports one. The phase owns the rerun rule (CONTEXT 7.5), the Task bead writes and the one
    corrective pass for uncited items (CONTEXT 7.6); its result is in `task-decomposition.md` §4. A
    `rerun` is recorded as ledger event `task-rerun` with its case and reason. A failure at stage
    `uncited-items` carries the items no Task cites after the corrective pass.
11. `deterministic` **Closure edges.** After every Story's decomposition: `depscore.py
    closure-edges --dir <work> --repos <span> --out <work>/closure-edges.json` returns `{ edges[{
    from, to, reason }], summary.warnings }`: the edges the delta's `requires` relations make. A
    warning for a required item with no Task, no open bead and not done fails the run at stage
    `task-edges`, cause `other`: repo scoping places every item and task decomposition covers every
    work item, so such an item is a defect for the incident-responder, and a `blocks` dependency
    with no builder would otherwise reach beads unnoticed. `closure-edges` failing to run fails the
    run at the same stage with the cause its result carries.
12. `agent` **Cross-Story Task dependencies.** Runs only when two or more Stories have Tasks, and
    `task-deps.json` is not reusable (its `.meta.json` inputs, the `tasks-<slug>.json` files, hash
    as recorded).
    - Agent: `task-dependency-mapper` (`<plugin>/agents/task-dependency-mapper.md`).
    - Input paths: each Story's `<work>/tasks-<slug>.json`; a short listing of each Story's Task
      keys, titles and same-Story edges (keys and titles only; descriptions stay in the files); the
      `closure-edges.json` path from step 11 as "these stand, do not return them".
    - Output file: `<work>/candidates/task-deps.json` (shape in section 4), validated against that
      schema and copied to `<work>/task-deps.json` by Python (an in-process validate-and-write),
      then recorded with `artifactio.record` (inputs = the `tasks-<slug>.json` files).
    - Model and effort as used today: frontmatter `model: fable`, call `effort: medium`
      (frontmatter also `effort: medium`); the shared `fable` block switches to `opus` on
      recovery. Medium effort fits a bounded read-and-relate job; the model for `fable` agents is
      merged question Q1 in `driver-contract.md`.
    - Runs alone (after step 11).
13. `deterministic` **Write the Task edges between Stories.** `depscore.py write-all-task-edges
    --epic <id> --dir <work> --repos <span> --out <work>/task-edges/all.json`: reads
    `task-deps.json` and the closure edges, drops any edge that closes a cycle, writes the `blocks`
    edges. Result `summary{ blockers{ to: [from] }, added, removed, standing, rejected }`. Runs when
    `task-deps.json` exists (fresh or reused) or step 11 returned edges.
14. `deterministic` **Finish.** **done** = **nothingToBuild**, or no repository failed in steps 9
    and 10 and steps 11 to 13 succeeded. Run `depscore.py elaboration-finish --epic <id> --owner
    <token> [--done]`. Result `{ ok, lifecycle (non-null when marked done), summary{ tasksScored,
    epicsWritten, tasksWritten, unscored, done }, storyEdges{ ok, added[], removed[], unchanged,
    refusedStories[], reason, conflicts[], cycles[], error? } }`. Scoring runs whether or not the
    Epic is done. This flow calls no WSJF judging and no dependency-assessment workflow: Epic and
    Task WSJF judgments (sizes, values) come from the task-decomposition phase and the earlier Epic
    scoring; finish only runs the arithmetic. A Task the maker left without a valid size stays
    unscored here (merged question Q10 in `wsjf-scoring.md`).
15. `deterministic` **Remove the target**, only when step 14 marked the Epic done and `archPath`
    is set: `depscore.py arch-target-remove --arch-root <archPath> --target-dir <targetDir>
    --message "<message in section 4>"`. Result `{ ok, removed, commit, refusals[] }`. A refusal
    is reported in `targetRemoval.reason`; it does not fail the run.
16. `deterministic` **Release** (on every exit after step 3 succeeded, unless step 14 marked the
    Epic done): `depscore.py elaboration-release`. The Epic stays `in_progress` with no owner. The
    driver acts on the handback: a transient `failure.cause` (`api`, `quota`, `bd-timeout`,
    `contention`; `relay` while it has a producer, merged question Q3) backs off and redispatches,
    and the rerun redoes only the failed steps (section 8); `other` opens an incident, whose hold
    (`incidents.IncidentBook.held_ids`) keeps the Epic out of dispatch until the
    incident-responder resolves it; `requiredHumanActions` holds it for the owner. A release that
    fails with `bd-timeout` or `contention` is retried with backoff (30 s, doubling, cap 30 min,
    CONTEXT 7.4); any other failure is recorded in `lifecycle.release`, and the driver reclaims the
    Epic later (`reclaim`, no live execution owns it).
17. `deterministic` **Record the run.** Write `<work>/run.json` (the record the JavaScript emitted
    as `RUN-JOURNAL` log lines: composite, Epic, PRD id, outcome, per-phase status and decision,
    the reused/stale/task-rerun events, partial results on failure), append the ledger events the
    driver reads (`driver-contract.md` §5, merged question Q19), and return the handback with
    `detailPath` = that file.

Parallelism summary: 8a with 8b; 9 across repositories; 10 across Stories; 12 alone. Each agent
session is started by the phase that owns it, with its definition, file paths and an output file.

Relay and command-runner calls of the JavaScript, each mapped:

| JavaScript relay label | Becomes |
|---|---|
| `resolve-plugin-root-<n>` (inline Python, up to 3 attempts) | dropped; the orchestrator knows its install |
| `epic:start` | step 3, subprocess `depscore.py elaboration-start` |
| `replay:read-saved-target` | step 5, `depscore.py saved-target` (or the same function in-process) |
| `resume:recheck-<step>` (`artifactio.py plan`) | dropped; each phase checks its own recorded inputs (step 4) |
| `steps:record:<step>` (`artifactio.py step`) | in-process `artifactio.complete_step` after each step |
| `arch:delta` | step 7, `depscore.py arch-delta --save` |
| `replay:read-saved-span` | moved into the repo-scoping phase (its reuse step) |
| `epic:hold` | dropped; the driver holds (`elabstate.hold_for_person`, incident hold) |
| `beads:closure-edges` | step 11, `depscore.py closure-edges` |
| `sequence:inputs` (`artifactRevision`) | step 12, in-process sha256 of the input files |
| `sequence:accept-cross-story` (`jsonartifact.py` acceptance) | step 12, in-process schema validation and write |
| `sequence:record` (`artifactio.py record`) | step 12, in-process `artifactio.record` |
| `beads:write-all-task-edges` | step 13, `depscore.py write-all-task-edges` |
| `epic:finish` | step 14, `depscore.py elaboration-finish` |
| `arch:target-remove` | step 15, `depscore.py arch-target-remove` |
| `epic:release` | step 16, `depscore.py elaboration-release` |

## 6. Checks kept / Checks dropped

**Checks kept**
- Selection filters at entry (step 2, CONTEXT 7.8): without them an Epic with no
  `elaboration_state` (the mobile Epics, a held Epic), no WSJF score or an unmet Epic dependency is
  claimed and elaborated into beads by any door that bypasses driver selection; nothing later
  undoes the Stories and Tasks.
- `elaboration-start` refusals (`not-an-open-epic`, `epic-done`, `epic-owned`): without them two
  runs write the same Epic's beads at once, or a done Epic's Tasks are rewritten.
- The done rule (CONTEXT 7.6): without it the Epic is marked done with a repository missing its
  Story or Tasks, and selection never elaborates it again.
- A required item with no builder fails step 11 (CONTEXT 6 check test): a `blocks` dependency with
  no builder in beads is caught by nothing later.
- Target removal only after done: without it `target/<subject>/` (the input of every rerun step)
  is deleted while steps still need it.
- Architecture reuse only when the saved result is current and has its Closure (step 5): a target
  interrupted before Closure yields `delta-items.json` with no prerequisite items (no Tasks, no
  `blocks` edges for them), and a stale target yields Tasks against an outdated architecture;
  nothing later recomputes either.
- Cycle drop in `write-all-task-edges` (inside `depscore.py`): a cycle in `blocks` edges makes
  every Task on it unbuildable, and nothing later breaks it.
- Schema validation of `candidates/task-deps.json` before it is written: a malformed edge (unknown
  key, wrong kind) reaches beads otherwise; `write-all-task-edges` validates keys too, so this may
  be merged into that one check (S02).
- Section 2 hard limit: the session runner's guard around every agent step (`driver-contract.md`
  §8); this flow's own steps write nothing under arc42.

**Checks dropped**
- Plugin-root resolution and its three attempts: the orchestrator runs from its install.
- `!hasText(emitTarget)` "no tracker" refusal and the PRD body-or-path check: typed arguments from
  the driver; the PRD path is checked once in step 1.
- "Architecture result names no target directory": `arch-delta` fails on a missing directory, and
  the architecture flow returns a typed result.
- The composite-level saved-work ruling and the upstream-rerun recheck in `resumeFresh`: each phase
  checks its own recorded input fingerprints (section 8); there is no chain logic and no second
  input list.
- The misplacement check (`misplaced`), the `avoidRepos` re-dispatch, the saved-span read
  (`readSavedSpan`, `depscore.py saved-span`), the `noCode` fill for items a reused span does not
  place, and the `noImplementationWork` derivation: owned by `repo-scoping.md` (steps 2, 3 and 6).
- The flow's own hold write (`beads-contract.py metadata set ... awaiting-human-action`), its
  owner inbox write, and the rule "hold attempted means never released": the driver holds from
  `requiredHumanActions` (owner facts) and from an open incident (every other non-transient
  cause), so the redispatch loop the rule prevented cannot happen; a second writer of the same
  hold is removed (CONTEXT 7.9).
- Bounded dispatch policy (`dispatchInterruption`, `settleWorkflow`, `settleAgent`,
  `dispatchRetry`, the 5 s x 3^n backoff): replaced by the runner's structured session result and
  the driver's `breaker.py` (CONTEXT 7.4).
- `dispatchFailureCause` text matching on error messages: forbidden (CONTEXT 7.4); causes come
  from structured facts.
- `RUN-JOURNAL` chunking into 4000-character log lines: the run record is a file (step 17).
- `EXPECTED_PHASES` entries `PRD`, `Epic`, `PRD Parse` and `Run Ledger` as phases: `PRD Parse` was
  never entered; the others do no work. Phase names for the dashboard are merged question Q19 in
  `driver-contract.md`.
- The fixed 10/30/90 s hold-write backoff: the hold write is gone; the release write uses the
  CONTEXT 7.4 backoff.
- The `degraded` flag and the `DEGRADED:` headline text: the driver reads neither
  (`driver-contract.md` §4 does not list them).
- `trd.summary` passed to spec authoring: the summary is in `trd.md` (`trd-authoring.md`).

## 7. Failure causes

| Failure point | Stage | Cause | Retry reasonable? |
|---|---|---|---|
| Typed input missing (Epic id, beads repo, PRD path) | `input` | `other` | No: the same input fails the same way. |
| Selection filter or `elaboration-start` refusal | `epic-lifecycle` (+ `refusal.code`) | none (a refusal, not a failure) | No; the driver waits or holds until the bead changes. |
| `depscore.py` / `bd` exit with a `bd` lock or timeout | the step's stage | `bd-timeout` or `contention`, from the field the script's JSON result carries (merged question Q5 in `driver-contract.md`) | Yes, backoff 30 s doubling, cap 30 min. |
| An agent session ends on an API error or quota | the phase's stage | `api` / `quota`, from the session's structured result (stream event / exit status), never from text | Yes, through `breaker.py`. |
| Architecture `owner-concern` / `no-arch-path` | `requires-human-action` | none (owner facts) | No: the driver holds for the owner. |
| Other architecture failure | `architecture` | the phase's `failure.cause` | Per that cause. |
| Repo scoping fails (incl. placement findings left after its corrective pass) | `repo-scoping` | the phase's cause | Per cause; `other`: incident-responder. |
| TRD authoring fails | `trd-authoring` | the phase's cause | Per cause. |
| One repository's detailing or spec fails | per repository: the phase's stage; run: `repositories-incomplete` | per repository from its phase's `failure.cause`; the run's cause is transient only when every failed repository's is | Transient: yes, rerun only the failed steps. Otherwise: incident-responder. |
| One Story's decomposition fails (incl. `uncited-items` after the one corrective pass) | per repository: the phase's stage; run: `repositories-incomplete` | as above; `uncited-items` is `other` | `uncited-items`: no, it already had its one corrective pass. |
| No repository produced a Spec, or no Story produced Tasks (and not nothingToBuild) | `repositories-incomplete` | combined, as above | as above. |
| `closure-edges` fails, or warns of a required item with no builder | `task-edges` | from its result; a warning is `other` | Contention: yes. A warning: no, incident-responder. |
| task-dependency-mapper ends without an accepted file | none; `crossStoryDependencies.reason` set, the run continues | the session's cause | Transient: yes, on the next dispatch (the step is not recorded). Otherwise no. |
| `write-all-task-edges` fails | `task-edges` | from its result | Contention: yes. |
| `elaboration-finish` fails | the Epic is not done; the run is `ok:true` today with a "scoring did not run" headline (Open question 1) | from its result | Contention: yes. |
| `arch-target-remove` refused | none; `targetRemoval.reason` | `other` | No. |
| Release write fails | recorded in `lifecycle.release` | `bd-timeout` / `contention` / `other` | `bd-timeout`/`contention`: yes, with backoff; else no (the driver reclaims). |
| Unexpected exception | the current phase's name | `other` | No: incident-responder. |

Every failure returns `failure: { stage, cause, repositories: [{ repository, stage, cause,
headline }] }`. `relay` is produced today only by relay plumbing; after the rewrite nothing in this
flow produces it (merged question Q3 in `driver-contract.md`).

## 8. Resume points

A step is reused when its saved files exist and every input recorded in their `.meta.json` hashes
as recorded now. A reused step starts no agent session. Step ids are those of
`artifactio.STEP_ORDER`, recorded in `STEPS.md`. Each phase's input list is in its own spec; this
table does not restate it.

| Step id | Saved files | Inputs that fingerprint it | A rerun after it redoes |
|---|---|---|---|
| (claim) | none | none | step 3 again; idempotent: the same owner token resumes an `in_progress` Epic |
| `architecture` | `architecture/` deliverables incl. `target.json` | `architecture.md` §8 | nothing in architecture when step 5's reuse test passes; otherwise the architecture flow's own resume points decide |
| (items) | `delta-items.json` | none: recomputed every run from `target/<subject>/` | always recomputed; costs no session |
| `repo-scoping` | `repo-scoping.json` | `repo-scoping.md` §8 | nothing when unchanged |
| `trd` | `trd.md` | `trd-authoring.md` §8 | nothing when unchanged |
| `recon:<slug>` | `recon-<slug>.json` | `prd-reconciliation.md` Resume points | nothing when unchanged |
| `spec:<slug>` | the spec documents, `story-<slug>.json` | `spec-authoring.md` Resume points | `depscore.py write-story` from the saved files (idempotent by `elab_key`), no agent |
| `tasks:<slug>` | `tasks-<slug>.json` | `task-decomposition.md` §8 | the missing Task beads only (CONTEXT 7.5 rule, owned by `task-decomposition.md`) |
| (closure edges) | `closure-edges.json` | none: recomputed | always recomputed; costs no session |
| `task-deps` | `task-deps.json` | every `tasks-<slug>.json` | `write-all-task-edges` from the saved file, no agent |
| (finish) | none | none | `elaboration-finish` again; idempotent |
| (target removal) | none | none | `arch-target-remove` again; `removed:false` when already gone |

A failed repository's steps are not recorded, so the next dispatch redoes exactly those. Setting
stale work aside is done by the phase that owns the files: the architecture phase moves its own
stale work aside (`archrevision.check`, `architecture.md` step 2); every other phase overwrites its
own outputs when it reruns. Whether the driver's `artifactio.set_aside_stale` keeps running before
the dispatch is merged question Q6 in `driver-contract.md`. The saved architecture surveys of
`ssbd-mb689`, `ssbd-hdqid` and `ssbd-guuuz` (CONTEXT 7.13) are reused through the architecture
phase's resume points when their inputs are unchanged.

## 9. Owner rules that apply

- **7.4 Retries:** structured causes only (section 7); transient causes release the Epic for a
  later rerun of the failed steps; succeeded steps are never redone (section 8); the same step with
  nothing changed is not retried but diagnosed (the driver's incident for the incident-responder).
- **7.5 Rerunning Task creation:** delegated to the task-decomposition phase; this flow passes the
  stale reason and records `task-rerun`.
- **7.6 Done:** step 14's done rule; the one corrective pass is inside the task-decomposition
  phase, and its leftover `uncitedItems` fail that repository. "Epic closed" is never used: done is
  `elaboration_state=done` and the Epic stays open.
- **7.7 Three-case architecture model:** `architectureChange` (`none`, `new`, `partial`) from
  `arch-delta` drives `deltaDir`; every case yields build items (view items and/or
  `implementationWork` gaps), so something always reaches the TRD and the Tasks unless the
  validated assessment says no implementation work.
- **7.8 Selection filters:** step 2 refuses an Epic with no `elaboration_state` (the mobile Epics
  `ssbd-cb6i4`, `ssbd-kfihs`, `ssbd-mx3vn` among them), no WSJF score, or an unmet Epic dependency,
  whichever door started the run.
- **7.9 Who gets asked what:** only `owner-concern` and the missing architecture path become
  `requiredHumanActions` (the driver writes the owner inbox and the hold); every other failure goes
  to the incident-responder through the driver's incident.
- **7.10 Repositories:** the repo-scoping phase owns placement through the polyrepo-steward.
- **7.11 Deterministic over agentic:** only step 12 and the phases' reasoning steps are agents.
- **7.13 Saved work:** the architecture resume point reuses the existing surveys.
- **Hard limits (CONTEXT 6):** no arc42 section 2 writes (the session runner's guard); no
  destructive operations beyond the target folder removal after done, and the unstarted-Task
  deletion inside task decomposition.

## 10. Open questions

1. **[S02] `elaboration-finish` failure.** Today a failed finish leaves the Epic not done but
   returns `ok:true` (headline "Scoring did not run"). Should it be a failure with its structured
   cause, so the Epic is released for a retry? The done rule suggests yes.
2. **[S02] Task-deps when one Story is reused and another changed.** The `task-deps` step is
   fingerprinted by all `tasks-<slug>.json` files; when one Story's Tasks are recreated, all
   cross-Story edges are derived again. Acceptable, or derive only the edges touching the changed
   Story?
3. **[S02] Pass-through inputs (merged Q13).** The driver never sends `prd.body`, `dependencies`
   or `accessPatterns` (nor `spec`). Drop each input, or add a producer? Asked also in
   `prd-reconciliation.md` and `spec-authoring.md`, which point here. Whether `prd.body` survives
   also depends on the doors (merged question Q12 in `route-elaboration.md`).
4. **[S02] The "nothing to build" record (CONTEXT 7.6, 7.12).** No artifact, bead field or
   metadata key records "nothing to build" today, for an empty span or for one span repository
   with no work items, and `observe.py` shows an Epic "Done" only with a TRD, a Story and a Task
   (`driver-contract.md` §7), so a correctly done Epic is shown as not done. S02 defines one record
   (for example an Epic metadata key listing the span repositories with nothing to build and the
   reason), names its one writer (this flow's step 14 is the natural place), and S05 makes
   `observe.py`'s Done rule accept it. Related: `spec-authoring.md` Open question 1 (whether such
   a repository gets a Story).
- Misplacement after the corrective pass: merged question Q11 in `repo-scoping.md`.
- The `relay` cause: merged question Q3 in `driver-contract.md`.
- The task-dependency-mapper's `fable` model: merged question Q1 in `driver-contract.md`.
- Inline PRD text and the manual doors: merged question Q12 in `route-elaboration.md`.
- Closure-edge warnings: settled (step 11 fails on them; S01h finding 24).
- Owner inbox writer: settled (the driver writes it from `requiredHumanActions`; S01h findings 11
  and 16).
