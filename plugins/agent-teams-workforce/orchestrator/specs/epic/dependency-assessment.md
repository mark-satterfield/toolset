# Net-effect spec: `dependency-assessment`

Failure handling: bounded transient retries and quota pauses remain. An ordinary item failure is recorded and excluded from selection for the current invocation; other eligible items continue. Setup, code, schema, and runtime type defects stop new dispatch, preserve the original diagnostic, and let current paid steps finish. Named within-step corrective passes remain bounded content work; failed runs do not dispatch repair or diagnosis agents.

**Status: not part of the Epic pipeline rewrite.** This flow assesses an Epic's dependencies and
re-scores Epics. Epic dependency assessment and Epic WSJF scoring belong to the future readiness
process, which is not yet built (CONTEXT 7.17; the owner's answer 6 of 2026-10-09); elaboration
assumes they are done and no Epic flow runs this one. Whether this owner-run command is kept until
the readiness process exists is the owner's concern, outside this rewrite. The rest of this file is the record
of its contract, for that decision and for the readiness process.

Source: `<plugin>/workflows/dependency-assessment.js` (`meta.description`), the plugin command
`<plugin>/commands/dependency-assessment.md`, the agent `<plugin>/agents/epic-sequencer.md` and its
skill `epic-sequencing`, `<plugin>/skills/beads-contract/SKILL.md` (bead metadata),
`<plugin>/workflows/README.md` (Portfolio section), and, for contracts only,
`<plugin>/scripts/portfolio/depscore.py` (`assess-plan`, `assess-context`, `validate`,
`apply-edges`), `edgeset.py`, `assesscontext.py`, and `<plugin>/bin/atw-matrix`. `<driver>` is the driver directory
the `pipeline-contracts` skill defines (`DRIVER_DIR_PARTS` under the control repository its
`CONTROL_REPO_ENV` variable names). It calls the flow in
`<orch>/specs/epic/wsjf-scoring.md`.

Bead metadata: every metadata key, key group, value vocabulary and value shape this spec names is
defined only in `<plugin>/skills/beads-contract/schemas/bead-metadata.schema.json` and is named
here by the constant `<plugin>/skills/beads-contract/scripts/bead_metadata.py` generates from it
(`KEY_*` for one key, `*_KEYS` for a key group, `ELABORATION_*` for an elaboration state). This
spec restates none of their names, values or shapes.

## Who calls it (the S01f question)

- **The Epic pipeline does not call this flow.** `prd-to-spec` neither assesses nor writes
  `tracks` edges; it consumes them (the driver holds an Epic whose blockers are unmet).
- **The driver does not call this flow.** Commit `64b4adbb` (2026-10-02) deleted `triggers.py`,
  which dispatched it for each new or changed Epic (`trigger_plan` / `trigger_dispatch` ledger
  events, now without a producer).
- **The driver depends on its output.** `elabstate.blockers` / `unmet_blockers` read an Epic's
  prerequisite edges, and `selection._epic_candidates` skips an Epic with an unmet one
  (`selection.waiting_epics`, `epic_dependency_graph` show them). The WSJF arithmetic reads the
  same `tracks` edges for an Epic's RR-OE.
- **The only caller today is the owner**, through `/agent-teams-workforce:dependency-assessment
  <epic-id> [--propose]`.

## 1. Purpose

Assess the architecture dependencies of ONE Epic and write its `tracks` edges, then re-score. An
Epic is a PRD, and an edge from Epic A to Epic B means an architecture decision B rests on should
be designed from A's requirements first, and no `effective` architecture view already settles it
(`epic-sequencing`). One `epic-sequencer` session reads the Epic's full PRD and the related PRDs,
answers the nine-layer foundation checklist, checks each decision against the effective
architecture, and proposes every edge to or from the Epic with a reason, a confidence and the
architecture view it checked, keeping or withdrawing (with a reason) every owned edge standing on
it. Code validates the proposal and applies the diff: only that Epic's owned edges change, and
hand-made edges are never touched. When the edges are applied, `wsjf-scoring` runs, because edges
decide RR-OE. With `apply: false` the diff is computed as a dry run and nothing is written or
scored.

`meta.description` says the session "runs apply-edges"; the code and the session's brief say the
opposite (the session must not write to beads; the workflow validates and applies). This spec
follows the code: the workflow applies.

## 2. Produces and decides

After a successful run (with `apply` true):
- The set of owned `tracks` edges touching the Epic equals the validated proposal: absent ones
  added (`bd dep add <blocked> <blocker> --type tracks`), owned ones stored as `blocks` converted
  to `tracks`, owned ones not proposed removed (withdrawn). Hand-made (unowned) edges are
  unchanged whatever the proposal says.
- On each blocked Epic touched: `KEY_SEQ_OWNED_BLOCKERS`, `KEY_SEQ_OWNED_BLOCKERS_AT`,
  `KEY_SEQ_EDGE_REASONS` (an entry's set time kept when unchanged) and `KEY_SEQ_EDGE_WITHDRAWN`
  (an entry is dropped when the edge is set again), each in the shape
  `skills/beads-contract/schemas/bead-metadata.schema.json` defines for that key, read and written
  through the types generated into `skills/beads-contract/scripts/bead_metadata.py`.
- On the assessed Epic: `KEY_SEQ_CONTENT_HASH` = its judging fingerprint at plan time, and
  `KEY_SEQ_ASSESSED_AT`.
- `wsjf-scoring` has run over the whole portfolio (see its spec).
- No edge between two other Epics changes; no Task edge changes.
- With `apply: false`: the diff and the proposal are in files; beads unchanged; no scoring.
- When the proposal does not validate: nothing is written, and the result names the Epic and every
  finding (`stop`).

## 3. Inputs

- Arguments: `epic` (required), `repoPath` (default: the control repository), `pluginRoot`,
  `workDir`, `archPath` (the architecture root; required by the command), `projectRoot`, `apply`
  (default true); the control repository, architecture root and project root come from the
  `CONTROL_REPO_ENV`, `ARCH_PATH_ENV` and `PROJECT_ROOT_ENV` variables of the `pipeline-contracts`
  skill. Optional, passed by no current caller: `priorFailure` (text put at the head of the
  brief), `score` (false skips the scoring step). `assess-context` reads the matrix the
  environment names and needs the PRD folder variable (`PRD_DIR_ENV`).
- beads, read with descriptions: every open Epic (title, description = PRD,
  `KEY_ELABORATION_STATE`), every `tracks`/`blocks` edge among Epics, the `SEQUENCING_KEYS` on each
  Epic, the judging
  fingerprint (`beads-contract.py content_hash --scope judging`).
- The matrix, through `atw-matrix`: the Epic's PRD path (`epic <id>`), the other Epics that reach
  what it reaches (`related --epic`), and, for what settles a decision, `find --kinds
  document,constraint,feature` then `node`. Only a document whose `lifecycle` is `effective`
  settles a decision. The related PRDs the matrix names are then read in full.

## 4. Outputs

Files (under `<workDir>`):
- `assess-plan.json`: `depscore.assess_plan` result: `{level: "epic", scope, since, unassessed:
  [ids], fingerprints: {id: sha} for every open Epic, summary: {level, scope, openEpics,
  unassessed, unassessedIds}}`.
- `context.json`: `assesscontext.assess_context` result: `epic` (with `prdPath`, the Epic's PRD
  file as the matrix names it, absolute, or null), `related` (the Epics `atw-matrix related
  --epic` returns, each with what is shared), `similar` (for an Epic no feature serves yet, other
  Epics' requirements and features that share its words), `standing: [{from, to, type, owned,
  reason, confidence, setBy, setAt}]`, `withdrawn: [{from, to, reason, withdrawnBy,
  withdrawnAt}]` and `summary`. No copy of a PRD and no index is written.
- `candidates/edges.json` (written by the agent): the proposal, `{edges: [{from, to, reason,
  confidence: high|medium|low, archCheck, answers?}], withdrawn: [{from, to, reason}]}`. Beside
  it the agent writes its progress file `candidates/edges.json.progress.json`, and
  `artifactcontract.py` writes the checkpoint `candidates/edges.json.checkpoint` from it. Both
  are defined by `skills/artifact-handoff/schemas/checkpoint.schema.json`; the checkpoint is
  bound to the candidate path, the digest of the proposal schema and the input revision (step 3).
- `edges.json`: the accepted proposal. `jsonartifact.py` checks the candidate against the
  proposal schema and publishes it in canonical JSON; nothing is stamped into it.
  `edges.json.receipt` holds `{artifactPath, sha256, bytes, schemaSha256, revision}` for the
  published bytes, `edges.json.prev` the proposal it replaced when the two differ, and
  `edges.json.publish` exists only while a publish is under way.
- `reasoning.md` (written by the agent): the foundation checklist answers, per-edge and
  per-withdrawal reasoning, related PRDs read, validation findings, uncertainty.
- `validation.json` (written by the agent's own check of its candidate, `depscore.py validate
  ... | tee validation.json`): the `edgeset.validate` result: `{ok, level, edgeCount,
  withdrawnCount, scope, badScope, outsideScope, missingReason, missingArchCheck,
  readdsWithdrawn, unaccounted, withdrawnNotOwned, keptAndWithdrawn, notEpicToEpic, cycle,
  dangling, selfEdges, ontoClosed, fromClosed, duplicates}`. The workflow's own validation of
  `edges.json` (step 7) is saved in its relay file.
- `relay/`: one numbered file per `depscore.py` command with its full result
  (`relay/<nnn>-<command>.json`), the source receipts the input revision is made from
  (`relay/assessment-inputs.json`), and the acceptance receipt (`relay/accepted-edges.json`,
  with `relay/accepted-edges.json.probe` for the reuse check).
- `apply-edges.json` (or `apply-edges-dry-run.json`): `edgeset.apply_edges` result: `{applied,
  dryRun, level, scope, planned, sequencedRecorded, validation, added, converted, removed,
  unchanged, withdrawn: [{from, to, reason}], reasonsRecorded, withdrawalsRecorded, plan: {add,
  convert, remove, unchanged, protectedHandMadeEdges, metadata}}`.
- `scoring/`: the `wsjf-scoring` work directory.

Bead writes: only through `edgeset.apply_edges` (section 2), in its order: ownership covering
every edge to be added first, then adds, conversions (remove then add as `tracks`), withdrawals,
final ownership with reasons and withdrawal records, then the assessed Epic's
`KEY_SEQ_CONTENT_HASH` and `KEY_SEQ_ASSESSED_AT`. Then the `wsjf-scoring` writes.

No vault writes, no git commits, no ledger events.

Result: `{ok, stage: "done" | "Assess" | "Score" | "args" | "agent-dispatch-failed", beadId,
headline, apply, settled, workDir, epic, assessment: {edgesPath, reasoningPath, edgeCount,
withdrawnCount, valid, saved, applySummary} | {failed: true, error?}, edges: {added, converted,
removed, unchanged, withdrawn, applied, proposed, resultFile, edgesFile, reasoning,
uncertaintyPath, reason?}, scoring: <wsjf-scoring result> | null, stop: {epic, findings,
edgesFile, validationFile, reasoning} | null, error?, dispatchFailed, dispatchFailures}`.

## 5. Steps

Each step is what `workflows/dependency-assessment.js` does. Every `depscore.py` and
`jsonartifact.py` command runs through the relay (the `relay` shared block, `relayrun.py` and a
`workflow-command-runner` session), and the script branches only on the checked copy of what the
command printed.

1. `deterministic` **Plan**: `depscore.py assess-plan --epic <id> --out assess-plan.json -C
   <repo>` (`depscore.assess_plan`). Its `fingerprints` are what `apply-edges` records as
   `KEY_SEQ_CONTENT_HASH`.
2. `deterministic` **Context**: `depscore.py assess-context --epic <id> --out
   context.json` (`assesscontext.assess_context`). Writes
   `context.json`. When step 1 or 2 fails, no session starts and the result's `edges.reason`
   says the context could not be written.
3. `deterministic` **Input revision**: `jsonartifact.py --source context.json`
   fingerprints the input (the file by its SHA-256 and size). The input revision is the SHA-256 of
   that receipt together with the Epic id and scope. When the fingerprint command fails, the
   revision is made from the path alone.
4. `deterministic` **Reuse**: `jsonartifact.py --candidate candidates/edges.json --final
   edges.json --schema-json <proposal schema> --revision <input revision> --probe --recover`.
   - `edges.json` is reused, and no session starts, when its bytes match `edges.json.receipt`
     and the receipt's `schemaSha256` and `revision` equal the current proposal schema digest and
     input revision.
   - Otherwise, when `candidates/edges.json.checkpoint` is bound to the same candidate path,
     schema digest and revision and its status is `complete`, the candidate is accepted as in
     step 6 and no session starts.
   - When that checkpoint's status is `blocked`, the run stops with the checkpoint's reason and
     its remaining items (`ARTIFACT_BLOCKED`).
   - In every other case step 5 runs.
5. `agent` **Assess**: `epic-sequencer`. The brief names `context.json` (the Epic's `prdPath`, the
   `related` and `similar` Epics, the standing and withdrawn edges) and the `atw-matrix` reads the
   session makes, carries the `priorFailure` text when given,
   and states THE TEST and the nine foundation layers (network and egress; identity and
   authorization; data stores and data residency; event platform; API shape; chassis and
   runtime; configuration and secrets; observability; environments), the eight-step order, the
   proposal format and that the session runs no command that writes to beads. It ends with the
   artifact contract data: the candidate path, the progress file path, the input revision and
   the `artifactcontract.py` commands (`validate`, `checkpoint`, `complete`, `submit`, `status`)
   bound to them. The session writes `candidates/edges.json` and `reasoning.md`, checks the
   candidate with `depscore.py validate --edges candidates/edges.json --epic <id> | tee
   validation.json` and revises it until `ok` is true or it records why it cannot be. Model
   `opus` (agent frontmatter), effort `medium` (frontmatter and JS), `maxTurns` 240. One session;
   nothing runs in parallel.
6. `deterministic` **Accept**: the step 4 command without `--probe`. `jsonartifact.py` checks
   the candidate against the proposal schema and publishes it as `edges.json` with
   `edges.json.receipt` (section 4), and reports the counts of `edges` and `withdrawn`. A
   candidate that fails the schema is not published and the run ends at stage `Assess` with
   nothing written to beads.
7. `deterministic` **Validate**: `depscore.py validate --edges edges.json --epic <id>`
   (`edgeset.validate`); its result is saved in its relay file. An Epic id that is not an open
   Epic is refused here (`badScope`). When the result is not `ok`, nothing is applied, the result
   carries `stop`, and the workflow starts no second session.
8. `deterministic` **Apply**: when step 7 is ok, `depscore.py apply-edges --edges edges.json
   --plan assess-plan.json --epic <id> [--dry-run] --out apply-edges.json`
   (`edgeset.apply_edges`). It validates again against the graph as read now and writes nothing
   if that fails. The proposal's `decisions` (`{decision, relationship, entry, heading}`) are then
   recorded in the matrix, one `atw-matrix link drives|restsOn` from the Epic to the feature or
   document heading for each, as role `script`; the result's `matrix` holds `{decisions, recorded,
   failures}`. The Epic-to-Epic edge stays a beads `tracks` edge.
9. `deterministic` **Score**: when the edges were applied, the run is not a dry run and `score`
   is not false, the workflow calls the `wsjf-scoring` workflow with `workDir =
   <workDir>/scoring` and the same `repoPath`, `pluginRoot`, `archPath` and `projectRoot`.
10. `deterministic` **Result**: assemble the result (section 4).

Agents the workflow dispatches:
- `epic-sequencer`: step 5, at most one session a run.
- `workflow-command-runner`: one session for each relay call of steps 1 to 4 and 6 to 8.
- The `wsjf-scoring` workflow's agents: see `<orch>/specs/epic/wsjf-scoring.md`.

## 6. Checks

**In `edgeset.validate`** (run in step 7 and again inside `apply_edges`)
- Edge does not touch the Epic (`outsideScope`): without it one Epic's assessment rewrites edges
  between two other Epics; nothing later re-assesses them.
- Both ends are Epics (`notEpicToEpic`), no dangling id, no self-edge: without it a `tracks` edge
  onto a Task or a missing bead reaches beads and the driver holds the Epic forever.
- Cycle against every other Epic edge: without it two Epics wait on each other and neither is
  ever elaborated; nothing breaks the cycle.
- Empty reason on an edge or withdrawal: without it `KEY_SEQ_EDGE_REASONS` records an edge nobody can
  later answer or withdraw on the merits.
- Owned standing edge neither kept nor withdrawn (`unaccounted`), withdrawal of an edge that is not
  owned (`withdrawnNotOwned`), both kept and withdrawn: without them a hand-made edge is removed
  or an owned one silently disappears; nothing records why.
- Closed ends are filtered out before applying: without it an edge onto a closed Epic is written.
- `apply_edges` writes ownership before adding an edge: without it a crash leaves an unowned edge
  no later assessment may withdraw.

**In `jsonartifact.py`** (steps 4 and 6)
- The candidate is valid against the proposal schema before it becomes `edges.json`.
- `edges.json` is read as accepted only when its bytes match `edges.json.receipt`.
- An accepted `edges.json` is reused only for the same proposal schema digest and the same input
  revision, so a change to `context.json` starts a
  new session.

**Checks the intent requires that the code does not enforce** (recorded, not settled: outside this rewrite, CONTEXT 7.17)
- Missing `archCheck` (`missingArchCheck`) and re-adding a withdrawn edge without `answers`
  (`readdsWithdrawn`) are reported by `validate` but are not part of `ok`, although the session's
  brief, the command text and `README.md` say they are refused.
- The workflow itself guards no write to arc42 section 2: its own steps write nothing in the
  vault, and the `epic-sequencer` session holds Write and reads `archPath`.

## 7. Failure causes

- Steps 1, 2, 7, 8 `bd` read or write (`beadgraph.GraphError`): its `cause` field gives
  `bd-timeout`, `contention` or `other`. The field exists, but `beadgraph._bd` chooses it from
  `bd`'s standard error, which CONTEXT 7.4 does not accept as structured (QUESTIONS.md item 6).
  The workflow does not retry the command; the run ends at stage `Assess` with the error in
  `edges.reason`.
- A relay call whose runner session returns nothing: stage `agent-dispatch-failed`, with the
  dispatch named in `dispatchFailures`.
- Step 5 session: a transient dispatch failure is retried by the bounded dispatch policy inside
  the workflow; a dispatch interruption ends the run as `paused` and `resumable`. A session that returns with no candidate, or with one that fails the schema: stage
  `Assess`; the tracker keeps its current edges.
- Step 7 not ok: the run stops with `stop`, naming the Epic and every finding. A cycle through a
  hand-made edge (`owned: false`) is among those findings and in the reasoning document; the
  owner corrects the edge or the PRD and assesses the Epic again.
- Step 8 refused (the graph changed between 7 and 8 and validation now fails): stage `Assess`
  with the findings in `stop`; a rerun reads the tracker again.
- Step 9 fails: as in the `wsjf-scoring` spec; the applied edges stand; `ok` false at stage
  `Score`.

## 8. Resume points

- Steps 1 to 3: recomputed every run (no `epic-sequencer` session).
- Step 5: saved as `edges.json` with `edges.json.receipt`. A rerun in the same `workDir` starts
  no session when the input revision is unchanged, that is when `context.json` has
  the same bytes (the Epic's PRD path, the related and similar Epics, the
  index, the standing and withdrawn edges). A session that was interrupted leaves
  `candidates/edges.json` with its progress file and checkpoint; a rerun with the same input
  revision accepts a checkpoint marked `complete` without a session, and otherwise starts a
  session that continues those files.
- Step 8: idempotent (`apply_edges` writes nothing for an unchanged proposal). A rerun after it
  writes nothing again.
- Step 9: resumes as `wsjf-scoring` does; after a scoring failure a rerun redoes only scoring.
- A rerun resumes only with the same `workDir`. The command gives every run a new one
  (`<repo>/.claude/workflow-runs/dependency-assessment/<UTC time>`), so a run the command starts
  begins at step 1 with nothing saved.

## 9. Requirements that apply

- 7.17 Epic readiness: Epic dependency assessment belongs to the future readiness process; no Epic
  pipeline step runs this flow.
- 7.8 "Epics wait on unmet Epic dependencies": this flow is the producer of the `tracks` edges
  that `elabstate.unmet_blockers` reads; an edge it writes holds the blocked Epic out of
  elaboration until the blocker's `KEY_ELABORATION_STATE` is `ELABORATION_DONE`. It never closes or opens an
  Epic, and it never uses "Epic closed" as a condition (7.6).
- 7.8 WSJF filter: via step 9 (see the `wsjf-scoring` spec).
- 7.4 Retries: the session checks its own candidate with `validate` and revises it before it
  returns; the workflow starts no second session on unchanged input.
- 7.9 Who gets asked: only a cycle through the owner's hand-made edge reaches the owner.
- 7.11 Deterministic over agentic: the matrix reads, fingerprints, validation and the diff are code;
  only the edge judgment is agent work.
- 7.14 Briefs: the brief states THE TEST and the files; it names no expected edge.
- 7.2: `apply: false` (`--propose`) is the owner's option; no session uses it as a rehearsal.

## 10. Open items

See QUESTIONS.md
