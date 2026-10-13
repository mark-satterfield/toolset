# Net-effect spec: `wsjf-scoring`

Failure handling: bounded transient retries and quota pauses remain. An ordinary item failure is recorded and excluded from selection for the current invocation; other eligible items continue. Setup, code, schema, and runtime type defects stop new dispatch, preserve the original diagnostic, and let current paid steps finish. Named within-step corrective passes remain bounded content work; failed runs do not dispatch repair or diagnosis agents.

**Status: not part of the Epic pipeline rewrite.** This flow judges and scores Epics. Epic WSJF
scoring belongs to the future readiness process, which is not yet built (CONTEXT 7.17; the owner's
answer 6 of 2026-10-09); elaboration assumes it is done and no Epic flow runs this one. The only
part of it the Epic pipeline uses is the Task WSJF arithmetic (`scoring.score`, rubric
`wsjf.py`), which the `prd-to-spec` steps `elaboration.score` and `elaboration.finish` run with the
write scope limited to the Epic's Tasks, from the sizes the Task bead writes record. Whether this owner-run command is kept until the readiness
process exists is the owner's concern, outside this rewrite. The rest of this file is the record of its
contract, for that decision and for the readiness process.

Source: `<plugin>/workflows/wsjf-scoring.js` (`meta.description`), the plugin command
`<plugin>/commands/wsjf-scoring.md`, the agent `<plugin>/agents/wsjf-scorer.md` and its skills
(`skills/wsjf`, `skills/beads-contract`), `<plugin>/workflows/README.md` (Portfolio section), and, for contracts
only, `<plugin>/scripts/portfolio/depscore.py` (`score-plan`, `judge-input`, `record`, `score`),
`scoring.py`, `prds.py`, `beadgraph.py` and `elaboration.py` (`finish`). Environment variables
are named only in `<plugin>/skills/pipeline-contracts/schemas/driver-surface.schema.json`
(`$defs.DriverEnvironment`; read `<plugin>/skills/pipeline-contracts/SKILL.md`); this spec writes
`$<CONSTANT>` for the value of the variable that schema constant names. `<driver>` is
`$<CONTROL_REPO_ENV>/<DRIVER_DIR_PARTS>`. Sibling specs: `<orch>/specs/epic/dependency-assessment.md`,
`<orch>/specs/epic/task-dependency-assessment.md`, `<orch>/specs/epic/prd-to-spec.md`,
`<orch>/specs/epic/task-decomposition.md`.

Bead metadata: every metadata key, key group, value vocabulary and fingerprint field set this spec
names is defined only in `<plugin>/skills/beads-contract/schemas/bead-metadata.schema.json` and
is named here by the constant `<plugin>/skills/beads-contract/scripts/bead_metadata.py` generates
from it (`KEY_*` for one key, `*_KEYS` for a key group, `*_HASH_*` for a fingerprint field set).
This spec restates none of their names or values.

## Who calls it (the S01f question)

- **The Epic pipeline does not call this flow.** `prd-to-spec` scores only in its steps
  `elaboration.score` and `elaboration.finish`, which run the **arithmetic** step of this flow
  (`scoring.score`) with the write scope limited to the Epic's Tasks and write no value on the
  Epic (CONTEXT 7.17). They never judge: the Epic's value must already be judged (by this flow),
  and its Tasks arrive sized and fingerprinted by the step `beadwrite.write_task` (see
  `<orch>/specs/epic/task-decomposition.md`, whose correction leaves no Task unsized). So the
  arithmetic is one shared Python function that both this flow and those steps call.
- **The driver does not call this flow.** Commit `64b4adbb` (2026-10-02) deleted `triggers.py`; the
  supervisor no longer assesses or re-scores on its own. What is left in `<driver>`: the ledger
  event types `trigger_plan` and `trigger_dispatch` (`ledger.EVENT_TYPES`, no producer),
  `failures.py` reading old `trigger_dispatch` events, and `runcost.FORMER_TRIGGER_COMPOSITES`
  costing old run files.
- **The driver depends on its output.** `selection._epic_candidates` declines an Epic with no
  `KEY_WSJF` value ("a person runs wsjf-scoring to score it"); `selection.build_candidates` and
  `waiting_build` consider only beads with a `KEY_WSJF` value; `ordering`, `storyorder`,
  `storyview` and `observe` rank and display by it (`BeadIndex.wsjf_of` reads metadata
  `KEY_WSJF`, falling back to a score line in `notes`).
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
- Every open Epic whose judged inputs were missing or changed carries freshly judged value, time
  criticality and value-confidence keys and, unless its size rolls up, its judged size keys (the
  `WSJF_KEYS` members `skills/wsjf/scripts/wsjf.py` records as judged), all beside
  `KEY_WSJF_CONTENT_HASH` = its judging fingerprint at plan time.
- Every open Task whose size was missing or changed carries freshly judged size keys and
  `KEY_WSJF_CONTENT_HASH`.
- With `all` and not `rejudge`, every item with values but no fingerprint ("unfingerprinted") has
  `KEY_WSJF_CONTENT_HASH` adopted (written) without judging.
- Every open Epic and Task that the rubric can score carries the computed `WSJF_KEYS` members
  that changed (those `skills/wsjf/scripts/wsjf.py` computes for its level; the schema states each
  key's value domain). Unchanged values are not rewritten.
- A Task under an unscored Epic, or under no Epic, has no value to inherit and stays unscored
  (no `KEY_WSJF` value), so the driver never selects it.
- No edge is created, removed or converted. Nothing is written in a dry run.
- A result object for the caller: `plan`, `judging`, `judgingFailed`, `record`, `score`,
  `failures` (fields in section 4).

## 3. Inputs

- Arguments: `repoPath` (beads repository; default `$<CONTROL_REPO_ENV>`), `pluginRoot`, `workDir`, `archPath`
  (`$<ARCH_PATH_ENV>`, required by the command), `projectRoot` (`$<PROJECT_ROOT_ENV>`, optional),
  `all`, `rejudge`, `only` (list of ids; no current caller passes it), `dryRun`, `priorFailure`
  (optional text from a failed earlier run; no current caller passes it).
- beads, read once per run with descriptions (`beadgraph.load(..., with_description=True)`): every
  open Epic and Task, their `parent` lineage, `tracks` edges between Epics and `blocks` edges
  between Tasks (`Bead.depends_on`), and metadata `KEY_ELABORATION_STATE` and the `WSJF_KEYS`
  members (judged, computed and `KEY_WSJF_CONTENT_HASH`).
- The judging fingerprint: `beads-contract.py` `content_hash` with `--scope judging`, over
  `JUDGING_HASH_FIELDS` with only `JUDGING_HASH_PRESENT` hashed by value.
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
- `judgments/<level>/candidates/<key>.json` (written by the agent): the judgment, in the shape of
  the next two entries. Beside it the agent writes its progress file
  `candidates/<key>.json.progress.json`, and `artifactcontract.py` writes the checkpoint
  `candidates/<key>.json.checkpoint` from it. Both are defined by
  `skills/artifact-handoff/schemas/checkpoint.schema.json`; the checkpoint is bound to the
  candidate path, the digest of the judgment schema and the session's input revision (step 3).
- `judgments/epic/<epic-id>.json`: the accepted Epic judgment, `{rubric: "epic-wsjf", scores:
  [{id, userBusinessValue, timeCriticality, confidence, jobSize?, sizeLow?, sizeHigh?,
  sizeConfidence?, rationale: {userBusinessValue, timeCriticality, jobSize}}], unscored: [{id,
  reason}]}`. `jsonartifact.py` checks the candidate against the judgment schema and publishes
  it in canonical JSON; nothing is stamped into it.
- `judgments/task/<group-key>.json`: the accepted Task judgment, `{rubric: "task-wsjf", scores:
  [{id, jobSize, sizeLow, sizeHigh, sizeConfidence, rationale: {jobSize}}], unscored: [{id,
  reason}]}`; group key = the Epic id, or the Task id for a Task with no Epic.
- `judgments/<level>/<key>.json.receipt`: `{artifactPath, sha256, bytes, schemaSha256, revision}`
  for the published judgment. `<key>.json.prev` holds the judgment it replaced when the two
  differ, and `<key>.json.publish` exists only while a publish is under way.
- `relay/`: one numbered file per `depscore.py` command with its full result
  (`relay/<nnn>-<command>.json`), the source receipts each input revision is made from
  (`relay/inputs-<level>-<key>.json`), and each acceptance receipt
  (`relay/accepted-<level>-<key>.json`, with `.probe` for the reuse check).
- `record.json`: `{dryRun, written: [ids], adopted: [ids], rejected: [{id, level, reason}],
  missing: [ids], unreadable: [{file, reason}], planned, summary: {dryRun, written, adopted,
  rejected, missing, unreadable}}`.
- `score.json`: `{epics: [row], tasks: [row], unscored: [{level, id, reason}], incomplete: [{id,
  reason}], sizeFaults, outsideRange, cycles: {epic, task}, dryRun, planned, summary: {dryRun,
  epicsScored, epicsWritten, tasksScored, tasksWritten, unscored, incomplete, outsideRange,
  epicCycle, taskCycle}}`; row = `{id, wsjf, costOfDelay, rroe, reaches, jobSize, sizeSource,
  sizeOutsideRange, written}`.

Bead writes (all through `beadgraph.Writer.metadata`, i.e. `bd update --set-metadata`, merge):
- `record`: judged keys + `KEY_WSJF_CONTENT_HASH` per judged item (never writes an empty
  fingerprint); `KEY_WSJF_CONTENT_HASH` only, per adopted item.
- `score`: the computed keys listed in section 2, per item whose values changed.

No vault writes, no git commits, no ledger events (the flow is not dispatched by the supervisor).

Result returned to the caller: `{ok, stage: "done" | "Apply" | "args", headline, workDir,
dryRun, plan: <score-plan summary>, judging: {epic: {sessions, judged, failed, failedSessions},
task: {sessions, judged, failed, failedGroups, failedSessions}}, judgingFailed: [ids], record:
<record summary>, score: <score summary>, failures: [{step, reason}], error?, dispatchFailed,
dispatchFailures}`.

## 5. Steps

Each step is what `workflows/wsjf-scoring.js` does. Every `depscore.py` and `jsonartifact.py`
command runs through the relay (the `relay` shared block, `relayrun.py` and a
`workflow-command-runner` session), and the script branches only on the checked copy of what the
command printed. A `depscore.py` command that fails is recorded in `failures`; one whose runner
session returns nothing is logged, and the next plan reads its effect from the tracker.

1. `deterministic` **Plan**: `depscore.py score-plan [--all] [--rejudge] [--only ids] --out
   score-plan.json -C <repo>` (`scoring.plan`). Writes `score-plan.json`.
2. `deterministic` **Judge input**: for each level with items to judge, `depscore.py judge-input
   --plan score-plan.json --level epic|task [--prd-dir prd] --out judge-input-<level>.json`
   (`scoring.judge_input`). The epic level writes `prd/<id>.md` for each Epic to judge. Skipped
   for a level with nothing to judge.

Steps 3 to 6 run once for each planned session (one per Epic id; one per Task group), all
sessions in parallel: every session reads only its own items, and no session's result is
another's input.

3. `deterministic` **Input revision**: `jsonartifact.py --source score-plan.json --source
   judge-input-<level>.json`, with `--source prd` at the epic level, fingerprints the inputs (a
   file by its SHA-256 and size; a directory by the relative path, SHA-256 and size of every file
   in it). The input revision is the SHA-256 of those receipts together with the level and the
   ids the session covers. When the fingerprint command fails, the revision is made from the
   paths alone.
4. `deterministic` **Reuse**: `jsonartifact.py --candidate judgments/<level>/candidates/<key>.json
   --final judgments/<level>/<key>.json --schema-json <judgment schema> --revision <input
   revision> --probe --recover`.
   - The accepted judgment is reused, and no session starts, when its bytes match
     `<key>.json.receipt` and the receipt's `schemaSha256` and `revision` equal the current
     judgment schema digest and input revision.
   - Otherwise, when the candidate's checkpoint is bound to the same candidate path, schema
     digest and revision and its status is `complete`, the candidate is accepted as in step 6 and
     no session starts.
   - When that checkpoint's status is `blocked`, the judgment is not accepted and its items
     count as failed.
   - In every other case step 5 runs.
5. `agent` **Judge**: `wsjf-scorer`, effort `medium` (the JS sets it), model `sonnet` (agent
   frontmatter). The brief ends with the artifact contract data: the candidate path, the
   progress file path, the input revision and the `artifactcontract.py` commands bound to them.
   - **Epic** (one session per Epic id): reads `prd/<id>.md` and its entry and the
     `referenceJobs` in `judge-input-epic.json`, with `archPath` and `projectRoot` as evidence of
     what is decided or built. It judges user-business value, time criticality and their
     confidence, and the size only when `sizedFromTasks` is false; it reads no other Epic's PRD
     or values, sizes by comparison with the reference jobs and never invents a solution in
     order to size; missing design widens the range and does not enlarge the size; RR-OE and
     WSJF are not the session's. It writes `judgments/epic/candidates/<id>.json`.
   - **Task group** (one session per group): reads the group's Tasks and the `referenceJobs` in
     `judge-input-task.json`. It judges size only (value is inherited); a Task above 13 is
     recorded as judged, with the split noted in its rationale. It writes
     `judgments/task/candidates/<key>.json`.
6. `deterministic` **Accept**: the step 4 command without `--probe`. `jsonartifact.py` checks
   the candidate against the judgment schema and publishes it as `judgments/<level>/<key>.json`
   with its receipt (section 4), and reports the counts of `scores` and `unscored`. A session
   whose judgment is not accepted is counted in `judging.<level>.failedSessions` and its ids in
   `judgingFailed`.
7. `deterministic` **Record**: when the plan has anything to judge or adopt (or the plan step
   returned nothing), `depscore.py record --plan score-plan.json --epics-dir judgments/epic
   --tasks-dir judgments/task [--dry-run] --out record.json` (`scoring.record`), over every
   `*.json` file directly in the two directories. Writes `record.json` and the judged metadata.
8. `deterministic` **Score**: `depscore.py score [--dry-run] --out score.json`
   (`scoring.score`). It reads the tracker after step 7, so the arithmetic uses the values just
   recorded. Writes `score.json` and the computed metadata. Runs even when some judging sessions
   failed: the values that did return, and every unchanged one, still score.
9. `deterministic` **Result**: assemble the result object (section 4). `ok` is false when a
   `depscore.py` command of step 1, 2, 7 or 8 failed, or dispatch was interrupted. A judging
   session that failed is reported in `judging` and `judgingFailed` and does not by itself make
   `ok` false.

Agents the workflow dispatches:
- `wsjf-scorer` (Epic) and `wsjf-scorer` (Task group): step 5.
- `workflow-command-runner`: one session for each relay call of steps 1 to 4 and 6 to 8.

## 6. Checks

**In `scoring.record` and `scoring.score`**
- `record` writes only items the plan named, and rejects a judgment for any other id: without it
  a session could overwrite a current Epic's value with one judged from nothing; nothing later
  re-judges a value whose fingerprint was stamped.
- `record` validates every judged value (positive integer, value capped at the rubric's top rung,
  percent range, range widened to contain the estimate) before writing: without it an off-scale
  value reaches beads and the arithmetic divides by or bands it; nothing later re-validates.
- `record` never writes an empty `KEY_WSJF_CONTENT_HASH`: without it a stale value would read as
  `unfingerprinted` and never be re-judged without `--all --rejudge`.
- `score` reads a non-positive or unparseable size as absent (item unscored or Epic incomplete,
  named in `score.json`): without it one bad bead aborts the arithmetic for the whole portfolio.
- `score` writes a bead only when a non-volatile value changed (`scoring._write`, numbers compared
  as numbers): kept as the idempotence that makes a rerun cost nothing; without it every run
  rewrites every scored bead.

**In `jsonartifact.py`** (steps 4 and 6)
- The candidate is valid against the judgment schema before it becomes the accepted judgment.
- An accepted judgment is read as accepted only when its bytes match its receipt.
- An accepted judgment is reused only for the same judgment schema digest and the same input
  revision. The revision covers the whole of `score-plan.json`, which holds the fingerprint of
  every open Epic and Task, so a change to any one of them gives every session a new revision.

**In the workflow**
- `record` is skipped when the plan names nothing to judge or adopt (it would write nothing).
- A dispatch interruption stops further sessions; the run ends as `paused` and `resumable`.
- The workflow itself guards no write to arc42 section 2: its own steps write nothing in the
  vault, and each `wsjf-scorer` session holds Write and Edit and reads `archPath`.

## 7. Failure causes

- `beads` read or write fails in steps 1, 2, 7, 8 (`beadgraph.GraphError`): its `cause` field
  (`beadgraph.py`: `CONTENTION`, `BD_TIMEOUT`, else `OTHER_CAUSE`) gives `contention`,
  `bd-timeout` or `other`. The field exists, but `beadgraph._bd` chooses it by reading `bd`'s
  standard error, which CONTEXT 7.4 does not accept as a structured fact (QUESTIONS.md item 6).
  The workflow does not retry the command: it is recorded in `failures` with its error and the
  run ends with `ok` false at stage `Apply`.
- `ScoringError` from the rubric or a malformed plan file: recorded in `failures` the same way.
- A judging session fails: a transient dispatch failure is retried by the bounded dispatch
  policy inside the workflow. A session that returns with no candidate, or with one that fails
  the schema, or a judgment `record` lists as `unreadable`/`rejected`/`missing`: not retried in
  this run; its items keep their old value and are planned again on the next run (the run
  reports them).
- `priorFailure` given: the brief carries it (a retry with clarified instructions, 7.4).
- A relay call whose runner session returns nothing: the command's effect is unknown to this
  run; the next plan reads it from the tracker.

## 8. Resume points

- Steps 1 and 2: not saved as resume points; recomputed every run from beads (no judging
  session).
- Step 5 judgments: saved as `judgments/<level>/<key>.json`, each with its `.receipt`. A rerun in
  the same `workDir` starts no session whose input revision is unchanged, that is when
  `score-plan.json`, `judge-input-<level>.json` and, for an Epic, every file under `prd/` have
  the same bytes. A session that was interrupted leaves its candidate with the progress file and
  checkpoint; a rerun with the same input revision accepts a checkpoint marked `complete`
  without a session, and otherwise starts a session that continues those files.
- Step 7: its effect is in beads (`KEY_WSJF_CONTENT_HASH` = plan fingerprint). A rerun after step 7
  plans none of those items, so it judges nothing again, whatever its `workDir`.
- Step 8: idempotent; a rerun writes only what changed (nothing, if nothing changed).
- A rerun reuses saved judgments only with the same `workDir`. The command gives every run a new
  one (`<repo>/.claude/workflow-runs/wsjf-scoring/<UTC time>`), and `dependency-assessment` and
  `task-dependency-assessment` pass `<their workDir>/scoring`; in a new `workDir` what is not
  judged again is decided by step 1 from the fingerprints in beads.

## 9. Requirements that apply

- 7.17 Epic readiness: Epic WSJF judging and scoring belong to the future readiness process; no
  Epic pipeline step runs this flow, and the pipeline's own finish step writes Task scores only.
- 7.8 WSJF selection filter: this flow is the producer of the `KEY_WSJF` value that
  `selection._epic_candidates` (Epics), `selection.build_candidates` and `waiting_build` (Tasks)
  and the dashboard require. It never writes an empty `KEY_WSJF`; an item it cannot score keeps no
  `KEY_WSJF` value and so stays out of selection and off the dashboard, which is the filter's
  intent. It does not filter itself: it scores every open Epic and Task, including the mobile Epics
  `ssbd-cb6i4`, `ssbd-kfihs`, `ssbd-mx3vn` (their exclusion is by `KEY_ELABORATION_STATE`, in
  `<driver>`).
- 7.2 Only the owner runs the pipeline: this flow is an owner-run command; no session runs it as
  a test, and `dryRun` exists for the owner, not for rehearsal.
- 7.4 Retries: section 7; a failed judging session is not rerun on unchanged input in the same run.
- 7.6 / prd-to-spec: the arithmetic is shared with the `prd-to-spec` finish step, which computes
  every Task's WSJF after the Tasks and their edges exist (never "Epic closed").
- 7.11 Deterministic over agentic: planning, fingerprints, validation, arithmetic and writes are
  code; only value and size judgments are agent work.
- 7.14 Briefs: the judging brief gives the rubric, the files and the expected output, no expected
  score.

## 10. Open items

See QUESTIONS.md
