# Driver contract for the Epic pipeline (elaboration lane)

Step S01g. What the driver at `<control>/ops/sdlc-automation` (`<driver>`) sends to an elaboration
dispatch, what it reads back, which ledger events and phase names its readers depend on, and how it
attributes cost to a run. Extracted from the driver's Python on 2026-10-09; code comments were not
used. Everything here describes **today's** contract, which the Python orchestrator must either honour
or replace in S05 (open items: QUESTIONS.md).

Paths below are relative to `<driver>` unless absolute.

This file is a boundary contract, not a workflow spec (PLAN S01g names it apart from the workflow
specs), so it does not use the ten S01 template headings. It carries the template's last two
(requirements that apply, open items) as §9 and §10, and §8 holds the session-runner rules every
Epic flow cites. Open items, including those shared by every Epic flow, live only in
`QUESTIONS.md`.

## 1. Purpose

The elaboration lane selects one Epic per slot and dispatches the `prd-to-spec` composite for it.
Today the dispatch is a headless Claude Code session whose only job is to call the Workflow tool with
`agent-teams-workforce:prd-to-spec` and print one `HANDBACK {json}` line. The driver then turns the
handback into an `Outcome`, writes ledger events, holds or backs off the Epic, files finished documents
in the vault, and records the run's token cost. The Epic pipeline's own behaviour is specified in
`<orch>/specs/epic/prd-to-spec.md` and the per-workflow specs beside it; this file covers only the
boundary with the driver.

## 2. Selection facts the driver decides before dispatch

From `selection.py` `_epic_candidates`, `elabstate.py`, `workitems.py`:

- Candidate: bead type `epic`, not closed, not excluded (held/settled), no unmet prerequisite
  (`elabstate.unmet_blockers`: a `tracks` or `blocks` edge to an open Epic whose
  `elaboration_state` is not `done`, or to an open non-Epic), `elabstate.candidacy` workable, and a
  WSJF score present (`index.wsjf_of`). One Epic per PRD stem per pass.
- `elabstate.candidacy`: `elaboration_state=ready` -> workable; `in_progress` -> workable only when no
  live execution owns it (`itemownership.reason`), and then marked `reclaimed`; `done` -> not
  workable; no state with `elaboration_state_cause=awaiting-human-action` -> held for a person; no
  state otherwise -> "PRD still being authored", not workable.
- A PRD file must resolve for the Epic (`workitems.find_prd`), or the Epic is skipped with
  `no PRD`.
- Bead metadata keys the driver reads and writes for the lifecycle: `elaboration_state`
  (`ready` | `in_progress` | `done` | empty), `elaboration_state_at`, `elaboration_state_cause`
  (`decomposed-into-tasks`, `human-ruling`, `awaiting-human-action`), `elaboration_state_owner`.
  The driver writes them only for a person hold (`elabstate.hold_for_person`: state empty, cause
  `awaiting-human-action`, owner empty) and from `elabmark.py` (owner's CLI, cause `human-ruling`).
  `in_progress` and `done` are written by the workflow (`depscore.py elaboration-start` /
  `elaboration-finish`, see `<orch>/specs/epic/prd-to-spec.md`).

## 3. What the driver sends (`extra_args` for `prd-to-spec`)

Built by `workitems.elaboration_args`, then extended by `lane.py` `_work_in_scope` and
`headless.py` `_dispatch_with_recovery` / `_dispatch_session`. Final keys, with their source:

| Key | Value | Source |
|---|---|---|
| `prd` | `{id: <PRD file stem>, title: <Epic title or stem>, path: <absolute PRD path>}` | `workitems.elaboration_args` |
| `epic` | `{key, id: <epic bead id>, type: "epic", title, prdRef: <PRD path>}` | `workitems.epic_ref` |
| `beadsRepoPath` | control repo main working tree | `beadsio.main_repo_path()` |
| `skillspokeRoot`, `projectRoot` | `$SKILLSPOKE_ROOT` or the parent holding `skillspoke-docs` | `artifactio.skillspoke_root()`, `atw.elaboration_args` |
| `artifactScript` | absolute path of `<driver>/artifactio.py` | `artifactio.recorder_path()` |
| `archPath` | `<vault>/docs/tech/architecture` | `workitems.arch_args` |
| `designSystem` | `{packagesDir, mocksDir?, shellsDir?}` from `$ATW_DESIGN_PACKAGES_DIR` (or vault default) and `CUSTOMIZABLE_DESIGN_SYSTEM_MOCKS_DIR` / `_SHELLS_DIR` (env or `.claude/settings*.json` `env`) | `workitems.design_system_args` |
| `trdPath` | `<prd dir>/../trds/<stem>-trd.md`, only when the PRD sits in a folder named `prds` | `workitems.trd_path_for` |
| `reclaim` | `true` when `elaboration_state=in_progress` with an owner and no live execution owns it | `workitems.reclaim_args` |
| `pluginRoot` | the installed plugin directory the pipeline runs | `pluginversion.running_dir()` |
| `resume` | `{root, dir, epicId, completed: [step...], stale: [{step, what, reason}], names?: {architecture: [...]}}` from the Epic's working folder (`STEPS.md` plus `.meta.json` input records); when the Epic is `ready`, the folder is retired once first (`artifactio.retire_once`) and stale files are set aside (`artifactio.set_aside_stale`) | `workitems.with_artifact_plan`, `artifactio.dispatch_resume` |
| `owner` | the execution id (prd-to-spec only) | `workitems.lifecycle_owner` (lane) |
| `executionId`, `supervisorInvocationId` | identity of this execution | lane; **host-only**, stripped from the prompt (`execidentity.HOST_ONLY_ARGS` also strips `dispatchAttemptId`, `predecessorExecutionId`) |
| `fableAgentTypes`, `fableRecovery` | Fable model recovery inventory and cutoffs | `headless._dispatch_with_recovery` |
| `relayExecutionId`, `relayRequestDir` (`<run>.scratch/relay-requests`), `relayCaptureScript` (`<plugin>/scripts/portfolio/relaycapture.py`) | relay plumbing for the command runner | `headless._dispatch_session` |
| `beadId` | the Epic id | `prompts.dispatch_prompt` |

The prompt (`prompts.dispatch_prompt`) drops `prd.body` / `epic.description` over 20 000 chars and
sheds `prd.body`, `epic.description`, `brd` to fit an 8 000-byte budget. Today's `elaboration_args`
sends none of those three keys.

Session environment (`headlessenv.child_env`, `atw.values`): `ATW_PROJECT_ROOT`, `ATW_ARTIFACT_SCRIPT`,
`ATW_PRD_EPIC_SYNC`, `ATW_PRD_EPIC_VERIFY`, `ATW_FLEET_DIR`, `ATW_CONTROL_REPO`, `ATW_ARCH_PATH`,
`ATW_DESIGN_PACKAGES_DIR`, `ATW_PRD_DIR` (each only if not already set), `TMPDIR`/`TMP`/`TEMP` =
`state/runs/<run>.scratch`, `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0`. Session: cwd = control repo
(`prd-to-spec` is not a target-repo composite), `claude -p --output-format stream-json --verbose
--permission-mode bypassPermissions`, `--disallowedTools` list in `headlessenv.DENIED_TOOLS`,
`--strict-mcp-config` with a minimal MCP config, model `opus` unless the plugin inventory marks the
composite `sessionModel: sonnet`, timeout 7 200 s (`DEFAULT_DISPATCH_TIMEOUT`).

Run files per dispatch (`headlessenv.run_paths`):
`state/runs/<bead>-<composite>-<YYYYMMDDTHHMMSS>-<pid>-<hex6>.{out,err,scratch}`, plus
`state/runs/<same stem>.cost.json` and `state/phases/<same stem>.json` (run record, `phaserec.py`).

## 4. What the driver reads back (`Handback`, `dispatch.py`)

The handback comes from, in order of preference: the completed workflow's own `result` object read
from the session's harness record
(`~/.claude*/projects/<cwd-slug>/<session>/workflows/wf_*.json`, `status == "completed"`,
`workflowName` ending `:prd-to-spec`; `runjournal.workflow_result` ->
`handbackio.handback_from_result`), else the session's `HANDBACK {json}` line
(`handbackio.parse_handback`), else a driver-made failure (`no-handback`, `timeout`,
`spawn-failed`, `shutdown`, ...).

Workflow result keys mapped into `Handback`: `ok`, `stage`, `headline` (or `error`), `detailPath` ->
`composite_detail`, `beadsEmitted`, `lifecycle.done` -> `lifecycle_done`, `refusal {code, reason}`,
`requiredHumanActions` (strings or objects with `proposedName|name|action|summary`), `artifacts
{dir, epicId, phases: {<name>: "passed"|"reused"}, filing: {<file>: <vault path>}}`, `failure {stage,
cause, repositories: [{repository, stage, cause, headline}]}`, `dispatchFailures [{phase, label,
message|note}]` (folded into the headline and into `failure_origin`). The driver adds
`detail_path` (the `.out` run log) and `session_id`, and sets `composite_detail` to the persisted run
journal `<control>/.claude/workflow-runs/<composite>-<runId>.jsonl` when the workflow gave none
(`runjournal.persist_session`, built from `RUN-JOURNAL` log lines of the workflow).

### Fields the elaboration lane actually uses

Readers: `healing.py` (turns a handback into an `Outcome`), `failurecause.py`, `refusal.py`,
`humanq.py`, `breaker.py`, `headless.py`; the files the plan names (`lane.py`, `outcomes.py`,
`elabstate.py`, `elabmark.py`, `failures.py`, `incidents.py`) read no `handback.` attribute directly:
`lane.py` reads the `Outcome`, and `outcomes.py` / `failures.py` read the ledger `handback` event.

| Field | Used for |
|---|---|
| `ok` | completed vs failed routing (`healing._resolved`); quota clear; `runcost` `completed` |
| `stage` | `interrupted`/`shutdown` -> halted; `requires-human-action` -> needs person; `epic-lifecycle` + `refusal.code` -> refusal; `account-quota-exhausted` -> pause; environment stages (`no-handback`, `session-quit-early`, `budget-exhausted`, `spawn-failed`, `session-exit`, `no-workflow-tool`, `unparsable-handback`, ...) -> `failure_origin=environment`; fallback incident stage |
| `failure.stage`, `failure.cause`, `failure.repositories` | the structured cause (`api`, `quota`, `bd-timeout`, `relay`, `contention`, `other`; `failurecause.stated_cause`); transient causes back off and retry, `other` opens an incident with signature `<bead>|<stage>|<cause>` and evidence `repositories` |
| `failure_origin` | `environment` vs `work`, recorded on the `handback` event; gates quota clearing |
| `headline` | Outcome headline; quota/API pause detection (`breaker.pause_of`: Fable wall mark, usage-limit text and reset time); the human need when no action is named |
| `refusal.code`, `refusal.reason` | `WAIT_CODES` (`upstream-not-elaborated`, `epic-owned`, `epic-authoring`, `epic-unscored`, `epic-state-unknown`, `no-tracker`) -> wait, hold until the Epic's tracker facts change (`no-tracker` -> backoff as `bd-timeout`); `PERSON_CODES` (`epic-done`, `not-an-open-epic`, `no-epic`) -> human-action log |
| `required_human_actions` | human-action log entries, which the supervisor's `human_log` writes to the owner inbox (`ownerinbox.Writer`, `$ATW_OWNER_INBOX`); any entry also means "needs a person" -> Epic held (`lane._person_needed` -> `elabstate.hold_for_person`), with the restore command (`elabstate.restore_command`) logged. The driver is the one writer of this hold and this inbox entry; the Epic flows only return `requiredHumanActions`, and only for owner facts (§9). A non-transient failure with no `requiredHumanActions` opens an incident instead, and the open incident keeps the Epic out of dispatch (`incidents.IncidentBook.held_ids`) until the incident-responder resolves it |
| `artifacts` | **only after** the lane reads `elaboration_state=done` from the tracker: `artifactio.file_in_vault(<working dir>, phases, prd, trd_target)` files the TRD (target from `artifacts.filing["trd.md"]` or `trdPath`) and Spec documents in the vault and writes bead metadata `artifact_trd_vault_path` (Epic) and `artifact_spec_vault_path`, `artifact_spec_data_model_vault_path`, `artifact_spec_criteria_vault_path` (each Story, matched by its `artifact_spec_path` file name) |
| `detail_path`, `composite_detail`, `session_id` | incident evidence; human-action detail paths; Fable recovery (`session_id`) |
| `beads_emitted`, `lifecycle_done` | recorded on the `handback` event only; read by `outcomes.py` to word the ending ("Finished: N Story and Task beads written" when `lifecycleDone`, else "unfinished") |

Not used by the elaboration lane (recorded on the `handback` event or unused): `deployed_to_dev`,
`smoke_passed`, `settled`, `pr_url`, `settle_failed`, `landing_stage`, `deploy_iteration`
(build/deploy), `version` (repair), `mechanism` (story deploy), `evidence`, `cds_audit` (build),
`incident` (incident-responder composite only).

"Elaboration done" is **not** taken from the handback: after every `prd-to-spec` dispatch the lane
re-reads `elaboration_state` from the tracker (`lane._elaboration_done`); only `done` triggers the
`elaboration_state` event and vault filing.

## 5. Ledger events and phase names the readers depend on

All events: `{ts, type, beadId, ...}` appended to `state/ledger.jsonl` (`ledger.append`; types in
`ledger.EVENT_TYPES`).

Events written around an elaboration dispatch, with the fields readers use:

- `dispatched`: identity (`executionId`, `dispatchAttemptId`, `predecessorExecutionId`,
  `executionContinued`, `resumesAttempt`, `supervisorInvocationId`), `composite`, `lane`, `reason`,
  `extraArgs`, `beadType`, `title`, `parentEpic`, `parentId`, `parentType`, `trackerUnblocked`,
  `subject` (PRD stem).
- `phase`: `{composite, phase, ...extra}`. Producers: (a) the driver: `headless session starting`
  (extras `runLog`, `sessionCwd`, `sessionCwdReason`, `omittedArgs`, `sessionModel`,
  `resumedSessionId`, `resumedWorkflowRunId`, plugin attestation), `interrupted by supervisor
  shutdown`, `interrupted in flight`, `interrupted before dispatch`, `held before dispatch (quota
  wall)` (`lane.QUOTA_HELD_PHASE`; older ledger lines read `(quota park)`); (b) the workflow: the `phaseTitle` of each workflow agent at its start, relayed through the
  session's `PHASE <title>` line. Workflow phase texts seen for `prd-to-spec`: its own `meta.phases`
  titles (`Epic Lifecycle`, `Architecture`, `Repo Scoping`, `TRD Authoring`, `Spec Authoring`,
  `Task Decomposition`, ...) and child-workflow titles of the form
  `▸ agent-teams-workforce:<child>` with ` #N` for repeats.
- `verdict`: `{composite, phase, label, verdict (reject|loop|escalate|pass|accept|""), detail}` for any
  agent whose result preview contains `"verdict"` or `"admissible"`.
- `handback`: `{composite, ok, stage, headline, failureOrigin, failureCause, failure, incidentReport,
  paused, pauseKind, pauseReason, resumeAt, resumeAtEpoch, detailPath, compositeDetailPath,
  deployedToDev, smokePassed, settled, prUrl, settleFailed, landingStage, deployIteration,
  beadsEmitted, lifecycleDone, refusal, requiredHumanActions, attempt, tier, childSessionId}`; a
  dispatch that raised writes `stage: "dispatch-error"`, `failureCause: "other"`.
- `elaboration_state`: `{lane, composite, elaborationState: "done", elaborationCause:
  "decomposed-into-tasks", writtenBy: "prd-to-spec", ok: true}`.
- `elaboration_wait`: `{lane, composite, code, retry: "later-pass"|"person"}` on a refusal.
- `refusal_hold` / `refusal_released` / `hold_read_failed`: holds until the Epic's tracker facts
  (`elabstate.lifecycle_facts`: its `elaboration_*` and `wsjf*` metadata, its prerequisites' states,
  closed) change.
- `repeat_backoff` (`stage`, `repeats`, `cause`, `headline`), `human_action`, `incident_opened` /
  `incident_resolved` / `incident_retry`, `quota_tripped` / `quota_cleared`, `execution_stopped`,
  `attempt_reopened`, `run_started` / `run_died` / `run_finished`, `heartbeat`.

Readers and what they need (from an AST scan of `event.get(...)` / literal event types):

- `outcomes.py`: `dispatched`, `phase`, `handback`, `run_started`, `run_died`, `attempt_reopened`;
  a `phase` counts as a phase name only when its text starts with `▸` or `>` (the
  `agent-teams-workforce:` prefix and ` #N` are stripped), so the phase shown for an Epic attempt is
  the child-workflow name; endings come from `ok`, `stage`, `lifecycleDone`, `beadsEmitted`,
  `refusal`, `paused`, `pauseKind`, `pauseReason`, `resumeAt`.
- `observe.py` (served by `dashboard.py`): `dispatched`, `phase`, `verdict`, `handback`,
  `elaboration_state`, `execution_fresh`, `execution_stopped`, `repeat_backoff`, `human_action`,
  `build_state`, run and keeper events. For an Epic it also reads, outside the ledger:
  the tracker export (`elaborationState`, `elaborationCause`, Story and Task counts, TRD filed) to
  decide "Done" (`done` needs state `done`, a cause in `decomposed-into-tasks|human-ruling`, a TRD,
  a Story and a Task); `artifactio.plan(<bead>)` over `artifacts/<bead>/` (`STEPS.md`, `.meta.json`)
  for accepted/stale steps and the resume phase among `architecture`, `repo-scoping`, `trd`; relay
  step files under `artifacts/relay/<bead>/`, `artifacts/<bead>/relay/` and
  `artifacts/<bead>/<phase>/relay/` (names `<n>-<step>.json`, `round<N>-<role>-...`) to show
  architecture rounds; and the live phase from the session's workflow journal
  (`attemptview.steps_of` over `phaserec.expected_phases`).
- `attemptview.py`, `runview.py`: `dispatched`, `phase`, `verdict`, `handback`, `run_*`, plus the
  harness workflow folders `<session>/subagents/workflows/wf_*/` (`journal.jsonl`,
  `agent-<id>.meta.json`) and the run records in `state/phases/`.
- `phaserec.expected_phases(composite)` reads the `phases: [{title: ...}]` list out of the installed
  plugin's `workflows/<composite>.js` meta. Deleting `prd-to-spec.js` removes the Epic's expected
  phase list.
- `failures.py`: `handback` (`ok`), `run_started`, `trigger_dispatch`; `incidents.py`:
  `incident_*` events.

## 6. Cost attribution (`runcost.py`, `harnesspaths.py`)

- After each dispatch `headless._account` calls `runcost.record_run(bead, composite, out_path, lines,
  handback, identity)` and folds the record into `state/budget.json` (`runbudget.fold_run`;
  `prd-to-spec` opens an `epic`-kind budget item).
- Session id: the first `[session] <id>` line the driver writes into the `.out` log from the stream's
  `session_id`, or any `"session_id": "<uuid>"` in it (`runcost.session_id_from`).
- Transcripts: `<CONFIG_DIR>/projects/<slug>/<session>.jsonl` (host) and every `*.jsonl` under
  `<CONFIG_DIR>/projects/<slug>/<session>/` (subagents, workflow agents), where `<slug>` is the
  session cwd with `/` and `.` replaced by `-` (`harnesspaths.project_dir`), falling back to a scan of
  all project folders (`runcost.session_project`).
- Measure: every `assistant` event's `message.usage` (`input_tokens`, `output_tokens`,
  `cache_creation_input_tokens`, `cache_read_input_tokens`), deduplicated per `requestId` (else
  `uuid`) by taking the max of each component; weighted = input + 5 x output + 1.25 x cacheCreate +
  0.1 x cacheRead. Broken down by phase (`workflowPhase` in each agent's `.meta.json`; host transcript
  = `(host session)`) and by role (`description` prefix plus `agentType` from `.meta.json`).
- Record: `state/runs/<run stem>.cost.json` with `beadId`, `composite`, `sessionId`, `role`
  (`primary`|`repair`), `runLog`, `startedAt` (from the file-name stamp), `recordedAt`, `completed`
  (`handback.ok`), `stage`, `weights`, the four totals, `weighted`, `sessions`, `requests`, `models`,
  `unknown`, `note`, `phases`, `roles`, plus identity `executionId`, `supervisorInvocationId`.
- Aggregation: `runcost.records` scans `state/runs/*.cost.json`, keeps the newest record per
  `sessionId`; `totals_by_bead`, `for_bead`, and `subtree_total([epic, *task ids])` feed the
  dashboard; `KNOWN_COMPOSITES` = `dispatch.COMPOSITE_PHASES` keys + `probe` + the former trigger
  composites.
- `harnesspaths.session_dir_for` finds a dispatch's session folder by the marker
  `dispatching bead <id> to` in the first 64 KiB of a transcript born between 30 s before and 120 s
  after the dispatch start, in the project folders of the cwds recorded for the bead.

## 7. Contracts the Python orchestrator breaks or must replace

Facts, for S02 and S05 to decide on:

- One run today = one host session; cost, phases, verdicts and the live phase are all read from that
  one session's transcript tree and its `subagents/workflows/wf_*` folders. A Python run that starts
  several agent sessions directly has no host session, no Workflow journal, no `PHASE` lines and no
  `HANDBACK` line.
- `phaserec.expected_phases` and `outcomes._phase_name` depend on the `.js` meta and the
  `▸ agent-teams-workforce:<child>` phase titles.
- `observe.py` relay-step views read `artifacts/**/relay/` files that the relay produces.
- `extra_args` keys `relayExecutionId`, `relayRequestDir`, `relayCaptureScript`, `fableAgentTypes`,
  `fableRecovery`, `pluginRoot` exist for the Workflow runtime and the command runner.
- Some of today's classification reads text: `breaker.pause_of` parses the headline for the usage
  wall and its reset time, `handbackio._died_of_outage` and `step_defect_origin` match output and
  `dispatchFailures` message text, and `headless._resume_unavailable` matches headline phrases.
  CONTEXT 7.4 says causes are never classified by matching error text.
- `observe.py` shows an Epic "Done" only with state `done`, a TRD, a Story and a Task. That rule
  stays as it is: every Epic that reaches elaboration gets Stories and Tasks (CONTEXT 7.6), so no
  "nothing to build" record exists for it to accept.

## 8. Session-runner rules every Epic flow cites

**Section 2 guard (hard limit, CONTEXT 6).** Every agent session of every Epic flow (the
composite's own step, every phase, and the owner-run portfolio flows) runs inside one guard, which
S02 places in the session runner. No flow keeps a copy of its own.

1. Before the session: `archstate.snapshot_constraints(<arch>, keep=True)` (today `depscore.py
   arch-constraints --keep`): the digest of `$ATW_ARCH_PATH/arc42/02-architecture-constraints/`,
   its git status, whether it exists, and a kept copy.
2. After the session ends, whatever its outcome: snapshot again.
3. Any difference in digest, existence or git status: `archstate.restore_constraints(<arch>,
   kept)` (today `depscore.py arch-constraints-restore --kept <copy>`), then fail the step at stage
   `constraints-written`, cause `other` (incident-responder; no retry).
4. A snapshot or restore that itself fails fails the step at its stage, cause `other`.

It stops wrong output nothing later catches: every agent with Write or Edit (the polyrepo-steward,
`prd-reality-reconciler`, the architecture writers and maintainer, `trd-author`, the four spec
makers, `task-decomposer`, `task-dependency-mapper`, `wsjf-scorer`, `epic-sequencer`) can write
anywhere, and no later step re-reads section 2. How the guard spans sessions that run in parallel
(the per-repository detailing and spec chains, the architecture reviewers) is S02's to settle.

**Input record.** Every Epic flow records a saved result's inputs with `artifactio.record` as
`<result>.meta.json` (`inputs[]` of `{path, kind, sha256}`; kinds `file`, `dir`, `missing`,
`git-main`, `arc42-revision`, `arch-views`), and a result is reused when every recorded input hashes
as recorded. The one exception is the architecture survey's existing seal
(`survey.json.baseline-inputs.json`, CONTEXT 7.13). The driver's `artifactio.plan` already reads
`.meta.json`, so this is the format; each flow's own spec is the single source of its input list.

## 9. Requirements that apply

- **7.18 Entry point.** The owner starts the pipeline only with `python3
  ops/sdlc-automation/keeper.py`; the elaboration lane is the only door into `prd-to-spec`. No
  plugin command (`/start-prd`, `/work-bead`) dispatches it; S08 deletes both.
- **7.6 and 7.17 at the boundary.** The lane's "Elaboration done" read (`elaboration_state=done`)
  now means Stories, Tasks, Task edges and Task WSJF scores all exist; the Epic's own WSJF is not
  rewritten by elaboration.

- **7.12 Dashboard truth.** "Running" only from a live lease and a verified session process. Today
  one Epic run is one host session, whose process and lease the driver verifies. A Python Epic run
  is the orchestrator's process for the Epic, holding the Epic's lease (`elaboration_state_owner`
  and the driver's execution identity), plus at most a few agent sessions at a time. The Epic is
  shown running only while that lease is live and that process is verified; an agent step is shown
  running only while its session's process is verified. A phase or step name shown comes only from
  an event the run wrote (no inferred phases), and no counter is shown that the records cannot
  compute (no "Tasks built" style totals). How the run unit is recorded is an open item in
  QUESTIONS.md.
- **7.4 Structured causes.** The text-based classifications listed in §7 (`breaker.pause_of`,
  `handbackio._died_of_outage`, `step_defect_origin`, `headless._resume_unavailable`) do not carry
  into the Python run: the runner sets `api`, `quota`, `bd-timeout`, `contention`, `other` from the
  session's structured result (exit status, stream events), exception types and script JSON
  fields. The remaining choices are open items in QUESTIONS.md.
- **7.9 Who gets asked what.** Only owner facts become `requiredHumanActions`: the architecture's
  `owner-concern` (business or section 2 conflict), a missing architecture path (`no-arch-path`),
  and credentials the run cannot hold. The driver alone writes the hold and the owner inbox from
  them (§4). Every other failure is `failure.cause`; `other` opens an incident for the
  incident-responder, never an owner action.
- **7.2** Only the owner runs the pipeline; nothing in this contract is run as a test.
- **7.8** Selection filters stay in `selection.py` / `elabstate.py` (§2), and only there: the
  driver is the only door, so `prd-to-spec` does not repeat them.

## 10. Open items

See QUESTIONS.md
