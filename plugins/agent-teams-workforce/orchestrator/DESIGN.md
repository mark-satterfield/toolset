# DESIGN: the Python orchestrator for the Epic pipeline

Failure handling: bounded transient retries and quota pauses remain. An ordinary item failure is recorded and excluded from selection for the current invocation; other eligible items continue. Setup, code, schema, and runtime type defects stop new dispatch, preserve the original diagnostic, and let current paid steps finish. Named within-step corrective passes remain bounded content work; failed runs do not dispatch repair or diagnosis agents.

This document describes how the Epic (elaboration) pipeline runs as a Python orchestrator: where
the code lives, how a step is declared and run, where a run begins, how agent sessions are started
and costed, how failures get a structured cause, what runs in parallel, how owner questions travel,
what the driver does for the elaboration lane, and how the matrix is stored and fed. The documents
under `specs/epic/` describe each part of the flow step by step.

Names used throughout:

- `<plugin>` = the `agent-teams-workforce` plugin (`$ATW_PLUGIN_ROOT`)
- `<orch>` = `<plugin>/orchestrator`
- `<control>` = `$ATW_CONTROL_REPO`, the control repository
- `<driver>` = `<control>/ops/sdlc-automation`
- `<work>` = `<control>/.claude/workflow-runs/artifacts/<epic-id>/` (the Epic's work directory;
  `core/io.py` `work_directory`)
- `<arch>` = `$ATW_ARCH_PATH`
- `<config>` = `$CLAUDE_CONFIG_DIR` of the pipeline
- `<installPath>` = the installed plugin the pipeline runs, from `pluginversion.running_dir()`

## 0. Evidence used

Facts about Claude Code were taken from tools on 2026-10-09, not from memory:

- `claude --version`: `2.1.296 (Claude Code)`.
- `claude --help` (same version). The flags this design relies on: `-p`, `--output-format
  stream-json`, `--verbose`, `--agent <agent>`, `--agents <json-or-file>` ("with --print the path
  to a file that holds one"), `--model` (aliases include `fable`, `opus`, `sonnet`),
  `--session-id <uuid>`, `-r/--resume`, `--setting-sources`, `--settings <file-or-json>`,
  `--plugin-dir`, `--permission-mode`, `--add-dir`. `--bare` makes
  Anthropic auth "strictly ANTHROPIC_API_KEY or apiKeyHelper (OAuth and keychain are never read)".
- Context7 `/websites/code_claude`:
  - `code.claude.com/docs/en/sub-agents`: `--agent` "applies a subagent's tool restrictions,
    model, and system prompt to the main session thread. Custom subagent system prompts replace
    the default Claude Code prompt, while CLAUDE.md files and project memory still load"; a
    plugin agent is named `plugin:agent`. The verifier's query of the same page adds: the
    `--agents` file form needs v2.1.281 or later, and a definition accepts `description`, `tools`,
    `disallowedTools`, `model`, `permissionMode`, `mcpServers`, `hooks`, `maxTurns`, `skills`,
    `effort`, `omitClaudeMd` and `isolation`.
  - `code.claude.com/docs/en/plugins/components`: in a plugin agent's frontmatter `permissionMode`,
    `hooks`, `mcpServers` and `initialPrompt` are ignored; `isolation` accepts only `worktree`.
  - `code.claude.com/docs/en/agent-sdk/python`: the result message has `subtype` (`success`,
    `error_during_execution`, `error_max_turns`, `error_max_budget_usd`,
    `error_max_structured_output_retries`), `is_error`, `api_error_status` (HTTP status of the
    terminating API error), `terminal_reason` (`completed`, `max_turns`, `api_error`,
    `aborted_streaming`, `aborted_tools`), `session_id`; `ClaudeAgentOptions.env` is "passed to the
    CLI subprocess", that is, the SDK runs the same CLI.
- `python3 -c "import claude_agent_sdk"` fails: the SDK is not installed. `python3` is 3.14.8 with
  `jsonschema` 4.26 and `yaml` installed.
- The driver code read for this design: `dispatch.py`, `headless.py`, `headlessenv.py`,
  `ledger.py`, `failurecause.py`, `breaker.py`, `runcost.py`, `pluginversion.py`, `mcpconfig.py`,
  `fablerecovery.py`, `fablewall.py`, `handbackio.py`, `artifactio.py`, `workitems.py`,
  `beadsio.py`; in the plugin `scripts/portfolio/beadgraph.py`, `beadwrite.py`, `archstate.py`, and
  `skills/polyrepo-repo/scripts/polyrepo.py`; `<control>/ops/lib/central-beads-lock.sh`;
  `<config>/settings.json`; `<control>/.claude/settings.json`.
- Read-only checks run for this design:
  - `bd show ssbd-zzzzzz-nonexistent --json`: exit 1; the JSON error object carries only `error`,
    `hint`, `schema_version`, no error code.
  - `bd show ssbd-mb689 ssbd-hdqid ssbd-guuuz --json`: all three carry the elaboration state
    `bead_metadata.ELABORATION_IN_PROGRESS` (beads-contract schema).
  - `ls $SKILLSPOKE_APPS`: the application repositories fall in the app spaces
    `personal-agent`, `shared`, `marketing` and `employer`.

## 1. Where it lives (S02 item 1)

**Decision.** The orchestrator is a Python package in the plugin, `<orch>/`, with `run.py` as its
entry point. `supervisor.py` stays the driver: it selects work and starts the orchestrator as a
child process per dispatch, with the command line `ops/sdlc-automation/dispatchargs.command` builds
(the one place that defines the `run.py` options and the scratch file names).

`<python>` is the driver's own interpreter (`sys.executable`), so the orchestrator imports the same
installed `jsonschema` and `yaml` the portfolio scripts use; no `uv`, no new dependency.

Layout:

| Path | Holds |
|---|---|
| `<orch>/run.py` | argument parsing, the flow registry, handback writing, signal handling, the top-level handler of section 6.7 |
| `<orch>/core/` | the step journal (`step_journal.py`) and its runner (`journal_run.py`, `journal_steps.py`, `journal_changes.py`), the registry of step code (`journal_registry.py`), the session runner and launcher (`agents.py`, `agent_context.py`, `agent_process.py`, `frontmatter.py`), the tools layer for `bd`, git, `gh`, `polyrepo.py` and `cdk` (`tools.py`, `tool_locks.py`), the section 2 guard (`constraints.py`), the event writer (`events.py`), the handback contract and classification (`handback_contract.py`, `handback.py`), the run record (`manifest.py`) and the driver modules the plugin loads (`driver_contracts.py`) |
| `<orch>/flows/` | the steps of the Epic's journal: `prd_to_spec.py` (the dispatch and the open-run step), `architecture.py`, `architecture_check.py`, `architecture_ruling.py`, `architecture_promotion.py`, `architecture_earlier.py`, `architecture_files.py`, `trd_authoring.py`, `repo_scoping.py`, `repo_placement.py`, `spec_authoring.py`, `spec_authoring_ui.py`, `spec_review.py`, `task_decomposition.py`, `task_edges.py`, `elaboration_steps.py`, `elaboration_files.py`, `elaboration_support.py`, `elaboration_result.py` |
| `<orch>/port_journal.py` | builds the step journal of a bead that has saved run data and no journal; the driver's `journalport.py` calls it |
| `<orch>/specs/`, `<orch>/measurements/`, `<orch>/DESIGN.md` | documents |

There is no brief template folder: a brief is built in code from facts only (section 2.3).

**Verification.** The agent that changes pipeline tooling sanity-checks its own change once before
committing: it imports the module and calls the changed function or entry point once with a
realistic input, as a throwaway probe scoped to what changed, plus lint and strict type checking on
the changed files and the generators' `--check` when a schema or shared block changed. No test or
check suite exists for the pipeline tooling and none is written; a sanity check is not kept,
committed, wired into a hook or run again by a later step. The owner's pipeline run is the test.

The flow registry holds one flow, `prd-to-spec`. Its work is the steps of the Epic's journal
(section 2.1), not separate flows: the only entry into the Epic pipeline is the driver
(CONTEXT 7.18).

**Reasons and evidence.**
- The flows call the plugin's agent definitions, skills and `scripts/portfolio/` modules, and must
  run against the same version of them. The driver resolves the installed version
  (`pluginversion.running_dir()` reads `installed_plugins.json` `installPath`), so a dispatch that
  runs `<installPath>/orchestrator/run.py` gets matching code and agents.
- A child process per dispatch keeps a crash out of the supervisor, picks up a newly installed
  version on the next dispatch, and lets the driver stop it by process group.
- The Agent SDK is not used (section 5.1), so the package needs nothing beyond the interpreter the
  driver runs.

## 2. Step model (S02 item 2)

### 2.1 The step journal and its two kinds of step

One elaboration dispatch is a loop over the step journal of the Epic
(`<control>/.claude/workflow-runs/step-journals/<epic-id>.step-journal.json`,
`core/step_journal.py`, schema `skills/pipeline-contracts/schemas/step-journal.schema.json`). The
dispatch creates the journal when its file does not exist, with every outermost step planned, then
asks the journal for the next step, runs it, and repeats until no step is left or one fails
(`core/journal_run.py`). There is no other cursor: a restart is the same loop on the same file, so
it begins at the first step without child steps that is not done.

The outermost steps of an Epic's journal are Open the run, Architecture, TRD, Specs and Stories,
Tasks, Task edges, Score the Tasks, Apply the done rule, Story edges and Mark the Epic elaborated
(`flows/prd_to_spec.py` `outermost_steps`). A step with child steps is never run itself. Steps
found at run time are added by the step that finds them: the open-run step plans the architect's
step and the check after it, the check plans the promotion, the span step plans
one container per repository with its first step, that first step plans the repository's spec
steps, and the Story bead write plans the repository's container under Tasks.

A step without child steps is one of two kinds, and the registry (`core/journal_registry.py`) finds
its code:

- **Script step.** The step's `script` text is the key of a handler (`@script_step("<key>")`). The
  keys are defined in `flows/architecture_files.py`, `flows/repo_scoping.py` and
  `flows/elaboration_files.py`: `prd_to_spec.open_run`, `architecture.earlier_work`,
  `atw-matrix check; atw-matrix review-scope`, `atw-matrix sync-documents; atw-matrix commit`, `trd.confirm`,
  `atw-matrix epic --closure`, `spec_authoring.context`, `cdsbundles.list_bundles`,
  `spec_authoring.normalize_ui`, `specui.spec_ui_append`, `spec_authoring.story_document`,
  `beadwrite.write_story`, `task_decomposition.context`, `beadwrite.plan_story_tasks`,
  `beadwrite.write_task`, `beadwrite.retire_superseded_tasks`, `task_decomposition.record`,
  `beadwrite.closure_task_edges`, `task_edges.listing`, `beadwrite.write_all_task_edges`,
  `elaboration.score`, `elaboration.done_rule`, `storyedges.story_edges`, `elaboration.finish`. A
  handler returns a `Completion` or raises `StepError(stage, cause, evidence)` (section 6).
- **Agent step.** The step's `agent` name is the key of a launch builder (`@agent_step(...)`). A
  builder of the architecture team is registered for every agent whose definition states its role;
  the builders of the spec, Task and Task edge agents are registered by agent name. The builder returns an
  `AgentLaunch`: the output path, the validator of the output, the one-line outcome, the readable
  directories, the labelled files of the brief, and an `accept` function that says what the step
  records when the output is accepted.

Both receive a `StepRun` (`core/journal_steps.py`): the step, the journal, the run context, the
tools, and the step's inputs resolved from the journal, which are the artifacts, by name, of the
steps its `inputs` name and of the steps below them. A handler never looks for an earlier output by
a file name, a glob or a derived path. Parameters of a step planned at run time are a value
artifact named `for <step id>` on the step that planned it.

The runner marks a step running before its code or its session starts, with the agent session id
for an agent step. When the output is accepted, one journal change records the step's artifacts,
adds every step the result plans and marks the step done (`core/journal_changes.py`
`apply_completion`). A step that raises is marked failed with a structured cause and the dispatch
ends; the next dispatch starts at that step. A stop request leaves the step running.

An agent that starts other agents in its own session (`aws-solutions-architect`) or plans steps for
the script (`architecture-team-lead`) adds child steps and a last child step "Finish" under its own
step with `atw-step-journal`, by the protocol in `helper-steps.schema.json` that the
`subagent-contract` skill applies. After such a session the
runner reads the journal again: a step whose child steps are all done and end with a "Finish" the
agent closed in its own session is completed through that "Finish" (the accept of its launch, its
result recorded on the agent's step); one whose child steps end with no done "Finish" gets a
planned "Finish"; a child left not done is the next step. An agent left running is launched as its own session from
the request file its step holds; "Finish" is launched as the same agent, continuing its session.

A step that already holds a session id, a "Finish" step, and a later step of an agent that holds a
session earlier in the journal continue that session (`claude --resume`); when the conversation is
gone a new session starts. A session is continued only when the plugin version that runs now
started it: each new session records that version in `<work>/sessions/<session id>.json`, and a
session another version started, or one with no record, was made under other agent definitions
and contracts, so the step starts a new session.

A step that reads a file an earlier step wrote, and finds that it does not satisfy the contract
the step reads it by (the architecture context the open-run step wrote, a request the step above a
helper wrote), is not failed (`StaleInputError`): once the steps running with it end, the step
that wrote the file and every step after it are set back to planned, and the run goes on from
there, so the file is written again to the current contract. When the same writer is named twice
in one dispatch, the step fails. The solutions architect writes its result as the work goes, and every
step of it keeps a result already at the result path, so a new session continues from the partial
result and the design work done before the stop is not done again.

When a spec step creates a Story bead and a Task step creates Task beads, the same step creates
that bead's journal in the same directory (pipeline `deploy` for a Story, `build` for a Task), with
the creating step as its first, done step and the files the bead's later steps are handed as its
artifacts.

The dispatch result (the handback, section 4.4) is assembled from the journal's artifacts
(`flows/elaboration_result.py`), so it is the same whichever dispatch ran a step.

### 2.2 How `scripts/portfolio/` and the other tools are called

**Decision.** In-process import for every `scripts/portfolio/` module the flow uses (`matrixstore`,
`matrixsync`, `matrixreview`, `matrixquery`, `beadgraph`, `beadwrite`,
`hierarchy`, `elaboration`, `storyedges`, `cdsbundles`, `specui`, `archstate`).
Subprocess, argv list, no shell, with a timeout, for executables: `bd` (through
`beadgraph.run_bd`), `git`, `gh`, `uv run <plugin>/skills/polyrepo-repo/scripts/polyrepo.py <cmd>
--json`, `cdk` (`core/tools.py` `Tools.command`, `git`, `polyrepo`, `cdk`).

**Reasons.**
- `depscore.py` is the command line over these modules for the workflows and the owner; calling it
  as a subprocess returns only an exit status and printed JSON.
- The modules raise typed exceptions, and `beadgraph.GraphError` carries a `cause` field set from
  structured facts (section 6.2). An in-process call keeps the exception and its cause.
- The orchestrator runs from the same plugin version as the modules (section 1). The driver modules
  it loads from the control repository are the ones `core/driver_contracts.py` names.

**What an in-process call handles.**
- A step calls a module function through `Tools.portfolio` (one call) or `Tools.operation` (a whole
  operation that re-reads its inputs before it writes). An exception that is not a `StepError`
  becomes `StepError(<stage>, <cause>, <path of an evidence file holding the traceback>)`; the
  cause is the `GraphError`'s own, and `other` for every other exception (section 6.1).
- Imported calls run under `contextlib.redirect_stdout(sys.stderr)`, one at a time, so nothing a
  module prints can enter the event channel (section 4.1).
- `run.py`'s top-level handler catches `BaseException` (section 6.7), so `SystemExit` or
  `KeyboardInterrupt` raised in a worker thread and re-raised by `future.result()` still produces a
  handback.
- Every subprocess the tools layer starts has a timeout.

The scoring step and the marking step call `elaboration.finish`, and the Story edge step calls
`storyedges.story_edges` (section 11.6).

### 2.3 Briefs carry facts only

A brief is built in code (`core/agent_context.py` `brief`), never from a prose template, and holds
exactly:

1. the bead id;
2. the input file paths (absolute), each with a label: either the name of the journal artifact
   that holds the file, or the label the agent's definition names (for example `prd`, `criteria`,
   `context`, `findings`, `step journal`);
3. the output file path (absolute);
4. a one-line expected outcome;
5. for a journal step, `request` (what is asked: the builder's text, or the step's description)
   and `step` (the journal step id).

It carries no instructions, no rules, no procedures, no schemas and no file content. Everything
else an agent needs is in its definition (`<plugin>/agents/<name>.md`) and in the skills its
front matter names, which Claude Code loads when the session starts as that agent, or the skills
it loads itself with the Skill tool (section 5.1). The
validation errors of a corrective retry are written by Python to a file and listed as one more
input.

### 2.4 One set of criteria for the architecture team

`<plugin>/skills/effective-architecture/review-criteria.json` holds every criterion as data: its id,
its level (architecture, technical requirement or implementation), its home document and its text;
and, for each level, the agents responsible for it and the agent that reviews and approves it.
`review-standard.md` beside it is written from that file by
`skills/artifact-handoff/scripts/review_criteria.py`.

`aws-solutions-architect` develops the architecture and the TRD to exactly these criteria, answers
each architecture and technical-requirement criterion in its result, and reviews and approves its
own architecture against them; nothing else reviews it. Criterion P10 requires that no decision is
made by instinct: every AWS resource the design defines is reviewed with the AWS tools, the design
has a Well-Architected review, and every decision between two or more options states the options
and the reason. The architect records all of it in the Epic's review log, whose contract is the
`log-architecture-review` skill (`schemas/review-log.schema.json`, written and checked by
`scripts/review_log.py`). A criterion is satisfied by the document that is its home. No brief
carries any part of the criteria: agents read them in `effective-architecture/review-standard.md`.

### 2.5 Where the contracts and schemas live

Every file an agent produces or consumes has one JSON Schema in
`<plugin>/skills/artifact-handoff/schemas/`. Python validates each result against the same file and
reads it through a module generated from it: `scripts/architecture_work_contract.py` (from
`architecture-result.schema.json`, which defines every shape of the architecture team's files
once; each file has a wrapper schema that refers to its definition), `scripts/matrix_contract.py`
(from `matrix.schema.json`), and the other
generated contracts the `artifact-handoff` skill lists. An agent of the architecture team finds
the schemas through the `effective-architecture` skill; the spec and Task agents through
`artifact-handoff`. A contract only code produces and consumes is one typed Python module, named in
the register. No schema text is placed in a prompt.

## 3. Where a run begins, and what the phases still record

### 3.1 The journal decides

Nothing but the step journal decides whether a step runs: no file hash, timestamp, changed
document or freshness check. A step's output is recorded as an artifact of the step right after it
is written (a file by path, or a value such as a count of findings); later steps are handed
those artifacts from the journal. A missing file is found only when a step reads it, and is then
that step's failure. An earlier start is made by invalidating a step (`atw-step-journal
invalidate`), which resets it and every step after it; only the owner asks for it.

Files stay flat under `<work>`, with the architecture part's files under `<work>/architecture/`
(`specs/epic/INDEX.md` lists them). Run facts that are not about one file (session ids, model,
effort, timings, the cause of a failed step) go in the run record `<work>/run.json` (section 4.4).

### 3.2 The spec, Task and Task edge steps

Every step of spec authoring, the spec review, Task decomposition, the Task edges and the finish is
its own journal step, planned by the step that discovers it: the span step plans one container per
repository, each repository's first step plans that repository's steps, a review plans the
correction its result calls for, a plan plans one step per Task bead write. `specs/epic/` lists
them. The journal is the one record of what is done; a step keeps none of its own. A step that
writes a bead finds the bead by its elaboration key,
so running it again after an invalidation updates that bead and creates no second one.

### 3.3 What the orchestrator names itself

The orchestrator names the Epic's work directory (`core/io.py` `work_directory`) and the directory
that holds step journals (`core/step_journal.py` `journals_directory`). It loads no artifact code
from the driver.

## 4. Ledger, dashboard and cost (S02 item 4)

### 4.1 Events on stdout

**Decision.** The orchestrator writes one JSON object per line on stdout and nothing else there
(diagnostics go to stderr, and imported code runs with stdout redirected to stderr, section 2.2).
The driver captures stdout to the run's `.out` file and routes each event to its own callbacks
(`<driver>/orchestrated.py` `Events.feed`), which write the ledger's phase and verdict events.

The event names, their fields, the session states and the note kinds are defined in one place,
`orchestrator/core/handback_contract.py` (`EventName`, `OrchestratorEvent` and its member
TypedDicts, `validate_event`, and the event builders). `core/events.py` `EventWriter` validates
each event before it writes the line. The driver loads the contract through
`ops/sdlc-automation/handbackcontract.py`, validates every line with `validate_event`, and branches
on the `Wire` event values. How the driver routes each event:

- a phase event is announced with the composite contract's progress prefix before the phase;
- a verdict event goes to the verdict callback with its fields;
- a session event is announced as `agent <agent> <state>`; when a session starts and its process
  group is verified, the driver registers the group with `childproc`, `spendguard` and
  `sessionregistry`, and forgets it when the session ends;
- a heartbeat is announced nowhere; it counts as progress for the dispatch's idle timeout
  (section 9);
- a note is announced as `note <kind>`;
- a fable-wall event is recorded with `fablewall.record`.

A session's runner writes a heartbeat every `ATW_HEARTBEAT` seconds (default 300) while the session
has written a stream line since its last heartbeat (`core/agent_process.py`). Session and note
texts carry no progress prefix, so `outcomes._phase_name` records them and counts only phases.

### 4.2 Phase names

The phases of `prd-to-spec` that the orchestrator emits as phase events are, in run order:
`architecture`, `trd-authoring`, `repo-scoping`, `spec-authoring`, `task-decomposition`,
`task-edges`, `finish`. They are defined once as `handback_contract.PrdToSpecPhase`; the composite's
display list is `skills/pipeline-contracts/schemas/composites.json`. The open-run step enters
`architecture`, and the steps of the Architecture container run under it; `trd.confirm` enters
`trd-authoring`; the span step enters `repo-scoping`; each spec step, Task step and the Task edge
step enters its own phase, with the repository where it has one; the scoring, Story edge and
marking steps enter `finish`. The handback's `artifacts.phases` holds `trd` and one `spec:<slug>`
per repository, each read from the journal.

### 4.3 Verdict events

No step of the elaboration emits a verdict event. What the check step found, what the lead routed and
what the decider ruled are artifacts of their journal steps.

### 4.4 Handback and run record (QUESTIONS 22)

**Decision.** The handback is a file. `run.py` writes it atomically before it exits. Its keys, value
types and value vocabularies (failure classification, failure cause, stop stages, phase statuses,
refusal codes) are defined in one place, `orchestrator/core/handback_contract.py`
(`HandbackDocument`, `validate`, `Wire`); the driver loads it through
`ops/sdlc-automation/handbackcontract.py`.

The flow's report is projected to the wire contract by `handback_contract.wire_result`; a report
that fails validation is saved beside the handback as `.invalid.json` and replaced by the
contract's `rejected` document.

`detailPath` is the run record `<work>/run.json`, whose shape is `orchestrator/core/manifest.py`
`RunManifest`; each of its sessions is a `handback_contract.Session`. It also carries the flow's
report and the note and verdict events of the dispatch. For a failure that escapes the flow
(section 6.7) `detailPath` is the traceback file beside the handback.

`run.py` exits 0 whenever it wrote a handback, whatever `ok` says; a process that ended without
one is a failed dispatch at the driver's stage `no-handback`, built from the child's last
exception line (`orchestrated.failed_handback`).

The driver sets the failure origin from the handback's structured failure
(`<driver>/pluginhandback.py`): a cause of `api` or `quota`, and the classification `interrupted`,
are `environment`; every other failure is `work`.

The dispatch arguments the orchestrator reads, the scratch file names and the `run.py` command line
are defined in one place, `ops/sdlc-automation/dispatchargs.py` (`DispatchArguments`,
`build_arguments`, `parse_arguments`, `command`); the plugin reads them through
`orchestrator/core/driver_contracts.py`.

### 4.5 Cost attribution and the run unit (QUESTIONS 21)

**Decision.** The run unit is one dispatch: one cost record per orchestrator run, at
`costsidecar.sidecar_for(<run log>)`, summing every agent session that run started. Each agent
session is its own top-level Claude Code session, so the record lists them:

- The journal runner chooses each session's id (`--session-id <uuid>`, section 5.2) and records it
  on the journal step; the session runner records it in `run.json` and the handback's `sessions[]`.
  A resumed session (sections 2.1, 5.5, 6.3) keeps its id.
- The driver measures the sessions the handback names together (`runcost.measure_sessions`), each
  from its transcript, and builds the per-phase and per-role totals from the session rows. The
  record's shape and its deduplication key are defined in one place,
  `ops/sdlc-automation/costsidecar.py` (`CostSidecar`, `record_key`).

**What proves a run is running (CONTEXT 7.12).** The Epic shows "running" only while the driver's
lease is live and the orchestrator's process is verified, as for any dispatch
(`sessionregistry`, `childproc`). An agent step shows "running" only between its `session started`
and `session ended` events and only while its `pid` is alive (`os.kill(pid, 0)`, with the `pgid`
from the event matching `os.getpgid(pid)`). The phase shown is the last `phase` event the run wrote;
no phase is inferred. No counter is shown that the records cannot compute.

## 5. Agent runner (S02 item 5)

### 5.1 The headless CLI, with the agent started by name

**Decision.** Each agent step runs the Claude Code CLI as a subprocess (`claude -p`), not the Agent
SDK. Reasons: the driver already starts, supervises, kills and costs `claude` processes
(`headless.py`, `childproc.py`, `runcost.py`) under `CLAUDE_CONFIG_DIR=<config>`; the SDK is not
installed (section 0) and its own documentation says it passes its options to "the CLI subprocess",
so it would add a dependency and run the same binary.

An agent is defined in one place, its own definition file. The launcher (`core/agent_context.py`)
starts the session as that agent by name; Claude Code loads the agent, and the prompt is only the
brief (section 2.3):

1. The launcher reads from `<plugin>/agents/<agent>.md` only the front matter fields it decides
   something with (`load_agent`): `model` (required; it drives the Fable fallback), `role` (the
   matrix role, section 5.2). It reads no tools, no body and no skill.
2. It launches the session with `--agent <agent>`, the agent's plain front matter `name`, for
   every agent. Claude Code loads the definition: its body, tools, disallowed tools, model,
   effort, MCP servers, turn limit and front matter skills. An agent whose definition states
   `mcpServers` (which Claude Code ignores for a plugin agent) runs from the user-level copy in
   `~/.claude/agents/` that the plugin's `hooks/sync-user-agents.cjs` keeps; by Claude Code's name
   precedence the user-level copy wins over the plugin agent of the same plain name. The launcher
   writes no agent definition, no skill text and no MCP configuration, and adds no tool or skill.
   `--model` is the definition's model, or `opus` in its place on a Fable fallback (section 5.5).
3. Any agent loads any other skill on demand with the Skill tool, with that skill's scripts and
   relative paths intact. No code reads a skill's text and feeds it to an agent.
4. An agent the launched agent starts is named the same way, by its plain name, and runs with its
   own front matter. `scripts/check-agent-types.mjs` fails a prefixed agent name in the plugin.
   The step journal records the agent name a step is planned with.
5. The brief is written on stdin.

No schema text, rule text, agent text, skill text or file content is placed in the brief.

**Minimum CLI version.** The runner requires 2.1.281 or later (section 0). Before its
first session the runner reads `claude --version` once; a version below 2.1.281, or one it cannot
parse, is a session setup failure (classification `setup`) before any session starts.

### 5.2 The command line and minimal context

```
claude -p --output-format stream-json --verbose
  --session-id <uuid>            (or --resume <uuid> to continue a session)
  --agent <agent>                (the plain front matter name)
  --model <model>
  --setting-sources project
  --settings <session dir>/settings.json
  --plugin-dir <plugin>
  --permission-mode bypassPermissions
  --add-dir <each directory the launch names>
```

For example, the launch of `aws-solutions-architect`:

```
claude -p --output-format stream-json --verbose --session-id <uuid>
  --agent aws-solutions-architect --model opus --setting-sources project
  --settings <session dir>/settings.json --plugin-dir <plugin>
  --permission-mode bypassPermissions
```

- **Working directory.** A per-session directory outside every repository,
  `<temporary directory>/atw-session-<session id>/`, made before the session and removed after it.
  It is named for the session id, so a later dispatch that resumes the id runs in a directory of
  the same name. It holds `settings.json`. Reason: with the working
  directory inside `<control>`, Claude Code auto-discovers the control repository's
  `AGENTS.md`/`CLAUDE.md` and the ones above it; an Epic agent needs none of them, because its
  brief names every path it reads and its definition and skills hold its rules.
- **Settings.** `--setting-sources project` with a working directory that holds no project
  settings loads no settings file; user settings (`<config>/settings.json`) are not loaded.
  `--settings <session dir>/settings.json` holds (`agent_context.session_settings`):
  every `PreToolUse` hook of `<config>/settings.json` whose command names one of
  `no-verify-blocker.sh`, `pipeline-run-blocker.sh`, `bd-init-blocker.sh`,
  `aws-profile-required.sh` (a constant list, matched by script file name, so the hook commands
  themselves are read from the owner's file); every `PostToolUse` hook group of
  `<control>/.claude/settings.json` (`<control>` is `ATW_CONTROL_REPO`), so an edit is checked by
  the edit hook the control repository declares for its own sessions and by no other copy;
  `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1`, so every start
  blocks; and `bashOutputMaxChars` at Claude Code's largest value, so a command's output reaches
  the session whole. The settings are the same for every session; none depends on the agent.
- **Plugins and skills.** `--plugin-dir <plugin>` loads `agent-teams-workforce` and no other
  plugin. The agent's front matter skills load with the agent (section 5.1); any other skill the
  agent loads itself with the Skill tool.
- **MCP servers.** The launcher passes no MCP flag. The servers an agent's front matter
  `mcpServers` names load with the agent, from its user-level copy (section 5.1).
- **Tools.** An agent's tools are the allow-list its front matter `tools` field states, which
  Claude Code enforces: every tool it does not list is denied. The launcher passes no tool flag,
  so nothing is added to or taken from that list. Which tools an agent gets is the owner's
  decision, made in its definition file.
- **What loads besides.** `<config>` holds `rules`, `skills` and `agents` entries and may hold a
  user `CLAUDE.md`. They are user-level memory and content, not settings files, and
  `--setting-sources` does not exclude them; a different `CLAUDE_CONFIG_DIR` for agent sessions
  would also move the transcripts and the login the driver relies on. The descriptions of the
  plugin's own skills load with `--plugin-dir`. The `system`/`init` event at the top of an agent
  session's transcript lists what loaded (tools, skills, MCP servers, plugins).
- **Not used:** `--bare` (it accepts only `ANTHROPIC_API_KEY` auth, and the pipeline runs on the
  subscription: `breaker.exhausted_reset` reads the subscription windows); `--json-schema` (results
  are files, section 5.6); `--no-session-persistence` (the transcript is the cost record).
- **Environment.** `headlessenv.child_env(<work>/scratch/<run id>)`, with the plugin's `bin`
  folder first on `PATH` (so a session runs `atw-matrix` and `atw-step-journal` by name) and `ATW_MATRIX_ROLE` set to the launched agent's `role` when the matrix contract knows it.

### 5.3 `isolation: worktree` (QUESTIONS 2)

**Decision.** The launcher passes no `--worktree` for the launched agent. An agent the launched
agent starts is the plugin's agent, so its front matter `isolation` applies to it. Every Epic agent writes only under `<work>` (outside every repository) or, for
`architecture-maintainer`, under `<arch>`, and reads repositories by absolute path; a worktree
would isolate nothing it writes. The working directory is outside every repository (section 5.2),
so there is no repository to cut a worktree of.

### 5.4 The agents the Epic pipeline launches

Model and effort are the definition's front matter (`model`, `effort`), which Claude Code applies
when it loads the agent. The launcher passes `--model` (for the Fable fallback, section 5.5) and
records the model in `run.json`; it passes no effort.

| Agent | Role | Launched |
|---|---|---|
| `aws-solutions-architect` | `solutions-architect` | by the script: its first step, a correction, a competing design, its "Finish" |
| Any agent the `find-specialists` catalog lists that has no row here (for example `persistence-architecture-specialist`, `c4-diagram-author`, `polyrepo-steward`) | its own, if any | by the architect in its own session, by the name it chose from the catalog; by the script when the architect names it in its result's `requests`, when it was left running, or when the lead asks it for an opinion |
| `trd-author` | | by the script: the TRD initial write, the first step of the Architecture container; by the architect in its own session for each update; by the script when left running |
| `architecture-maintainer` | | by the architect in its own session; by the script when left running |
| `architecture-team-lead` | `architecture-lead` | by the script, only when the architect's result is unsettled |
| `architecture-decider` | `decider` | by the script, only for a step the lead plans |
| `ui-design-source-selector` | | by the script, in a frontend repository's container under Specs and Stories: the UI sources step |
| `api-specification-author`, `data-model-specification-author`, `acceptance-criteria-writer` | | by the script, in a repository's container under Specs and Stories: the step that writes its document, and a correction or a revision the review plans |
| `dynamodb-schema-access-pattern-reviewer` | | by the script, once per repository whose stacks hold a DynamoDB store, beside the acceptance criteria and before the review |
| `spec-reviewer` | | by the script, once per repository, after the three documents |
| `review-dispute-decider` | | by the script, only when an author disputed a finding of the review |
| `task-decomposer` | | by the script, in a repository's container under Tasks: the decomposition, and one correction when the plan has a gap |
| `task-dependency-mapper` | | by the script, under Task edges, when the span has two or more repositories |

No code chooses an agent for a subject: the architect and the lead choose from the
`find-specialists` catalog, and the script starts the agent they name. `ATW_MATRIX_ROLE` is the
launched agent's role, which decides the `atw-matrix` commands it may run.

### 5.5 Agents declaring `model: fable` (QUESTIONS 1)

**Decision.** The runner uses `fable` as the front matter says; the CLI accepts `fable` as a model
alias (section 0). The Fable allowance is handled per step, from structured facts
(`core/agents.py`):

- When the stream of a session that runs on `fable` carries a rejected `rate_limit_event` whose
  `rate_limit_info` `fablewall.is_refusal` accepts, the runner ends that session, emits a
  `fable-wall` event (the driver records it with `fablewall.record`), and runs **that one step
  again on `opus`**, resuming the same session so its work so far is kept. On the resume the
  launcher passes `--resume <sessionId> --agent <agent> --model opus`,
  together with every other flag of section 5.2. An agent the session starts runs on its own front
  matter model. The model changed, so the retry is reasonable (CONTEXT 7.4). A second refusal, on `opus`,
  fails the step with cause `other`.
- While the Fable wall stands, every `fable` step starts on `opus` (`--model`). The driver passes `fableUntil` (the epoch from
  `fablewall.resets_at()`, or absent) in the dispatch arguments; the orchestrator also honours a
  wall it saw itself during the run.
- The driver's `fablerecovery.py` serves the build and deploy lanes' Workflow sessions and has no
  part in an orchestrated run. `fablewall.py` reads structured fields only.

### 5.6 Output, validation, timeouts, kill and session id

- **Output.** The agent writes its result to the path the brief names: a JSON result or a Markdown document
  to its final path. The runner reads the file, never the transcript. A JSON result is parsed
  strictly (duplicate keys refused) and validated against its schema where it was written; a
  document is checked as its spec says. An accepted output is recorded as an artifact of its
  journal step. When the file is missing or invalid after a normal session end, the one corrective
  retry of section 6.3 runs.
- **Session id.** The runner generates the UUID and passes `--session-id`; nothing is parsed out of
  the stream to find it. The transcript is `<config>/projects/<slug of the session cwd>/<uuid>.jsonl`
  (`harnesspaths.project_dir` rule).
- **Stream reading.** The runner reads stdout line by line for three things only: `rate_limit_event`
  (section 6), the final `result` event (section 6), and liveness. It writes the raw stream to
  `<work>/scratch/<run id>/<step>-<session id>-<attempt>.stream.jsonl`, with the session's standard
  error beside it, and a failure names that file as evidence.
- **Timeouts.** A session with no stream line for `ATW_SESSION_IDLE` seconds (default 1800) or
  running longer than `ATW_SESSION_LIMIT` seconds (default 7200) is killed; the step fails at its
  stage, cause `other` (a stuck session is not a transient fault).
- **Kill.** Each session starts in its own process group (`start_new_session=True`), so the runner
  can kill one session with its MCP server children (`SIGTERM`, then `SIGKILL` after
  `childproc.TERMINATE_GRACE`). `run.py` handles `SIGTERM` by killing every live session group,
  writing a handback with stage `interrupted`, and exiting. The driver registers each session's
  `pgid` from the `session started` event, so its reap covers sessions even if the orchestrator is
  killed with `SIGKILL`.

## 6. Failure causes and retry policy (S02 item 6)

### 6.1 Every cause from a structured fact

| Failure point | Structured fact | Cause |
|---|---|---|
| Agent session: account usage wall | a `rate_limit_event` with `rate_limit_info.status == "rejected"` that `fablewall.is_refusal` does not accept | `quota`, with `failure.resumeAt` = `breaker.exhausted_reset(info)` |
| Agent session: Fable allowance | the same event, accepted by `fablewall.is_refusal`, in a session that runs on `fable` | none: the step reruns on `opus` (section 5.5) |
| Agent session: API failure | the `result` event with `terminal_reason == "api_error"`, or `is_error` with `api_error_status` set | `api` |
| Agent session: ended with no `result` event, killed by a timeout, a failure exit status, or a `result` whose `subtype` is not `success` | the exit status and the absence or `subtype` of the `result` event | `other` |
| Agent session: stopped because another session of the run hit the usage wall or an API failure | the stop the runner recorded for the run's sessions | the cause of that stop (`quota` with its `resumeAt`, or `api`) |
| Agent session: no valid output file after the corrective retry | the parse or schema exception | `other` |
| Agent session: its schema file cannot be read or applied | the exception of the schema load or of the validation machinery | `other`, classified `pipeline-code-defect` |
| `bd` call: the call outlived its timeout | `subprocess.TimeoutExpired` (timeout `ATW_BD_TIMEOUT`, default 180 s) | `bd-timeout` |
| `bd` call: a lock was not acquired in time | the lock acquisition's own result (section 6.2) | `contention` |
| `bd` call: any other non-zero exit | the exit status | `other` |
| git: the index lock is held | the failing subcommand's exit is non-zero and the file `git rev-parse --git-path index.lock` names exists | `contention` |
| git push rejected because the branch moved | after the failed push, `git fetch` then `git merge-base --is-ancestor <remote>/<branch> HEAD` exits 1 | `contention`, after a pull with rebase |
| any executable (`git`, `gh`, `uv run polyrepo.py`, `cdk`): the call outlived its timeout | `subprocess.TimeoutExpired` | `tool-timeout` |
| any executable: the connection failed | `ConnectionError` | `network` |
| any executable: any other non-zero exit | the exit status (the JSON results of `polyrepo.py` carry only `error` text, no code) | `other`, except the owner facts of section 11.3 |
| the section 2 guard: its lock wait expired | the lock's own result (section 7.3) | `contention` |
| a portfolio module raises `beadgraph.GraphError` | the exception's `cause` field | as the field says |
| a portfolio module raises any other exception (the matrix file missing or not valid, its lock wait expired, a refused matrix command, a scoring or UI-source error) | the exception type | `other`, with the traceback in the evidence file |
| section 2 changed by a session | the guard's comparison (section 7.3) | `other`, at stage `constraints-written` |

No cause is set from message text. CONTEXT 7.4 settles this for every row. The cause constants are
defined once, in `core/handback_contract.py`.

### 6.2 `bd`: the structured fact for `bd-timeout` and `contention` (QUESTIONS 6)

**Decision.** `bd` reports no structured lock or server code: its JSON error object carries only
`error`, `hint` and `schema_version` and it exits 1 for every error (section 0). So the facts are
made at the call site, `beadgraph.run_bd`, which every `bd` call of the orchestrator and of the
owner-run portfolio commands goes through:

- **Serialize to prevent contention.** Every `bd` call holds the driver's gate, an exclusive
  `fcntl.flock` on `<driver>/state/bd-gate.lock` (the gate the driver holds around its own `bd`
  calls). Every `bd` write also holds the central beads lock the Linear sync and the fleet sync take
  (the `mkdir` lock at `$CENTRAL_BEADS_LOCK`, default `<temporary directory>/central-beads.lock`,
  the same lock the project's sync scripts take), taken after the gate (`core/tool_locks.py` `bd_gate`). With both
  held, the only writers that can overlap a pipeline write are a person's own `bd` commands.
- **`contention`** = a lock above not acquired within its wait (`ATW_BD_LOCK_WAIT`, default 120 s).
- **`bd-timeout`** = `subprocess.TimeoutExpired` on the `bd` call.
- **`other`** = any other non-zero exit, with the command and `bd`'s output in the failure's
  evidence.

`beadgraph.run_bd` reads nothing from `bd`'s standard error to choose a cause; a `GraphError`
carries one of the three causes above.

### 6.3 Retry policy

- **`contention`, `bd-timeout`, `tool-timeout` and `network`**: retried at the call site
  (`core/tools.py` `retry_call`), the same call or the same whole operation again, three attempts
  in all, waiting 30 s and then 60 s. A write is retried as a whole operation (`Tools.operation`)
  whose body reads the beads again before it writes, so an applied write is updated, never created
  twice (the bead writes are keyed by the elaboration key, `bead_metadata.KEY_ELAB_KEY` in the
  beads-contract schema). Exhaustion is a `RetryExhaustedError`, classified `item`.
- **`api` and `quota`**: not retried in the orchestrator. Every live session of the run is stopped
  with that cause, the journal keeps every done step, and the run returns `ok:false` with
  `failure.cause` (and `failure.resumeAt` for `quota`). The driver's breaker pauses and
  dispatches again; that dispatch begins at the first step that is not done, and a step that holds
  a session continues it.
- **One corrective retry** with specific feedback (CONTEXT 7.4): when an agent step's output is
  missing or invalid after a normal session end, Python writes the exact validation errors to
  `<output>.errors.json` and resumes the same session once (`--resume <sessionId>`, with the flags
  of section 5.2) with a brief whose inputs add that file, labelled `validation errors`, and whose
  outcome line says "Correct the output named in the errors file." The session keeps what it
  already read, and the prompt cache makes the resume cheaper than a new session. A second failure
  fails the step with cause `other`. A launch can switch the corrective retry off; the
  decomposer's correction step does.
- **Corrections that are journal steps.** A correction the flow plans is a step of its own, with
  the file that states what to correct among its inputs: the architect's correction of a
  mechanical defect (at most 3, section 11.1), a correction the lead plans for a finding, an
  author's correction and revision of a spec document, and the decomposer's one correction of a
  plan with a gap.
- **A session that cannot be resumed.** When a session that was asked to resume ends with a failure
  status and no turn, the journal runner gives the step a new session id and starts it once in a
  new session (`SessionNotResumedError`).
- **Never**: rerunning a step with nothing changed. `other` fails the step with its stage, its
  cause and the evidence paths, in the journal and in the handback.

### 6.4 Bead writes have one retry layer (QUESTIONS 7)

**Decision.** `beadwrite.write_story` and `write_task` raise on the first `GraphError`; the
orchestrator's call site applies the retry of section 6.3. Reason: two retry layers multiply
attempts and hide the cause.

### 6.5 The usage-wall pause and the API-outage origin (QUESTIONS 8)

**Decision.** For orchestrated runs the pause and origin come from the handback's structured
fields, not from text:
- `failurecause.pause_for` uses `pause_from_cause` whenever the handback states a known cause: it
  reads `failure.resumeAt` (a number) for `quota`, and pauses without a reset time for `api`.
- The driver sets the failure origin from `failure.cause` and the classification (section 4.4).
- `breaker.pause_of`'s text paths, `handbackio._died_of_outage`, `handbackio.step_defect_origin`
  and `headless._resume_unavailable` read the output of the build and deploy lanes' Workflow
  sessions; a handback that states its cause does not reach them.

### 6.6 The `relay` cause (QUESTIONS 5)

**Decision.** The orchestrator never produces `relay`. `failurecause.CAUSE_RELAY` is the driver's
own cause for the relay of the build and deploy lanes' Workflow scripts; the handback contract
does not define it.

### 6.7 The top-level handler

A step that raises is recorded as failed in the journal (section 2.1) and the flow reports the
failure itself: it releases the Epic (`elaboration.release`) when it had claimed it and the Epic is
not marked done, writes the run record, and returns a report with `ok:false`.

`run.py` wraps the whole flow in `try ... except BaseException` for what escapes it (`SystemExit`,
`KeyboardInterrupt`, an exception re-raised from a worker thread, or a failure before the flow
starts). It writes the traceback to a file beside the handback (suffix `.traceback.txt`), runs
the cleanup the run registered (stop every live session group, then release the Epic), and writes
a handback with `ok:false`, the stage of the step that was running, the cause and classification
of section 6.8, and the traceback file as `detailPath`, then exits 0. `SIGINT` and `SIGTERM` raise
`InterruptedError` in the main thread; the run stops its sessions and reports the stop stage
`interrupted`. Only a failure to write the handback file itself, or a failure before the handback
path is known (the control repository variable unset, the dispatch-arguments contract unloadable),
leaves the driver's `no-handback`.

### 6.8 Classification

Every failure carries a classification beside its cause (`core/handback.py` `failure_for`,
vocabulary in `core/handback_contract.py`). It is decided from the exception chain:

| Classification | When | What the driver does |
|---|---|---|
| `interrupted` | the stop file was seen between sessions (`PipelineStoppedError`, stage `shutdown`), or a signal or keyboard interrupt (stage `interrupted`); the stage that was running is kept as `interruptedStage` | never an item failure, never counted toward repeated failures |
| `pipeline-code-defect` | a session cleanup error, a runtime type check failure, a handback validation failure, a `PipelineDefectError`; a `TypeError`, `ValueError`, `AttributeError`, `KeyError`, `NameError` or `IndexError` in the chain; an `ImportError` after an agent session started; any failure that is no `StepError` and fits no other row. An exception raised `from None` ends the chain: the content failure a step found in a file or an agent's output and stated in its evidence is raised that way, so it is an `item` failure | stops new dispatch |
| `setup` | a failure before the flow started, a session setup error, or a `StepError` at stage `input`; an `ImportError` before any agent session started | stops new dispatch |
| `item` | a retry allowance used up; any other `StepError` whose cause is not transient | recorded for the item; other items continue |
| `transient` | a cause among `quota`, `api`, `bd-timeout`, `contention`, `timeout`, `tool-timeout`, `network`, or a timeout or connection error in the chain, with retries left to the driver | pauses or backs off, then dispatches again |

The rows are tested in the order `pipeline-code-defect` (the first four conditions), `setup`,
`pipeline-code-defect` (the named exception types), `item` (retries used up), `transient`, `item`.

A fatal classification (`setup`, `pipeline-code-defect`) also touches the stop file
`$ATW_STOP_FILE` when the driver set it, so no further agent step starts while the paid sessions
that are running finish.

## 7. Concurrency (S02 item 7)

### 7.1 What runs in parallel

One orchestrator process per Epic dispatch; the driver's lanes keep their slots. Steps run in the
journal's walk order. The one exception: consecutive sibling steps that each have an agent, have no
child steps and name only done steps in their inputs run as concurrent sessions
(`journal_run.concurrent_group`). That is how the
contracts author and the data-model author of one repository. Repositories run one after another,
each in its own container of steps.

**The cap.** At most `ATW_ORCH_SESSIONS` agent sessions at once per run (default 4). Steps beyond
the cap wait. The account-wide number is this cap times the driver's `--elaboration-concurrency`;
the owner sets both.

### 7.2 `bd` writes

Serialized by the two locks of section 6.2. The driver's `bd-gate.lock` is held by the orchestrator
for every `bd` call, so orchestrators and the driver take turns; the central beads lock is held for
writes, so the Linear and fleet syncs take turns with them too.

### 7.3 The section 2 guard across runs (QUESTIONS 4)

**Decision.** One guard per architecture root, shared by every orchestrator process
(`core/constraints.py` `Section2Guard`), kept in `<driver>/state/section2-guard/<key>/`, where
`<key>` is the first 16 hexadecimal digits of the SHA-256 of the architecture root's path. The
session runner puts every agent session inside it whenever the dispatch names an architecture
root.

- `guard.lock`: an exclusive `fcntl.flock` taken for every guard operation below (wait
  `ATW_ARCH_LOCK_WAIT`, default 120 s), so two orchestrator processes never snapshot, compare or
  restore at the same time.
- `live/<sessionId>`: one file per live agent session of any run, holding the process id of the
  orchestrator that runs it, written before the session starts and removed after its check. An
  entry whose process is not alive is removed under the lock.
- `snapshot.json` and `kept/`: the one standing snapshot
  (`archstate.snapshot_constraints(<arch>, keep=True)`: digest, git status, existence, kept copy),
  with the vault's `HEAD` commit when it was taken.

Rules, each under `guard.lock`:

1. **Snapshot.** Before an agent session starts, when `live/` is empty (no session of any run is
   live), the snapshot is taken. Otherwise the new session shares the standing snapshot.
2. **Check.** When any session ends, section 2 is snapshotted again and compared with the standing
   snapshot (digest, existence, git status).
3. **An owner's committed change is accepted.** When section 2 differs, its git status is clean,
   the vault's `HEAD` moved forward from the snapshot's, at least one commit between the two
   touches section 2 and none of those commits carries a `Pipeline-Run:` trailer, the change is
   the owner's committed work: the snapshot is taken again, nothing is restored, nothing fails.
4. **Any other change is restored.** The changed folder is copied to `changed-<timestamp>/` in the
   guard's folder (so an uncommitted edit the owner made at the same moment is never lost),
   section 2 is restored with `archstate.restore_constraints(<arch>, kept)`, every live session of
   **this** run is stopped, and the step whose session just ended fails at stage
   `constraints-written`, cause `other`. The evidence names the `changed-` copy, the sessions that
   were live (of any run, from `live/`) and what the restore wrote and deleted. Another run's guard
   check that then sees section 2 equal to the snapshot finds nothing to do.
5. A snapshot, check or restore that fails fails the step at stage `constraints-written`, cause
   `other`; a lock wait that expires fails it with cause `contention`.

**Reason.** Sessions of one run and of concurrent Epic runs overlap, so a per-session or per-run
before-and-after cannot attribute a change and two runs would restore from different copies. One
shared snapshot under one lock gives one answer; the outcome (restore and record the failure) does
not depend on which session is blamed. The owner's way to change section 2 while the pipeline runs
is to commit the change: a committed change by the owner is accepted, and an uncommitted change
made while sessions run is restored but kept as a copy and named in the failure's evidence.

### 7.4 Two Epics changing arc42 at the same time

Every change of the matrix is made under the matrix's lock (`matrixstore.update_matrix`). Before
it designs a change to something that exists, the architect asks the matrix what rests on it
(`atw-matrix impact --id`) and which other Epics share it (`atw-matrix related --epic`). The
review scope of an Epic is the documents that Epic reaches that are not effective. The promotion
step sets effective and commits only the documents of its own review scope.

## 8. Owner holds and questions (S02 item 8)

**Decision.** The orchestrator writes no owner inbox entry and no hold. It returns owner facts in
the handback and the driver acts on them (`driver-contract.md` §4):

- a step that needs the owner fails with a `StepError` at stage `requires-human-action`, whose
  evidence lines each name the fact and what the owner does; the journal records the failure on
  the step;
- the dispatch result, assembled from the journal (`flows/elaboration_result.py`), is then
  `ok:false`, `stage: "requires-human-action"`, with `requiredHumanActions` set to those evidence
  lines;
- the driver's `lane._person_needed` holds the Epic (`elabstate.hold_for_person`:
  elaboration state `bead_metadata.ELABORATION_AUTHORING`, cause
  `bead_metadata.CAUSE_AWAITING_HUMAN`, both from
  `skills/beads-contract/schemas/bead-metadata.schema.json`), and its `human_log`
  writes the owner inbox (`ownerinbox.Writer`, `$ATW_OWNER_INBOX`) with the restore command;
- the next dispatch after the owner acts begins at that same step.

Only owner facts become `requiredHumanActions` (CONTEXT 7.9): the owner concerns of an
`architecture-decider` ruling (`business-conflict`: two business requirements no design meets
together; `section-2-conflict`: the only workable design conflicts with a section 2 constraint),
and the repository-creation owner facts of section 11.3. Every other failure returns a
`failure.cause` and a classification (section 6.8). The orchestrator releases the Epic's lifecycle
owner (`elaboration.release`) on every exit after a successful claim unless the Epic was marked
done (`prd-to-spec.md`, and section 6.7).

## 9. What the driver does for the elaboration lane

`<driver>/orchestrated.py` starts `run.py` in its own process group with the command line
`dispatchargs.command` builds and the arguments file `dispatchargs.build_arguments` writes,
translates its events (section 4.1), and reads the handback file. `lane.py` selects the Epic,
builds its arguments with `workitems.elaboration_args`, and adds the lifecycle owner and the
execution identity. The arguments name the Epic, its PRD and where things are; they say nothing
about which steps are done.

**The dispatch timeout is an idle timeout.** The driver kills the orchestrator's group only when it
has written no event line (any of section 4.1, the heartbeat included) for `ATW_ORCH_IDLE` seconds
(default 3600, above the 1800 s session idle limit and the 300 s heartbeat). There is no total
cap: an Epic run is many sessions long, and each session is bounded by `ATW_SESSION_LIMIT`
(section 5.6).

**The step journal.** The driver loads `<orch>/core/step_journal.py` by path
(`<driver>/stepjournal.py`) and never restates its rules.

| Driver module | What it does with a journal |
|---|---|
| `journalprogress.py` (`observe.journal_progress`) | reads it for the dashboard: the outermost steps, the steps running, the next step, a failed step, the counts |
| `journalstart.py`, run by `elabmark.py --bead <id> --start-at <step>` | sets the named step and every step after it back to planned, when the owner asks for an earlier start |
| `elabmark.py --bead <id> --steps` | lists the steps and marks the one the next run begins at |
| `journalport.py` | writes a journal for a bead that has saved run data and none yet, through `<orch>/port_journal.py` |

The driver changes a journal in those two cases only. A run begins at the first step the journal
does not mark done; no other file, state or argument makes it begin anywhere else.

## 10. The matrix

One JSON file, `<driver>/matrix.json`, tracked in git in the control repository, holds three
members: `version`, `entries` and `relationships`. The entries are Epics and their requirements,
features, constraints, disagreements, arc42 documents, services, components, infrastructure,
events, stacks, packages and layers; each entry and each relationship states the side it came
from, `architecture` or `repository`. Its generic shape is
`<plugin>/skills/artifact-handoff/schemas/matrix.schema.json` and its kinds are data, in
`schemas/matrix-kinds.json`; the modules
`<plugin>/scripts/portfolio/matrix*.py` implement it and `<plugin>/bin/atw-matrix` is the one
command. Agents use the command; the orchestrator calls the modules in-process. The
specification is `<plugin>/blueprint/design/matrix.md`.

- **Lifecycle.** A document entry mirrors the `lifecycle_state` of its arc42 file. The check step
  reads the documents an Epic reaches that are not effective (`review-scope`) and records nothing;
  the promotion step sets the approved documents to `lifecycle_state: effective`, mirrors that in
  the matrix (`sync-documents --paths`), and commits and pushes them in the vault.
- **The approved and verified flags.** `blueprint/requirements/pipelines.md` (the Elaboration
  pipeline) and `blueprint/requirements/matrix.md` state what each flag means and when it is set.
- **One home per entry.** An entry has at most one `homeIn` on each side; the command refuses a
  second.
- **Roles.** The role of the session (`ATW_MATRIX_ROLE`) decides which commands it may run.
- **Opening a run.** The open-run step brings the Epic's entry with its requirements, the document
  entries up to date in one change.

## 11. Flow-level decisions

### 11.1 Architecture

The Architecture container holds, in order: the architect's step; the check step; then either a
correction by the architect and a new check, or the lead and a new check, or the promotion step.
The architect reviews and approves its own architecture against the criteria; nothing else
reviews it.

- **The check step** (`flows/architecture_check.py`) judges nothing; every branch is a rule over
  the matrix, the criteria file, the architect's result and the Epic's review log. It writes
  `architecture/checks/<step id>/check.json`. A problem plans one correction by the architect and
  a new check, at most 3 times; after that the step fails. A problem is a matrix defect, an
  architecture or technical-requirement criterion with no answer, or a problem of the review log
  at the context's `reviewLogPath` as the `log-architecture-review` skill's check reports it: a
  missing or malformed log, a decision without two options, its choice or its reason, an AWS
  resource the design adds or changes (an `addedOrChangedElements` entry whose matrix entry has a
  `resourceType`) with no review entry, and a design with an AWS resource and no Well-Architected
  review. With no problem it reads what is in review, writes `review-scope.json` and
  `unlinked.json`, records nothing in the matrix, and, when the result's conclusion is
  `unsettled` and no lead has run, plans the lead and a new check. Otherwise it plans the
  promotion step.
- **The lead** (`flows/architecture_ruling.py`) writes its routing of the unsettled matters and
  adds the steps it calls for under its own step: a correction by the architect, a specialist's
  opinion, a competing design, or the decider. A routing that rejects every matter adds no step.
- **The decider** (`flows/architecture_ruling.py`) is handed one question file and writes one
  ruling, and settles each disagreement the question cites in the matrix (`atw-matrix settle`);
  the step that accepts the ruling reads each back and fails when `stands` is unset. A ruling that
  raises an owner concern fails the step at stage `requires-human-action`.
- **The promotion step** (`flows/architecture_promotion.py`) sets the documents of the review
  scope to effective, files the review log in the vault at
  `<architectureRoot>/review-logs/<epic id>.json`, mirrors the documents in the matrix and links
  the log from the Epic's entry (attribute `reviewLog`: its path in the vault and its SHA-256),
  removes each settled disagreement whose losing statement was corrected, commits and pushes the
  documents and the log in the vault, and commits and pushes the matrix. A document it cannot set
  effective fails the step, naming each with the reason.

### 11.2 Repository span

The step `atw-matrix epic --closure` (`flows/repo_scoping.py`; the script key keeps its old name)
reads what the Stories build: the architect's `addedOrChangedElements` and the existing elements
it names under `unchangedWorkElements` as where the Epic's work that leaves them unchanged lands;
an Epic can have both, and both empty fails the step. An event is built as part of the service that publishes it. A
Story is one repository's share of that. Each entry's architecture-side stack (`authority_holder`)
and that stack's repository come from the matrix; a stack that names no repository is given the
one the naming rules give it. No agent places anything. Each `story_build_problems` sentence,
a repository that may hold no product entry (the control repository, the architecture folder), and a missing repository whose stacks have more than one type or more than
one app each fail the step. It writes `span-elements.json` and `repo-scoping.json` and plans one
container per repository, each with its first step `spec_authoring.context`.

### 11.3 Repository creation (QUESTIONS 9; the verifier's finding 16)

A repository of a stack a Story builds in that the inventory (`polyrepo.py inventory --name
<name>`) lacks is created by the span step with `polyrepo.py create`, which requires `--space` and `--template`.
The tool records the stack the new repository holds in the matrix.

- **The template** is the type of the repository's stacks, the last token of a stack's name
  (`service`, `infra`, `lib`, `web` and so on). A repository is a frontend repository when that
  type is `web`.
- **The app space** is the `app` of the repository's stacks. Stacks of more than one type or more
  than one app and stacks that name no app fail the step. The folder inside
  the space comes from the placement in the steward's `.polyrepo/config.yaml`, which `polyrepo.py create` applies.

**Owner facts.** Recognised before the first `polyrepo.py create` runs, by a preflight whose
results are exit statuses and command output:
1. `gh auth status` exits non-zero → owner fact: the GitHub CLI is not signed in on this machine;
   run `gh auth login`.
2. `gh api user/memberships/orgs/<github_owner> --jq .state` (`<github_owner>` is the owner
   of the repositories `polyrepo inventory` lists on GitHub) exits non-zero or prints a value other than `active` → owner
   fact: the signed-in GitHub account is not an active member of `<github_owner>`.
Either is written to `repo-creation.json` and fails the span step at stage
`requires-human-action`, with the owner fact as its evidence (section 8). A `polyrepo.py create`
that fails after a passing preflight fails the step at stage `repo-creation`, cause `other` (its
result carries only error text, section 6.1).

### 11.4 The TRD

`trd-author` writes the TRD at the path the architecture context names. The TRD initial write
is the first step of the Architecture container, from a request the script writes: the
requirements not considered functional, many of them pre-written in arc42. Once the higher-level
architecture is in arc42, the architect has it make the TRD architecture update with the
technical or architecture decisions that impact the detailed design; the detailed design reads the
TRD, and the architect has it updated in place as the design settles. It reads the
Epic's constraints from `atw-matrix epic <id> --constraints`, the set the architect reads, and the
PRD requirement headings `atw-matrix epic <id>` names. Its answer lists every requirement each
write added or changed, and the step that accepts the answer records one constraint for each as
a pointer (`trd`: the Epic and the requirement id, a heading of the TRD), so the requirement's
text lives in the TRD alone. `trd.confirm` also fails on a constraint whose pointer names a
requirement the TRD has no heading for. The step
`trd.confirm` (`flows/trd_authoring.py`) runs after the Architecture container: it checks that the
TRD has YAML front matter and that every `decisionIds` entry resolves under the architecture root,
and records the TRD's path and digest on the Epic bead. The driver files the TRD in the vault after
elaboration is done.

### 11.5 Spec authoring

- **The Story's title and description are deterministic.** `story-<slug>.json` is `{title:
  "<repository name>: <PRD title>", description: <a fixed template listing the repository, the
  what the Story builds (id and element) and the three spec document paths>, decisionIds}`. The Story is a
  single-repository container and nothing reads its prose to decide anything, so no session writes
  it.
- **One review per repository.** `spec-reviewer` checks the three documents against the
  specs-and-Tasks criteria. For a repository whose stacks hold a DynamoDB store (an
  infrastructure entry with a `dynamodb-` resource type homed in a stack the Story builds in),
  `dynamodb-schema-access-pattern-reviewer` first checks the data-model document's DynamoDB access
  patterns, and its findings (D1, D2 ...) join the review's (F1, F2 ...). A finding goes once to the author of the document it names; a
  disputed finding goes to `review-dispute-decider`; an upheld finding goes back to that author. Each of these
  sessions is its own journal step, planned by the step whose result calls for it
  (`specs/epic/spec-authoring.md`).
- **Every author writes its document.** No structured field says which surface an item touches, so
  no author is skipped; an author with nothing to specify writes a short "not applicable" document.
- **UI design sources.** For a repository whose placement has `frontend: true`,
  `ui-design-source-selector` writes `<work>/candidates/spec-<slug>.ui.json`; which items the Story builds
  are UI items is its judgment; Python checks the file against the supplied bundles and the placed
  item ids. The `frontend` flag of the placement is the only structured field that says a repository
  holds UI.

### 11.6 Task decomposition and finish

- **The Task scope of the scoring steps.** `elaboration.finish` takes a scope: with
  `scope="epic-tasks"` it calls `scoring.score` with the write scope limited to the Tasks under the
  Epic and no Epic roll-up, and writes no Epic WSJF key. Step `elaboration.score` calls it without
  marking the Epic, step `elaboration.done_rule` reads the Tasks it left unscored, step
  `storyedges.story_edges` writes the Story edges, and step `elaboration.finish` calls it again to
  mark the Epic.
- **The task-deps schema check is the mapper session's output check.** The session's output is
  validated against the schema narrowed to the span's Task names, so the exact errors reach the one
  corrective retry; `write_all_task_edges` validates the keys again before it writes.
- **Which metadata marks a Task as started.** A Task is started when its status is neither `open`
  nor `blocked`, or any key of the `BUILD_LIFECYCLE_KEYS` or `CDS_AUDIT_KEYS` group of
  `skills/beads-contract/schemas/bead-metadata.schema.json` (imported from the generated
  `bead_metadata.py`) is present and non-empty. Only the build lane writes those keys, so their
  presence proves the lane worked on the Task and its Story worktree may hold that work. A `deferred`
  Task counts as started: a person set it.
- **A Task bead the plan no longer names.** When a decomposition runs again, an unstarted Task bead
  that elaboration wrote and that no Task of the new plan matches is deleted after the plan's Tasks
  are written (`beadwrite.retire_superseded_tasks`). Before the delete, each `blocks` edge from a
  Task outside the Story onto it is added onto every written Task that cites at least one of the
  same work items. An edge with no such Task is recorded as a warning, not re-added.
- **A `web-ui` Task citing UI items of two artifacts: warn and keep the first**, as
  `hierarchy.check_cds_contract` does. The planner can settle it deterministically; refusing would
  fail the Story for a normalization.
- **`surfaces` when the spec does not settle it: `null`.** The bead's description renders null as
  `unknown (none declared)`.
