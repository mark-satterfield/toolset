# Net-effect spec: `task-dependency-assessment`

Failure handling: bounded transient retries and quota pauses remain. An ordinary item failure is recorded and excluded from selection for the current invocation; other eligible items continue. Setup, code, schema, and runtime type defects stop new dispatch, preserve the original diagnostic, and let current paid steps finish. Named within-step corrective passes remain bounded content work; failed runs do not dispatch repair or diagnosis agents.

**Status: to be deleted in S08; not rewritten.** It assesses a Task created outside elaboration,
and no such Task legitimately exists: every Task is created by elaboration under a Story of an
Epic (CONTEXT 7.16; the owner's answers 7 and 8 of 2026-10-09). Elaboration sets every Task's
edges itself (`task-decomposition.md`, and the Task edges steps of `prd-to-spec.md`). S08 deletes
`task-dependency-assessment.js` unconditionally (PLAN S08), together with the
`task-dependency-mapper`'s second assignment and `assess-plan --level task` / `assess-context
--task` when nothing else uses them. This file stays only as the record of what is deleted.

Source: `<plugin>/workflows/task-dependency-assessment.js` (`meta.description`), the agent
`<plugin>/agents/task-dependency-mapper.md`, `<plugin>/skills/beads-contract/SKILL.md` (bead
metadata), `<plugin>/workflows/README.md` (Portfolio section), and, for contracts only,
`<plugin>/scripts/portfolio/depscore.py` (`assess-plan --level task`, `assess-context --task`,
`validate --task`, `apply-edges --task`), `edgeset.py`, `assesscontext.py` (`task_context`) and
`storyedges.py`. `<driver>` is the driver directory the `pipeline-contracts` skill defines
(`DRIVER_DIR_PARTS` under the control repository its `CONTROL_REPO_ENV` variable names). It shares
its shape with
`<orch>/specs/epic/dependency-assessment.md` and calls the flow in
`<orch>/specs/epic/wsjf-scoring.md`.

Bead metadata: every metadata key, key group and value shape this spec names is defined only in
`<plugin>/skills/beads-contract/schemas/bead-metadata.schema.json` and is named here by the
constant `<plugin>/skills/beads-contract/scripts/bead_metadata.py` generates from it (`KEY_*` for
one key, `*_KEYS` for a key group). This spec restates none of their names or shapes.

## Who calls it (the S01f question)

- **The Epic pipeline does not call this flow.** Tasks written by elaboration carry
  `KEY_ELAB_KEY` and get their `blocks` edges from elaboration (the step `beadwrite.write_task` within a Story,
  the step `beadwrite.write_all_task_edges` across Stories; see `<orch>/specs/epic/task-decomposition.md` and
  `<orch>/specs/epic/prd-to-spec.md`). `prd-to-spec` does dispatch the same agent,
  `task-dependency-mapper`, but in its other assignment (edges between Tasks of different Stories
  of one Epic), which belongs to the `prd-to-spec` spec, not here.
- **The driver does not call this flow.** Commit `64b4adbb` deleted `triggers.py`, which assessed
  each Task created outside elaboration; its commit message states "Tasks come only from
  prd-to-spec".
- **No plugin command calls it.** There is no `commands/task-dependency-assessment.md`; the only
  references are `workflows/README.md`, `skills/beads-contract/SKILL.md`,
  `scripts/shared-blocks.mjs` and `<driver>/runcost.py` (`FORMER_TRIGGER_COMPOSITES`). Today it is
  reachable only by calling the Workflow tool by name.

## 1. Purpose

Assess the build dependencies of ONE Task created outside elaboration (no `KEY_ELAB_KEY`) and write its
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
- On each blocked Task touched: `KEY_SEQ_OWNED_BLOCKERS`, `KEY_SEQ_OWNED_BLOCKERS_AT`,
  `KEY_SEQ_EDGE_REASONS` and `KEY_SEQ_EDGE_WITHDRAWN`, each in the shape the schema defines.
- On the assessed Task: `KEY_SEQ_CONTENT_HASH` (judging fingerprint at plan time),
  `KEY_SEQ_ASSESSED_AT`.
- Story order re-derived by `storyedges.story_edges` over the whole tracker: on each Story,
  `KEY_STORY_OWNED_BLOCKERS`, `KEY_STORY_OWNED_BLOCKERS_AT`, `KEY_STORY_EDGE_REASONS`, and the
  Story-to-Story `blocks` edges it owns. A Story whose order is contradictory is refused (not
  written) and named.
- `wsjf-scoring` has run over the whole portfolio. The Task gets a `KEY_WSJF` value only if it sits
  under a scored Epic (value is inherited); a Task with no Epic stays unscored.
- With `apply: false`: diff and proposal in files; beads unchanged; no Story edges; no scoring.
- When the proposal does not validate: nothing is written; the result names the Task and every
  finding (`stop`).

## 3. Inputs

- Arguments: `task` (required), `repoPath` (default: the control repository), `pluginRoot`,
  `workDir`, `archPath` (the architecture root), `projectRoot`, `apply` (default true),
  `priorFailure` (optional text put at the head of the brief), `score` (optional; false skips
  the scoring step). The control repository, architecture root and project root come from the
  `CONTROL_REPO_ENV`, `ARCH_PATH_ENV` and `PROJECT_ROOT_ENV` variables of the `pipeline-contracts`
  skill.
- beads, read with descriptions: every open Task (title, description, status, `parent` lineage to
  its Epic, metadata `KEY_REPO_PATH`, `KEY_ELAB_KEY`), every `blocks`/`tracks` edge among Tasks,
  the `SEQUENCING_KEYS`, the judging fingerprint (`beads-contract.py content_hash --scope judging`);
  Stories and their Tasks for `story_edges`.

## 4. Outputs

Files (under `<workDir>`):
- `assess-plan.json`: `depscore.assess_plan(level="task")`: `{level: "task", scope, since,
  unassessed, fingerprints: {id: sha} for every open Task without `KEY_ELAB_KEY`, summary: {level,
  scope, openTasks, candidates, unassessed, unassessedIds}}`.
- `context.json`: `assesscontext.task_context` result: `task` (with `elements`, the matrix ids
  the Task states, its `stacks`, and `unmatched`, the ids the matrix does not hold), `stacks`
  (for each stack the Task states: `work`, the open Tasks that touch it as `atw-matrix work --id`
  returns them, `dependsOn` and `dependents`, as `atw-matrix deps --of` and `deps --on` return
  them), `standing: [{from, to, type, owned, reason, confidence, setBy, setAt}]`, `withdrawn:
  [{from, to, reason, withdrawnBy, withdrawnAt}]` and `summary`. No copy of a Task and no index
  is written.
- `candidates/edges.json` (agent): the proposal, `{edges: [{from, to, reason, confidence,
  answers?}], withdrawn: [{from, to, reason}], elements: [matrix ids], stackDependencies:
  [{kind, from, to, through, interface, reason}]}`. No `archCheck` at Task level. Beside it the
  agent's progress file `candidates/edges.json.progress.json` and the checkpoint
  `candidates/edges.json.checkpoint` that `artifactcontract.py` writes from it, as in the Epic
  spec.
- `edges.json`: the accepted proposal, published by `jsonartifact.py` in canonical JSON with
  `edges.json.receipt` (`{artifactPath, sha256, bytes, schemaSha256, revision}`),
  `edges.json.prev` and, during a publish, `edges.json.publish`, as in the Epic spec; nothing is
  stamped into it.
- `reasoning.md` (agent): what the Task consumes and provides, per-edge and per-withdrawal
  reasoning, related Tasks read, findings, uncertainty.
- `validation.json` (written by the agent's own check of its candidate): the
  `edgeset.validate(level="task")` result (as in the Epic spec, with `notTaskToTask` in place of
  `notEpicToEpic`; `missingArchCheck` is always empty). The workflow's own validation of
  `edges.json` is saved in its relay file.
- `relay/`: as in the Epic spec.
- `apply-edges.json` / `apply-edges-dry-run.json`: `edgeset.apply_edges` result plus
  `storyEdges` (the `story_edges` result: `summary {added, removed, ...}`, or `{ok: false,
  error}`, or on refusal `refusedStories`, `conflicts`, `cycles`).
- `scoring/`: the `wsjf-scoring` work directory.

Bead writes: `edgeset.apply_edges` (order as in the Epic spec, edge type `blocks`), then
`storyedges.story_edges` (Story edges and `KEY_STORY_OWNED_BLOCKERS`,
`KEY_STORY_OWNED_BLOCKERS_AT`, `KEY_STORY_EDGE_REASONS`), then the `wsjf-scoring`
writes. The proposal's `elements` are written into the Task's `matrix_elements` key
(`beads-contract.py metadata set`) only when the Task states none. No matrix writes: the
mapper's edges and `stackDependencies` are never written into the matrix, whose architecture
side only arc42 (through `sync-documents`) and the architect's recorded design write; the beads
edge alone carries build order. No vault writes, no commits, no ledger events.

Result: as the Epic spec's, with `task` in place of `epic`, and the headline carrying the Story
edge outcome.

## 5. Steps

Each step is what `workflows/task-dependency-assessment.js` does. Every `depscore.py` and
`jsonartifact.py` command runs through the relay, as in the Epic spec.

1. `deterministic` **Plan**: `depscore.py assess-plan --level task --task <id> --out
   assess-plan.json -C <repo>` (`depscore.assess_plan`).
2. `deterministic` **Context**: `depscore.py assess-context --task <id> --out
   context.json` (`assesscontext.task_context`), which reads the matrix the environment names.
   When step 1 or 2 fails, no session starts.
3. `deterministic` **Input revision**: `jsonartifact.py --source context.json`
   fingerprints the input; the input revision is the SHA-256 of that receipt together
   with the Task id and scope, as in the Epic spec.
4. `deterministic` **Reuse**: `jsonartifact.py --candidate candidates/edges.json --final
   edges.json --schema-json <proposal schema> --revision <input revision> --probe --recover`,
   with the four outcomes of the Epic spec's step 4: an accepted `edges.json` with the same
   schema digest and input revision is reused and no session starts; a candidate whose
   checkpoint is `complete` under the same binding is accepted with no session; a `blocked`
   checkpoint stops the run; otherwise step 5 runs.
5. `agent` **Assess**: `task-dependency-mapper` (assignment: one Task created outside
   elaboration). The brief names `context.json` (the Task's stated ids and, for each of its
   stacks, the open Tasks that touch it and what it depends on and what depends on it), carries
   `priorFailure` when given, and states THE TEST (consumes or
   provides; both ends are Tasks; when in doubt leave it out), the seven-step order, the proposal
   format and that the session runs no command that writes to beads. It ends with the artifact
   contract data, as in the Epic spec. The session writes `candidates/edges.json` and
   `reasoning.md`, and checks the candidate with `depscore.py validate --edges
   candidates/edges.json --task <id> | tee validation.json`, revising it until `ok` is true or
   it records why it cannot be. Model `fable` (agent frontmatter), effort `medium` (frontmatter
   and JS), `maxTurns` 100. One session; nothing in parallel.
6. `deterministic` **Accept**: the step 4 command without `--probe`; the candidate is checked
   against the proposal schema and published as `edges.json` with its receipt.
7. `deterministic` **Validate**: `depscore.py validate --edges edges.json --task <id>`
   (`edgeset.validate` at level `task`); its result is saved in its relay file. A Task that is
   not open, or that elaboration wrote (`KEY_ELAB_KEY`), is refused here (`badScope`). When the
   result is not `ok`, nothing is applied, the result carries `stop`, and the workflow starts no
   second session.
8. `deterministic` **Apply and Story edges**: when step 7 is ok, `depscore.py apply-edges --edges
   edges.json --plan assess-plan.json --task <id> [--dry-run] --out apply-edges.json`
   (`edgeset.apply_edges`), which for `--task` also re-derives the Story-to-Story edges
   (`storyedges.story_edges`) and reports them as `storyEdges`. A Story edge refusal is
   reported in the headline and is not a run failure.
9. `deterministic` **Score**: when the edges were applied, the run is not a dry run and `score`
   is not false, the workflow calls the `wsjf-scoring` workflow with `workDir =
   <workDir>/scoring`.
10. `deterministic` **Result**.

Agents the workflow dispatches:
- `task-dependency-mapper`: step 5, at most one session a run.
- `workflow-command-runner`: one session for each relay call of steps 1 to 4 and 6 to 8.
- The `wsjf-scoring` workflow's agents: see `<orch>/specs/epic/wsjf-scoring.md`.

## 6. Checks

**In `edgeset.validate`** (step 7 and again inside `apply_edges`)
- Scope refusal of a Task elaboration wrote (`KEY_ELAB_KEY`): without it this flow and elaboration
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

**In `jsonartifact.py`** (steps 4 and 6): the schema check, the receipt check and the reuse
condition of the Epic spec.

**Checks the intent requires that the code does not enforce**
- Re-adding a withdrawn edge without `answers` (`readdsWithdrawn`) is reported but not part of
  `ok`. Not settled: the flow is deleted in S08.

## 7. Failure causes

As in `<orch>/specs/epic/dependency-assessment.md` section 7, with these differences:
- Step 7 scope refusal for a `KEY_ELAB_KEY` Task: the run stops with `stop` (the Task's edges
  are elaboration's).
- Step 8 `story_edges` fails to read the tracker (`GraphError`): recorded in `storyEdges`
  (`bd-timeout` / `contention` / `other` as for any `bd` call); the applied Task edges stand.
  `elaboration-finish` also re-runs `story_edges`, which repairs the Story order later.
- A cycle through a hand-made Task edge is among the findings in `stop` and in the reasoning
  document.

## 8. Resume points

- Steps 1 to 3: recomputed every run.
- Step 5: saved as `edges.json` with `edges.json.receipt`. A rerun in the same `workDir` starts
  no session when the input revision is unchanged, that is when `context.json` and every file
  under `context/` have the same bytes. An interrupted session's candidate, progress file and
  checkpoint are continued as in the Epic spec.
- Step 8: idempotent; the Story edge pass writes only changed Story edges and keys. Step 9:
  resumes as `wsjf-scoring` does.
- A rerun resumes only with the same `workDir`; no command starts this workflow, so the caller
  of the Workflow tool chooses it.

## 9. Requirements that apply

- 7.16 Hierarchy and sources of work: every Task is created by elaboration, so this flow has no
  input to assess; it is deleted in S08 and not rewritten.
- 7.8 "Tasks with no WSJF score are never considered": via step 9. A Task created outside
  elaboration under no Epic, or under an unscored Epic, gets no `KEY_WSJF` value and so is never selected by
  `selection.build_candidates`; this flow does not work around that.
- 7.8 "Unbuildable Tasks are hidden": the `blocks` edges this flow writes are what makes a Task
  wait (`selection.waiting_build`) rather than be dispatched.
- 7.4 Retries, 7.9 who gets asked, 7.11, 7.14, 7.2: as in the Epic spec.
- 7.5 (Task rerun rule) does not apply: this flow never creates or deletes a Task.

## 10. Open items

See QUESTIONS.md
