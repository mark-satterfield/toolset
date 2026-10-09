# Net-effect spec: `dependency-assessment`

**Status: not part of the Epic pipeline rewrite.** This flow assesses an Epic's dependencies and
re-scores Epics. Epic dependency assessment and Epic WSJF scoring belong to the future readiness
process, which is not yet built (CONTEXT 7.17; the owner's answer 6 of 2026-10-09); elaboration
assumes they are done and no Epic flow runs this one. Whether this owner-run command is kept until
the readiness process exists is the owner's concern, outside this rewrite. The rest of this file is the record
of its contract, for that decision and for the readiness process.

Source: `<plugin>/workflows/dependency-assessment.js` (`meta.description`), the plugin command
`<plugin>/commands/dependency-assessment.md`, the agent `<plugin>/agents/epic-sequencer.md` and its
skill `epic-sequencing`, `<plugin>/skills/beads-contract/SKILL.md` (sequencing keys),
`<plugin>/workflows/README.md` (Portfolio section), and, for contracts only,
`<plugin>/scripts/portfolio/depscore.py` (`assess-plan`, `assess-context`, `validate`,
`apply-edges`), `edgeset.py`, `assesscontext.py`, `prds.py`. `<driver>` is
`$ATW_CONTROL_REPO/ops/sdlc-automation`. It calls the flow in
`<orch>/specs/epic/wsjf-scoring.md`.

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
follows the code: Python applies.

## 2. Produces and decides

After a successful run (with `apply` true):
- The set of owned `tracks` edges touching the Epic equals the validated proposal: absent ones
  added (`bd dep add <blocked> <blocker> --type tracks`), owned ones stored as `blocks` converted
  to `tracks`, owned ones not proposed removed (withdrawn). Hand-made (unowned) edges are
  unchanged whatever the proposal says.
- On each blocked Epic touched: `seq_owned_blockers` (comma-separated owned blocker ids),
  `seq_owned_blockers_at`, `seq_edge_reasons` (JSON keyed by blocker:
  `{reason, confidence, setBy, setAt}`; `setAt` kept when unchanged), `seq_edge_withdrawn` (JSON
  keyed by blocker: `{reason, withdrawnBy, withdrawnAt}`; an entry is dropped when the edge is set
  again).
- On the assessed Epic: `seq_content_hash` = its judging fingerprint at plan time, and
  `seq_assessed_at`.
- `wsjf-scoring` has run over the whole portfolio (see its spec).
- No edge between two other Epics changes; no Task edge changes.
- With `apply: false`: the diff and the proposal are in files; beads unchanged; no scoring.
- When the proposal does not validate: nothing is written, and the result names the Epic and every
  finding (`stop`).

## 3. Inputs

- Arguments: `epic` (required), `repoPath` (default `$ATW_CONTROL_REPO`), `workDir`, `archPath`
  (`$ATW_ARCH_PATH`, required by the command), `projectRoot` (`$ATW_PROJECT_ROOT`), `apply`
  (default true), `priorFailure` (optional; no current caller).
- beads, read with descriptions: every open Epic (title, description = PRD, `elaboration_state`),
  every `tracks`/`blocks` edge among Epics, the sequencing keys above on each Epic, the judging
  fingerprint (`beads-contract.py content_hash --scope judging`).
- The architecture under `archPath`: arc42 views and their frontmatter (`subject`, `shows`,
  `lifecycle_state`). Only `lifecycle_state: effective` settles a decision.

## 4. Outputs

Files (under `<workDir>`):
- `assess-plan.json`: `depscore.assess_plan` result: `{level: "epic", scope, since, unassessed:
  [ids], fingerprints: {id: sha} for every open Epic, summary: {level, scope, openEpics,
  unassessed, unassessedIds}}`.
- `context/prd/<id>.md` (one per open Epic: `# <title>\n\n<description>`), `context/index.md`
  (`- <id> | <title> | elaboration: <state> | PRD: <path> | sections: <headings, max 40>`).
- `context.json`: `assesscontext.assess_context` result: `{epic: {id, title, fingerprint,
  elaborationState, prdPath}, standing: [{from, to, type, owned, reason, confidence, setBy,
  setAt}], withdrawn: [{from, to, reason, withdrawnBy, withdrawnAt}], corpusDir, indexPath,
  summary: {epic, openEpics, standing, withdrawn, owned, handMade}}`.
- `edges.json` (written by the agent): `{edges: [{from, to, reason, confidence: high|medium|low,
  archCheck, answers?}], withdrawn: [{from, to, reason}]}`; nothing is stamped into it.
- `edges.json.meta.json` (new, step 5): `artifactio.record` of `edges.json` with inputs
  `context.json` and the `context/` directory (kind `dir`): the one input-record format of every
  Epic flow.
- `reasoning.md` (written by the agent): the foundation checklist answers, per-edge and
  per-withdrawal reasoning, related PRDs read, validation findings, uncertainty.
- `validation.json`: `edgeset.validate` result: `{ok, level, edgeCount, withdrawnCount, scope,
  badScope, outsideScope, missingReason, missingArchCheck, readdsWithdrawn, unaccounted,
  withdrawnNotOwned, keptAndWithdrawn, notEpicToEpic, cycle, dangling, selfEdges, ontoClosed,
  fromClosed, duplicates}`.
- `apply-edges.json` (or `apply-edges-dry-run.json`): `edgeset.apply_edges` result: `{applied,
  dryRun, level, scope, planned, sequencedRecorded, validation, added, converted, removed,
  unchanged, withdrawn: [{from, to, reason}], reasonsRecorded, withdrawalsRecorded, plan: {add,
  convert, remove, unchanged, protectedHandMadeEdges, metadata}}`.
- `scoring/`: the `wsjf-scoring` work directory.

Bead writes: only through `edgeset.apply_edges` (section 2), in its order: ownership covering
every edge to be added first, then adds, conversions (remove then add as `tracks`), withdrawals,
final ownership with reasons and withdrawal records, then the assessed Epic's `seq_content_hash`
and `seq_assessed_at`. Then the `wsjf-scoring` writes.

No vault writes, no git commits, no ledger events.

Result: `{ok, stage: "done" | "Assess" | "Score", beadId, headline, apply, settled, workDir, epic,
assessment: {edgesPath, reasoningPath, edgeCount, withdrawnCount, valid, applySummary},
edges: {added, converted, removed, unchanged, withdrawn, applied, proposed, resultFile, edgesFile,
reasoning, reason?}, scoring: <wsjf-scoring result>, stop: {epic, findings, edgesFile,
validationFile, reasoning} | null, error?}`.

## 5. Steps

1. `deterministic` **Plan**: `depscore.assess_plan(graph, epic=<epic>, level="epic")` (today
   `depscore.py assess-plan --epic <id> --out assess-plan.json -C <repo>`). Its `fingerprints`
   are what `apply-edges` records as `seq_content_hash`. Refuse, with no session, when `<epic>` is
   not an open Epic (`edgeset.scope_defect`).
2. `deterministic` **Context**: `assesscontext.assess_context(graph, epic, context_dir)` (today
   `depscore.py assess-context --epic <id> --dir context --out context.json`). Writes the corpus,
   the index and `context.json`.
3. `deterministic` **Reuse**: if `edges.json` exists and every input recorded in its `.meta.json`
   (`context.json` and the `context/` directory) hashes as recorded, skip step 4.
4. `agent` **Assess**: `epic-sequencer`. Input paths: `context/prd/<epic>.md`, `context/prd/`,
   `context/index.md`, `context.json`, `archPath`; `priorFailure` text when given. Brief: THE
   TEST and the nine foundation layers (network and egress; identity and authorization; data
   stores and data residency; event platform; API shape; chassis and runtime; configuration and
   secrets; observability; environments), the eight-step order the JavaScript gives, the edge
   file format, "do not write to beads". The session may run `depscore.py validate --edges
   edges.json --epic <id>` itself, inside its own session, to check its file. Output files:
   `edges.json`, `reasoning.md`. Model `opus` (agent frontmatter), effort `medium` (frontmatter
   and JS), `maxTurns` 240. Opus is right: the session reads many full PRDs and makes the
   architecture judgments the edges encode, and a wrong or missing edge orders elaboration wrongly
   with nothing downstream to catch it. One session; nothing runs in parallel. It runs inside the
   session runner's section 2 guard (`driver-contract.md` §8): `epic-sequencer` holds Write and
   reads `archPath`.
5. `deterministic` **Record**: `artifactio.record` of `edges.json` with the step 3 inputs.
6. `deterministic` **Validate**: `edgeset.validate(graph, edges, epic, withdrawn, "epic")` (today
   `depscore.py validate --edges edges.json --epic <id>`). Writes `validation.json`.
7. `agent` **Correct** (only when step 6 is not ok, at most once): `epic-sequencer` again, new
   session, with `validation.json`'s path and the instruction to revise `edges.json` to THE TEST
   (drop an edge that fails it, never keep one to satisfy the validator; report a cycle through
   a hand-made edge instead of forcing it). Then steps 5 and 6 again. Same model and effort.
8. `deterministic` **Apply**: when step 6 is ok, `edgeset.apply_edges(graph, edges, writer, seen
   = assess-plan fingerprints, item=<epic>, withdrawn, level="epic")` (today `depscore.py
   apply-edges --edges edges.json --plan assess-plan.json --epic <id> [--dry-run] --out
   apply-edges.json`). It validates again against the graph as read now and writes nothing if
   that fails.
9. `deterministic` **Score**: when applied and not a dry run, run the `wsjf-scoring` flow
   in-process with `workDir = <workDir>/scoring` and the same `repoPath`, `archPath`,
   `projectRoot`.
10. `deterministic` **Result**: assemble the result (section 4); `stop` when the proposal did not
    validate after step 7.

Every `depscore.py` call the JavaScript sent through `relay.js` / `relayrun.py` /
`workflow-command-runner` (assess-plan, assess-context, validate, apply-edges) is a direct call
in steps 1, 2, 6 and 8; its `artifactRevision` and `authorArtifact` relay calls are replaced by
steps 3 and 5. The nested `settleWorkflow('wsjf-scoring')` is the in-process call in step 9.

Agents dispatched by the JavaScript, accounted for:
- `epic-sequencer`: kept, step 4 (and step 7 for the one corrective pass).
- `workflow-command-runner` (every relay call): dropped; replaced by direct steps.
- The `wsjf-scoring` workflow's agents: see `<orch>/specs/epic/wsjf-scoring.md`.

## 6. Checks kept / Checks dropped

**Checks kept** (all in `edgeset.validate`, run in step 6 and again inside `apply_edges`)
- Edge does not touch the Epic (`outsideScope`): without it one Epic's assessment rewrites edges
  between two other Epics; nothing later re-assesses them.
- Both ends are Epics (`notEpicToEpic`), no dangling id, no self-edge: without it a `tracks` edge
  onto a Task or a missing bead reaches beads and the driver holds the Epic forever.
- Cycle against every other Epic edge: without it two Epics wait on each other and neither is
  ever elaborated; nothing breaks the cycle.
- Empty reason on an edge or withdrawal: without it `seq_edge_reasons` records an edge nobody can
  later answer or withdraw on the merits.
- Owned standing edge neither kept nor withdrawn (`unaccounted`), withdrawal of an edge that is not
  owned (`withdrawnNotOwned`), both kept and withdrawn: without them a hand-made edge is removed
  or an owned one silently disappears; nothing records why.
- Closed ends are filtered out before applying: without it an edge onto a closed Epic is written.
- `apply_edges` writes ownership before adding an edge: without it a crash leaves an unowned edge
  no later assessment may withdraw.
- Hard limit: no write to arc42 section 2; this flow's own steps write nothing in the vault, and
  the session runner's guard covers the agent session.

**Checks the intent requires that the code does not enforce** (recorded, not settled: outside this rewrite, CONTEXT 7.17)
- Missing `archCheck` (`missingArchCheck`) and re-adding a withdrawn edge without `answers`
  (`readdsWithdrawn`) are reported by `validate` but are not part of `ok`, although the session's
  brief, the command text and `README.md` say they are refused.

**Checks dropped**
- `resolveArgs` / `refuseArgs` relay script: Python reads env vars directly.
- `artifactRevision` / `authorArtifact` (candidate file, schema check, publish under an input
  revision): the authoritative check is `validate` + `apply_edges`'s own re-validation; a
  malformed file fails `read_edges` and is reported. Step 3 covers the revision's resume job.
- `contextDir` and `--corpus-ready`: only the deleted triggers' "seed once, assess many" pass used
  them.
- `score: false`: only the deleted triggers passed it ("assess each, then score once"). A second
  scoring run judges nothing new (fingerprints unchanged) and only redoes the arithmetic.
- The relay `noResult` / `agent-dispatch-failed` stage: there is no runner.

## 7. Failure causes

- Steps 1, 2, 6, 8 `bd` read or write (`beadgraph.GraphError`): its `cause` field gives
  `bd-timeout`, `contention` or `other`. The field exists, but `beadgraph._bd` chooses it from
  `bd`'s standard error, which CONTEXT 7.4 does not accept as structured (QUESTIONS.md item 6). Retry reasonable for the first two with backoff (30 s doubling, cap 30
  min).
- Step 1 scope refused (not an open Epic) or `SequencingError`: `other`; not retried.
- Step 4/7 session: `api` / `quota` from the headless runner's structured result (breaker);
  retry reasonable. Returned with no `edges.json`, or an unreadable one: `other`; not retried on
  unchanged input; incident-responder.
- Step 6 not ok after the one corrective pass: `other`; not retried; the run stops with `stop`.
  When the cycle runs through a hand-made edge (`owned: false`), that is an owner fact (the owner
  made the edge): the finding goes to the owner inbox (`ownerinbox.py`, `$ATW_OWNER_INBOX`).
  Otherwise the incident-responder diagnoses.
- Step 8 refused (the graph changed between 6 and 8 and validation now fails): `contention`;
  rerun from step 1 is reasonable (the tracker moved).
- Step 9 fails: as in the `wsjf-scoring` spec; the applied edges stand; `ok` false at stage
  `Score`.
- `relay`: no producer in this flow.

## 8. Resume points

- Steps 1 and 2: recomputed every run (cheap, no session).
- Step 4 (and 7): `edges.json` + `reasoning.md`, with `edges.json.meta.json`; fingerprint =
  `context.json` and the corpus and index files under `context/` (the Epic's and every open Epic's
  PRD, the standing and withdrawn edges). A rerun with unchanged recorded inputs starts no session.
- Step 8: idempotent (`apply_edges` writes nothing for an unchanged proposal). A rerun after it
  writes nothing again.
- Step 9: resumes as `wsjf-scoring` does; after a scoring failure a rerun redoes only scoring.
- A rerun needs the same `workDir`; not designed here, the flow being outside this rewrite (CONTEXT 7.17).

## 9. Requirements that apply

- 7.17 Epic readiness: Epic dependency assessment belongs to the future readiness process; no Epic
  pipeline step runs this flow.
- 7.8 "Epics wait on unmet Epic dependencies": this flow is the producer of the `tracks` edges
  that `elabstate.unmet_blockers` reads; an edge it writes holds the blocked Epic out of
  elaboration until the blocker's `elaboration_state` is `done`. It never closes or opens an
  Epic, and it never uses "Epic closed" as a condition (7.6).
- 7.8 WSJF filter: via step 9 (see the `wsjf-scoring` spec).
- 7.4 Retries: one corrective pass with the exact findings (specific gap feedback); no rerun on
  unchanged input.
- 7.9 Who gets asked: only a cycle through the owner's hand-made edge reaches the owner.
- 7.11 Deterministic over agentic: corpus, index, fingerprints, validation and the diff are code;
  only the edge judgment is agent work.
- 7.14 Briefs: the brief states THE TEST and the files; it names no expected edge.
- 7.2: `apply: false` (`--propose`) is the owner's option; no session uses it as a rehearsal.

## 10. Open items

See QUESTIONS.md
