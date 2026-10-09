# DESIGN: the Python orchestrator for the Epic pipeline

Step S02 of the pipeline rewrite. This document decides how the Epic (elaboration) pipeline runs
once the Workflow scripts are gone: where the code lives, how a step is declared, how saved work is
reused, how agent sessions are started and costed, how failures get a structured cause, what runs
in parallel, how owner questions travel, what the driver stops doing, and how the element status
matrix is stored and fed. Every later step (S03 to S05a) builds from it. Where this document and a
spec under `specs/epic/` differ, this document is the later decision and wins; each such case is
named where it is decided.

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
- Context7 `/websites/code_claude` (three ctx7 commands in total):
  - `code.claude.com/docs/en/sub-agents`: `--agent` "applies a subagent's tool restrictions,
    model, and system prompt to the main session thread. Custom subagent system prompts replace
    the default Claude Code prompt, while CLAUDE.md files and project memory still load"; a
    plugin agent is named `plugin:agent`.
  - `code.claude.com/docs/en/plugins/components`: in a plugin agent's frontmatter `permissionMode`,
    `hooks`, `mcpServers` and `initialPrompt` are **ignored**; `isolation` accepts only `worktree`.
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
  `<config>/settings.json`; `<control>/.claude/settings.json`; `<control>/.polyrepo/`.
- Read-only checks run for this design:
  - `archbaseline.survey_freshness(<work>/architecture/survey.json, seal=False)` for `ssbd-mb689`,
    `ssbd-hdqid` and `ssbd-guuuz`: all three `current: true`, no errors, no warnings.
  - `bd show ssbd-zzzzzz-nonexistent --json`: exit 1; the JSON error object carries only `error`,
    `hint`, `schema_version`, no error code.
  - `bd show ssbd-mb689 ssbd-hdqid ssbd-guuuz --json`: all three `elaboration_state=in_progress`.
  - `ls <arch>/target/`: only `README.md` (no saved target folder exists).
  - The three Epics' `architecture/candidates/` folders: every complete candidate has the same
    bytes as its final file in `plans/` or `rounds/`; the others are `.checkpoint` and
    `.progress.json` files with no result body.

## 1. Where it lives (S02 item 1)

**Decision.** The orchestrator is a Python package in the plugin, `<orch>/`, with `run.py` as its
entry point. `supervisor.py` stays the driver: it selects work and starts the orchestrator as a
child process per dispatch:

```
<python> <installPath>/orchestrator/run.py prd-to-spec --bead <epic-id> --args <args.json> --handback <handback.json>
```

`<python>` is the driver's own interpreter (`sys.executable`), so the orchestrator imports the same
installed `jsonschema` and `yaml` the portfolio scripts use; no `uv`, no new dependency.

Layout:

| Path | Holds |
|---|---|
| `<orch>/run.py` | argument parsing, the flow registry, handback writing, signal handling |
| `<orch>/core/` | the step model, the artifact store and fingerprints, the tools layer (`bd`, git, `gh`, `polyrepo.py`, `cdk`), the agent runner, the section 2 guard, the event writer, the element status matrix module |
| `<orch>/flows/` | one module per Epic flow: `prd_to_spec.py`, `architecture.py`, `repo_scoping.py`, `trd_authoring.py`, `spec_authoring.py`, `task_decomposition.py` |
| `<orch>/briefs/<flow>/<step>.md` | brief templates (section 2.3) |
| `<orch>/seed_matrix.py` | the one-time matrix seeding script (section 10.6, PLAN S05a) |
| `<orch>/specs/`, `<orch>/measurements/`, `<orch>/DESIGN.md` | documents |

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

### 2.1 Two kinds of step

A flow is plain Python: loops, conditionals and a thread pool calling steps. There is no generic DAG
engine; no spec needs one (the deepest structure is the architecture rounds loop, a `for` loop of at
most 3).

- **Deterministic step**: a Python function with declared inputs (paths, input kinds of section 3.2,
  bead ids) and declared outputs (paths). It either returns a typed result or raises
  `StepError(stage, cause, evidence)` (section 6).
- **Agent step**: a declaration with these fields:

| Field | Meaning |
|---|---|
| `agent` | the agent definition's file stem under `<plugin>/agents/` |
| `brief` | the template path under `<orch>/briefs/` |
| `facts` | the values filled into the template: paths, ids, enum values, counts; never file content |
| `inputs` | the input paths and input kinds that fingerprint the step |
| `outputs` | the output paths; for a JSON result, the candidate path and the final path |
| `schema` | the JSON Schema file a JSON result is validated against; for a Markdown document, the document check (exists, non-empty UTF-8, and where the spec says so the `decisionIds` resolution check) |
| `model`, `effort` | from the table in section 5.4 |
| `cwd`, `addDirs` | section 5.2 |
| `timeouts` | section 5.6 |
| `corrective` | whether the one corrective retry of section 6.3 applies |

### 2.2 How `scripts/portfolio/` and the other tools are called

**Decision.** In-process import for every `scripts/portfolio/` module (`archstate`, `archbaseline`,
`archresume`, `archrevision`, `archfiles`, `archclosure`, `beadgraph`, `beadwrite`, `hierarchy`,
`elaboration`, `scoring`, `storyedges`, `cdsbundles`, `specui`, `resumefacts`). Subprocess, argv
list, no shell, for executables: `bd` (through `beadgraph`), `git`, `gh`, `uv run
<plugin>/skills/polyrepo-repo/scripts/polyrepo.py <cmd> --json`, `cdk`. `artifactio.py` (driver
code, located by `$ATW_ARTIFACT_SCRIPT`) is loaded in-process with `importlib`, as
`beadgraph._contract()` already loads `beads-contract.py`.

**This overturns the PLAN recommendation** (subprocess for `depscore.py` subcommands). Evidence:
- `depscore.py` is a CLI over these modules (its docstring lists each subcommand as a call into
  them); calling it as a subprocess returns only an exit status and printed JSON.
- The modules raise typed exceptions that already carry the structured cause CONTEXT 7.4 asks for:
  `beadgraph.GraphError.cause` (`contention`, `bd-timeout`, `other`), `scoring.ScoringError`,
  `specui.SpecUiError`, `archresume.ResumeError`. A subprocess loses the type.
- The specs already plan in-process calls: `task-decomposition.md` §5 ("calling the existing
  library functions directly (no `depscore.py` subprocess)"), `spec-authoring.md` step 12
  (`beadwrite.write_story` in-process), `prd-to-spec.md` step 14 (`elaboration.finish` logic
  in-process).
- The orchestrator runs from the same plugin version as the modules (section 1), so there is no
  version skew to isolate.

`depscore.py` is not rewritten. Where a spec needs a module function to behave differently, the
change is made in place in that module by the S04 sub-step that uses it (section 11.7).

### 2.3 Briefs

A brief is a Markdown template at `<orch>/briefs/<flow>/<step>.md` with `{name}` placeholders. The
runner fills each placeholder from the step's `facts`. A brief states facts and the expected outcome
(CONTEXT 7.14): what to read (absolute paths), what to write (absolute path and schema path), the
rules of the step that are not already in the agent definition or its skills, and the exit
condition. It carries no file content and no theory about the answer.

The agent's own instructions come from its definition (section 5.1), so a brief does not repeat
them. Rule text that is the same for every run moves out of the brief into the agent definition or
into a skill file the brief names by path.

### 2.4 One review standard for the architecture team (QUESTIONS 26)

**Decision.** One file, `<plugin>/skills/architecture-baseline/review-standard.md`, written in
S04a, is the standard every architecture writer, reviewer, the coordinator and the decider work to.
Every one of their briefs names it by path as "your work is judged against this file", and S04a
adds the same sentence to each of those agent definitions. It holds:

1. **What is judged** (today's `DESIGN_REVIEW_STANDARD` and `COVERAGE_RULE`): the acceptance basis
   (applicable PRD outcomes, settled owner decisions and section 2 constraints, the relevant
   obligations of `reference/architecture-documentation-model.md`, cited evidence, the retained
   target and delta); the coverage rule; and the reviewers' own checklist, taken from what the
   review schema records (`findings[].verdict` `verified | unsupported | wrong`,
   `coverageChecks`, `repairChecks`) and from the five reviewer and two cost reviewer definitions,
   so a writer sees in advance every check a reviewer will make.
2. **The level of implementation detail a view must carry** (CONTEXT 7.21). For every element the
   target adds or changes, its views together state: the owning repository; the CDK stack and the
   construct kind that provision it; its runtime entry (the Lambda handler and the chassis
   superclass it extends, or the container); the data stores it owns with key schema, indexes and
   access patterns; every API route (method, path, authorizer) and every event (name, envelope,
   publisher, consumers, delivery path, retry and dead-letter behaviour); its IAM boundary (who may
   call it, what it may call); the configuration it reads and the values it publishes (SSM
   parameter names); its failure behaviour (timeouts, retries, idempotency key); and its
   observability (log, metric and alarm names). The test is: a Task can name the repository,
   stack, handler, table, route and event without making a design decision of its own.
3. **The constant rules** of today's `INPUTS_RULE` and `PRD_RULE` (the PRD states what, never how;
   what counts as an input; citation forms), with one correction: repository code is read only for
   current design detail, never to judge whether anything is built (CONTEXT 7.23; built-ness comes
   from the element status matrix, section 10).
4. **The draft layout rules** of today's `DRAFT_RULES` (the arc42 section layout of the draft and
   its `delta/` folder; never `02-architecture-constraints/`).

What stays inline in a brief: the paths of this run (today's `ARCH_WHERE`: architecture root, draft
folder, ledger, PRD), the round number and plan entry, and the step-specific instruction of the
recheck brief (today's RECHECK block), which applies only to that one session.

**Reason.** Reviewers find gaps in nearly every first round because only some briefs carry the
standard (`architecture.md` step 15). Giving every writer the reviewers' own checklist, by path, is
the one change that makes their expectations the same, and moving constant text out of briefs
shrinks every session's prompt.

### 2.5 Where the result schemas live (QUESTIONS 27)

**Decision.** Every JSON result the orchestrator validates has a JSON Schema file in
`<plugin>/skills/artifact-handoff/schemas/`, beside the three that exist
(`architecture-writer.schema.json`, `architecture-review.schema.json`,
`architecture-baseline.schema.json`). New files, written by the S04 sub-step that uses them:
`survey`, `coordinator-plan`, `decision`, `maintain`, `conformance`, `closure-walk`, `closure`,
`placement` (repo scoping), `task-deps`, `tasks`, `tasks-correction`, `spec-ui`, each
`<name>.schema.json`. The `REPOSITORIES` and `DEPLOYMENTS` schemas are not carried over: their
sessions are gone (section 11.1 and `architecture.md` old step 30).

**Reason.** One folder is already the home of result schemas, every agent that writes these results
loads the `artifact-handoff` skill, and `archbaseline.SCHEMA_PATH` already points there; an agent
reads the schema by path and Python validates against the same file.

## 3. Artifact store, fingerprints and resume (S02 item 3)

### 3.1 Layout: the specs' layout, with `.meta.json` as the resume record

**Decision.** Files stay where the specs and `INDEX.md` put them: flat under `<work>`, with the
architecture phase's files under `<work>/architecture/`. Every saved result has a
`<file>.meta.json` written by `artifactio.record` (the one input-record format of every Epic flow):
`{artifact, path, epic_id, phase, producer, run_id, created_at, updated_at, sha256, bytes,
inputs[{path, kind, sha256, ...}]}`. The orchestrator fills `phase` with the step id, `producer`
with the agent name (or `python` for a deterministic step) and `run_id` with the dispatch's
execution id. Run facts that are not about one file (session ids, model, effort, timings, the cause
of a failed step) go in the run record `<work>/run.json` (section 4.4), not beside the files.

**This overturns the PLAN recommendation** (a `<flow>/<step>/step.json` layout). Evidence:
- `beadwrite.write_story` reads `artifact_<key>_sha256` from each spec file's `.meta.json` into the
  Story bead's metadata.
- The driver's `artifactio.plan` (read by `observe.py` for the dashboard's accepted and stale steps)
  reads `STEPS.md` and the `.meta.json` files.
- The three saved surveys (CONTEXT 7.13) carry `.meta.json` records in this format, under
  `<work>/architecture/`.
- Every spec and `INDEX.md` name these paths; moving files would change every reader for no
  gain.

A step's skip rule is the same as the PLAN's, expressed on these records: a step is skipped when
each of its outputs has a `.meta.json` whose `sha256` equals the file's current sha256, the record
names at least one input, and every recorded input hashes as recorded now
(`artifactio.input_problem` returns nothing for each). A failed step writes no `.meta.json`, so it
is never reused; this is the PLAN's `status: ok`.

`STEPS.md` keeps one line per completed step id (`artifactio.complete_step`), written by the
orchestrator, read only by the dashboard. It decides no reuse.

### 3.2 Input kinds (fingerprints)

`artifactio.hashed_inputs` already computes these kinds; the orchestrator uses them as they are:

| Kind | Fingerprint |
|---|---|
| `file` | sha256 of the bytes |
| `dir` | `artifactio.sha256_tree`: the sorted list of (relative path, sha256) |
| `missing` | the path did not exist when recorded |
| `arc42-revision` | the revision record `archrevision` writes (`<work>/architecture/arc42-revision.json`) |
| `arch-views` | the digest of the effective views whose catalog frontmatter names the listed elements |

Added in S03a (in `artifactio.py`, committed in `<control>` with `rewrite-step: S03a`):

| Kind | Fingerprint |
|---|---|
| `matrix-rows` | `{"matrix": <path>, "elements": [<element ids>]}`; the sha256 of the canonical JSON of those rows as read now (an element with no row hashes as `null`) |

Two further fingerprints PLAN item 3 names are defined, and used by no Epic step:
- **Bead**: the `beads-contract.py` content hash (`content_hash`, scope `judging`). No Epic step
  records a bead as an input: every bead read happens in a step that always reruns
  deterministically (Story write, Task write, the rerun case of `task-decomposition`).
- **Repository**: the `main` commit id (`git -C <repo> rev-parse main`). No Epic step records it
  (`driver-contract.md` §8: its only user was the removed detailing step). The saved surveys' seal
  binds `main^{tree}`; section 3.4 decides how that seal is read.

### 3.3 Which inputs fingerprint each step (QUESTIONS 10)

**Decision.** Each spec's resume section is the single source of its step's input list, with these
additions and settlements:

- `spec:<slug>` (`spec-authoring.md` §8 R1 and R2) also records `targetDir` as a `dir` input.
  Reason: the makers read the target and delta views; a view edit that leaves `trd.md`,
  `repo-scoping.json` and `delta-items.json` byte-identical would otherwise leave stale spec
  documents in place.
- The element status matrix rows are recorded as kind `matrix-rows` by the steps that read them:
  `repo-scoping.json` (the rows of the build items' elements), `<work>/architecture/closure.json`
  (the rows of the elements in `closure-walk.json`). The survey does not record them (section
  3.5).
- The driver keeps **no** reuse ruling of its own for elaboration. It stops sending `resume`, stops
  calling `artifactio.set_aside_stale` before an elaboration dispatch, and stops calling
  `artifactio.dispatch_resume` (section 9). It keeps `artifactio.retire_once` (the owner's
  start-over ruling when an Epic is set `ready`) and `artifactio.plan` as the dashboard's reader.
  Reason: two reuse rulings over the same files disagree; each step now proves its own reuse from
  its recorded inputs, before any session starts.

### 3.4 Adopting the three saved surveys (CONTEXT 7.13; QUESTIONS 11, 12, 32b)

The saved surveys of `ssbd-mb689`, `ssbd-hdqid` and `ssbd-guuuz` are read in place under
`<work>/architecture/` and reused when their inputs are unchanged. Steps, in the architecture
flow's survey step, before any session:

1. **Old seal check.** Call `archbaseline.survey_freshness(survey.json, seal=False)` with
   `context_sha=None` and no `inputs` or `repos`, so the saved seal's own `inputs`, `repos` and
   `contextSha` are used. It returns `current: true` today for all three (section 0).
2. **Adopt.** When `current` is true, the survey step is reused: no session starts. The existing
   `survey.json.meta.json` and `survey.md.meta.json` stay the step's records.
3. **Reseal in the new form, once.** Right after a successful adoption, the seal is rewritten in
   the new form (section 3.5): the same `inputs`, the cited documents and evidence, the schema and
   the saved `contextSha`, **without** repository `main^{tree}` bindings. From then on a commit to a
   product repository's `main` no longer makes the survey stale.
4. **Not current.** When the old seal is not current, the survey is produced again (the cost is
   accepted; a changed binding cannot be split into "only a repository moved" because the seal
   stores one digest, not its parts).

**`contextSha` (QUESTIONS 12): reuse the saved value; do not reproduce the JavaScript.** "Match"
means string equality of the `contextSha` stored in the seal with the one passed in. For an adopted
survey none is passed (`context_sha=None`), so `survey_freshness` takes the saved value and the
comparison is of everything else. Evidence: `survey_freshness` falls back to
`saved.get("contextSha")` when `context_sha is None` (`archbaseline.py` lines 334-335). For a new
survey, `contextSha` is the sha256 of the canonical JSON (sorted keys, no spaces) of
`survey.schema.json` (section 2.5). The JavaScript's `prdBody` part is dropped: the driver never
sends a PRD body, and the PRD file is already a bound input.

**`main^{tree}` (QUESTIONS 11): honoured once, then not bound.** The old seal is read exactly as it
was written (step 1), so adoption is decided by the same rule that sealed it. New surveys and
resealed surveys bind no repository tree, because the survey no longer judges code (section 3.5).

**The code-derived fields (QUESTIONS 32b).** The saved surveys' `implementationAction`,
`code.state` and the `implementationWork` derived from them were judged from code. They are not
recomputed and the survey is not rerun for them: section 3.5 makes every consumer derive
built-ness from the element status matrix in Python, so those survey fields are read by nothing
that decides scope. `survey.json` is never rewritten, so its bytes and seal stay valid, and
`contextSha` does not change.

### 3.5 The survey does not depend on the matrix

**Decision.** Built-ness is derived in Python, never asked of the survey session. `implementationWork`
(the input of `arch-target`'s `baseline.json` and of `arch-delta`) is computed by
`archbaseline.baseline_facts` from the survey's capabilities **and the element status matrix**:
a capability is implementation work when any element its cited documents show (catalog
`subject`/`shows`, `archstate._catalog`) is not satisfied by the matrix (section 10.4), or when
the survey marks it unknown or in conflict. The survey's own `implementationAction` and
`code.state` are kept in the file for its readers' context and decide nothing. The survey brief
(S04a) stops asking the session to judge built-ness. `survey-matrix.json` is not written and the
survey seal binds no matrix rows.

**This overrides `architecture.md` steps 5 and 7** (survey seal binding matrix rows; the session
setting `implementationAction` from the rows). Reason: if the survey bound matrix rows, every Task
the build pipeline marks `built` would stale every survey that cites that element and rerun an
850k-token session; a deterministic derivation gives the same answer at no cost, and CONTEXT 7.11
puts consistency-without-reasoning in code.

### 3.6 Stale architecture work (QUESTIONS 13)

**Decision.** When `archrevision.check` reports `stale` (a cited arc42 view changed), everything in
`<work>/architecture/` is moved to `<work>/stale-<timestamp>/architecture/` **except** the survey
files (`survey.json`, `survey.md`, their `.meta.json`, the seal, the receipt), which stay when
`survey_freshness` still reports the survey current. The rounds, plans, draft, decision and later
files move aside and are produced again.

**Reason.** The survey's seal already binds by content every document and evidence path the survey
cites (`archbaseline.survey_freshness`, the `files` binding), so it is the exact test of whether the
survey is stale; `archrevision.check` binds the views the rounds and decision cite as well, which
the survey does not depend on. Keeping a still-current survey saves its cost on every view change
it does not cite.

### 3.7 Other resume settlements

- **The `delta/closure.json` fallback read (QUESTIONS 14): dropped.** `resumefacts.saved_target`
  stops looking for `closure.json` in `deltaDir`. Evidence: `<arch>/target/` holds only
  `README.md`, so no saved target exists that could carry the old location.
- **`candidates/` in saved work (QUESTIONS 15): ignored.** Evidence: in all three Epics every
  complete candidate has the same bytes as its final file, and the rest are checkpoint and progress
  files with no result body (section 0). Nothing would be promoted.
- **Live repository inventory as a repo-scoping input (QUESTIONS 17): not an input.** The
  inventory changes whenever part B creates a repository, which would make the ruling stale after
  every run that created one. When a reused ruling's checks are re-applied (`repo-scoping.md`
  step 3), a `missingRepos` entry whose name the current inventory holds is not a finding: part B
  records it as `existed: true` with its path.
- **Other Epics' open Tasks as a Task rerun input (QUESTIONS 18): not an input.** They decide only
  `blockedByExternal` edges, not the Story's own work; making them an input would delete and
  recreate a Story's unstarted Tasks whenever another Epic's Tasks change (CONTEXT 7.5: only
  upstream changes of this Epic replace Tasks).
- **Cross-Story Task dependencies when one Story changed (QUESTIONS 19): derive all edges again.**
  `task-deps.json` is fingerprinted by every `tasks-<slug>.json`; any change reruns the one
  `task-dependency-mapper` session over all Stories. An edge between two unchanged Stories can
  depend on a Task of a changed Story through ordering, and a partial derivation would need its own
  rules for that; one session over all Stories is the simple correct form.
- **Leftover step names in saved `STEPS.md` (QUESTIONS 20): ignored.** The orchestrator decides
  reuse only from `.meta.json` records, so a stray name (for example `prd-validation`) has no
  effect. S05 changes `artifactio.plan` to skip step names that are not in its `STEP_ORDER`
  instead of reporting them stale, and removes `recon:<repo>` from `STEP_ORDER` and `STEP_FILES`.
  No file is cleaned.

## 4. Ledger, dashboard and cost (S02 item 4)

### 4.1 Events on stdout

**Decision.** The orchestrator writes one JSON object per line on stdout and nothing else there
(diagnostics go to stderr). The driver captures stdout to the run's `.out` file and translates each
event into the existing callbacks, so `ledger.EVENT_TYPES`, `observe.py`, `outcomes.py`,
`runview.py` and the dashboard keep their event types.

| Orchestrator event | Fields | The driver calls |
|---|---|---|
| `phase` | `phase` (a name in `dispatch.COMPOSITE_PHASES["prd-to-spec"]`), `step`, `repository?` | `on_phase(bead, "prd-to-spec", "▸ " + phase, step=..., repository=...)` |
| `verdict` | `phase`, `label`, `verdict`, `detail` | `on_verdict(...)` with the same fields |
| `session` | `state` (`started`/`ended`), `sessionId`, `pid`, `pgid`, `agent`, `step`, `model`, `effort`, and on `ended` `exit`, `cause` | `on_phase(bead, "prd-to-spec", "agent <agent> <state>", **fields)`; the driver also registers `pgid` with `childproc` and `sessionregistry` on `started` and forgets it on `ended` |
| `note` | `kind` (`rounds-warning`, `reused`, `stale`, `task-rerun`), plus its facts | `on_phase(bead, "prd-to-spec", "note " + kind, **fields)` |
| `fable-wall` | `resetsAt`, `window` | `fablewall.record(resetsAt, window)` |

The `▸` prefix keeps `outcomes._phase_name` counting phases as it does today; session and note
texts carry no `▸`, so they are recorded but never counted as phases. No ledger event type is added.

### 4.2 Phase names (QUESTIONS 23)

**Decision.** `dispatch.COMPOSITE_PHASES["prd-to-spec"]` becomes `("architecture", "repo-scoping",
"trd-authoring", "spec-authoring", "task-decomposition", "task-edges", "finish")`:
`prd-reconciliation` is removed (CONTEXT 7.10) and the two composite steps that run after the
Stories are named. The orchestrator emits exactly these phase names. Readers changed in S05:

- `phaserec.expected_phases("prd-to-spec")` returns `dispatch.COMPOSITE_PHASES["prd-to-spec"]`
  instead of parsing `workflows/prd-to-spec.js` (which S08 deletes).
- `observe.py`'s relay-file view of architecture rounds is replaced by a read of the real result
  files: `<work>/architecture/plans/round<n>-plan-0.json` (what each round dispatched) and
  `<work>/architecture/rounds/r<n>-<seq>-<role>-<agent>.json` (what came back), and
  `decision.json`.
- The per-phase record stays `state/phases/<run stem>.json` (`phaserec.py`), fed by the phase
  events as today.
- The architecture `rounds-warning` note: `{"event": "note", "kind": "rounds-warning",
  "phase": "architecture", "rounds": <n>, "drivers": [{"round": <r>, "findings": [<finding
  ids>], "file": <rounds file path>}]}`, also written into `run.json` and the architecture result.

### 4.3 Verdict events (QUESTIONS 24)

**Decision.** Kept, emitted by Python from the accepted result files, never from text: one
`verdict` event per accepted decider result (`decision.json` `verdict`), per accepted reviewer
result (`verdict` = `pass` when no finding is `unsupported` or `wrong`, else `reject`, with the
counts in `detail`), and per conformance result (`conforms`). Reason: the dashboard shows them today
(`observe.py` reads `verdict`), and the values are fields of validated files.

### 4.4 Handback and run record (QUESTIONS 22)

**Decision.** The handback is a file. `run.py` writes `--handback <file>` atomically before it
exits, as one JSON object with the key names the workflow result used, so the driver parses it with
`handbackio.handback_from_result` unchanged:

`{ok, stage, beadId, headline, detailPath, beadsEmitted, lifecycle{owner, start, finish, release,
done}, refusal?, requiredHumanActions?, artifacts{dir, epicId, phases, filing}, failure?{stage,
cause, repositories[], resumeAt?}, hierarchy, repoSpan, targetRemoval, storyEdges?,
crossStoryDependencies, closureEdges, createdRepos?, sessions[{sessionId, agent, step, phase}]}`.

`detailPath` is `<work>/run.json`, the run record (`prd-to-spec.md` step 17): composite, Epic, PRD
id, outcome, each step with `reused | ran | failed`, its cause and evidence paths, every session
(`sessionId`, `agent`, `step`, `model`, `effort`, `cwd`, `startedAt`, `endedAt`, `exit`,
`cause`), and the notes of section 4.1.

`run.py` exits 0 whenever it wrote a handback, whatever `ok` says; a non-zero exit means it died
before writing one, and the driver makes its usual environment failure (`no-handback`).

Keys dropped from the handback: `dispatchFailures` (folded into `failure`), `degraded`. The driver
sets `failure_origin` from `failure.cause` (`api` and `quota` are `environment`, every other cause
is `work`) instead of `handbackio.step_defect_origin`, which reads text (section 6.5).

Dispatch arguments (`extra_args`) the orchestrator reads: `prd`, `epic`, `owner`, `reclaim`,
`beadsRepoPath`, `archPath`, `trdPath`, `designSystem`, `skillspokeRoot`, `executionId`, and a new
`fableUntil` (section 5.5). Dropped: `resume` (section 3.3), `pluginRoot` (the orchestrator runs
from its install), `relayExecutionId`, `relayRequestDir`, `relayCaptureScript` (no relay),
`fableAgentTypes`, `fableRecovery` (section 5.5), `artifactScript` (the orchestrator reads
`$ATW_ARTIFACT_SCRIPT`, which `headlessenv.child_env` already sets), `accessPatterns`, `spec`
(section 11.5).

### 4.5 Cost attribution and the run unit (QUESTIONS 21)

**Decision.** The run unit stays one dispatch: one cost record `state/runs/<run stem>.cost.json`
per orchestrator run, summing every agent session that run started. Each agent session is its own
top-level Claude Code session, so the record lists them:

- The runner chooses each session's id itself (`--session-id <uuid>`, section 5.2) and records it
  in `run.json` and the handback's `sessions[]`.
- S03d changes `runcost.py`: `measure_run` takes the session list from the handback
  (`dispatch.Handback` gains `sessions: tuple[dict, ...]`), measures each with
  `measure_session(sessionId)` (which already finds a transcript in any project folder through
  `session_project`), sums the four components, and builds `phases` and `roles` from the session
  list's `phase` and `agent` instead of workflow `.meta.json` files. `sessionId` on the record
  becomes the first session's id plus `sessionIds` with all of them; `runcost._scan` keys
  deduplication by the run log path for records that carry `sessionIds`.
- `KNOWN_COMPOSITES` is unchanged.

**What proves a run is running (CONTEXT 7.12).** The Epic shows "running" only while the driver's
lease is live and the orchestrator's process is verified, as for any dispatch today
(`sessionregistry`, `childproc`). An agent step shows "running" only between its `session started`
and `session ended` events and only while its `pid` is alive (`os.kill(pid, 0)`, with the `pgid`
from the event matching `os.getpgid(pid)`). The phase shown is the last `phase` event the run wrote;
no phase is inferred. No counter is shown that the records cannot compute.

## 5. Agent runner (S02 item 5)

### 5.1 The headless CLI, with the agent applied by `--agent`

**Decision.** Each agent step runs the Claude Code CLI as a subprocess (`claude -p`), not the Agent
SDK. Reasons: the driver already starts, supervises, kills and costs `claude` processes
(`headless.py`, `childproc.py`, `runcost.py`) under `CLAUDE_CONFIG_DIR=<config>`; the SDK is not
installed (section 0) and its own documentation says it passes its options to "the CLI subprocess",
so it would add a dependency and run the same binary.

The agent's definition is applied with `--agent`, from a session-local definition:

1. The runner reads `<installPath>/agents/<agent>.md`: its frontmatter and its body.
2. It writes `<session dir>/agents.json` = `{"atw-<agent>": {description, prompt: <body>, tools,
   disallowedTools, model, skills, maxTurns}}` with the values from the frontmatter and the model of
   section 5.4.
3. It passes `--agents <session dir>/agents.json --agent atw-<agent>`.

Why a session-local definition and not `--agent agent-teams-workforce:<agent>`: the runner must
leave out `isolation` (section 5.3) and set the model on a Fable fallback (section 5.5) without
editing agent files, and the documented `--agent` behaviour ("applies a subagent's tool
restrictions, model, and system prompt to the main session thread") then holds for the exact
definition the runner wrote. The `atw-` prefix keeps the name apart from the plugin's own agent.

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
  --add-dir <each path the brief names a directory of>
```

The prompt (the filled brief) is written on stdin, as `headless._deliver_prompt` does today.

- **Working directory.** A per-session directory outside every repository,
  `$ATW_SESSION_ROOT/<run id>/<step>-<n>/` (new environment variable; default
  `<config>/atw-sessions/`). It holds `agents.json`, `settings.json`, `mcp.json` and nothing else.
  Reason: with the working directory inside `<control>`, Claude Code auto-discovers the control
  repository's `AGENTS.md`/`CLAUDE.md` and the `ops/` and `ops/sdlc-automation/` ones above it; an
  Epic agent needs none of them, because its brief names every path it reads and its definition
  holds its rules. The repositories and folders it reads are named with `--add-dir`.
- **Settings.** `--setting-sources project` with a working directory that holds no project
  settings loads no settings file; user settings (`<config>/settings.json`) are not loaded. Today
  they enable nine plugins, two `SessionStart` context injectors, a `UserPromptSubmit` injector,
  the status line, `model: opus` and `effortLevel: high` (read 2026-10-09), all of which load into
  every session. `--settings <session dir>/settings.json` brings back only the safety hooks: the
  runner copies, from `<config>/settings.json`, every `PreToolUse` hook whose command names one of
  `no-verify-blocker.sh`, `pipeline-run-blocker.sh`, `bd-init-blocker.sh`,
  `aws-profile-required.sh` (a constant list in the runner, matched by script file name, so the
  hook commands themselves are read from the owner's file, not copied into code).
- **Plugins and skills.** `--plugin-dir <installPath>` loads `agent-teams-workforce`. For every
  skill the agent's frontmatter `skills` names with another plugin's prefix (for example `cds:`),
  the runner adds that plugin's `installPath` from `<config>/plugins/installed_plugins.json`. No
  other plugin loads.
- **MCP servers.** The CLI ignores a plugin agent's `mcpServers` field (section 0), so the runner
  reads it: it writes `<session dir>/mcp.json` with only the servers the agent's frontmatter
  `mcpServers` names, taking each definition from the sources `mcpconfig.collect_allowed` reads
  (`<control>/.mcp.json`, then the global config). With none named, `--mcp-config` is omitted and
  `--strict-mcp-config` loads none.
- **Tools.** The agent's `tools` and `disallowedTools` come from its frontmatter through
  `agents.json`; `--disallowedTools` adds the driver's denied list plus `Agent` and
  `AskUserQuestion`, so no Epic session starts another agent or waits on a person.
- **Not used:** `--bare` (it accepts only `ANTHROPIC_API_KEY` auth, and the pipeline runs on the
  subscription: `breaker.exhausted_reset` reads the `five_hour` and `seven_day` subscription
  windows); `--json-schema` (results are files, section 5.6); `--no-session-persistence` (the
  transcript is the cost record).
- **Environment.** `headlessenv.child_env` as today (the `ATW_*` variables, `TMPDIR` in the run's
  scratch folder, `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0`).

The 68k-token startup measured in S00 is the target; S07 measures what this context costs.

### 5.3 `isolation: worktree` (QUESTIONS 2)

**Decision.** Ignored: the runner leaves `isolation` out of `agents.json` and passes no
`--worktree`. Every Epic agent writes only under `<work>` (outside every repository) or, for the
architecture writers and maintainer, under `<arch>`, and reads repositories by absolute path; a
worktree would isolate nothing it writes. The working directory is outside every repository
(section 5.2), so there is no repository to cut a worktree of.

### 5.4 Model and effort per agent (QUESTIONS 3)

**Decision.** The step declaration names the model and effort; the agent's frontmatter is the
default where this table agrees with it. Where the Epic pipeline's call and the frontmatter
disagree, the value below is the one used, and the reason is given. The value used is recorded in
`run.json`.

| Agent | Epic step | Frontmatter | Used | Reason |
|---|---|---|---|---|
| `prd-reality-reconciler` | survey, recheck, Closure walk | opus / medium | opus / medium | the expensive assessment; a wrong scope costs every later step |
| `architecture-boundary-guardian` | Check plan, round reviewer | sonnet / low | sonnet / medium | the same review standard as every other reviewer (section 2.4) |
| `architecture-decision-workflow-coordinator` | round plan | sonnet / medium | sonnet / medium | routing only |
| 9 proposers (`integration-pattern-architect`, `persistence-architecture-specialist`, `security-architecture-designer`, `cdk-infrastructure-designer`, `event-schema-designer`, `api-contract-designer`, `graphql-schema-designer`, `domain-event-modeler`, `bounded-context-mapper`) | writers | fable / medium | fable / high | design authoring to the implementation-detail level of section 2.4, aimed at approval in round 1 |
| `architecture-diagram-author`, `c4-diagram-author`, `uml-diagram-author` | writers | sonnet / medium | sonnet / medium | drawing from a settled design |
| `architecture-pattern-challenger`, `architecture-tradeoff-skeptic`, `failure-mode-analyst` | reviewers | fable / medium | fable / medium | as the frontmatter |
| `operational-readiness-reviewer` | reviewer | opus / low | opus / medium | one review standard for all reviewers |
| `cost-architecture-reviewer`, `cost-impact-reviewer` | cost reviewers | sonnet / medium | sonnet / medium | as the frontmatter |
| `architecture-decider` | decision | opus / high | opus / high | approval authority |
| `architecture-maintainer` | integration, correction | sonnet / medium | sonnet / medium | applies an approved design |
| `architecture-conformance-reviewer` | conformance | sonnet / low | sonnet / medium | it gates what becomes effective; nothing re-reviews effective views |
| `polyrepo-steward` | placement | sonnet / medium | sonnet / high | a wrong placement propagates into every later step (`repo-scoping.md` step 5) |
| `trd-author` | TRD | fable / medium | fable / medium | as the frontmatter |
| `api-specification-author` | contracts, UI design sources | sonnet / medium | sonnet / medium | as the frontmatter |
| `data-model-specification-author` | data model | fable / medium | fable / medium | as the frontmatter |
| `acceptance-criteria-writer` | criteria | sonnet / medium | sonnet / low | derivation from two finished documents (`spec-authoring.md` step 7) |
| `task-decomposer` | decomposition, corrective pass | fable / medium | fable / medium | as the frontmatter |
| `task-dependency-mapper` | cross-Story edges | fable / medium | fable / medium | a bounded read-and-relate job |

`user-story-writer` and the `polyrepo-steward` repository listing are no longer dispatched
(sections 11.1, 11.5).

### 5.5 Agents declaring `model: fable` (QUESTIONS 1)

**Decision.** The runner passes `--model fable` as the frontmatter says; the CLI accepts `fable` as a
model alias (section 0). The Fable allowance is handled per step, from structured facts:

- When a session's stream carries a `rate_limit_event` whose `rate_limit_info` `fablewall.is_refusal`
  accepts, the runner ends that session, emits a `fable-wall` event (the driver records it with
  `fablewall.record`), and runs **that one step again on `opus`**, resuming the same session
  (`--resume <sessionId> --model opus`) so its work so far is kept. The model changed, so the retry
  is reasonable (CONTEXT 7.4).
- While the Fable wall stands, every `fable` step starts on `opus`. The driver passes
  `fableUntil` (the epoch from `fablewall.resets_at()`, or absent) in the dispatch arguments; the
  orchestrator also honours a wall it saw itself during the run.
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
  `<run scratch>/<step>-<n>.stream.jsonl` for the incident-responder.
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
| git: the index lock is held | `<repo>/.git/index.lock` (or the worktree's) exists when the command fails | `contention` |
| git push rejected because `main` moved | after the failed push, `git fetch` then `git merge-base --is-ancestor origin/main HEAD` exits 1 | `contention` (pull with rebase, then push again) |
| git: anything else | the exit status | `other` |
| `polyrepo.py`, `gh`, `cdk`: non-zero exit | the exit status (their JSON results carry only `error` text, no code: `polyrepo.py` `cmd_create`, `res["error"] = str(exc)`) | `other`, except the owner facts of section 11.3 |
| element status matrix: lock wait expired | the lock's own result (section 10.3) | `contention` |
| element status matrix: file missing or not JSON | `FileNotFoundError`, `json.JSONDecodeError` | `other` |
| a portfolio module raises | the exception type and its field (`GraphError.cause`; `ScoringError`, `ResumeError`, `SpecUiError` are `other`) | as named |
| section 2 changed by a session | the guard's digest comparison (section 7.3) | `other` |

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
- **`other`** = any other non-zero exit, with the command and `bd`'s output as evidence for the
  incident-responder.

`beadgraph._bd` is changed in place (S03b): it takes the gate from the orchestrator (a callable the
orchestrator installs), passes a timeout, and stops classifying `bd`'s standard error
(`failure_cause`, `connection_retryable`, `CONNECTION_BACKOFF`); a `GraphError` carries the cause
above. The owner-run portfolio commands use the same function and get the same behaviour.

### 6.3 Retry policy

- **`contention` and `bd-timeout`**: retried at the call site, the same call again, with backoff
  starting at 30 s, doubling, capped at 1800 s, until it succeeds or the run is stopped. Each
  attempt re-reads what it needs, so an applied write is updated, never created twice (the writers
  are keyed by `elab_key`).
- **`api` and `quota`**: not retried in the orchestrator. Every live session of the run is stopped,
  completed steps keep their records, and the run returns `ok:false` with `failure.cause` (and
  `failure.resumeAt` for `quota`). The driver's breaker pauses and redispatches; the rerun reuses
  every recorded step.
- **One corrective retry** with specific feedback (CONTEXT 7.4): when an agent step's output is
  missing or invalid after a normal session end, the runner resumes the same session
  (`--resume <sessionId>`) once with the exact validation errors or the missing path; the session
  keeps what it already read, and the prompt cache makes the resume cheaper than a new session. A
  second failure fails the step with cause `other`. The specs' named corrective passes (repo
  scoping's avoid list, task decomposition's uncited items, the closure refusal, the decider's
  re-ask) are this same rule with their own feedback.
- **Never**: rerunning a step with nothing changed. `other` fails the run with the step, its cause
  and the evidence paths, for the incident-responder.

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

## 7. Concurrency (S02 item 7)

### 7.1 What runs in parallel

One orchestrator process per Epic dispatch; the driver's lanes keep their slots. Inside one run, a
thread pool runs:

- repo scoping alongside TRD authoring (`prd-to-spec.md` step 8);
- spec authoring across span repositories, and inside one repository the contracts maker alongside
  the data-model maker (`spec-authoring.md` steps 3 and 4);
- task decomposition across Stories (`prd-to-spec.md` step 10);
- the reviewers of one architecture round (`architecture.md` step 16).

Everything else is sequential, including the writers of a round, in plan order.

**The cap.** At most `ATW_ORCH_SESSIONS` agent sessions at once per run (default 4). Steps beyond
the cap wait in the pool. The account-wide number is this cap times the driver's
`--elaboration-concurrency`; the owner sets both.

### 7.2 `bd` writes

Serialized by the two locks of section 6.2. The driver's `bd-gate.lock` is used by the orchestrator
for every `bd` call, so orchestrators and the driver take turns; the central beads lock is used for
writes, so the Linear and fleet syncs take turns with them too.

### 7.3 The section 2 guard across parallel sessions (QUESTIONS 4)

**Decision.** One guard per run, in the runner, shared by every session of the run:

1. **Snapshot.** Before an agent session starts, when no other session of this run is live, the
   runner takes `archstate.snapshot_constraints(<arch>, keep=True)` (digest, git status, existence,
   and a kept copy under `<work>/section2/kept-<n>/`). While another session is live, the new
   session shares the standing snapshot.
2. **Check.** When any session ends, the runner snapshots again and compares digest, existence and
   git status with the standing snapshot.
3. **On a difference:** copy the changed folder to `<work>/section2/changed-<timestamp>/` (so an
   edit the owner made at the same moment is never lost), restore with
   `archstate.restore_constraints(<arch>, kept)`, stop every live session of the run, and fail the
   step that just ended at stage `constraints-written`, cause `other`. The run's failure names the
   step and the sessions that were live, with the `changed-` copy as evidence.
4. A snapshot or restore that fails fails the step at its stage, cause `other`.

**Reason.** A per-session before-and-after cannot attribute a change when sessions overlap, and a
restore by one session's guard could undo a change another overlapping session's guard would also
see. With one shared snapshot every change made while any session runs is caught at the next session
end; the outcome (restore, fail, incident) does not depend on which session is blamed. Retaking the
snapshot only when no session is live absorbs an owner's edit made between steps.

## 8. Owner holds and questions (S02 item 8)

**Decision.** The orchestrator writes no owner inbox entry and no hold. It returns owner facts in
the handback and the driver acts on them exactly as today (`driver-contract.md` §4):

- the flow returns `ok:false`, `stage: "requires-human-action"`, and `requiredHumanActions` (a list
  of strings, each naming the fact and what the owner does);
- the driver's `lane._person_needed` holds the Epic (`elabstate.hold_for_person`:
  `elaboration_state=""`, `elaboration_state_cause=awaiting-human-action`), and its `human_log`
  writes the owner inbox (`ownerinbox.Writer`, `$ATW_OWNER_INBOX`) with the restore command.

Only owner facts become `requiredHumanActions` (CONTEXT 7.9): the architecture decider's
`business-conflict` and `architecture-conflict` concerns, a missing architecture root
(`no-arch-path`), and the repository-creation owner facts of section 11.3. Every other failure
returns a `failure.cause`; `other` opens an incident whose hold keeps the Epic out of dispatch until
the incident-responder resolves it. The orchestrator releases the Epic's lifecycle owner
(`elaboration-release`) on every exit after a successful claim unless the Epic was marked done
(`prd-to-spec.md` step 16).

## 9. What the driver stops doing for the elaboration lane (S02 item 9)

S05 adds `<driver>/orchestrated.py`, which starts `run.py` in its own process group, translates its
events (section 4.1), enforces the dispatch timeout with the orchestrator's events as progress, and
reads the handback file. `headless.HeadlessClaudeDispatcher.dispatch_one` routes `prd-to-spec` to
it. Then, for `prd-to-spec`:

| Driver code | Fate |
|---|---|
| `prompts.dispatch_prompt` / `prompts.resume_prompt` for `prd-to-spec` | **delete** the `prd-to-spec` paths in S05; the functions stay for the Task pipeline until S12 |
| `headless._dispatch_with_recovery` and `_fresh_fable_attempt` (Fable workflow recovery) | **not used** for `prd-to-spec`; stay for the Task pipeline until S12 |
| `fablerecovery.py` | **not used** for `prd-to-spec`; **delete** in S15 |
| `fablewall.py` | **keep** (structured fields; the driver records the orchestrator's `fable-wall` events and passes `fableUntil`) |
| `headless._render_progress`, `_announce_phase_of`, `_render_agent_entry` (workflow progress parsing), `VERDICT_MARKER` text verdicts | **not used** for `prd-to-spec`; stay for the Task pipeline until S12 |
| `headless._silent_after_workflow`, `_workflow_ended`, `_believe_workflow_result`, `runjournal.workflow_result`, `runjournal.persist_session` | **not used** for `prd-to-spec`; stay until S12 |
| `handbackio.parse_handback` (`HANDBACK` line) | **not used** for `prd-to-spec` (handback file through `handback_from_result`) |
| `handbackio._died_of_outage`, `step_defect_origin`, `breaker.pause_of` text paths, `headless._resume_unavailable` | **not used** for `prd-to-spec` (section 6.5) |
| the relay arguments in `headless._dispatch_session` | **not sent** for `prd-to-spec` |
| `workitems.plugin_root_args` (`pluginRoot`) | **delete** for `prd-to-spec` |
| `workitems.with_artifact_plan`: `resume`, `_rule_saved_files`, `artifactio.set_aside_stale`, `artifactio.dispatch_resume` | **delete** for `prd-to-spec`; **keep** `_start_over` / `artifactio.retire_once` |
| `phaserec.expected_phases` reading `prd-to-spec.js` | **change** to `dispatch.COMPOSITE_PHASES` (section 4.2) |
| `observe.relay_steps` for elaboration | **change** to the rounds and plans files (section 4.2) |
| `artifactio.plan` | **keep** as the dashboard's reader; skip unknown step names; drop `recon:<repo>` (section 3.7) |
| `runcost.record_run` / `measure_run` | **change** to sum the handback's sessions (section 4.5) |
| `failurecause.pause_from_cause` | **change** to read `failure.resumeAt` (section 6.5) |
| `spendguard.LIVE` registration, `sessionregistry`, `childproc` reaping | **keep**, for the orchestrator's group and each session `pgid` it reports |
| `ledger.EVENT_TYPES` `trigger_plan`, `trigger_dispatch`, and the `trigger_dispatch` branch in `failures.py` | **delete** in S05 (QUESTIONS 25: no producer since commit `64b4adbb`; `ledger.read_all` parses old lines whatever their type, so old ledgers still read) |
| `routing.route_elaboration` reason texts | **change** in S05 (QUESTIONS 48): a feature returns `skip`, reason "a feature needs a PRD and an Epic; the owner writes the PRD"; the Story reason says the Story is elaborated through its parent Epic; `selection.select_only`'s feature skip reason stops naming `/agent-teams-workforce:start-prd`. Reason: S05 is the step that edits the driver's elaboration path; S08 deletes the command the old texts name |

## 10. Element status matrix (S02 item 10; QUESTIONS 32e, 32f)

### 10.1 Storage and format

**Decision.** One JSON file, untracked run state like the ledger:
`$ATW_ELEMENT_MATRIX`, default `<driver>/state/element-matrix.json` (inside `state/`, which
`ops/sdlc-automation/.gitignore` ignores). Every change is also appended, one JSON line per change,
to `<same folder>/element-matrix.log.jsonl` (`{ts, element, from, to, task, commit, by}`), so the
history is kept and the file can be rebuilt from it.

```
{
  "version": 1,
  "seededAt": "<iso>",
  "elements": {
    "<element id>": {
      "id": "<element id>",
      "name": "<name as the arc42 views write it>",
      "kind": "element | repository | stack",
      "repository": "<repository name> | null",
      "repositorySource": "seed | build | null",
      "stack": "<CDK stack name> | null",
      "views": ["<arc42-relative view path>", ...],
      "expected": "<what the architecture says it should contain>",
      "state": "unknown | built | deployed",
      "task": "<Task bead id> | null",
      "commit": "<commit sha> | null",
      "changedAt": "<iso> | null",
      "changedBy": "<step that last set state> | null"
    }
  }
}
```

Written sorted by key with an indent of 2, atomically (temporary file, then replace), so a diff of
two copies reads row by row.

**Reason it is not committed.** The build pipeline writes it on every passing Task. Committing those
writes would make unattended runs commit to, and push, the control repository's `main` from the
primary working tree, which also pushes any local commits of the owner's that are not yet pushed,
and contends with the owner's own work there. The ledger, the driver's other durable record, already
lives in `state/` for the same reason; the change log gives the matrix its history. S05a commits
only the seeding script.

### 10.2 Element identifier and matching rule

An element's id is its name with whitespace collapsed to single spaces and `str.casefold()`
applied. This is the rule `archstate` already uses to compare element names from catalog
frontmatter (`archstate._effective_elements` and the partial-change test compare
`e.casefold()`). A view names elements in its catalog frontmatter `shows` (and `subject`), read by
`archstate._catalog`; a build item's `element` in `delta-items.json` is a name from that frontmatter,
so the same function maps both to a row. A repository row's id is `repository:<repository name>`
(casefolded) and a stack row's id is `stack:<repository name>/<stack name>` (casefolded), so they
never collide with element names.

### 10.3 Reading, writing and failures

`<orch>/core/matrix.py` is the one module that reads and writes the file:
- **Read**: a shared `fcntl.flock` (`LOCK_SH`) on `<file>.lock`, then parse. Writes take the
  exclusive lock (`LOCK_EX`). Lock wait `ATW_MATRIX_LOCK_WAIT`, default 120 s.
- **Read failure facts**: lock not acquired in time → `contention` (backoff, section 6.3); file
  missing → `other` (the seeded file must exist; a missing file would silently pull every built
  element back into scope); not valid JSON or no `elements` object → `other`. Stage `matrix` in the
  step that read it.
- **Unknown element**: no row reads as state `unknown` (CONTEXT 7.25).

### 10.4 What counts as satisfied (QUESTIONS 32f)

**Decision.** A row satisfies a reader (the Closure, `implementationWork`) when its state is
`deployed`, or when its state is `built` and its repository holds no CDK stack (the repository's
`repository:` row lists no `stack:` rows after seeding). Every other row, and every element with no
row, is not satisfied and is pulled into the Epic's scope.

**Reason.** `built` means only that tests pass. For a repository that deploys, a Story's deploy can
need the element present in AWS dev (a VPC, a Lambda layer), which only `deployed` proves. Pulling a
`built`-but-not-deployed element into scope gives it a Task whose Red step finds its tests already
passing (CONTEXT 7.19) and a Story deploy that deploys it, so the cost is small; leaving it out would
let a deploy fail for a missing prerequisite. A repository with no stack (a library) never reaches
`deployed` through a stack deploy, so `built` is the most its elements can reach.

### 10.5 Writers and readers

| Who | When | Writes |
|---|---|---|
| Task pipeline, after the whole suite passes and the Task's commit is made (the commit step of `task-to-deploy`, S11) | each Task | state `built`, `task` = the Task id, `commit` = its commit sha, `repository` = the Task's `repoPath` basename with `repositorySource: build`, for each element of the delta items the Task cites (`requirement_ids` joined to its Epic's `<work>/delta-items.json`). A row at `deployed` goes back to `built`: the deployed code is older than this commit. |
| Story deploy, after `built-version` verifies the deploy (S11) | each Story | state `deployed` for every element its Tasks set to `built`, with the deploy's commit |
| Seeding (section 10.6) | once, and on a re-seed | new rows; seeded fields only; never `state`, `task` or `commit` |
| Elaboration | never | nothing |

Readers (elaboration only reads): `archbaseline.baseline_facts` for `implementationWork` (section
3.5), the architecture Closure's classification (`architecture.md` step 32), and repo scoping's
placement facts (`repo-scoping.md` steps 3, 5, 6). Each records the rows it read as a `matrix-rows`
input (section 3.3).

### 10.6 Seeding (PLAN S05a)

`<orch>/seed_matrix.py`, deterministic, no agent session. Sources:

1. **Repositories**: `uv run <plugin>/skills/polyrepo-repo/scripts/polyrepo.py inventory --json
   --no-fetch`. One `repository:` row per repository with a path on disk, `lifecycle` not
   `archived`, and a path not under `$SKILLSPOKE_ROOT/apps/marketing/`; `repository` = its name,
   `expected` = its manifest `purpose`.
2. **CDK stacks**: in each such repository that has a `cdk.json`, `cdk ls --profile dev` run in the
   repository (the CDK app as the repository declares it). One `stack:` row per stack listed, with
   its repository. A repository whose `cdk ls` exits non-zero gets `stacksError` (the exit status
   and the command) on its row and no stack rows; S05a's verifier reports those.
3. **Elements**: every effective view under `<arch>/arc42/` (excluding `02-architecture-constraints/`),
   read with `archstate._catalog`: one row per name in `shows` (and `subject` when `shows` is
   empty), `views` = every view that names it, `expected` = the views' titles joined. When an
   element id equals a repository name or a stack name (same casefold rule), the row takes that
   repository (and stack) with `repositorySource: seed`; otherwise `repository` is null and the
   steward places it in repo scoping.

Every seeded row has `state: unknown`, `task: null`, `commit: null`.

**Re-seeding** never changes `state`, `task`, `commit`, `changedAt`, `changedBy`, or a `repository`
whose `repositorySource` is `build`. It adds rows that are new, and refreshes `views`, `expected`,
`stack` and a seed-sourced `repository`. A row whose element no view names any more is kept (the
build pipeline may have built it) and gets `views: []`.

## 11. Flow-level decisions

### 11.1 Architecture

- **Repository list without a steward session (QUESTIONS 28).** The survey's repository list comes
  from `polyrepo.py inventory --json --no-fetch` (the `name`, `path`, `role`, `lifecycle` fields
  of each record; repositories under `apps/marketing/` and archived ones left out), run in Python.
  The `polyrepo-steward` session of `architecture.md` step 6 is dropped. Evidence: the inventory
  record carries exactly the four fields the old `REPOS_SCHEMA` asked the steward for
  (`polyrepo.py` `record`), and repo scoping already takes the inventory this way
  (`repo-scoping.md` step 4).
- **Build items for every case (QUESTIONS 29).** `arch-delta` lists, per case (CONTEXT 7.7):
  - `partial`: one item per element the `delta/` views show; plus one `implementation-gap` item per
    element of the future set (the target views of the PRD's capabilities) that the matrix does not
    satisfy (section 10.4) and that is not already an item; plus the Closure's prerequisites.
  - `new`: one item per element the target views show; plus the Closure's prerequisites.
  - `none`: one `implementation-gap` item per element the cited effective views
    (`baseline.json` `entries[].documents`) show, **whether or not the matrix satisfies it**; plus
    the Closure's prerequisites. With no architecture change there is no delta to guarantee an
    item, and CONTEXT 7.6 gives every Epic Stories and Tasks: a satisfied element still gets a Task,
    and the build pipeline's tests settle that nothing changes. When the cited views show no
    element at all, `arch-delta` returns a refusal and repo scoping fails at stage `input`, cause
    `other` (`repo-scoping.md` step 1).
- **Agent definitions that describe removed work (QUESTIONS 32c).** Each is updated by the S04
  sub-step that implements the flow using it, in the same commit: `prd-reality-reconciler.md`
  (survey without built judgments, section 3.5; Closure as a walk over views only) in S04a; the
  `polyrepo-steward` placement brief and any line in its definition about creating repositories
  during placement or listing deployments in S04b; `task-decomposer.md` (no item statuses, no
  `planned-elsewhere`, no `done` items citing code; section 11.6) in S04d.

### 11.2 Repo scoping

- **Findings left after the corrective pass (QUESTIONS 30): fail**, at stage `repo-scoping`, cause
  `other`. An item still unplaced, placed twice, or in a never-placed repository would leave work
  with no Task or put it in the wrong repository, and nothing later places it.
- **An item placed elsewhere than its matrix row's repository (QUESTIONS 31): a warning.** The
  target may move an element, and most seeded rows carry no repository or one matched only by name
  (section 10.6); failing would block correct moves.

### 11.3 Repository creation owner facts (QUESTIONS 9)

**Decision.** Recognised before any `polyrepo.py create` runs, by a preflight whose results are exit
statuses and JSON fields:
1. `gh auth status` exits non-zero → owner fact: "the GitHub CLI is not signed in on this machine;
   run `gh auth login`".
2. `gh api user/memberships/orgs/<github_owner> --jq .state` (`github_owner` from
   `<control>/.polyrepo/config.yaml`, today `satteritsik`) exits non-zero or prints a value other
   than `active` → owner fact: "the signed-in GitHub account is not an active member of
   `<github_owner>`".
Either returns `requiredHumanActions` and stops repo scoping at stage `repo-creation` with no cause
(section 8). A `polyrepo.py create` that fails after a passing preflight is cause `other` for the
incident-responder (its result carries only error text, section 6.1).

### 11.4 TRD authoring

- **Filing path for a PRD outside a `prds/` folder (QUESTIONS 33): no rule is added; the case does
  not reach elaboration.** Evidence: the driver finds PRDs only through `workitems.prd_index`, which
  globs `prds/*.md`, so every dispatched PRD is in a `prds/` folder and `workitems.trd_path_for`
  always returns its TRD path.
- **The 40-requirement and 25,000-character limits (QUESTIONS 34): stay instructions, not checks.**
  A longer TRD is not wrong output: every requirement in it still cites a source and an element, and
  the citation check (`trd-authoring.md` step 5) still runs. They fail the check test.

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
  nothing to specify writes a short "not applicable" document, which its brief allows.
- **UI design sources (QUESTIONS 32a): confirmed** as `spec-authoring.md` places them. The
  contracts maker (`api-specification-author`) writes `<work>/candidates/spec-<slug>.ui.json` for a
  repository whose placement has `frontend: true`; which placed items are UI items is the maker's
  judgment; Python checks the file against the supplied bundles and the placed item ids (step 6).
  The steward's `frontend` flag is the only structured field that says a repository holds UI.

### 11.6 Task decomposition

- **The Task scope of the finish step (QUESTIONS 41).** `elaboration.finish` is changed in place to
  take a scope: with `scope="epic-tasks"` it calls `scoring.score` with the write scope limited to
  the Tasks under the Epic and no Epic roll-up, and writes no Epic WSJF key. The "every Task
  scored" check reads the result's `unscored` list filtered to the Epic's Task ids. The
  orchestrator calls it in-process (section 2.2).
- **The task-deps schema check (QUESTIONS 42): kept in the orchestrator's acceptance, not merged
  into `write-all-task-edges`.** The acceptance step must produce the exact errors for the one
  corrective retry; `write-all-task-edges` keeps the key validation it already has as the writer.
- **Which metadata marks a Task as started (QUESTIONS 43).** A Task is started when its status is
  `in_progress` or `closed`, or any metadata key starting `build_` or `cds_audit_` is present and
  non-empty (`build_state`, `build_stop_stage`, `cds_audit_*`). Reason: only the build lane writes
  those keys, so their presence proves the lane worked on the Task and its Story worktree may hold
  that work.
- **`blocked` and `deferred` (QUESTIONS 44).** `blocked` with no build key is unstarted (deleted and
  recreated on a `replaced` rerun): it is a dependency state. `deferred` is kept like a started
  Task: a person set it, and recreating the Task would erase that ruling.
- **Deleting a Task another Epic's Task depends on (QUESTIONS 45): re-point.** Before the delete,
  the orchestrator records every `blocks` edge from a Task outside the Story onto a Task it is about
  to delete, with the deleted Task's cited work items. After the new set is written, each recorded
  edge is added onto every new Task that cites at least one of the same work items. An edge with no
  such new Task is recorded as a warning in `run.json` and the incident evidence, not re-added.
- **A `web-ui` Task citing UI items of two artifacts (QUESTIONS 46): warn and keep the first**, as
  `hierarchy.check_cds_contract` does. `task-decomposer.md` is aligned to that (S04d). Reason: the
  planner can settle it deterministically; refusing would fail the Story for a normalization.
- **`surfaces` when the spec does not settle it (QUESTIONS 47): `null`.** `task-decomposer.md` is
  aligned to the schema (S04d); the bead's description renders null as `unknown (none declared)` as
  `beadwrite` does today.

### 11.7 Scripts that read the removed detailing file (QUESTIONS 32d)

**Decision.** Changed in place in `scripts/portfolio/`, each by the S04 sub-step that uses it, and
called in-process by the orchestrator (section 2.2):
- `hierarchy.WORK_STATUSES` and `hierarchy.derive_prerequisites`, `beadwrite.plan_story_tasks`,
  `beadwrite.closure_task_edges`: read the work items from `repo-scoping.json` and
  `delta-items.json` (every placed item is a work item; no status) instead of `recon-*.json`
  (S04d).
- `archclosure.write_closure`: takes the classified closure Python builds from the walk and the
  matrix (`architecture.md` step 32) and no `status_of` bead read (S04a).
- `archstate.delta_items` / `arch-delta`: prerequisite fields become `state` (the matrix state read)
  and `repository` (from the matrix row); `deployedBy` and `plannedBy` are removed (S04a).

## 12. Requirements map

| CONTEXT rule | Where this design implements it |
|---|---|
| 5 Python orchestrates; sessions only for reasoning; paths, not data; zero command-runner sessions; near-zero restart cost | §2 (no step starts a session to run a command; deterministic steps are Python), §2.3 (briefs carry paths), §3 (reuse decided before any session) |
| 6 Rewrite intent; check test; hard limits | §2.2, §7.3 (section 2), §5.2 (safety hooks), §10.6 (no marketing repositories), §11.6 (deletion only of unstarted Tasks) |
| 7.1 Tier 2 | commits and pushes on `main` per PLAN; §10.1 keeps the matrix out of git |
| 7.2 Only the owner runs the pipeline | §5.2 (`pipeline-run-blocker.sh` in every session) |
| 7.3 Plugin versions | §1 (the driver runs `<installPath>`) |
| 7.4 Retries and structured causes | §6 |
| 7.5 Task rerun rule | §3.7 (QUESTIONS 18), §11.6 (QUESTIONS 43 to 45) |
| 7.6 Done; no "nothing to build"; one corrective pass; Epic stays open | §6.3, §11.1 (QUESTIONS 29), §11.6 (QUESTIONS 41) |
| 7.7 Three cases; writers before reviewers; last writer reconciles; 3 rounds | §2.1 (rounds as a loop of at most 3), §11.1 |
| 7.8 Selection filters | unchanged in the driver (§9 changes no selection code except reason texts) |
| 7.9 Who gets asked what | §8, §11.3 |
| 7.10 Repositories | §11.1 (inventory), §11.2, §11.3 |
| 7.11 Deterministic over agentic | §2.2, §3.5, §11.5 (Story text) |
| 7.12 Dashboard truth | §4.5 |
| 7.13 Saved surveys | §3.4 |
| 7.14 Facts, not guesses | §2.3 |
| 7.15 Standing rules | §5.2 and §10.1 (paths from `ATW_*` variables, new ones named), §10.6 (`cdk ls --profile dev`), §5.2 (no person's name: hook scripts matched by file name) |
| 7.16 Hierarchy; no bug beads | unchanged: the only beads written are Stories and Tasks under the Epic |
| 7.17 Epic readiness out of scope | §11.6 (Task-only scoring) |
| 7.18 Entry point | §1 (one flow in the registry, started by the driver) |
| 7.19, 7.23, 7.24 Existing code; Tasks are activities | §3.5, §11.1, §11.7 |
| 7.20 Missing prerequisites are built | §10.4, §11.1 |
| 7.21 arc42 detail gap; same expectations | §2.4 |
| 7.22 What elaboration produces | the flow registry runs every phase (§1, §4.2) |
| 7.25 Element status matrix | §10 |
