# Driver contract for the Epic pipeline (elaboration lane)

Failure handling: bounded transient retries and quota pauses remain. An ordinary item failure is recorded and excluded from selection for the current invocation; other eligible items continue. Setup, code, schema, and runtime type defects stop new dispatch, preserve the original diagnostic, and let current paid steps finish. Named within-step corrective passes remain bounded content work; failed runs do not dispatch repair or diagnosis agents.

Step S01g. What the driver at `<control>/ops/sdlc-automation` (`<driver>`) sends to an elaboration
dispatch, what it reads back, which ledger events and phase names its readers depend on, and how it
attributes cost to a run. Extracted from the driver's Python on 2026-10-09; code comments were not
used. Everything here describes **today's** contract, in which the elaboration lane dispatches the
Python orchestrator (open items: QUESTIONS.md).

Paths below are relative to `<driver>` unless absolute.

This file is a boundary contract, not a workflow spec (PLAN S01g names it apart from the workflow
specs), so it does not use the ten S01 template headings. It carries the template's last two
(requirements that apply, open items) as §9 and §10, and §8 holds the session-runner rules every
Epic flow cites. Open items, including those shared by every Epic flow, live only in
`QUESTIONS.md`.

**Where each contract is defined.** This file describes behaviour at the boundary and names the
constants of each contract; it never restates a contract's keys, fields or allowed values. The
one place of each:

| Contract | Defined only in |
|---|---|
| Driver surface: the environment variables, the session's denied tools, the termination grace, the rate-limit event, and the driver modules and attributes the plugin imports (`DRIVER_DIR_PARTS`, `DRIVER_MODULES` and the `HeadlessEnvironment`, `FableWall`, `Breaker` and `ChildProcess` protocols) | the pipeline-contracts skill, `<plugin>/skills/pipeline-contracts/SKILL.md` (`schemas/driver-surface.schema.json`, generated `scripts/driver_surface_types.py`); the driver loads it through `<driver>/driversurface.py`; the plugin reaches the driver modules only through `<orch>/core/driver_contracts.py` `driver_module()` |
| Dispatch arguments and the `run.py` command line | `<driver>/dispatchargs.py`; the plugin reaches it through `<orch>/core/driver_contracts.py` `dispatch_arguments()`. `dispatch_arguments()` returns the frozen dataclass `DispatchArguments`, built from the module and type-checked name by name (a second, hand-written definition of the names; open item, QUESTIONS.md) |
| Orchestrator handback, its failure, refusal and artifact report, its class, stage and cause vocabularies, and the `prd-to-spec` phase list | `<orch>/core/handback_contract.py`; the driver loads it through `<driver>/handbackcontract.py`. The lifecycle refusal stage and codes are driver-local in `<driver>/refusal.py` (`STAGE`, `WAIT_CODES`, `PERSON_CODES`), the needs-a-person stage is `<driver>/pipeline.py` `HUMAN_ACTION_STAGE`, and the TRD filing key is a literal in `<driver>/lane.py` (open item, QUESTIONS.md) |
| Workflow result envelope and the sentinel lines a host session prints (build and deploy lanes only) | not defined in one place (open item, QUESTIONS.md): the host prompt's `HANDBACK_SENTINEL` is the literal in `<driver>/prompts.py`; `PHASE_SENTINEL` is the pipeline-contracts composites contract's, read through `<driver>/compositecontract.py`; the envelope's keys are read ad hoc by `<driver>/handbackio.py` |
| Journal change a workflow script reports (build and deploy lanes) | `<plugin>/skills/pipeline-contracts/schemas/step-journal.schema.json` (`definitions/journalChange`); the driver applies each one with `<orch>/core/journal_lines.py` |
| Build and deploy step kinds and up-front plans | `<plugin>/skills/pipeline-contracts/schemas/pipeline-steps.json`, read through `<orch>/core/pipeline_steps.py` |
| Ledger events | `<driver>/ledgerevents.py` |
| Run cost sidecar | `<driver>/costsidecar.py` |
| Fable inventory, model fallback arguments and the held allowance refusal (build and deploy lanes only) | `<driver>/recoverytypes.py` (`ModelInventory`, `WorkflowInventory`, `BlockedRecovery`); the inventory is produced by `<plugin>/scripts/fable-inventory.py`, and the plugin's Fable shared block (`<plugin>/scripts/shared-blocks/fable.js`) reads the model fallback arguments `fableAgentTypes` and `fableFallback` with no typed definition (open item, QUESTIONS.md) |
| Relay request, receipt and registered result (build and deploy lanes only) | not defined in one place (open item, QUESTIONS.md): `<plugin>/scripts/portfolio/relayregistry.py`, `<plugin>/scripts/portfolio/relaycapture.py`, the relay shared block of the workflows, and the argument names `<driver>/headless.py` writes |
| Step journal (one file per bead; the only thing that decides where a run begins) | `<orch>/core/step_journal.py`, schema `<plugin>/skills/pipeline-contracts/schemas/step-journal.schema.json`; the driver loads the module through `<driver>/stepjournal.py`, reads it for the dashboard (`journalprogress.py`), resets it only through `journalstart.py`, and writes one only through `<orch>/port_journal.py` (`journalport.py`) |

`<arch>` below is the architecture directory, the one the driver surface's `ARCH_PATH_ENV` names.

## 1. Purpose

The elaboration lane selects one Epic per slot and dispatches the `prd-to-spec` composite for it.
`prd-to-spec` is an orchestrated flow (`dispatchargs.ORCHESTRATED_FLOWS`; `headless` routes every
composite in the composites contract's `ORCHESTRATED` set to `orchestrated.run`): the dispatch is a
child process running the installed plugin's `orchestrator/run.py`, which starts the bounded agent
sessions itself and writes a handback file. No host Claude Code session, Workflow tool call or
sentinel line is involved; those belong to the build and deploy lanes. The driver reads the run's
events from the child's output, then turns the handback into an `Outcome`, writes ledger
events, holds or backs off the Epic, files finished documents in the vault, and records the run's
token cost. The Epic pipeline's own behaviour is specified in `<orch>/specs/epic/prd-to-spec.md`
and the per-workflow specs beside it; this file covers only the boundary with the driver.

## 2. Selection facts the driver decides before dispatch

From `selection.py` `_epic_candidates`, `elabstate.py`, `workitems.py`:

Bead metadata keys and their values are defined only in the bead metadata schema,
`<plugin>/skills/beads-contract/schemas/bead-metadata.schema.json`; code reads them as the
constants of the generated `<plugin>/skills/beads-contract/scripts/bead_metadata.py` (the driver
loads it through `beadmeta.py`). This file names those constants and never restates a key's values.

- Candidate: bead type `epic`, not closed, not excluded (held/settled), no unmet prerequisite
  (`elabstate.unmet_blockers`: a `tracks` or `blocks` edge to an open Epic whose
  `KEY_ELABORATION_STATE` is not `ELABORATION_DONE`, or to an open non-Epic), `elabstate.candidacy`
  workable, and a WSJF score present (`index.wsjf_of`). One Epic per PRD stem per pass.
- `elabstate.candidacy`: `ELABORATION_READY` -> workable; `ELABORATION_IN_PROGRESS` -> workable only
  when no live execution owns it (`itemownership.reason`), and then marked `reclaimed`;
  `ELABORATION_DONE` -> not workable; `ELABORATION_AUTHORING` with cause `CAUSE_AWAITING_HUMAN` ->
  held for a person; `ELABORATION_AUTHORING` otherwise -> "PRD still being authored", not workable.
- A PRD file must resolve for the Epic (`workitems.find_prd`), or the Epic is skipped with
  `no PRD`.
- The lifecycle metadata the driver reads is the schema's `LANE_KEYS` group. The driver writes
  `KEY_ELABORATION_STATE`, `KEY_ELABORATION_STATE_AT`, `KEY_ELABORATION_STATE_CAUSE` and
  `KEY_ELABORATION_STATE_OWNER` (a subset of that group) only for a person hold (`elabstate.hold_for_person`: `ELABORATION_AUTHORING`, cause
  `CAUSE_AWAITING_HUMAN`, owner empty) and from `elabmark.py` (owner's CLI, cause `CAUSE_HUMAN`).
  `ELABORATION_IN_PROGRESS` and `ELABORATION_DONE` are written by the orchestrator
  (`elaboration.start` when a dispatch claims the Epic, `elaboration.finish` in the journal step
  that marks the Epic elaborated; see `<orch>/specs/epic/prd-to-spec.md`).

## 3. What the driver sends

The dispatch arguments are `dispatchargs.DispatchArguments`. `orchestrated.prepare` builds them
with `dispatchargs.build_arguments(args, fablewall.resets_at())` from `workitems.elaboration_args`
(whose PRD, Epic and design-system builders delegate to `dispatchargs.prd_ref`, `epic_ref` and
`design_system`) plus the lane's owner and execution-identity keys; keys outside the contract are
dropped. It writes them to the run's scratch folder at `dispatchargs.arguments_path`, exports the
execution id as the driver surface's `EXECUTION_ID_ENV`, and starts the run with
`dispatchargs.command`. `run.py` reads them back with `dispatchargs.parse_arguments`, which rejects
any document outside the contract.

Where each value comes from:

| Key constant | Source |
|---|---|
| `KEY_PRD` | the resolved PRD file (`workitems.find_prd`) and the Epic title |
| `KEY_EPIC` | the Epic bead |
| `KEY_BEADS_REPO_PATH` | `beadsio.main_repo_path()` |
| `KEY_ARCH_PATH` | `workitems.arch_args` |
| `KEY_DESIGN_SYSTEM` | `workitems.design_system_args` |
| `KEY_TRD_PATH` | `workitems.trd_path_for`, only when the PRD sits in a folder named `prds` |
| `KEY_RECLAIM` | `workitems.reclaim_args`: the Epic is `ELABORATION_IN_PROGRESS` with an owner and no live execution owns it |
| `KEY_OWNER` | `workitems.lifecycle_owner` (the execution id) |
| `KEY_EXECUTION_ID`, `KEY_SUPERVISOR_INVOCATION_ID` | the lane's execution identity; written to `arguments.json`, and the execution id also exported as `EXECUTION_ID_ENV` |
| `KEY_FABLE_UNTIL` | `fablewall.resets_at()`, written by `dispatchargs.build_arguments` |

The child process (`orchestrated.prepare`): the interpreter is `sys.executable`, the entry point is
the installed plugin's `orchestrator/run.py` (`pluginversion.plugin_file`), and the environment is
`headlessenv.child_env(<scratch>)` (the driver surface, `DriverEnvironment` and
`HeadlessEnvironment`, each variable set only if not already set), with the driver surface's
`SCRATCH_ENV_KEYS` passed through only from the supervisor's own environment. The run is stopped
when it writes no event for the idle limit, the driver surface's `ORCH_IDLE_ENV` (default
`ORCH_IDLE_DEFAULT`), which must be a positive finite number.

Run files per dispatch (`headlessenv.run_paths`):
`state/runs/<bead>-<composite>-<YYYYMMDDTHHMMSS>-<pid>-<hex6>.{out,err,scratch}`, plus the cost
sidecar at `costsidecar.sidecar_for(<run log>)` and `state/phases/<same stem>.json` (run record,
`phaserec.py`).

## 4. What the driver reads back (`Handback`, `dispatch.py`)

The handback is the `run.py` handback file at `dispatchargs.handback_path`, read by
`orchestrated.read_handback` (`handbackio.read_plugin_handback` -> `pluginhandback.read`) and
validated with `handback_contract.validate`; a file that cannot be read or fails validation is
replaced by the contract's `rejected` document, keeping the original payload as evidence. When the dispatch raised, `orchestrated.failed_handback` builds the handback
(`handback_contract.failure`, or `handback_contract.interrupted_failure` for a shutdown); an
unfinished handback read while the supervisor is shutting down is restated as an interruption.
The sessions the run registered through its session events are added when the handback names none.

The build and deploy lanes' host-session path (the completed workflow's result object read by
`runjournal.workflow_result` and `handbackio.handback_from_result`, else the session's
`HANDBACK_SENTINEL` line read by `handbackio.parse_handback`) is not used by this lane. That result
object is not validated against any schema, and its failure, refusal and artifact parts are not
mapped into `Handback` (§7).

### Parts the elaboration lane actually uses

Readers: `attempts.py` (turns a handback into an `Outcome`), `failurecause.py`, `refusal.py`,
`humanq.py`, `breaker.py`, `headless.py`; the files the plan names (`lane.py`, `outcomes.py`,
`elabstate.py`, `elabmark.py`, `failures.py`) read no `handback.` attribute directly:
`lane.py` reads the `Outcome`, and `outcomes.py` / `failures.py` read the ledger handback event.

| Part | Used for |
|---|---|
| success flag | completed vs failed routing (`AttemptRunner._resolved`); quota clear; the cost record's completion |
| stage | a stage in `STOP_STAGES` -> halted; `pipeline.HUMAN_ACTION_STAGE` -> needs a person; `refusal.STAGE` with a refusal -> refusal; `breaker.QUOTA_STAGE` -> pause; the environment stages `handbackio` classifies -> environment failure origin; otherwise the fallback failure stage |
| `Failure` | the structured cause (`failurecause.stated_cause`): a cause in `RETRYABLE_CAUSES` backs off and retries, `OTHER_CAUSE` records the failure with its repository evidence; the classification decides item failure versus fatal stop (`FATAL_CLASSES`) |
| failure origin | environment vs work (`ledgerevents.FailureOrigin`), recorded on the handback event; gates quota clearing |
| headline | Outcome headline; quota/API pause detection (`breaker.pause_of`: Fable wall mark, usage-limit text and reset time); the human need when no action is named |
| `Refusal` | read by `refusal.code_of`: a code in `refusal.WAIT_CODES` -> wait, hold until the Epic's tracker facts change; a code in `refusal.PERSON_CODES` -> human-action log |
| required human actions | human-action log entries, which the supervisor's `human_log` writes to the owner inbox (`ownerinbox.Writer`); any entry also means "needs a person" -> Epic held (`lane._person_needed` -> `elabstate.hold_for_person`), with the restore command (`elabstate.restore_command`) logged. The driver is the one writer of this hold and this inbox entry; the Epic flows only return required human actions, and only for owner facts (§9). An ordinary item failure with none is recorded and excluded for the invocation; a fatal classification stops new dispatch |
| `ArtifactReport` | **only after** the lane reads `ELABORATION_DONE` from the tracker: `artifactio.file_in_vault(<working dir>, phases, prd, trd_target)` files the TRD (target from the report's filing entry for the TRD file, a literal key in `lane.py`, or `KEY_TRD_PATH`) and Spec documents in the vault; `lane._vault_metadata` then composes the writes of the vault-path keys of the bead schema's `ARTIFACT_KEYS` group (the TRD's on the Epic, each Spec document's on its Story, matched by the Story's `KEY_ARTIFACT_SPEC_PATH` file name; kinds and the spec-file aspect map are `ARTIFACT_KINDS` and `SPEC_ASPECT_KIND`) |
| detail paths, sessions | failure evidence; human-action detail paths |
| beads emitted, lifecycle done | recorded on the handback event only; read by `outcomes.py` to word the ending ("Finished: N Story and Task beads written" when the lifecycle is done, else "unfinished") |

The build and deploy parts of `Handback` are recorded on the handback event or unused by this lane.

**Interruption.** An item stopped by an owner stop-execution of that item, a SIGTERM to it, or a
supervisor shutdown or drain gets a handback from `handback_contract.interrupted_failure`:
classification `INTERRUPTED_CLASS`, cause `SHUTDOWN_CAUSE`, and stage `INTERRUPTED_STAGE` for an
owner stop of that one item or `SHUTDOWN_STAGE` for a supervisor shutdown or drain. An interruption
never counts toward a repeated-failure streak and never latches a fatal stop; an item the owner
stopped is kept from being dispatched again by its active stop record, not by a recorded failure. A
session-cleanup error raised while stopping is classified `DEFECT_CLASS`.

"Elaboration done" is **not** taken from the handback: after every `prd-to-spec` dispatch the lane
re-reads `KEY_ELABORATION_STATE` from the tracker (`lane._elaboration_done`); only `ELABORATION_DONE`
triggers the elaboration-state event and vault filing.

## 5. Ledger events and phase names the readers depend on

Event types, field names and per-type shapes are defined only in `ledgerevents.py`. Events are
appended to `state/ledger.jsonl` by `ledger.append`, which validates the envelope only
(`ledger._event`): a nonempty `ts`, a `type` in `ledgerevents.EVENT_TYPES`, and a `beadId` that is
a string or null. The per-type shapes in `ledgerevents.py` type the producers; they are not
checked when an event is appended.

Events written around an elaboration dispatch:

- `EVENT_DISPATCHED`: the execution identity, the composite and the dispatch arguments.
- `EVENT_PHASE`. Producers: (a) the driver: the orchestrator start (`orchestrated.launch`, with
  the run log and session cwd), the interruptions, and the quota hold before dispatch
  (`lane.QUOTA_HELD_PHASE`); (b) the orchestrator: each phase event it writes, validated against
  the orchestrator event contract (`handback_contract.py`, through `handbackcontract`) and recorded
  as the composites contract's `PROGRESS_PREFIX` followed by the phase (`orchestrated.Events.feed`).
- `EVENT_VERDICT`: for each verdict event the orchestrator writes.
- `EVENT_FAILURE`: a dispatch that raised first records `failures.failed(failures.KIND_DISPATCH,
  ...)`.
- `EVENT_HANDBACK`: built by `ledgerevents.handback_event` from the handback; for a dispatch that
  raised, the handback's failure cause is `handbackcontract.wire().other_cause`.
- `EVENT_ELABORATION_STATE` when the lane reads `ELABORATION_DONE` with cause `CAUSE_DECOMPOSED`;
  `EVENT_ELABORATION_WAIT` on a refusal.
- `EVENT_REFUSAL_HOLD` / `EVENT_REFUSAL_RELEASED` / `EVENT_HOLD_READ_FAILED`: holds until the
  Epic's tracker facts (`elabstate.lifecycle_facts`: its `LANE_KEYS` and `WSJF_KEYS` metadata, its
  prerequisites' states, closed) change.
- `EVENT_REPEAT_BACKOFF`, `EVENT_HUMAN_ACTION`, `EVENT_QUOTA_TRIPPED` / `EVENT_QUOTA_CLEARED`,
  `EVENT_EXECUTION_STOPPED`, `EVENT_ATTEMPT_REOPENED`, the run events, `EVENT_HEARTBEAT`.

Readers and what they need:

- `outcomes.py`: `EVENT_DISPATCHED`, `EVENT_PHASE`, `EVENT_HANDBACK`, `EVENT_RUN_STARTED`,
  `EVENT_RUN_DIED`, `EVENT_ATTEMPT_REOPENED`; a phase counts as a phase name only when its text
  starts with `▸` or `>` (the `agent-teams-workforce:` prefix and ` #N` are stripped), so the phase
  shown for an Epic attempt is the phase the orchestrator last reported; endings come from the
  handback event.
- `observe.py` (served by `dashboard.py`): the dispatch, phase, verdict, handback,
  elaboration-state, execution, repeat, human-action, build-state, run and keeper events. For an
  Epic it also reads, outside the ledger: the tracker export (elaboration state and cause, Story
  and Task counts, TRD filed) to decide "Done" (it needs `ELABORATION_DONE`, a cause in
  `DONE_CAUSES`, a TRD, a Story and a Task); and the Epic's step journal
  (`observe.journal_progress`, which is `journalprogress.progress`): the outermost steps with
  their status, the steps running now, the step the next run begins at, a failed step with its
  failure text, and how many steps are done.
- `attemptview.py`, `runview.py`: the dispatch, phase, verdict, handback and run events, plus the
  harness workflow folders `<session>/subagents/workflows/wf_*/` (`journal.jsonl`,
  `agent-<id>.meta.json`) and the run records in `state/phases/`.
- `phaserec.expected_phases(composite)` reads `prd-to-spec`'s phases from
  `handbackcontract.wire().prd_to_spec_phases` (defined in `handback_contract.py`) and every other
  composite's from the composites contract's `PHASE_TITLES`; it reads no `.js` file.
- `failures.py`: `EVENT_FAILURE` and `EVENT_FAILURE_CLEARED` (which it also writes),
  `EVENT_HANDBACK` and `EVENT_RUN_STARTED`.

## 6. Cost attribution (`runcost.py`, `harnesspaths.py`)

- After each dispatch `headless._account` calls `runcost.record_run(bead_id, composite, out_path,
  lines, RunOptions(handback=..., identity=...))` and folds the record into `state/budget.json` (`runbudget.fold_run`;
  `prd-to-spec` opens an `epic`-kind budget item).
- Sessions: for an elaboration run, the agent sessions the orchestrator registered through its
  session events (the handback's sessions, `orchestrated.Events`), measured together
  (`runcost.measure_sessions`). Only when the handback names no session: the first `[session] <id>`
  line in the `.out` log, or any `"session_id": "<uuid>"` in it (`runcost.session_id_from`),
  measured as one host session (`runcost.measure_session`).
- Transcripts: `<CONFIG_DIR>/projects/<slug>/<session>.jsonl` (host) and every `*.jsonl` under
  `<CONFIG_DIR>/projects/<slug>/<session>/` (subagents, workflow agents), where `<slug>` is the
  session cwd with `/` and `.` replaced by `-` (`harnesspaths.project_dir`), falling back to a scan of
  all project folders (`runcost.session_project`).
- Measure and record: `runcost` measures usage from the transcripts, deduplicated per request
  (`runcost._fold_file`). The cost sidecar, its fields, roles, weights, phase and role breakdown,
  and its record-level deduplication are defined only in `costsidecar.py` (`CostSidecar`, `Role`,
  `role_for`, `WEIGHTS`, `COMPONENTS`, `HOST_PHASE`, `record_key`, `newest_records`); `runcost`
  writes it with `costsidecar.write_sidecar` at `costsidecar.sidecar_for(<run log>)`.
- Aggregation: `runcost.records` scans the sidecars with `costsidecar.read_sidecar` and keeps the
  newest record per `costsidecar.record_key` (`costsidecar.newest_records`); `totals_by_bead`,
  `for_bead`, and `subtree_total([epic, *task ids])` feed the dashboard.
- `harnesspaths.session_dir_for` finds a dispatch's session folder by the marker
  `dispatching bead <id> to` in the first 64 KiB of a transcript born between 30 s before and 120 s
  after the dispatch start, in the project folders of the cwds recorded for the bead.

## 7. How an elaboration run differs from a build or deploy run

- A build or deploy run is one host session, whose transcript tree and `subagents/workflows/wf_*`
  folders carry its cost, phases and verdicts. An elaboration run has no host session, no Workflow
  journal, no phase sentinel lines and no handback sentinel line: its phases and verdicts come from
  the orchestrator's events (`orchestrated.Events.feed`) and its cost from the sessions it
  registered (§6).
- `phaserec.expected_phases` takes `prd-to-spec`'s phase list from `handback_contract.py`, and
  `outcomes._phase_name` depends on the `PROGRESS_PREFIX` the driver puts before each phase.
- `observe.py` relay-step views read `artifacts/**/relay/` files that the relay produces.
- The relay arguments (written by `headless._dispatch_session` for every session it starts) and
  the model fallback arguments `fableAgentTypes` and `fableFallback` (written by
  `headless._dispatch_with_recovery`) exist only for the build and
  deploy lanes' Workflow runtime and command runner; an orchestrated dispatch carries neither. The
  workflow result envelope those lanes read has no single definition (§4).
- Some classification of a build or deploy run reads text: `breaker.pause_of` parses the headline
  for the usage wall and its reset time, `handbackio._died_of_outage` and `step_defect_origin`
  match output and dispatch-failure message text, and `headless._resume_unavailable` matches
  headline phrases. An elaboration handback states its cause and classification as structured
  fields, and the driver reads those (`failurecause.pause_for`, `pluginhandback.py`): CONTEXT 7.4
  says causes are never classified by matching error text.
- `observe.py` shows an Epic "Done" only with state `ELABORATION_DONE`, a TRD, a Story and a Task. That rule
  stays as it is: every Epic that reaches elaboration gets Stories and Tasks (CONTEXT 7.6), so no
  "nothing to build" record exists for it to accept.

## 8. Session-runner rules every Epic flow cites

**Section 2 guard (hard limit, CONTEXT 6).** Every agent session of an elaboration run runs inside
one guard, which the session runner applies (`<orch>/core/constraints.py` `Section2Guard`,
`<orch>/DESIGN.md` section 7.3). No flow keeps a copy of its own. The guard is shared by every
orchestrator process and keeps its state under `state/section2-guard/`, one folder per
architecture root.

1. Before a session, when no session of any run is live: `archstate.snapshot_constraints(<arch>,
   keep=True)`: the digest of `<arch>/arc42/02-architecture-constraints/`, its git status, whether
   it exists, and a kept copy, with the vault's `HEAD` commit. A session that starts while another
   is live shares that snapshot.
2. After a session ends, whatever its outcome: snapshot again and compare.
3. A difference that is the owner's committed work (clean git status, new commits that touch
   section 2, none with a `Pipeline-Run:` trailer) is accepted: the snapshot is taken again.
4. Any other difference in digest, existence or git status: the changed folder is copied aside,
   `archstate.restore_constraints(<arch>, kept)` restores section 2, the run's live sessions are
   stopped, and the step fails at stage `constraints-written`, cause `OTHER_CAUSE`.
5. A snapshot or restore that itself fails fails the step at stage `constraints-written`, cause
   `OTHER_CAUSE`; a guard lock that is not acquired in time fails it with `CONTENTION_CAUSE`.

It stops wrong output nothing later catches: every agent with Write or Edit (the polyrepo-steward,
the solutions architect and the agents it starts, `architecture-maintainer`, `trd-author`, the
spec authors, `task-decomposer`, `task-dependency-mapper`) can write anywhere, and no later step
re-reads section 2.

**Step record.** A step's output is recorded in the Epic's step journal as an artifact, by file
path or as a value, in the one journal change that marks the step done. A later step is handed
the artifacts of the steps its `inputs` name. Nothing else records what a step produced or
decides whether it runs again: there is no file beside an output, no input hash and no
freshness check.

## 9. Requirements that apply

- **7.18 Entry point.** The owner starts the pipeline only with `python3
  ops/sdlc-automation/keeper.py`; the elaboration lane is the only door into `prd-to-spec`. No
  plugin command dispatches it: `/work-bead` rules that an Epic or a Story is elaboration work
  and then reports that the driver's elaboration lane elaborates the Epic, with the step the
  Epic's journal names next.
- **7.6 and 7.17 at the boundary.** The lane's "Elaboration done" read (`ELABORATION_DONE`)
  now means Stories, Tasks, Task edges and Task WSJF scores all exist; the Epic's own WSJF is not
  rewritten by elaboration.

- **7.12 Dashboard truth.** "Running" only from a live lease and a verified session process. An
  Epic run is the orchestrator's process for the Epic, holding the Epic's lease
  (`KEY_ELABORATION_STATE_OWNER` and the driver's execution identity), plus at most a few agent
  sessions at a time, each recorded by the driver only after its process group is verified
  (`orchestrated.Events`, `sessionregistry.record`). The Epic is
  shown running only while that lease is live and that process is verified; an agent step is shown
  running only while its session's process is verified. A phase or step name shown comes only from
  an event the run wrote (no inferred phases), and no counter is shown that the records cannot
  compute (no "Tasks built" style totals). How the run unit is recorded is an open item in
  QUESTIONS.md.
- **7.4 Structured causes.** The text-based classifications listed in §7 (`breaker.pause_of`,
  `handbackio._died_of_outage`, `step_defect_origin`, `headless._resume_unavailable`) do not carry
  into the Python run: the runner sets the cause (a `*_CAUSE` constant of `handback_contract.py`)
  from the session's structured result (exit status, stream events), exception types and script
  JSON fields. The remaining choices are open items in QUESTIONS.md.
- **7.9 Who gets asked what.** Only owner facts become required human actions: the owner concerns
  of an `architecture-decider` ruling (two business requirements no design meets together, or a
  conflict with section 2), and a GitHub sign-in or organisation membership the span step needs
  before it can create a repository. The driver alone writes the hold and the owner inbox from
  them (§4). Every other failure carries its cause and its classification; ordinary item failures are recorded and fatal defects stop new dispatch. Neither creates an owner action automatically.
- **7.2** Only the owner runs the pipeline; nothing in this contract is run as a test.
- **7.8** Selection filters stay in `selection.py` / `elabstate.py` (§2), and only there: the
  driver is the only door, so `prd-to-spec` does not repeat them.

## 10. Open items

See QUESTIONS.md
