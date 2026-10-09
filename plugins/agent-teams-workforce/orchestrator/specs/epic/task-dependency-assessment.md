# Net-effect spec: `task-dependency-assessment`

Source: `<plugin>/workflows/task-dependency-assessment.js` (`meta.description`), the agent
`<plugin>/agents/task-dependency-mapper.md`, `<plugin>/skills/beads-contract/SKILL.md` (sequencing
and Story-edge keys), `<plugin>/workflows/README.md` (Portfolio section), and, for contracts only,
`<plugin>/scripts/portfolio/depscore.py` (`assess-plan --level task`, `assess-context --task`,
`validate --task`, `apply-edges --task`), `edgeset.py`, `assesscontext.py` (`task_context`) and
`storyedges.py`. `<driver>` is `$ATW_CONTROL_REPO/ops/sdlc-automation`. It shares its shape with
`<orch>/specs/epic/dependency-assessment.md` and calls the flow in
`<orch>/specs/epic/wsjf-scoring.md`.

## Who calls it (the S01f question)

- **The Epic pipeline does not call this flow.** Tasks written by elaboration carry `elab_key`
  and get their `blocks` edges from elaboration (`depscore.py write-task-edges` within a Story,
  `write-all-task-edges` across Stories; see `<orch>/specs/epic/task-decomposition.md` and
  `<orch>/specs/epic/prd-to-spec.md`). `prd-to-spec` does dispatch the same agent,
  `task-dependency-mapper`, but in its other assignment (edges between Tasks of different Stories
  of one Epic), which belongs to the `prd-to-spec` spec, not here.
- **The driver does not call this flow.** Commit `64b4adbb` deleted `triggers.py`, which assessed
  each Task created outside elaboration; its commit message states "Tasks come only from
  prd-to-spec".
- **No plugin command calls it.** There is no `commands/task-dependency-assessment.md`; the only
  references are `workflows/README.md`, `skills/beads-contract/SKILL.md`,
  `scripts/shared-blocks.mjs` and `<driver>/runcost.py` (`FORMER_TRIGGER_COMPOSITES`). Today it is
  reachable only by calling the Workflow tool by name. See Open question 1.

## 1. Purpose

Assess the build dependencies of ONE Task created outside elaboration (no `elab_key`) and write its
`blocks` edges, then re-score. An edge from Task A to Task B means B cannot be built until A is
built, because B consumes something A provides (an API, an event contract, a table, an IAM grant, a
deployed resource); sharing a domain, a repository or an Epic is not an edge, and when in doubt an
edge is left out. One `task-dependency-mapper` session reads the Task, finds the Tasks that provide
what it consumes or consume what it provides, and proposes every edge to or from it with a reason
and a confidence, keeping or withdrawing (with a reason) every owned edge standing on it. Code
validates and applies the diff (only that Task's owned edges; hand-made edges untouched), then
re-derives the Story-to-Story `blocks` edges, and `wsjf-scoring` runs. With `apply: false` the diff
is a dry run and nothing is written or scored.

As with `dependency-assessment`, `meta.description` says the session runs `apply-edges`; the code
and the brief say the workflow applies. This spec follows the code.

## 2. Produces and decides

After a successful run (with `apply` true):
- The owned `blocks` edges touching the Task equal the validated proposal (added; owned ones
  stored as `tracks` converted to `blocks`; owned ones not proposed removed). Hand-made edges are
  unchanged.
- On each blocked Task touched: `seq_owned_blockers`, `seq_owned_blockers_at`, `seq_edge_reasons`
  (`{reason, confidence, setBy, setAt}` per blocker), `seq_edge_withdrawn`
  (`{reason, withdrawnBy, withdrawnAt}` per blocker).
- On the assessed Task: `seq_content_hash` (judging fingerprint at plan time), `seq_assessed_at`.
- Story order re-derived by `storyedges.story_edges` over the whole tracker: on each Story,
  `story_owned_blockers`, `story_owned_blockers_at`, `story_edge_reasons`, and the Story-to-Story
  `blocks` edges it owns. A Story whose order is contradictory is refused (not written) and named.
- `wsjf-scoring` has run over the whole portfolio. The Task gets a `wsjf` only if it sits under a
  scored Epic (value is inherited); a Task with no Epic stays unscored.
- With `apply: false`: diff and proposal in files; beads unchanged; no Story edges; no scoring.
- When the proposal does not validate: nothing is written; the result names the Task and every
  finding (`stop`).

## 3. Inputs

- Arguments: `task` (required), `repoPath` (default `$ATW_CONTROL_REPO`), `workDir`, `archPath`
  (`$ATW_ARCH_PATH`), `projectRoot` (`$ATW_PROJECT_ROOT`), `apply` (default true),
  `priorFailure` (optional).
- beads, read with descriptions: every open Task (title, description, status, `parent` lineage to
  its Epic, metadata `repoPath`, `elab_key`), every `blocks`/`tracks` edge among Tasks, the
  sequencing keys, the judging fingerprint (`beads-contract.py content_hash --scope judging`);
  Stories and their Tasks for `story_edges`.

## 4. Outputs

Files (under `<workDir>`):
- `assess-plan.json`: `depscore.assess_plan(level="task")`: `{level: "task", scope, since,
  unassessed, fingerprints: {id: sha} for every open Task without `elab_key`, summary: {level,
  scope, openTasks, candidates, unassessed, unassessedIds}}`.
- `context/task/<id>.md` (one per open Task: `# <id> — <title>\n\n<description>`),
  `context/index.md` (`- <id> | <title> | Epic: <id or none> | repo: <repoPath or unset> |
  status: <status> | file: <path>`).
- `context.json`: `assesscontext.task_context` result: `{task: {id, title, fingerprint, epic,
  repoPath, path}, standing: [{from, to, type, owned, reason, confidence, setBy, setAt}],
  withdrawn: [{from, to, reason, withdrawnBy, withdrawnAt}], corpusDir, indexPath, summary: {task,
  openTasks, standing, owned, handMade, withdrawn}}`.
- `edges.json` (agent): `{edges: [{from, to, reason, confidence, answers?}], withdrawn: [{from,
  to, reason}]}`; nothing is stamped into it. No `archCheck` at Task level.
- `edges.json.meta.json` (new, step 5): `artifactio.record` with inputs `context.json` and the
  `context/` directory, as in the Epic spec.
- `reasoning.md` (agent): what the Task consumes and provides, per-edge and per-withdrawal
  reasoning, related Tasks read, findings, uncertainty.
- `validation.json`: `edgeset.validate(level="task")` (as in the Epic spec, with `notTaskToTask`
  in place of `notEpicToEpic`; `missingArchCheck` is always empty).
- `apply-edges.json` / `apply-edges-dry-run.json`: `edgeset.apply_edges` result plus
  `storyEdges` (the `story_edges` result: `summary {added, removed, ...}`, or `{ok: false,
  error}`, or on refusal `refusedStories`, `conflicts`, `cycles`).
- `scoring/`: the `wsjf-scoring` work directory.

Bead writes: `edgeset.apply_edges` (order as in the Epic spec, edge type `blocks`), then
`storyedges.story_edges` (Story edges and `story_*` keys), then the `wsjf-scoring` writes. No vault
writes, no commits, no ledger events.

Result: as the Epic spec's, with `task` in place of `epic`, and the headline carrying the Story
edge outcome.

## 5. Steps

1. `deterministic` **Plan**: `depscore.assess_plan(graph, level="task", task=<task>)` (today
   `depscore.py assess-plan --level task --task <id> --out assess-plan.json -C <repo>`). Refuse,
   with no session, when `edgeset.scope_defect(graph, task, "task")` names a defect: not an open
   Task, or a Task elaboration wrote (`elab_key`).
2. `deterministic` **Context**: `assesscontext.task_context(graph, task, context_dir)` (today
   `depscore.py assess-context --task <id> --dir context --out context.json`).
3. `deterministic` **Reuse**: skip step 4 when `edges.json` exists and every input recorded in
   its `.meta.json` (`context.json`, the `context/` directory) hashes as recorded.
4. `agent` **Assess**: `task-dependency-mapper` (assignment: one Task created outside
   elaboration). Input paths: `context/task/<task>.md`, `context/task/`, `context/index.md`,
   `context.json`; `priorFailure` when given. Brief: THE TEST (consumes/provides; both ends are
   Tasks; when in doubt leave it out), the seven-step order the JavaScript gives, the file format,
   "do not write to beads". The session may run `depscore.py validate --edges edges.json --task
   <id>` itself. Outputs: `edges.json`, `reasoning.md`. Model `fable` (agent frontmatter), effort
   `medium` (frontmatter and JS), `maxTurns` 100. Right-sized: reading a bounded set of Task
   descriptions for consume/provide matches is narrower than the Epic test; a missing edge is
   caught only at build time (a Task built before its provider), so a capable model is kept. One
   session; nothing in parallel. It runs inside the session runner's section 2 guard
   (`driver-contract.md` §8).
5. `deterministic` **Record**: `artifactio.record` of `edges.json` with the step 3 inputs.
6. `deterministic` **Validate**: `edgeset.validate(graph, edges, task, withdrawn, "task")`.
7. `agent` **Correct** (only when step 6 is not ok, at most once): `task-dependency-mapper`, new
   session, with `validation.json` and the instruction to revise to THE TEST. Then 5 and 6 again.
8. `deterministic` **Apply**: `edgeset.apply_edges(..., item=<task>, level="task")` with the
   plan's fingerprints (today `depscore.py apply-edges --edges edges.json --plan assess-plan.json
   --task <id> [--dry-run] --out apply-edges.json`).
9. `deterministic` **Story edges**: when applied and not a dry run, reload the graph and run
   `storyedges.story_edges(graph, writer)` (today done inside `depscore.py apply-edges` for
   `--task`). A refusal is reported, not a run failure.
10. `deterministic` **Score**: when applied and not a dry run, the `wsjf-scoring` flow in-process
    with `workDir = <workDir>/scoring`.
11. `deterministic` **Result**.

Relay calls mapped: assess-plan, assess-context, validate, apply-edges (with its Story-edge pass)
become steps 1, 2, 6, 8, 9; `artifactRevision` / `authorArtifact` become steps 3 and 5; the nested
`settleWorkflow('wsjf-scoring')` becomes step 10.

Agents dispatched by the JavaScript, accounted for:
- `task-dependency-mapper`: kept, step 4 (and step 7).
- `workflow-command-runner`: dropped; replaced by direct steps.
- The `wsjf-scoring` workflow's agents: see `<orch>/specs/epic/wsjf-scoring.md`.

## 6. Checks kept / Checks dropped

**Checks kept** (in `edgeset.validate`, step 6 and again inside `apply_edges`)
- Scope refusal of a Task elaboration wrote (`elab_key`): without it this flow and elaboration
  both own that Task's edges and overwrite each other; nothing reconciles them.
- Edge outside the Task, ends not both open Tasks (`notTaskToTask`), dangling, self-edge: without
  it a `blocks` edge onto an Epic or Story or a missing bead holds the Task out of the build lane
  for good.
- Cycle against every other Task edge: without it two Tasks wait on each other and neither builds.
- Empty reason, `unaccounted`, `withdrawnNotOwned`, `keptAndWithdrawn`: as in the Epic spec.
- Ownership written before adds (`apply_edges`): as in the Epic spec.
- Story-edge refusal on contradictory order or a cycle (`story_edges` writes the difference only
  for Stories it does not refuse): without it a Story-to-Story cycle reaches beads, and the next
  `story_edges` run (from this flow or `elaboration-finish`) derives from that same contradictory
  input, so nothing later clears it.

**Checks the intent requires that the code does not enforce**
- Re-adding a withdrawn edge without `answers` (`readdsWithdrawn`) is reported but not part of
  `ok` (Open question 1 of `<orch>/specs/epic/dependency-assessment.md`).

**Checks dropped**
- `resolveArgs` / `refuseArgs`, `artifactRevision`, `authorArtifact`, relay `noResult`, and
  `score: false`: same reasons as in the Epic spec.

## 7. Failure causes

As in `<orch>/specs/epic/dependency-assessment.md` section 7, with these differences:
- Step 1 scope refusal for an `elab_key` Task: `other`; not retried; reported (the Task's edges
  are elaboration's).
- Step 9 `story_edges` fails to read the tracker (`GraphError`): recorded in `storyEdges`
  (`bd-timeout` / `contention` / `other` as for any `bd` call); the applied Task edges stand; a
  rerun of step 9 alone is reasonable for the transient causes. `elaboration-finish` also re-runs
  `story_edges`, which repairs the Story order later.
- A cycle through a hand-made Task edge goes to the owner inbox (owner fact); other validation
  failures go to the incident-responder.

## 8. Resume points

- Steps 1, 2: recomputed every run.
- Step 4 (and 7): `edges.json` + `reasoning.md`, with `edges.json.meta.json` recording
  `context.json` and the corpus and index files; unchanged recorded inputs start no session.
- Step 8: idempotent. Step 9: idempotent (writes only changed Story edges and keys). Step 10:
  resumes as `wsjf-scoring` does.
- A stable `workDir` is needed: merged question Q8 in `wsjf-scoring.md`.

## 9. Owner rules that apply

- 7.8 "Tasks with no WSJF score are never considered": via step 10. A Task created outside
  elaboration under no Epic, or under an unscored Epic, gets no `wsjf` and so is never selected by
  `selection.build_candidates`; this flow does not work around that.
- 7.8 "Unbuildable Tasks are hidden": the `blocks` edges this flow writes are what makes a Task
  wait (`selection.waiting_build`) rather than be dispatched.
- 7.4 Retries, 7.9 who gets asked, 7.11, 7.14, 7.2: as in the Epic spec.
- 7.5 (Task rerun rule) does not apply: this flow never creates or deletes a Task.

## 10. Open questions

1. **[owner] Keep or delete this flow.** It has no caller: no plugin command, no driver trigger,
   and the Epic pipeline writes its own Tasks' edges. The commit that removed the triggers says
   Tasks come only from `prd-to-spec`. If the owner never creates Tasks by hand, the flow (and the
   `task-dependency-mapper`'s second assignment, and `assess-plan --level task` /
   `assess-context --task`) can go; if the owner does, it needs a command. S08 or S15 acts on the
   answer.
2. **[owner] Orphan Tasks are never scored.** A Task with no Epic has no value to inherit and so
   never gets a `wsjf`, which keeps it out of the build lane even after this flow gives it edges.
   Is that intended, or should such a Task be refused at step 1?
- The `task-dependency-mapper`'s `fable` model: merged question Q1 in `driver-contract.md`.
- A stable work directory: merged question Q8 in `wsjf-scoring.md`.
