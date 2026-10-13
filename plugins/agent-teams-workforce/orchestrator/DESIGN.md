# DESIGN: the Python orchestrator for the Epic pipeline

Failure handling: bounded transient retries and quota pauses remain. An ordinary item failure is recorded and excluded from selection for the current invocation; other eligible items continue. Setup, code, schema, and runtime type defects stop new dispatch, preserve the original diagnostic, and let current paid steps finish. Named within-step corrective passes remain bounded content work; failed runs do not dispatch repair or diagnosis agents.

Step S02 of the pipeline rewrite. This document decides how the Epic (elaboration) pipeline runs
once the Workflow scripts are gone: where the code lives, how a step is declared, how saved work is
reused, how agent sessions are started and costed, how failures get a structured cause, what runs
in parallel, how owner questions travel, what the driver stops doing, and how the element status
matrix is stored and fed. Every later step (S03 to S05a) builds from it. Where this document and a
spec under `specs/epic/` differ, this document is the later decision and wins; each such case is
named where it is decided.

Revised the same day for the independent verifier's 21 findings
(`claude-inbox/pipeline-python-rewrite/S02-findings.md`) and the owner's fifth-round rulings
(briefs carry facts only; the matrix is tracked in git; the pipeline is single-user and
single-machine).

Names used throughout:

- `<plugin>` = `/Users/msat1971/projects/mark-satterfield/toolset/plugins/agent-teams-workforce`
- `<orch>` = `<plugin>/orchestrator`
- `<control>` = `$ATW_CONTROL_REPO` (today `/Users/msat1971/projects/SkillSpoke/apps/personal-agent/SkillSpoke`)
- `<driver>` = `<control>/ops/sdlc-automation`
- `<work>` = `<control>/.claude/workflow-runs/artifacts/<epic-id>/` (the Epic's working directory;
  `artifactio.working_dir`)
- `<arch>` = `$ATW_ARCH_PATH`
- `<config>` = `$CLAUDE_CONFIG_DIR` of the pipeline (today `~/.claude-skillspoke`)
- `<installPath>` = the installed plugin the pipeline runs, from `pluginversion.running_dir()`

## 0. Evidence used

Facts about Claude Code were taken from tools on 2026-10-09, not from memory:

- `claude --version`: `2.1.296 (Claude Code)`.
- `claude --help` (same version). The flags this design relies on: `-p`, `--output-format
  stream-json`, `--verbose`, `--agent <agent>`, `--agents <json-or-file>` ("with --print the path
  to a file that holds one"), `--model` (aliases include `fable`, `opus`, `sonnet`), `--effort`
  (`low`, `medium`, `high`, `xhigh`, `max`), `--session-id <uuid>`, `-r/--resume`,
  `--setting-sources`, `--settings <file-or-json>`, `--strict-mcp-config`, `--mcp-config`,
  `--plugin-dir`, `--permission-mode`, `--disallowedTools`, `--add-dir`. `--bare` makes
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
  `beadsio.py`; in the plugin `scripts/portfolio/beadgraph.py`, `beadwrite.py`,
  `archbaseline.py`, `resumefacts.py`, `archclosure.py`, `archstate.py`, and
  `skills/polyrepo-repo/scripts/polyrepo.py`; `<control>/ops/lib/central-beads-lock.sh`;
  `<config>/settings.json`; `<control>/.claude/settings.json`; `<control>/.polyrepo/config.yaml`
  and `manifest.yaml`.
- Read-only checks run for this design:
  - `archbaseline.survey_freshness(<work>/architecture/survey.json, seal=False)` for `ssbd-mb689`,
    `ssbd-hdqid` and `ssbd-guuuz`: all three `current: true`, no errors, no warnings.
  - `bd show ssbd-zzzzzz-nonexistent --json`: exit 1; the JSON error object carries only `error`,
    `hint`, `schema_version`, no error code.
  - `bd show ssbd-mb689 ssbd-hdqid ssbd-guuuz --json`: all three carry the elaboration state
    `bead_metadata.ELABORATION_IN_PROGRESS` (beads-contract schema).
  - `ls <arch>/target/`: only `README.md` (no saved target folder exists).
  - The three Epics' `architecture/candidates/` folders: every complete candidate has the same
    bytes as its final file in `plans/` or `rounds/`; the others are `.checkpoint` and
    `.progress.json` files with no result body.
  - `<control>/.polyrepo/config.yaml` `repositories.patterns`: each application name pattern names
    its app space (`personal-agent`, `shared`, `marketing`, `employer`).

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
| `<orch>/core/` | the step journal and its runner, the registry of step code, the agent runner and launcher, the artifact store, the tools layer (`bd`, git, `gh`, `polyrepo.py`, `cdk`), the section 2 guard, the event writer |
| `<orch>/flows/` | the steps of the Epic's journal: `prd_to_spec.py` (the dispatch and the open-run step), `architecture.py`, `architecture_check.py`, `architecture_review.py`, `architecture_promotion.py`, `architecture_files.py`, `trd_authoring.py`, `repo_scoping.py`, `elaboration_steps.py`, `elaboration_result.py`, and the phase functions `spec_authoring.py`, `spec_review.py`, `task_decomposition.py`, `task_edges.py` |
| `<orch>/checks/brief_check.py` | the brief and contract-skill check (section 2.3, PLAN S03e) |
| `<orch>/checks/run_all.py` | the one command that runs every check in `<orch>/checks/` |
| `<orch>/specs/`, `<orch>/measurements/`, `<orch>/DESIGN.md` | documents |

There is no brief template folder: a brief is built in code from facts only (section 2.3).

**Running the checks.** One command runs every check script in `<orch>/checks/` (each Python file
there with a `__main__` entry point, found by listing the directory), supplies `--artifact-script`
and `--survey-dir` to the checks that declare them, prints one line per check and the full output
of each failure, and exits non-zero unless every check passed:

```sh
"$SKILLSPOKE_CC/.venv/bin/python" "$ATW_PLUGIN_ROOT/orchestrator/checks/run_all.py"
```

The control repository comes from `ATW_CONTROL_REPO`, then `SKILLSPOKE_CC`, or `--control-repo`. A
check that needs a saved survey is tried against the saved architecture directories under
`<control repo>/.claude/workflow-runs/artifacts/*/architecture`, newest first, because a saved
survey stops being reusable when the documents and repository trees it is bound to change; with
none saved the check is reported `SKIPPED` and the command exits non-zero. No hook runs this
command.

The flow registry holds one flow, `prd-to-spec`. Its phases are functions called by it, not
separate entries: the only entry into the Epic pipeline is the driver (CONTEXT 7.18).

**Reasons and evidence.**
- The flows call the plugin's agent definitions, skills and `scripts/portfolio/` modules, and must
  run against the same version of them. The driver already resolves the installed version
  (`pluginversion.running_dir()` reads `installed_plugins.json` `installPath`), so a dispatch that
  runs `<installPath>/orchestrator/run.py` gets matching code and agents.
- A child process per dispatch keeps a crash out of the supervisor, picks up a newly installed
  version on the next dispatch, and lets the driver keep killing by process group as
  `headless._kill_group` does today.
- The Agent SDK is not used (section 5.1), so the package needs nothing beyond the interpreter the
  driver already runs.

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
Tasks, Task edges, Score the Tasks, Story edges and Mark the Epic elaborated
(`flows/prd_to_spec.py` `outermost_steps`). A step with child steps is never run itself. Steps
found at run time are added by the step that finds them: the open-run step plans the architect's
step and the check after it, the check plans the reviewers and the promotion, the span step plans
one spec step per repository, and a spec step plans its repository's Task step.

A step without child steps is one of two kinds, and the registry (`core/journal_registry.py`) finds
its code:

- **Script step.** The step's `script` text is the key of a handler (`@script_step("<key>")`):
  `prd_to_spec.open_run`, `atw-matrix check; atw-matrix unapproved`, `atw-matrix approve`,
  `trd.confirm`, `atw-matrix prd --closure`, `spec_authoring.run`, `task_decomposition.run`,
  `task_edges.run`, `elaboration.score`, `storyedges.story_edges`, `elaboration.finish`. A handler
  returns a `Completion` or raises `StepError(stage, cause, evidence)` (section 6).
- **Agent step.** The step's `agent` name is the key of a launch builder (`@agent_step(...)`), which
  is registered by role for every agent whose definition states that role. The builder returns an
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
step with `atw-step-journal`, as the `subagent-contract` skill describes. After such a session the
runner reads the journal again: a step whose child steps are all done is closed by the runner; a
child left not done is the next step. An agent left running is launched as its own session from
the request file its step holds; "Finish" is launched as the same agent, continuing its session.

A step that already holds a session id, a "Finish" step, and a later step of an agent that holds a
session earlier in the journal continue that session (`claude --resume`); when the conversation is
gone a new session starts.

When a spec step creates a Story bead and a Task step creates Task beads, the same step creates
that bead's journal in the same directory (pipeline `deploy` for a Story, `build` for a Task), with
the creating step as its first, done step and the files the bead's later steps are handed as its
artifacts.

The dispatch result (the handback, section 4.4) is assembled from the journal's artifacts
(`flows/elaboration_result.py`), so it is the same whichever dispatch ran a step.

### 2.2 How `scripts/portfolio/` and the other tools are called

**Decision.** In-process import for every `scripts/portfolio/` module (`matrixstore`, `matrixsync`,
`matrixreview`, `matrixquery`, `matrixexpertise`, `beadgraph`, `beadwrite`, `hierarchy`,
`elaboration`, `scoring`, `storyedges`, `cdsbundles`, `specui`).
Subprocess, argv list, no shell, with a timeout, for executables: `bd` (through `beadgraph`),
`git`, `gh`, `uv run <plugin>/skills/polyrepo-repo/scripts/polyrepo.py <cmd> --json`, `cdk`.
`artifactio.py` (driver code, located by `$ATW_ARTIFACT_SCRIPT`) is loaded in-process with
`importlib`, as `beadgraph._contract()` already loads `beads-contract.py`.

**This overturns the PLAN recommendation** (subprocess for `depscore.py` subcommands). Evidence:
- `depscore.py` is a CLI over these modules (its docstring lists each subcommand as a call into
  them); calling it as a subprocess returns only an exit status and printed JSON.
- The modules raise typed exceptions: `beadgraph.GraphError` with a `cause` field,
  `scoring.ScoringError`, `specui.SpecUiError`, `archresume.ResumeError`. A subprocess reduces them
  to exit 2 and a JSON `{error, cause}` (`depscore.main`). The `GraphError.cause` field is kept as
  the carrier, and section 6.2 changes how it is set (from structured facts, not from `bd`'s
  standard error).
- The specs already plan in-process calls: `task-decomposition.md` §5 ("calling the existing
  library functions directly (no `depscore.py` subprocess)"), `spec-authoring.md` step 12
  (`beadwrite.write_story` in-process), `prd-to-spec.md` step 14 (`elaboration.finish` logic
  in-process).
- The orchestrator runs from the same plugin version as the modules (section 1). The one piece of
  code loaded from outside the plugin is `artifactio.py`; section 3.3 sets its compatibility rule.

**What an in-process call must handle** (the verifier's finding 9):
- Every deterministic step body runs inside `try ... except Exception`; an exception that is not a
  `StepError` becomes `StepError(<step's stage>, "other", <path of a file holding the
  traceback>)`. The typed exceptions above map as section 6.1 says.
- Imported calls run under `contextlib.redirect_stdout(sys.stderr)`, so nothing a module prints can
  enter the event channel (section 4.1).
- `run.py`'s top-level handler catches `BaseException` (section 6.7), so `SystemExit` or
  `KeyboardInterrupt` raised in a worker thread and re-raised by `future.result()` still produces a
  handback.
- A module that starts a subprocess must give it a timeout. The ones that do not today are listed
  in the modules themselves.

`depscore.py` stays the command line over these modules for the workflows and the owner. The
orchestrator calls the module functions themselves: the scoring step calls `elaboration.finish`
and the Story edge step calls `storyedges.story_edges` (section 11.6).

### 2.3 Briefs carry facts only

A brief is built in code (`core/agent_context.py` `brief`), never from a prose template, and holds
exactly:

1. the bead id;
2. the input file paths (absolute), each with a label: either the name of the journal artifact
   that holds the file, or the label the agent's definition names (for example `prd`, `criteria`,
   `context`, `review scope`, `findings`, `step journal`);
3. the output file path (absolute);
4. a one-line expected outcome;
5. for a journal step, `request` (what is asked: the builder's text, or the step's description)
   and `step` (the journal step id).

It carries no instructions, no rules, no procedures, no schemas and no file content. Everything
else an agent needs is in its definition (`<plugin>/agents/<name>.md`) and in the skills its
front matter names, whose text the launcher puts in the agent's context (section 5.1). The
validation errors of a corrective retry are written by Python to a file and listed as one more
input.

`<orch>/checks/brief_check.py` exits non-zero, naming each finding, when a flow module's brief
construction holds JSON schema text or prose beyond the fact fields, or when the register
(`specs/epic/agent-contracts.md`), the index (`specs/epic/INDEX.md`), the agent front matter and
the shared contract rules disagree: every agent of an agent-facing contract loads a contract skill
(`artifact-handoff` or `architecture-baseline`), every contract has its rules section in
`skills/artifact-handoff/epic-contracts.md`, and every named schema exists.

### 2.4 One set of criteria for the architecture team

`<plugin>/skills/architecture-baseline/review-criteria.json` holds every criterion as data: its id,
its level (architecture, technical requirement or implementation), its home document and its text;
the agents responsible for each level; and, for each reviewer group, its reviewer, the criteria it
covers and the rule that selects it (`appliesWhen`: kinds of unapproved content, and the names of
review signals in the architect's result). `review-standard.md` beside it is written from that
file by `skills/artifact-handoff/scripts/review_criteria.py`.

`aws-solutions-architect` develops the architecture and the TRD to exactly these criteria and
answers each architecture and technical-requirement criterion in its result. The reviewers apply
exactly these and no others, each to the items its group covers. A criterion is satisfied by the
document that is its home; nobody asks a document for detail below its level. No brief carries any
part of the criteria: the brief names the criteria file as the input `criteria`.

### 2.5 Where the contracts and schemas live

Every file an agent produces or consumes has one JSON Schema in
`<plugin>/skills/artifact-handoff/schemas/`. Python validates each result against the same file and
reads it through a module generated from it: `scripts/architecture_work_contract.py` (from
`architecture-result.schema.json`, which defines every shape of the architecture team's files
once; each file has a wrapper schema that refers to its definition), `scripts/matrix_contract.py`
(from `matrix.schema.json`, including the review scope a reviewer is handed), and the other
generated contracts the `artifact-handoff` skill lists. An agent of the architecture team finds
the schemas through the `architecture-baseline` skill; the spec and Task agents through
`artifact-handoff`. A contract only code produces and consumes is one typed Python module, named in
the register. No schema text is placed in a prompt.

## 3. Where a run begins, and what the phases still record

### 3.1 The journal decides

Nothing but the step journal decides whether a step runs: no file hash, timestamp, changed
document or freshness check. A step's output is recorded as an artifact of the step right after it
is written (a file by path, or a value such as a reviewer's findings); later steps are handed
those artifacts from the journal. A missing file is found only when a step reads it, and is then
that step's failure. An earlier start is made by invalidating a step (`atw-step-journal
invalidate`), which resets it and every step after it; only the owner asks for it.

Files stay flat under `<work>`, with the architecture part's files under `<work>/architecture/`
(`specs/epic/INDEX.md` lists them). Run facts that are not about one file (session ids, model,
effort, timings, the cause of a failed step) go in the run record `<work>/run.json` (section 4.4).

### 3.2 Inside the spec, Task and Task edge steps

Each of the steps `spec_authoring.run`, `task_decomposition.run` and `task_edges.run` runs one
phase function of the same name for one repository (or for the Epic) as a single journal step.
Inside that step the phase function starts its agent sessions through `AgentRunner.run_step`,
which records each accepted result with `artifactio.record` (`<file>.meta.json`) and does not start
a session again whose recorded inputs hash as recorded (`ArtifactStore.reusable`). `STEPS.md` keeps
one line per completed phase step for the dashboard. These records decide nothing about which
journal step runs.

### 3.3 Compatibility with `artifactio.py`

`artifactio.py` is driver code, loaded in-process from `$ATW_ARTIFACT_SCRIPT`. The orchestrator
uses only the functions `core/artifact_contract.py` names, and the driver changes them additively.

## 4. Ledger, dashboard and cost (S02 item 4)

### 4.1 Events on stdout

**Decision.** The orchestrator writes one JSON object per line on stdout and nothing else there
(diagnostics go to stderr, and imported code runs with stdout redirected to stderr, section 2.2).
The driver captures stdout to the run's `.out` file and translates each event into the existing
callbacks, so `ledger.EVENT_TYPES`, `observe.py`, `outcomes.py`, `runview.py` and the dashboard keep
their event types.

The event names, their fields, the session states and the note kinds are defined in one place,
`orchestrator/core/handback_contract.py` (`EventName`, `OrchestratorEvent` and its member
TypedDicts, `validate_event`, and the event builders). The driver loads that module through
`ops/sdlc-automation/handbackcontract.py`, validates every line with `validate_event`, and branches on
the `Wire` event values. How the driver routes each event:

- a phase event is announced through `on_phase` with the composite contract's progress prefix;
- a verdict event goes to `on_verdict` with its fields;
- a session event is announced through `on_phase`, and the driver registers the session's process
  group with `childproc` and `sessionregistry` when it starts and forgets it when it ends;
- a heartbeat writes nothing to the ledger; it counts as progress for the dispatch's idle timeout
  (section 9);
- a note is announced through `on_phase` with its kind;
- a fable-wall event is recorded with `fablewall.record`.

The orchestrator writes a heartbeat every `ATW_HEARTBEAT` seconds (default 300) while any of its
sessions has written a stream line since the last heartbeat. The progress prefix keeps
`outcomes._phase_name` counting phases as it does today; session and note texts carry no prefix, so
they are recorded but never counted as phases. No ledger event type is added.

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

No step of the elaboration emits a verdict event. What a reviewer found, what the lead routed and
what the decider ruled are artifacts of their journal steps.

### 4.4 Handback and run record (QUESTIONS 22)

**Decision.** The handback is a file. `run.py` writes it atomically before it exits. Its keys, value
types and value vocabularies (failure classification, failure cause, stop stages, phase statuses,
refusal codes) are defined in one place, `orchestrator/core/handback_contract.py`
(`HandbackDocument`, `validate`, `Wire`); the driver loads it through
`ops/sdlc-automation/handbackcontract.py`.

`detailPath` is the run record, whose shape is `orchestrator/core/manifest.py` `RunManifest`; each
of its sessions is a `handback_contract.Session`. It also carries the notes of section 4.1.

`run.py` exits 0 whenever it wrote a handback, whatever `ok` says; a non-zero exit means it died
before writing one, and the driver makes its usual environment failure (`no-handback`). Section 6.7
makes that case rare.

Keys dropped from the handback: `dispatchFailures` (folded into `failure`), `degraded`. The driver
sets `failure_origin` from `failure.cause` (`api` and `quota` are `environment`, every other cause
is `work`) instead of `handbackio.step_defect_origin`, which reads text (section 6.5).

The dispatch arguments the orchestrator reads, the scratch file names and the `run.py` command line
are defined in one place, `ops/sdlc-automation/dispatchargs.py` (`DispatchArguments`,
`build_arguments`, `parse_arguments`, `command`); the plugin reads them through
`orchestrator/core/driver_contracts.py`.

### 4.5 Cost attribution and the run unit (QUESTIONS 21)

**Decision.** The run unit stays one dispatch: one cost record `state/runs/<run stem>.cost.json`
per orchestrator run, summing every agent session that run started. Each agent session is its own
top-level Claude Code session, so the record lists them:

- The runner chooses each session's id itself (`--session-id <uuid>`, section 5.2) and records it
  in `run.json` and the handback's `sessions[]`. A resumed session (sections 5.5, 6.3) keeps its id.
- S03d changes `runcost.py`: `measure_run` takes the session list from the handback
  (`dispatch.Handback` gains `sessions: tuple[dict, ...]`), measures each with
  `measure_session(sessionId)` (which already finds a transcript in any project folder through
  `session_project`), sums the four components, and builds the per-phase and per-role totals from
  the session list instead of workflow `.meta.json` files. The record's shape and its
  deduplication key are defined in one place, `ops/sdlc-automation/costsidecar.py` (`CostSidecar`,
  `record_key`).
- `KNOWN_COMPOSITES` is unchanged.

**What proves a run is running (CONTEXT 7.12).** The Epic shows "running" only while the driver's
lease is live and the orchestrator's process is verified, as for any dispatch today
(`sessionregistry`, `childproc`). An agent step shows "running" only between its `session started`
and `session ended` events and only while its `pid` is alive (`os.kill(pid, 0)`, with the `pgid`
from the event matching `os.getpgid(pid)`). The phase shown is the last `phase` event the run wrote;
no phase is inferred. No counter is shown that the records cannot compute.

## 5. Agent runner (S02 item 5)

### 5.1 The headless CLI, with the agent and its skills loaded by `--agent`

**Decision.** Each agent step runs the Claude Code CLI as a subprocess (`claude -p`), not the Agent
SDK. Reasons: the driver already starts, supervises, kills and costs `claude` processes
(`headless.py`, `childproc.py`, `runcost.py`) under `CLAUDE_CONFIG_DIR=<config>`; the SDK is not
installed (section 0) and its own documentation says it passes its options to "the CLI subprocess",
so it would add a dependency and run the same binary.

The runner loads the agent's definition and its skills; the prompt is only the brief (section 2.3):

1. The runner reads `<installPath>/agents/<agent>.md`: its frontmatter and its body.
2. It writes `<session dir>/agents.json` = `{"atw-<agent>": {description, prompt: <body>, tools,
   disallowedTools, model, effort, skills, maxTurns, mcpServers}}` with the values from the
   frontmatter, except `model` and `effort`, which come from section 5.4 (and `model` from section
   5.5 on a Fable fallback). `isolation` is left out (section 5.3). `skills` is the frontmatter list
   as it stands, so the skills holding the agent's procedures and contracts (sections 2.4, 2.5) load
   with it.
3. It passes `--agents <session dir>/agents.json --agent atw-<agent>`.
4. It writes the brief on stdin.

No schema text, rule text or file content is placed in the prompt.

Why a session-local definition and not `--agent agent-teams-workforce:<agent>`: the runner must
leave out `isolation` and set the model on a Fable fallback without editing agent files, and the
documented `--agent` behaviour then holds for the exact definition the runner wrote. The `atw-`
prefix keeps the name apart from the plugin's own agent.

**Minimum CLI version.** The `--agents` file form needs 2.1.281 or later (section 0). At start the
runner reads `claude --version` once (`pluginversion.claude_version` does the same read); a version
below 2.1.281, or one it cannot parse, fails the run at stage `input`, cause `other`, before any
session.

### 5.2 The command line and minimal context

```
claude -p --output-format stream-json --verbose
  --session-id <uuid>
  --agents <session dir>/agents.json --agent atw-<agent>
  --model <model> --effort <effort>
  --setting-sources project
  --settings <session dir>/settings.json
  --strict-mcp-config [--mcp-config <session dir>/mcp.json]
  --plugin-dir <installPath> [--plugin-dir <other plugin installPath> ...]
  --permission-mode bypassPermissions
  --disallowedTools <each of headlessenv.DENIED_TOOLS, plus Agent and AskUserQuestion>
  --add-dir <each directory the step's addDirs names>
```

- **Working directory.** A per-session directory outside every repository,
  `$ATW_SESSION_ROOT/<run id>/<step>-<n>/` (new environment variable; default
  `<config>/atw-sessions/`). It holds `agents.json`, `settings.json`, `mcp.json` and nothing else.
  Reason: with the working directory inside `<control>`, Claude Code auto-discovers the control
  repository's `AGENTS.md`/`CLAUDE.md` and the `ops/` and `ops/sdlc-automation/` ones above it; an
  Epic agent needs none of them, because its brief names every path it reads and its definition and
  skills hold its rules.
- **Settings.** `--setting-sources project` with a working directory that holds no project
  settings loads no settings file; user settings (`<config>/settings.json`) are not loaded. Today
  they enable nine plugins, two `SessionStart` context injectors, a `UserPromptSubmit` injector,
  the status line, `model: opus` and `effortLevel: high` (read 2026-10-09), all of which would load
  into every session. `--settings <session dir>/settings.json` brings back only the safety hooks:
  the runner copies, from `<config>/settings.json`, every `PreToolUse` hook whose command names one
  of `no-verify-blocker.sh`, `pipeline-run-blocker.sh`, `bd-init-blocker.sh`,
  `aws-profile-required.sh` (a constant list in the runner, matched by script file name, so the
  hook commands themselves are read from the owner's file, not copied into code).
- **Plugins and skills.** `--plugin-dir <installPath>` loads `agent-teams-workforce`. For every
  skill the agent's frontmatter `skills` names with another plugin's prefix (for example `cds:`),
  the runner adds that plugin's `installPath` from `<config>/plugins/installed_plugins.json`. No
  other plugin loads.
- **MCP servers.** The runner writes `<session dir>/mcp.json` with only the servers the agent's
  frontmatter `mcpServers` names, taking each definition from the sources `mcpconfig.collect_allowed`
  reads (`<control>/.mcp.json`, then the global config), and passes it with `--strict-mcp-config`.
  With none named, `--mcp-config` is omitted and no server loads. Reason: `--strict-mcp-config`
  stops every other configured server from loading, and the server definitions live in those config
  files, not in the agent file; the `mcpServers` list in `agents.json` then names servers that exist.
- **Tools.** The agent's `tools` and `disallowedTools` come from its frontmatter through
  `agents.json`; `--disallowedTools` adds the driver's denied list plus `Agent` and
  `AskUserQuestion`, so no Epic session starts another agent or waits on a person.
- **What is accepted as loading, explicitly.** `<config>` holds `rules`, `skills` and `agents`
  entries (symlinks into the owner's `~/.claude`), and a user `CLAUDE.md` may exist there. They are
  user-level memory and content, not settings files, and `--setting-sources` is not documented to
  exclude them. They are accepted: excluding them would mean a different `CLAUDE_CONFIG_DIR` for
  agent sessions, which would also move the transcripts and the login the driver relies on. The
  descriptions of the plugin's own skills load with `--plugin-dir`; that is accepted, because the
  agents name those skills. The `Agent` tool is denied, so no agent listing is loaded. **S07 checks
  this** from the owner's first run: the `system`/`init` event at the top of one agent session's
  transcript lists what loaded (tools, skills, MCP servers, plugins), and the first assistant
  turn's `usage` gives the startup tokens against the 68k baseline (`measurements/baseline.md`).
- **Not used:** `--bare` (it accepts only `ANTHROPIC_API_KEY` auth, and the pipeline runs on the
  subscription: `breaker.exhausted_reset` reads the `five_hour` and `seven_day` subscription
  windows); `--json-schema` (results are files, section 5.6); `--no-session-persistence` (the
  transcript is the cost record).
- **Environment.** `headlessenv.child_env` as today (the `ATW_*` variables, `TMPDIR` in the run's
  scratch folder, `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0`).

### 5.3 `isolation: worktree` (QUESTIONS 2)

**Decision.** Ignored: the runner leaves `isolation` out of `agents.json` and passes no
`--worktree`. Every Epic agent writes only under `<work>` (outside every repository) or, for the
architecture writers and maintainer, under `<arch>`, and reads repositories by absolute path; a
worktree would isolate nothing it writes. The working directory is outside every repository
(section 5.2), so there is no repository to cut a worktree of.

### 5.4 The agents the Epic pipeline launches

Model and effort are the definition's front matter (`model`, `effort`); the launcher passes them as
`--model` and `--effort` and records them in `run.json`. The flow names agents by the `role` their
definitions state, never by name, so the roster of a role is the set of definitions that state it.

| Agent | Role | Launched |
|---|---|---|
| `aws-solutions-architect` | `solutions-architect` | by the script: its first step, a correction, a competing design, its "Finish" |
| `integration-pattern-architect`, `persistence-architecture-specialist`, `security-architecture-designer`, `cdk-infrastructure-designer`, `event-schema-designer`, `api-contract-designer`, `graphql-schema-designer`, `domain-event-modeler`, `bounded-context-mapper` | `design-specialist` | by the architect in its own session; by the script when left running or when the lead asks for an opinion |
| `architecture-diagram-author`, `c4-diagram-author`, `uml-diagram-author` | `diagram-author` | by the architect in its own session; by the script when left running |
| `trd-author` | `trd-author` | by the architect in its own session; by the script when left running |
| `architecture-maintainer` | `document-maintainer` | by the architect in its own session; by the script when left running |
| `polyrepo-steward` | `repository-steward` | by the architect in its own session; by the script when left running |
| `architecture-boundary-guardian`, `failure-mode-analyst`, `architecture-pattern-challenger`, `architecture-tradeoff-skeptic`, `operational-readiness-reviewer`, `cost-architecture-reviewer`, `cost-impact-reviewer`, `trd-validator` | `architecture-reviewer` | by the script, when the rule of its reviewer group selects it; again for a re-check the lead plans |
| `architecture-team-lead` | `architecture-lead` | by the script, only when a review raised something or the architect's result is unsettled |
| `architecture-decider` | `decider` | by the script, only for a step the lead plans |
| `api-specification-author`, `data-model-specification-author`, `acceptance-criteria-writer`, `openapi-contract-reviewer`, `spec-decider` | | inside the step `spec_authoring.run` |
| `task-decomposer` | | inside the step `task_decomposition.run` |
| `task-dependency-mapper` | | inside the step `task_edges.run`, when the span has two or more repositories |

An agent whose definition has `startsRoles` is given an `Agent` tool limited to agents with those
roles, at depth one; an agent started by another agent starts no one. `ATW_MATRIX_ROLE` is the
launched agent's role, which decides the `atw-matrix` commands it may run.

### 5.5 Agents declaring `model: fable` (QUESTIONS 1)

**Decision.** The runner uses `fable` as the frontmatter says; the CLI accepts `fable` as a model
alias (section 0). The Fable allowance is handled per step, from structured facts:

- When a session's stream carries a `rate_limit_event` whose `rate_limit_info` `fablewall.is_refusal`
  accepts, the runner ends that session, emits a `fable-wall` event (the driver records it with
  `fablewall.record`), and runs **that one step again on `opus`**, resuming the same session so its
  work so far is kept. On the resume the runner rewrites `agents.json` with `model: "opus"` and
  passes `--resume <sessionId> --agents <session dir>/agents.json --agent atw-<agent> --model opus`,
  together with every other flag of section 5.2 unchanged, so the agent definition and the session
  model agree and no precedence question arises. The model changed, so the retry is reasonable
  (CONTEXT 7.4).
- While the Fable wall stands, every `fable` step starts on `opus` (written the same way into
  `agents.json` and `--model`). The driver passes `fableUntil` (the epoch from
  `fablewall.resets_at()`, or absent) in the dispatch arguments; the orchestrator also honours a
  wall it saw itself during the run.
- `fablerecovery.py` (workflow resume, `FABLE-CALL` log cutoffs, `workflow_record`) does not apply
  to orchestrated runs. It stays for the Task pipeline's Workflow dispatches until S12 and is
  deleted in S15. `fablewall.py` stays: it reads structured fields only.

### 5.6 Output, validation, timeouts, kill and session id

- **Output.** The agent writes its result to the path the brief names: a JSON result to
  `<work>/candidates/<name>.json` (or under `<work>/architecture/candidates/`), a Markdown document
  to its final path. The runner reads the file, never the transcript. A JSON candidate is parsed
  strictly (duplicate keys refused) and validated against its schema; on success Python writes the
  canonical JSON to the final path and records its `.meta.json`. A document is checked as its
  spec says and recorded. When the file is missing or invalid after a normal session end, the one
  corrective retry of section 6.3 runs.
- **Session id.** The runner generates the UUID and passes `--session-id`; nothing is parsed out of
  the stream to find it. The transcript is `<config>/projects/<slug of the session cwd>/<uuid>.jsonl`
  (`harnesspaths.project_dir` rule).
- **Stream reading.** The runner reads stdout line by line for three things only: `rate_limit_event`
  (section 6), the final `result` event (section 6), and liveness. It writes the raw stream to
  `<run scratch>/<step>-<n>.stream.jsonl` in the failure record.
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
| Agent session: Fable allowance | the same event, accepted by `fablewall.is_refusal` | none: the step reruns on `opus` (section 5.5) |
| Agent session: API failure | the `result` event with `terminal_reason == "api_error"`, or `is_error` with `api_error_status` set | `api` (`quota` when the same stream carried a rejected `rate_limit_event`) |
| Agent session: ended with no `result` event, killed by a timeout, or `subtype` `error_max_turns` / `error_during_execution` | the exit status and the absence or `subtype` of the `result` event | `other` |
| Agent session: no valid output file after the corrective retry | the parse or schema exception | `other` |
| `bd` call: the call outlived its timeout | `subprocess.TimeoutExpired` (timeout `ATW_BD_TIMEOUT`, default 180 s, as `beadsio.DEFAULT_TIMEOUT`) | `bd-timeout` |
| `bd` call: the lock was not acquired in time | the lock acquisition's own result (section 6.2) | `contention` |
| `bd` call: any other non-zero exit | the exit status | `other` |
| git (run by the orchestrator, or by a module changed per section 11.7): the index lock is held | the failing subcommand's `exit` is non-zero and `<repo>/.git/index.lock` (or the worktree's) exists | `contention` |
| git push rejected because the branch moved | after the failed push (`subcommand: push`), `git fetch` then `git merge-base --is-ancestor origin/<branch> HEAD` exits 1 | `contention` (pull with rebase, then push again) |
| git: anything else, or a git subprocess timeout | the exit status, or `subprocess.TimeoutExpired` | `other` |
| `polyrepo.py`, `gh`, `cdk`: non-zero exit | the exit status (their JSON results carry only `error` text, no code: `polyrepo.py` `cmd_create`, `res["error"] = str(exc)`) | `other`, except the owner facts of section 11.3 |
| element status matrix or the vault integration: lock wait expired | the lock's own result (sections 7.4, 10.3) | `contention` |
| element status matrix: file missing or not valid | `FileNotFoundError`, `json.JSONDecodeError`, a missing `elements` object | `other` |
| a portfolio module raises a typed error | the exception type and its field (`GraphError.cause`; `ScoringError`, `ResumeError`, `SpecUiError` are `other`) | as named |
| a deterministic step raises any other `Exception` | the exception type (section 2.2) | `other`, with the traceback file as evidence |
| section 2 changed by a session | the guard's comparison (section 7.3) | `other` |

No cause is set from message text. CONTEXT 7.4 settles this for every row.

### 6.2 `bd`: the structured fact for `bd-timeout` and `contention` (QUESTIONS 6)

**Decision.** `bd` reports no structured lock or server code: its JSON error object carries only
`error`, `hint` and `schema_version` and it exits 1 for every error (section 0). So the
orchestrator creates the facts itself at the call site:

- **Serialize to prevent contention.** Every `bd` call the orchestrator makes (directly or through
  `beadgraph._bd`) holds the driver's gate, an exclusive `fcntl.flock` on
  `<driver>/state/bd-gate.lock` (the gate `beadsio._bd_gate` already holds around every driver
  `bd` call). Every `bd` write also holds the central beads lock the Linear sync and the fleet sync
  take (the `mkdir` lock at `$CENTRAL_BEADS_LOCK`, default `$TMPDIR/skillspoke-central-beads.lock`,
  `ops/lib/central-beads-lock.sh`), taken after the gate. With both held, the only writers that can
  overlap a pipeline write are a person's own `bd` commands.
- **`contention`** = a lock above not acquired within its wait (`ATW_BD_LOCK_WAIT`, default 120 s,
  as `beadsio.BD_GATE_WAIT`).
- **`bd-timeout`** = `subprocess.TimeoutExpired` on the `bd` call.
- **`other`** = any other non-zero exit, with the command and `bd`'s output as evidence in the failure record.

`beadgraph._bd` is changed in place (S03b): it takes the gate from the orchestrator (a callable the
orchestrator installs), passes a timeout, and stops classifying `bd`'s standard error
(`failure_cause`, `connection_retryable`, `CONNECTION_BACKOFF`); a `GraphError` carries the cause
above. The owner-run portfolio commands use the same function and get the same behaviour.

### 6.3 Retry policy

- **`contention` and `bd-timeout`**: retried at the call site, the same call again, with backoff
  starting at 30 s and doubling, with at most three attempts. Exhaustion records an item failure. Each
  attempt re-reads what it needs, so an applied write is updated, never created twice (the writers
  are keyed by the elaboration key, `bead_metadata.KEY_ELAB_KEY` in the beads-contract schema).
- **`api` and `quota`**: not retried in the orchestrator. Every live session of the run is stopped,
  completed steps keep their records, and the run returns `ok:false` with `failure.cause` (and
  `failure.resumeAt` for `quota`). The driver's breaker pauses and redispatches; the rerun reuses
  every recorded step.
- **One corrective retry** with specific feedback (CONTEXT 7.4): when an agent step's output is
  missing or invalid after a normal session end, Python writes the exact validation errors (or the
  missing path) to `<output>.errors.json` and resumes the same session once (`--resume
  <sessionId>`, with the flags of section 5.2) with a brief whose inputs add that file and whose
  outcome line says "Correct the output named in the errors file." The session keeps what it already
  read, and the prompt cache makes the resume cheaper than a new session. A second failure fails the
  step with cause `other`. The specs' named corrective passes (repo scoping's avoid list, task
  decomposition's uncited items, the closure refusal, the decider's re-ask) follow the same rule:
  their feedback is a file Python writes, listed as an input.
- **Never**: rerunning a step with nothing changed. `other` fails the run with the step, its cause
  and the evidence paths, in the failure record.

### 6.4 `beadwrite.WRITE_BACKOFF` (QUESTIONS 7)

**Decision.** Removed from the library. `beadwrite.write_story` and `write_task` raise on the first
`GraphError`; the orchestrator's call site applies the backoff of section 6.3. Reason: two retry
layers multiply attempts and hide the cause, and CONTEXT 7.4 sets one schedule (30 s, doubling, cap
30 min) that the library's 2 s and 5 s do not follow.

### 6.5 The usage-wall pause and the API-outage origin (QUESTIONS 8)

**Decision.** For orchestrated runs the pause and origin come from the handback's structured
fields, not from text:
- `failurecause.pause_from_cause` reads `failure.resumeAt` (a number) for `quota` instead of
  `reset_epoch_in(headline)`.
- The driver sets `failure_origin` from `failure.cause` (section 4.4).
- `breaker.pause_of`'s text paths (`wall_of` parsing the headline, `transient_of`'s regex),
  `handbackio._died_of_outage`, `handbackio.step_defect_origin` and
  `headless._resume_unavailable` are not called for an orchestrated composite. They remain for the
  Task pipeline's Workflow sessions until S12 moves those lanes, and are deleted then.

### 6.6 The `relay` cause (QUESTIONS 5)

**Decision.** The orchestrator never produces `relay`. `failurecause.CAUSE_RELAY` stays until S15,
because the Task pipeline's Workflow scripts still use the relay until then; S15 removes it from
`failurecause.py` and its readers, as PLAN S15 step 3 says.

### 6.7 The top-level handler

`run.py` wraps the whole flow in `try ... except BaseException`. On any escape (a `StepError` not
handled by its flow, `SystemExit`, `KeyboardInterrupt`, or an exception re-raised from a worker
thread by `future.result()`) it stops every live session group, releases the Epic
(`elaboration-release`, section 8) when it had claimed it, writes a handback with `ok:false`, the
stage of the step that was running (from the run record), cause `other` (or the `StepError`'s
cause), and the traceback file as evidence, then exits 0. Only a failure to write the handback file
itself leaves the driver's `no-handback`.

## 7. Concurrency (S02 item 7)

### 7.1 What runs in parallel

One orchestrator process per Epic dispatch; the driver's lanes keep their slots. Steps run in the
journal's walk order. The one exception: consecutive sibling steps that each have an agent, have no
child steps and name only done steps in their inputs run as concurrent sessions
(`journal_run.concurrent_group`). That is how the reviewers of one review run together.
Repositories run one after another, each as one spec step and one Task step; inside a spec step
the contracts author and the data-model author run together.

**The cap.** At most `ATW_ORCH_SESSIONS` agent sessions at once per run (default 4). Steps beyond
the cap wait. The account-wide number is this cap times the driver's `--elaboration-concurrency`;
the owner sets both.

### 7.2 `bd` writes

Serialized by the two locks of section 6.2. The driver's `bd-gate.lock` is used by the orchestrator
for every `bd` call, so orchestrators and the driver take turns; the central beads lock is used for
writes, so the Linear and fleet syncs take turns with them too.

### 7.3 The section 2 guard across runs (QUESTIONS 4)

**Decision.** One guard per architecture root, shared by every orchestrator process, kept in
`<driver>/state/section2-guard/`:

- `guard.lock`: an exclusive `fcntl.flock` taken for every guard operation below, so two
  orchestrator processes never snapshot, compare or restore at the same time.
- `live/<sessionId>`: one empty file per live agent session of any run, created before the session
  starts and removed after its check (stale entries, whose recorded pid is not alive, are removed
  under the lock).
- `snapshot.json` and `kept/`: the one standing snapshot
  (`archstate.snapshot_constraints(<arch>, keep=True)`: digest, git status, existence, kept copy),
  plus the vault's `HEAD` commit when it was taken.

Rules, each under `guard.lock`:

1. **Snapshot.** Before an agent session starts, when `live/` is empty (no session of any run is
   live), the snapshot is retaken. Otherwise the new session shares the standing snapshot.
2. **Check.** When any session ends, section 2 is snapshotted again and compared with the standing
   snapshot (digest, existence, git status).
3. **An owner's committed change is accepted.** When section 2 differs but its git status is clean
   and every commit between the snapshot's `HEAD` and the current `HEAD` that touches section 2
   carries no `Pipeline-Run:` trailer, the change is the owner's committed work: the snapshot is
   retaken, nothing is restored, nothing fails. The promotion step commits only the
   documents it names, and none of them is in section 2.
4. **Any other change is restored.** The changed folder is copied to
   `<driver>/state/section2-guard/changed-<timestamp>/` (so an uncommitted edit the owner made at the
   same moment is never lost), section 2 is restored with `archstate.restore_constraints(<arch>,
   kept)`, every live session of **this** run is stopped, and the step whose session just ended
   fails at stage `constraints-written`, cause `other`, naming the sessions that were live (of any
   run, from `live/`) and the `changed-` copy. Another run's guard check that then sees section 2
   equal to the snapshot finds nothing to do.
5. A snapshot, check or restore that fails fails the step at its stage, cause `other`.

**Reason.** Sessions of one run and of concurrent Epic runs overlap, so a per-session or per-run
before-and-after cannot attribute a change and two runs would restore from different copies. One
shared snapshot under one lock gives one answer; the outcome (restore and record the failure) does not
depend on which session is blamed. The owner's way to change section 2 while the pipeline runs is to
commit the change: a committed change by the owner is accepted, and an uncommitted change made
while sessions run is restored but kept as a copy and named in the failure record.

### 7.4 Two Epics changing arc42 at the same time

Every change of the matrix is made under the matrix's lock (`matrixstore.update_matrix`). Before
deciding a fact whose home is an existing heading, the architect claims it (`atw-matrix claim`); a
heading another Epic in progress holds is that Epic's to have reviewed, and the review scope lists
it under `heldByOthers`. The promotion step approves and commits only the items of its own Epic's
reviews, by name.

## 8. Owner holds and questions (S02 item 8)

**Decision.** The orchestrator writes no owner inbox entry and no hold. It returns owner facts in
the handback and the driver acts on them exactly as today (`driver-contract.md` §4):

- the flow returns `ok:false`, `stage: "requires-human-action"`, and `requiredHumanActions` (a list
  of strings, each naming the fact and what the owner does);
- the driver's `lane._person_needed` holds the Epic (`elabstate.hold_for_person`:
  elaboration state `bead_metadata.ELABORATION_AUTHORING`, cause
  `bead_metadata.CAUSE_AWAITING_HUMAN`, both from
  `skills/beads-contract/schemas/bead-metadata.schema.json`), and its `human_log`
  writes the owner inbox (`ownerinbox.Writer`, `$ATW_OWNER_INBOX`) with the restore command.

Only owner facts become `requiredHumanActions` (CONTEXT 7.9): the architecture decider's
`business-conflict` and `architecture-conflict` concerns, a missing architecture root
(`no-arch-path`), and the repository-creation owner facts of section 11.3. Every other failure
returns a `failure.cause`; `other` records an item failure and excludes it from selection for the current invocation. Fatal classifications stop new dispatch. The orchestrator releases the Epic's lifecycle owner
(`elaboration-release`) on every exit after a successful claim unless the Epic was marked done
(`prd-to-spec.md` step 16, and section 6.7).

## 9. What the driver stops doing for the elaboration lane (S02 item 9)

S05 adds `<driver>/orchestrated.py`, which starts `run.py` in its own process group, translates its
events (section 4.1), and reads the handback file. `headless.HeadlessClaudeDispatcher.dispatch_one`
routes `prd-to-spec` to it.

**The dispatch timeout is an idle timeout.** The driver kills the orchestrator's group only when it
has written no event line (any of section 4.1, the heartbeat included) for
`ATW_ORCH_IDLE` seconds (default 3600, above the 1800 s session idle limit and the 300 s
heartbeat). There is no total cap: an Epic run is many sessions long, and each session is already
bounded by `ATW_SESSION_LIMIT` (section 5.6). The 7200 s `DEFAULT_DISPATCH_TIMEOUT` keeps applying
to the Workflow dispatches until S12.

Then, for `prd-to-spec`:

| Driver code | Fate |
|---|---|
| `prompts.dispatch_prompt` / `prompts.resume_prompt` for `prd-to-spec` | **delete** the `prd-to-spec` paths in S05; the functions stay for the Task pipeline until S12 |
| `headless._dispatch_with_recovery` and `_fresh_fable_attempt` (Fable workflow recovery) | **not used** for `prd-to-spec`; stay for the Task pipeline until S12 |
| `fablerecovery.py` | **not used** for `prd-to-spec`; **delete** in S15 |
| `fablewall.py` | **keep** (structured fields; the driver records the orchestrator's `fable-wall` events and passes `fableUntil`) |
| `headless._render_progress`, `_announce_phase_of`, `_render_agent_entry` (workflow progress parsing), `VERDICT_MARKER` text verdicts | **not used** for `prd-to-spec`; stay for the Task pipeline until S12 |
| `headless._wait_while_progressing` (total deadline plus progress grace) | **not used** for `prd-to-spec`; the idle timeout above replaces it |
| `headless._silent_after_workflow`, `_workflow_ended`, `_believe_workflow_result`, `runjournal.workflow_result`, `runjournal.persist_session` | **not used** for `prd-to-spec`; stay until S12 |
| `handbackio.parse_handback` (`HANDBACK` line) | **not used** for `prd-to-spec` (handback file through `handback_from_result`) |
| `handbackio._died_of_outage`, `step_defect_origin`, `breaker.pause_of` text paths, `headless._resume_unavailable` | **not used** for `prd-to-spec` (section 6.5) |
| the relay arguments in `headless._dispatch_session` | **not sent** for `prd-to-spec` |
| `workitems.plugin_root_args` (`pluginRoot`) | **delete** for `prd-to-spec` |
| `workitems.with_artifact_plan`: `resume`, `_rule_saved_files`, `artifactio.set_aside_stale`, `artifactio.dispatch_resume` | **delete** for `prd-to-spec`; **keep** `_start_over` / `artifactio.retire_once` |
| `phaserec.expected_phases` reading `prd-to-spec.js` | **change** to `dispatch.COMPOSITE_PHASES` (section 4.2) |
| `observe.relay_steps` for elaboration | **change** to the rounds and plans files (section 4.2) |
| `artifactio.plan` | **keep** as the dashboard's reader; skip unknown step names; drop `recon:<repo>` |
| `runcost.record_run` / `measure_run` | **change** to sum the handback's sessions (section 4.5) |
| `failurecause.pause_from_cause` | **change** to read `failure.resumeAt` (section 6.5) |
| `spendguard.LIVE` registration, `sessionregistry`, `childproc` reaping | **keep**, for the orchestrator's group and each session `pgid` it reports |
| `ledger.EVENT_TYPES` `trigger_plan`, `trigger_dispatch`, and the `trigger_dispatch` branch in `failures.py` | **delete** in S05 (QUESTIONS 25: no producer since commit `64b4adbb`; `ledger.read_all` parses old lines whatever their type, so old ledgers still read) |
| `routing.route_elaboration` reason texts | **change** in S05 (QUESTIONS 48): a feature returns `skip`, reason "a feature needs a PRD and an Epic; the owner writes the PRD"; the Story reason says the Story is elaborated through its parent Epic; `selection.select_only`'s feature skip reason stops naming `/agent-teams-workforce:start-prd`. Reason: S05 is the step that edits the driver's elaboration path; S08 deletes the command the old texts name |

## 10. The matrix

One JSON file, `<driver>/matrix.json`, tracked in git in the control repository, holds how
repositories, stacks, elements, PRDs, features, design facts, disagreements and architecture
documents relate, with each row's approval and the code state of each element. Its shape is
`<plugin>/skills/artifact-handoff/schemas/matrix.schema.json`; the modules
`<plugin>/scripts/portfolio/matrix*.py` implement it and `<plugin>/bin/atw-matrix` is the one
command. Agents use the command; the orchestrator calls the modules in-process.

- **Approval.** A row or a heading is approved or not. The check step lists what is not approved for
  an Epic and marks it in review; the promotion step marks what the reviews covered approved,
  sets the reviewed documents to `lifecycle_state: effective`, and commits and pushes them in the
  vault. Reviewers see only unapproved content.
- **Code state.** An element's code is `none`, `legacy`, `built` or `deployed`. Only the build
  pipeline sets `built` and `deployed`; only that code is trusted. The repository span of an Epic
  is the elements its features are realized by, and everything those depend on, whose code is
  neither `built` nor `deployed`.
- **One home per fact.** A design fact is registered with its one home (document and heading); the
  command refuses a second home.
- **Roles.** The role of the session (`ATW_MATRIX_ROLE`) decides which commands it may run.
- **Opening a run.** The open-run step brings the Epic's PRD row, the document rows and the Epic's
  expertise list up to date in one change.

## 11. Flow-level decisions

### 11.1 Architecture

The Architecture container holds, in order: the architect's step; the check step; then either a
correction by the architect and a new check, or the lead and a new check, or the reviewers and the
promotion step, with the lead's step between them when a review raised something.

- **The check step** (`flows/architecture_check.py`) judges nothing; every branch is a rule over
  the matrix, the criteria file and the architect's result. It writes `check-<n>.json`. A problem
  plans one correction by the architect and a new check, at most 3 times; after that the step
  fails. With no problem it lists what is not approved, writes `review-scope.json`, and, when the
  result's conclusion is `unsettled` and no lead has run, plans the lead and a new check. Otherwise
  it selects the reviewers by the `appliesWhen` rules, writes each its own narrowed scope, and
  plans one step per reviewer and the promotion after them. A rule that selects no reviewer fails
  the step.
- **A review** (`flows/architecture_review.py`) records its file, the findings inside the
  reviewer's scope and the number dropped as outside it. The first review that holds a finding or
  a request for alternatives plans one step for the lead after the last reviewer.
- **The lead** writes its routing and adds the steps it calls for under its own step: a correction
  by the architect with a re-check by the reviewer that raised the finding, a specialist's opinion,
  a competing design, or the decider. A routing that rejects every item adds no step.
- **The decider** is handed one question file and writes one ruling, which it also records in the
  matrix. A ruling that raises an owner concern fails the step at stage `requires-human-action`.
- **The promotion step** (`flows/architecture_promotion.py`) refuses while a review raised
  something and no lead records that every item is resolved. It approves in the matrix, sets the
  documents to effective, commits and pushes them in the vault, and commits the matrix. An item it
  cannot approve fails the step, naming each with the reason.

### 11.2 Repository span

The step `atw-matrix prd --closure` (`flows/repo_scoping.py`) reads the span from the matrix; no
agent places anything. An element with no repository in the matrix, a repository that may hold no
product element (the control repository, the architecture folder, a marketing repository), and a
missing repository whose name matches no template each fail the step. It writes
`span-elements.json` and `repo-scoping.json` and plans one spec step per repository. An Epic whose
features reach no element to build fails the step.

### 11.3 Repository creation (QUESTIONS 9; the verifier's finding 16)

**The app space.** `polyrepo.py create` requires `--space`, `--template` and `--purpose`. The
steward's `missingRepos` entry gives name, template and purpose; part B derives `--space`
deterministically from the name: the `space` of the first `repositories.patterns` entry in
`<control>/.polyrepo/config.yaml` whose `regex` matches the name and whose `kind` is `application`
(the same rule `polyrepo.py` uses to classify a name). A name that matches no application pattern,
or matches the `marketing` pattern, is a placement finding for the one corrective pass
(`repo-scoping.md` step 6). The folder inside the space comes from the config's
`templates.placement`, which `polyrepo.py create` already applies.

**Owner facts.** Recognised before any `polyrepo.py create` runs, by a preflight whose results are
exit statuses and JSON fields:
1. `gh auth status` exits non-zero → owner fact: "the GitHub CLI is not signed in on this machine;
   run `gh auth login`".
2. `gh api user/memberships/orgs/<github_owner> --jq .state` (`github_owner` from
   `<control>/.polyrepo/config.yaml`, today `satteritsik`) exits non-zero or prints a value other
   than `active` → owner fact: "the signed-in GitHub account is not an active member of
   `<github_owner>`".
Either returns `requiredHumanActions` and stops repo scoping at stage `repo-creation` with no cause
(section 8). A `polyrepo.py create` that fails after a passing preflight is a recorded failure with cause `other` (its result carries only error text, section 6.1).

### 11.4 The TRD

`trd-author` writes the TRD at the path the architecture context names, at the architect's
request: drafted as soon as the architect's state file exists, then updated in place. The step
`trd.confirm` (`flows/trd_authoring.py`) runs after the Architecture container: it checks that the
TRD has YAML front matter and that every `decisionIds` entry resolves under the architecture root,
and records the TRD's path and digest on the Epic bead. The driver files the TRD in the vault after
elaboration is done.

### 11.5 Spec authoring

- **Pass-through inputs with no producer (QUESTIONS 36): dropped.** `accessPatterns` and `spec` are
  not dispatch arguments (section 4.4); the data-model maker derives access patterns from the PRD,
  TRD and views, as it does today when none are sent.
- **The Story's title and description are deterministic; the `user-story-writer` session is
  dropped (QUESTIONS 37).** `story-<slug>.json` = `{title: "<repository name>: <PRD title>",
  description: <a fixed template listing the repository, the placed items (id and element) and the
  three spec document paths>, decisionIds}`. Reason: the Story is a single-repository container
  (CONTEXT 7.16); nothing reads its prose to decide anything; the session costs a full startup per
  repository for text a template produces (CONTEXT 7.11). This overrides `spec-authoring.md` steps
  10 and 11: step 10 is removed, and step 11 writes the template.
- **`outOfRepoFindings` (QUESTIONS 38): dropped**, with the session that produced it; nothing
  consumed it (`spec-authoring.md` §6 checks dropped).
- **An independent review pass of the spec set (QUESTIONS 39): none is added.** The makers work from
  an architecture that was reviewed and approved and from a TRD whose citations are checked; the
  spec documents' citations are checked deterministically (step 5); the check test is a test for
  keeping a check, and today's pipeline has no spec review to keep. S07 measures whether spec
  defects show up in the build lane.
- **Skipping a maker whose surface no item touches (QUESTIONS 40): not done.** No structured field
  says which surface an item touches; a guess could drop a document the Tasks cite. A maker with
  nothing to specify writes a short "not applicable" document, which its definition allows (S03e).
- **UI design sources (QUESTIONS 32a): confirmed** as `spec-authoring.md` places them. The
  contracts maker (`api-specification-author`) writes `<work>/candidates/spec-<slug>.ui.json` for a
  repository whose placement has `frontend: true`; which placed items are UI items is the maker's
  judgment; Python checks the file against the supplied bundles and the placed item ids (step 6).
  The steward's `frontend` flag is the only structured field that says a repository holds UI.

### 11.6 Task decomposition and finish

- **The Task scope of the finish step (QUESTIONS 41).** `elaboration.finish` is changed in place to
  take a scope: with `scope="epic-tasks"` it calls `scoring.score` with the write scope limited to
  the Tasks under the Epic and no Epic roll-up, and writes no Epic WSJF key. The "every Task
  scored" check reads the result's `unscored` list filtered to the Epic's Task ids. The
  orchestrator calls it in-process (section 2.2). Step 14c then calls `storyedges.story_edges`
  after `elaboration.finish`, as `depscore.run` does for `elaboration-finish`.
- **The task-deps schema check (QUESTIONS 42): kept in the orchestrator's acceptance, not merged
  into `write-all-task-edges`.** The acceptance step must produce the exact errors for the one
  corrective retry; `write-all-task-edges` keeps the key validation it already has as the writer.
- **Which metadata marks a Task as started (QUESTIONS 43).** A Task is started when its status is
  `in_progress` or `closed`, or any key of the `BUILD_LIFECYCLE_KEYS` or `CDS_AUDIT_KEYS` group of
  `skills/beads-contract/schemas/bead-metadata.schema.json` (imported from the generated
  `bead_metadata.py`) is present and non-empty. Reason: only the build lane writes
  those keys, so their presence proves the lane worked on the Task and its Story worktree may hold
  that work.
- **`blocked` and `deferred` (QUESTIONS 44).** `blocked` with no build key is unstarted (deleted and
  recreated on a `replaced` rerun): it is a dependency state. `deferred` is kept like a started
  Task: a person set it, and recreating the Task would erase that ruling.
- **Deleting a Task another Epic's Task depends on (QUESTIONS 45): re-point.** Before the delete,
  the orchestrator records every `blocks` edge from a Task outside the Story onto a Task it is about
  to delete, with the deleted Task's cited work items. After the new set is written, each recorded
  edge is added onto every new Task that cites at least one of the same work items. An edge with no
  such new Task is recorded as a warning in `run.json` and the failure evidence, not re-added.
- **A `web-ui` Task citing UI items of two artifacts (QUESTIONS 46): warn and keep the first**, as
  `hierarchy.check_cds_contract` does. `task-decomposer.md` is aligned to that (S03e). Reason: the
  planner can settle it deterministically; refusing would fail the Story for a normalization.
- **`surfaces` when the spec does not settle it (QUESTIONS 47): `null`.** `task-decomposer.md` is
  aligned to the schema (S03e); the bead's description renders null as `unknown (none declared)` as
  `beadwrite` does today.
