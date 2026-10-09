# Net-effect spec: `wsjf-scoring`

Source: `<plugin>/workflows/wsjf-scoring.js` (`meta.description`), the plugin command
`<plugin>/commands/wsjf-scoring.md`, the agent `<plugin>/agents/wsjf-scorer.md` and its skills
(`wsjf`, `beads-contract`), `<plugin>/workflows/README.md` (Portfolio section), and, for contracts
only, `<plugin>/scripts/portfolio/depscore.py` (`score-plan`, `judge-input`, `record`, `score`),
`scoring.py`, `prds.py`, `beadgraph.py` and `elaboration.py` (`finish`). `<driver>` is
`$ATW_CONTROL_REPO/ops/sdlc-automation`. Sibling specs: `<orch>/specs/epic/dependency-assessment.md`,
`<orch>/specs/epic/task-dependency-assessment.md`, `<orch>/specs/epic/prd-to-spec.md`,
`<orch>/specs/epic/task-decomposition.md`.

## Who calls it (the S01f question)

- **The Epic pipeline does not call this flow.** `prd-to-spec` scores only through
  `depscore.py elaboration-finish` (`elaboration.finish`), which runs the **arithmetic** step of
  this flow (`scoring.score`) scoped to the Epic and its Tasks, with the Epic's size rolled up from
  its Tasks when it is being marked `done`. It never judges: the Epic's value must already be
  judged (by this flow), and its Tasks arrive sized and fingerprinted by `depscore.py write-task`
  (see `<orch>/specs/epic/task-decomposition.md`). So the arithmetic is one shared Python function
  that both this flow and the `prd-to-spec` finish step call.
- **The driver does not call this flow.** Commit `64b4adbb` (2026-10-02) deleted `triggers.py`; the
  supervisor no longer assesses or re-scores on its own. What is left in `<driver>`: the ledger
  event types `trigger_plan` and `trigger_dispatch` (`ledger.EVENT_TYPES`, no producer),
  `failures.py` reading old `trigger_dispatch` events, and `runcost.FORMER_TRIGGER_COMPOSITES`
  costing old run files.
- **The driver depends on its output.** `selection._epic_candidates` declines an Epic with no
  `wsjf` ("a person runs wsjf-scoring to score it"); `selection.build_candidates` and
  `waiting_build` consider only beads with a `wsjf`; `ordering`, `storyorder`, `storyview` and
  `observe` rank and display by it (`BeadIndex.wsjf_of` reads metadata `wsjf`, falling back to a
  `wsjf_score: N` line in `notes`).
- **The only caller today is the owner**, through `/agent-teams-workforce:wsjf-scoring`, and
  `dependency-assessment` / `task-dependency-assessment` call it after applying edges.

## 1. Purpose

Score every open Epic and Task with WSJF from the dependency edges already in beads. A model judges
only the inputs that need judgment, and only for items whose content changed or whose value is
missing: each Epic's user-business value, time criticality, value confidence and (until its size
rolls up from its Tasks) its job size, one Epic per session from its own PRD; and each Epic's
Tasks' job sizes, one session per Epic (one per Task with no Epic). The judgments are recorded with
the fingerprint of the content they were judged from; then the arithmetic (RR-OE from reachability
over the `tracks`/`blocks` graph, cost of delay, WSJF, child-size roll-up) runs over every open item
and only changed values are written. `all` includes items that already have a value; `rejudge`
judges them again; `only` restricts judging to named items; `dryRun` writes nothing. It never sets
or changes a dependency edge.

## 2. Produces and decides

After a successful run:
- Every open Epic whose judged inputs were missing or changed carries freshly judged `wsjf_ubv`,
  `wsjf_tc`, `wsjf_confidence` and, unless its size rolls up, `wsjf_size_estimate`,
  `wsjf_size_low`, `wsjf_size_high`, `wsjf_size_confidence`, all beside `wsjf_content_hash` = its
  judging fingerprint at plan time.
- Every open Task whose size was missing or changed carries freshly judged size keys and
  `wsjf_content_hash`.
- With `all` and not `rejudge`, every item with values but no fingerprint ("unfingerprinted") has
  `wsjf_content_hash` adopted (written) without judging.
- Every open Epic and Task that the rubric can score carries the computed keys that changed:
  `wsjf`, `wsjf_calculated_at`, `wsjf_rubric`, `wsjf_rroe`, `wsjf_reaches` (Epic) or
  `wsjf_unblocks` (Task), `wsjf_cod`, `wsjf_size`, `wsjf_size_source` (`supplied` or
  `child-rollup`), `wsjf_value_from` (Task), `wsjf_size_outside_range` (Epic sized from Tasks), as
  `skills/wsjf/scripts/wsjf.py` names them. Unchanged values are not rewritten.
- A Task under an unscored Epic, or under no Epic, has no value to inherit and stays unscored
  (no `wsjf`), so the driver never selects it.
- No edge is created, removed or converted. Nothing is written in a dry run.
- A result object for the caller: `plan`, `judging`, `judgingFailed`, `record`, `score`,
  `failures` (fields in section 4).

## 3. Inputs

- Arguments: `repoPath` (beads repository; default `$ATW_CONTROL_REPO`), `workDir`, `archPath`
  (`$ATW_ARCH_PATH`, required by the command), `projectRoot` (`$ATW_PROJECT_ROOT`, optional),
  `all`, `rejudge`, `only` (list of ids; no current caller passes it), `dryRun`, `priorFailure`
  (optional text from a failed earlier run; no current caller passes it).
- beads, read once per run with descriptions (`beadgraph.load(..., with_description=True)`): every
  open Epic and Task, their `parent` lineage, `tracks` edges between Epics and `blocks` edges
  between Tasks (`Bead.depends_on`), and metadata `elaboration_state`, the judged keys, the
  computed keys and `wsjf_content_hash`.
- The judging fingerprint: `beads-contract.py` `content_hash` with `--scope judging` (title,
  description, issue_type, priority; WSJF, lane, sequencing keys, labels and dependencies nulled).
- The rubric: `<plugin>/skills/wsjf/scripts/wsjf.py` (bands, Fibonacci size scale, snapping,
  roll-up), loaded by `scoring._load_wsjf`.
- Agent context: the architecture under `archPath` and code under `projectRoot`, read by the
  judging sessions as evidence of what is already decided or built.
- An Epic's PRD is its bead `description` (`prds.write_prds` writes `# <title>\n\n<description>`).

## 4. Outputs

Files (under `<workDir>`; JSON unless stated):
- `score-plan.json`: `scoring.plan` result: `judge: {epics: [{id, reason}], tasks: [{id, reason,
  epic}]}`, `adopt: [ids]`, `fingerprints: {id: sha}` for every open Epic and Task, `summary:
  {includeAll, rejudge, openEpics, openTasks, states: {missing, changed, unfingerprinted,
  current}, epicsToJudge, tasksToJudge, toAdopt, only?}`.
- `judge-input-epic.json`, `judge-input-task.json`: `scoring.judge_input` result: `level`,
  `items` (Epic: `{id, title, reason, prdPath, sizedFromTasks}`; Task: `{id, title, reason,
  description, epic: {id, title} | null}`), `referenceJobs` (`{id, title, estimate, low, high,
  refinedSize, tasks}` per Epic whose elaboration is done and whose Tasks are all sized),
  `summary: {items, toJudge, referenceJobs, ids (epic) | groups: [{key, epic, tasks}] (task)}`.
- `prd/<epic-id>.md`: the PRD of each Epic to judge.
- `judgments/<level>/<key>.input.json` (new, written by step 3): `{<id>: <judging fingerprint>}`
  for every item the session covers, in canonical JSON. It is the session's resume input.
- `judgments/epic/<epic-id>.json`: `{rubric: "epic-wsjf", scores: [{id, userBusinessValue,
  timeCriticality, confidence, jobSize?, sizeLow?, sizeHigh?, sizeConfidence?, rationale:
  {userBusinessValue, timeCriticality, jobSize}}], unscored: [{id, reason}]}`, written by the
  agent; nothing is stamped into it.
- `judgments/task/<group-key>.json`: `{rubric: "task-wsjf", scores: [{id, jobSize, sizeLow,
  sizeHigh, sizeConfidence, rationale: {jobSize}}], unscored: [{id, reason}]}`; group key = the
  Epic id, or the Task id for a Task with no Epic.
- `judgments/<level>/<key>.json.meta.json` (new, step 6): `artifactio.record` of the judgment file
  with the session's `<key>.input.json` and its other input files (`prd/<id>.md` for an Epic,
  `judge-input-<level>.json`) as inputs: the one input-record format of every Epic flow.
- `record.json`: `{dryRun, written: [ids], adopted: [ids], rejected: [{id, level, reason}],
  missing: [ids], unreadable: [{file, reason}], planned, summary: {dryRun, written, adopted,
  rejected, missing, unreadable}}`.
- `score.json`: `{epics: [row], tasks: [row], unscored: [{level, id, reason}], incomplete: [{id,
  reason}], sizeFaults, outsideRange, cycles: {epic, task}, dryRun, planned, summary: {dryRun,
  epicsScored, epicsWritten, tasksScored, tasksWritten, unscored, incomplete, outsideRange,
  epicCycle, taskCycle}}`; row = `{id, wsjf, costOfDelay, rroe, reaches, jobSize, sizeSource,
  sizeOutsideRange, written}`.

Bead writes (all through `beadgraph.Writer.metadata`, i.e. `bd update --set-metadata`, merge):
- `record`: judged keys + `wsjf_content_hash` per judged item (never writes an empty
  fingerprint); `wsjf_content_hash` only, per adopted item.
- `score`: the computed keys listed in section 2, per item whose values changed.

No vault writes, no git commits, no ledger events (the flow is not dispatched by the supervisor).

Result returned to the caller: `{ok, stage: "done" | "Judge" | "Apply", headline, workDir,
dryRun, plan: <score-plan summary>, judging: {epic: {sessions, judged, failed}, task: {sessions,
judged, failed, failedGroups}}, judgingFailed: [ids], record: <record summary>, score: <score
summary>, failures: [{step, cause, reason}]}`.

## 5. Steps

1. `deterministic` **Plan**: `scoring.plan(graph, include_all, rejudge, only)` (today
   `depscore.py score-plan [--all] [--rejudge] [--only ids] --out score-plan.json -C <repo>`).
   Writes `score-plan.json`.
2. `deterministic` **Judge input**: for each level with items to judge,
   `scoring.judge_input(graph, plan, level, prd_dir)` (today `depscore.py judge-input --plan
   score-plan.json --level epic|task [--prd-dir prd] --out judge-input-<level>.json`). The epic
   level writes `prd/<id>.md` for each Epic to judge. Skipped for a level with nothing to judge.
3. `deterministic` **Reuse**: for each planned session (one per Epic id; one per Task group), write
   `judgments/<level>/<key>.input.json` (the current plan fingerprints of every item the session
   covers). If `judgments/<level>/<key>.json` exists and every input recorded in its `.meta.json`
   hashes as recorded (so the fingerprints are the ones it was judged from), the session is not
   started.
4. `agent` **Judge Epic** (one session per Epic id still to judge): `wsjf-scorer`. Input paths:
   `prd/<id>.md`, `judge-input-epic.json` (its entry and `referenceJobs`), `archPath`,
   `projectRoot`. Brief: the facts the JavaScript states (judge UBV, TC, value confidence, and
   size only when `sizedFromTasks` is false; read no other Epic's PRD or values; size by
   comparison with the reference jobs; never invent a solution to size it; missing design widens
   the range, it does not enlarge the size; RR-OE and WSJF are not the session's). Output file:
   `judgments/epic/<id>.json`. Model `sonnet` (agent frontmatter), effort `medium` (the JS sets
   it). That is right: one PRD against a fixed rubric is bounded judgment, not design.
5. `agent` **Size Tasks** (one session per group still to judge): `wsjf-scorer`. Input paths:
   `judge-input-task.json` (the group's Task ids, their descriptions, `referenceJobs`),
   `archPath`, `projectRoot`. Brief: size only, value is inherited; a Task above 13 is recorded as
   judged, with the split noted in its rationale. Output: `judgments/task/<key>.json`. Model
   `sonnet`, effort `medium`; right for the same reason.
   Steps 4 and 5 all run in parallel: every session reads only its own items, and no session's
   result is another's input. Each session runs inside the session runner's section 2 guard
   (`driver-contract.md` §8): `wsjf-scorer` holds Write and Edit and reads `archPath`.
6. `deterministic` **Record inputs**: after each session returns, Python records the judgment file
   with `artifactio.record` (inputs in section 4). The agent never writes the record.
7. `deterministic` **Record**: when the plan has anything to judge or adopt,
   `scoring.record(graph, plan, judgments, writer)` over every `*.json` under `judgments/epic/`
   and `judgments/task/` (today `depscore.py record --plan score-plan.json --epics-dir
   judgments/epic --tasks-dir judgments/task [--dry-run] --out record.json`). Writes
   `record.json` and the judged metadata.
8. `deterministic` **Score**: `scoring.score(graph_reloaded, writer)` (today `depscore.py score
   [--dry-run] --out score.json`). The graph is read again after step 7 so the arithmetic uses
   the values just recorded. Writes `score.json` and the computed metadata. Runs even when some
   judging sessions failed: the values that did return, and every unchanged one, still score.
9. `deterministic` **Result**: assemble the result object (section 4). `ok` is false when any
   step 1, 2, 7 or 8 failed or any judging session failed.

Every `depscore.py` call that the JavaScript sent through `relay.js` / `relayrun.py` /
`workflow-command-runner` is a direct call (in-process function or one subprocess) in steps 1, 2,
7 and 8. The JavaScript's `artifactRevision` and `authorArtifact` relay calls (input revision
binding, candidate file, schema check, publish) are not carried over: see section 6.

Agents dispatched by the JavaScript, accounted for:
- `wsjf-scorer` (Epic): kept, step 4.
- `wsjf-scorer` (Task group): kept, step 5.
- `workflow-command-runner` (every `step()`, `artifactRevision`, `authorArtifact`): dropped;
  replaced by steps 1, 2, 3, 6, 7, 8.

## 6. Checks kept / Checks dropped

**Checks kept**
- `record` writes only items the plan named, and rejects a judgment for any other id: without it
  a session could overwrite a current Epic's value with one judged from nothing; nothing later
  re-judges a value whose fingerprint was stamped.
- `record` validates every judged value (positive integer, value capped at the rubric's top rung,
  percent range, range widened to contain the estimate) before writing: without it an off-scale
  value reaches beads and the arithmetic divides by or bands it; nothing later re-validates.
- `record` never writes an empty `wsjf_content_hash`: without it a stale value would read as
  `unfingerprinted` and never be re-judged without `--all --rejudge`.
- `score` reads a non-positive or unparseable size as absent (item unscored or Epic incomplete,
  named in `score.json`): without it one bad bead aborts the arithmetic for the whole portfolio.
- `score` writes a bead only when a non-volatile value changed (`scoring._write`, numbers compared
  as numbers): kept as the idempotence that makes a rerun cost nothing; without it every run
  rewrites every scored bead.
- Reuse (step 3) compares the recorded input file with the current fingerprints: without it a
  judgment of old content is recorded with a new fingerprint and never re-judged.
- Section 2 hard limit: the session runner's guard around each judging session.

**Checks dropped**
- `resolveArgs` / `refuseArgs` (a Python script run through a relay to resolve paths from env
  vars): the Python entry point reads `os.environ` directly; a missing `ATW_ARCH_PATH` is refused
  by the command before the flow starts.
- `artifactRevision` input binding and `authorArtifact` candidate-then-publish with a schema check:
  `record` already validates every field it writes and reports an unreadable file under
  `unreadable`; the binding's job (not recording a stale judgment) is done by step 3's
  fingerprint comparison and by `record` stamping the plan-time fingerprint.
- The relay `noResult` case ("the runner returned no result; read its effect from the tracker"):
  there is no runner; a direct call returns or raises.
- `dispatchInterruption` checks between sessions: a sandbox artifact; the Python runner stops on
  the breaker (`<driver>/breaker.py`) or a signal.
- The `records` guard skipping `record` when nothing was planned: kept only as an optimisation
  (it writes nothing anyway), not as a check.

## 7. Failure causes

- `beads` read or write fails in steps 1, 2, 7, 8 (`beadgraph.GraphError`): its `cause` field
  (`beadgraph.py`: `CONTENTION`, `BD_TIMEOUT`, else `OTHER_CAUSE`) gives `contention`,
  `bd-timeout` or `other`. Retry reasonable for `bd-timeout`/`contention` (backoff 30 s doubling,
  cap 30 min); not for `other`. The field exists, but `beadgraph._bd` chooses it by reading `bd`'s
  standard error, which CONTEXT 7.4 does not accept as a structured fact; merged question Q5 in
  `driver-contract.md`.
- `ScoringError` from the rubric or a malformed plan file: `other`; not retried (same input, same
  result); incident-responder.
- A judging session fails: `api` or `quota` from the headless runner's structured result (the
  breaker handles them); retry reasonable. A session that returns but writes no judgment file, or
  one `record` lists as `unreadable`/`rejected`/`missing`: `other`; not retried in this run; its
  items keep their old value and are planned again on the next run (the run reports them).
- `priorFailure` given: the brief carries it (a retry with clarified instructions, 7.4).
- `relay`: no producer in this flow.

## 8. Resume points

- Steps 1 and 2: not saved as resume points; recomputed every run from beads (cheap, no session).
- Step 4/5 judgment files: saved, each with `.meta.json`; fingerprint = the session's
  `<key>.input.json` (the judging fingerprint of each item the session covers) and its other input
  files. A rerun starts no session whose recorded inputs are unchanged.
- Step 7: its effect is in beads (`wsjf_content_hash` = plan fingerprint). A rerun after step 7
  plans none of those items, so it judges nothing again.
- Step 8: idempotent; a rerun writes only what changed (nothing, if nothing changed).
- A rerun after any point therefore redoes no session whose inputs are unchanged and starts no
  session when nothing needs judging. This needs a `workDir` that survives between runs: merged
  question Q8.

## 9. Owner rules that apply

- 7.8 WSJF selection filter: this flow is the producer of the `wsjf` value that
  `selection._epic_candidates` (Epics), `selection.build_candidates` and `waiting_build` (Tasks)
  and the dashboard require. It never writes an empty `wsjf`; an item it cannot score keeps no
  `wsjf` and so stays out of selection and off the dashboard, which is the filter's intent. It
  does not filter itself: it scores every open Epic and Task, including the mobile Epics
  `ssbd-cb6i4`, `ssbd-kfihs`, `ssbd-mx3vn` (their exclusion is by `elaboration_state`, in
  `<driver>`).
- 7.2 Only the owner runs the pipeline: this flow is an owner-run command; no session runs it as
  a test, and `dryRun` exists for the owner, not for rehearsal.
- 7.4 Retries: section 7; a failed judging session is not rerun on unchanged input in the same run.
- 7.6 / prd-to-spec: the arithmetic is shared with `elaboration-finish` (Epic rolled up from its
  Tasks only once `done`; never "Epic closed").
- 7.11 Deterministic over agentic: planning, fingerprints, validation, arithmetic and writes are
  code; only value and size judgments are agent work.
- 7.14 Briefs: the judging brief gives the rubric, the files and the expected output, no expected
  score.

## 10. Open questions

**Q8 [S02] (merged; also asked in `dependency-assessment.md` and `task-dependency-assessment.md`).
A stable work directory for the owner-run portfolio flows.** The commands create a fresh `workDir`
per run (`.claude/workflow-runs/wsjf-scoring/<timestamp>`, and the same for the two assessment
flows), so a crashed run's judgments and edges are never reused. Reuse needs a stable directory
(for example `<control>/.claude/workflow-runs/artifacts/_portfolio/<flow>/`, or per Epic or Task
for the assessments).

**Q9 [S02] (merged; also asked in `dependency-assessment.md`). Which PRD text is authoritative for
judging and assessment?** Judging and the assessment corpus read the Epic's bead `description` as
its PRD; `prd-to-spec` reads the vault PRD it finds through `workitems.find_prd` /
`$ATW_PRD_DIR`. If the two differ, value and edges are judged from a different text than the one
elaborated. S02 checks whether the driver's PRD-to-Epic sync (`ATW_PRD_EPIC_SYNC`,
`ATW_PRD_EPIC_VERIFY`) keeps them equal, and if not, picks the vault PRD or the description.

**Q10 [owner] (merged; also asked in `dependency-assessment.md`, `task-decomposition.md` and
`prd-to-spec.md`). Do new Epics, and Tasks left unsized, stay manual for scoring and dependency
assessment, or does the orchestrator run them?** With the triggers removed (commit `64b4adbb`, on
purpose), a new Epic has no `wsjf` and no `tracks` edges until the owner runs
`/wsjf-scoring` and `/dependency-assessment`, so the driver never selects it. The same holds for a
Task `task-decomposition` writes without a valid size: nothing in the Epic pipeline or the driver
judges its size later, so it stays unselectable (CONTEXT 7.8) and the Epic's size roll-up is
incomplete until the owner runs `/wsjf-scoring`. If the owner wants the orchestrator to do it, S02
picks where (for unsized Tasks: `task-decomposition`'s one corrective pass with the exact Task keys,
or Task-level judging for this Epic's unsized Tasks before `elaboration-finish`).

1. **[S02] Leftover driver trigger vocabulary.** `ledger.EVENT_TYPES` `trigger_plan`/
   `trigger_dispatch` and `failures.py`'s `trigger_dispatch` handling have no producer. Keep them
   for old ledgers or remove them (S05)?
- The structured cause for `bd` failures: merged question Q5 in `driver-contract.md`.
- `wsjf-scorer` frontmatter `isolation: worktree`: merged question Q2 in `driver-contract.md`.
