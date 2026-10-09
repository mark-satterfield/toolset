# Net-effect spec: `spec-authoring` (one repository's Spec set and its Story bead)

Source of intent: `workflows/spec-authoring.js` `meta.description`; agents
`agents/api-specification-author.md`, `data-model-specification-author.md`,
`acceptance-criteria-writer.md`, `user-story-writer.md`; skills `subagent-contract`,
`artifact-handoff`; CONTEXT section 7. Contracts were read from `scripts/portfolio/specui.py`
(`spec-ui-append`), `beadwrite.py` (`write_story`), `hierarchy.py` (`read_story`), `depscore.py`
(`write-story`), `<driver>/artifactio.py` (`record`, `step`, `plan`), the call site in
`workflows/prd-to-spec.js` (`specArgs`, `renderInventory`, `renderDependencies`,
`renderUiAuthority`, `authorSpecForRepo`) and the consumer `workflows/task-decomposition.js`.

Path conventions: `<art>`, `<slug>` and `<repo>` as in
`<orch>/specs/epic/prd-reconciliation.md`. `<recon>` = `<art>/recon-<slug>.json`.

## Purpose

Author the implementation-ready spec set for ONE repository of an Epic's span, from the TRD and
the approved target and delta views, specifying the change for exactly the delta items the
repository's detailing marks `add`, `modify` or `remove`: the API/OpenAPI, event and error
contracts; the data model; the acceptance criteria and Definition of Done. The contracts maker and
the data-model maker run in parallel; the criteria maker then reads their completed documents. For
a repository with `ui` work items the contracts document carries one section per item stating its
design source (`bundle`: cites the owner-supplied bundle's `spec/build-spec.md` and its Section
IDs; `cds`: designed with the CDS design system; `none`: changes no design), and the flow appends a
`## UI design sources` section built from the detailing. The saved documents decide; nothing a
maker did not save carries a decision id. One more session authors the ONE Story the Spec pairs
with (a container, single repository); the flow saves `story-<slug>.json` with its title,
description and the decision ids, records every saved document, and writes that ONE Story bead
with `depscore.py write-story`, keyed by its `elab_key`, whose full result lands in
`story-<slug>.written.json`. When the saved spec set is reusable, no session runs and only the
Story write is repeated.

## Produces and decides

After a successful run:

- `<art>/spec-<slug>.md` exists: the contracts document, one section each for `apiSpec`,
  `eventContracts`, `errorSpec`, and, when the repository has `ui` work items, one section per UI
  item headed by its id, ending with a `## UI design sources` section written by
  `spec_ui_append`. YAML frontmatter `decisionIds:` lists the architecture views it rests on.
- `<art>/spec-<slug>.data-model.md` exists: the data-model specification (stores, keys, indexes,
  item shapes per access pattern), with YAML frontmatter `decisionIds:`.
- `<art>/spec-<slug>.criteria.md` exists: `acceptanceCriteria` (given/when/then, at most 120) and
  `definitionOfDone` (true/false verifiable items, at most 30), each traced to its delta/TRD
  obligation id and source section.
- `<art>/story-<slug>.json` exists: `{title, description, decisionIds}`.
- Each of the four files has a `.meta.json` (`artifactio.record`) binding its sha256 to its
  inputs.
- A Story bead exists under the Epic with `elab_key = story:<slug>` (created, or updated when open
  and its title, description or metadata differ, or left unchanged when not open).
- `<art>/story-<slug>.written.json` holds the full `write-story` result, including
  `existingTasks` and `otherEpicTasks` (read by `task-decomposition`).
- The step `spec:<slug>` is recorded as passed in `STEPS.md` when authored in this run.
- Decided: the union of decision ids the contracts and data-model documents cite (deduplicated,
  in order).
- Returned to the caller in-process: `story` (`key` = `S<n>` from the caller, `type: "story"`,
  `id` (bead id), `elabKey`, `title`, `descriptionPath` = `<art>/story-<slug>.json#/description`,
  `repoPath`, `parentEpicKey`), `specPaths` (the three spec documents), `decisionIds`,
  `writtenPath`, `summary` `{created, updated}`, `resumed`.

## Inputs

- **Epic:** Epic bead id (`beads.epicId`), its key/title.
- **Repository:** `<repo>`; the Story key `S<n>` (the repository's index in the span, from the
  `prd-to-spec` flow).
- **Spec header:** `{id, title, summary, service?, repoPath}`; default id/title from the PRD,
  summary from the TRD's summary or "The PRD is the document at <PRD path>".
- **TRD:** `<art>/trd.md` (`trd.trdPath`) and its summary (spec: `<orch>/specs/epic/trd-authoring.md`).
- **Approved target:** `targetDir`, `deltaDir`, `architectureChange` (`none | new | partial`) from
  `<art>/architecture/target.json` (CONTEXT 7.7 three cases, same sentence as in
  `prd-reconciliation.md`).
- **Detailing:** `<recon>` (read by the makers by path) and its facts from `prd-reconciliation`:
  `work`, `idle` (`{id, status, plannedBy}`), `uiWork` (`{id, designSource, artifact, bundle,
  buildSpec, sections}`), `dependenciesCurrent`, `dependencyFindings`.
- **Access patterns:** optional list (`accessPatterns` in the `prd-to-spec` arguments; the driver
  sends none today, so the data-model maker derives them).
- **Code:** `<repo>` at `main`, read only through the detailing's evidence.
- **Beads:** read and written by `write_story` (`beadgraph.load` with descriptions, `bd create` /
  `bd update`), central database through `atw-bd` semantics.
- **Project root** (`$SKILLSPOKE_ROOT` / the resume root): artifact paths are recorded in the
  Story's metadata relative to it.

## Outputs

- **Documents** (written by the makers, one file each): `<art>/spec-<slug>.md`,
  `<art>/spec-<slug>.data-model.md`, `<art>/spec-<slug>.criteria.md` (Markdown; the first two with
  YAML frontmatter `decisionIds: [<arc42-relative view path>#<heading>, ...]`).
- **`<art>/story-<slug>.json`**: `title` (string), `description` (string), `decisionIds`
  (list of strings). Written by the flow from the story maker's result file plus the computed
  decision ids. `read_story` also honours an optional `acceptanceCriteria` list (none is written
  today).
- **`.meta.json`** beside each of the four files (`artifactio.record`, phase `spec:<slug>`).
- **`<art>/story-<slug>.written.json`** (`write_story` result): `ok`, `epic`, `story` `{id,
  elabKey, action (created|updated|unchanged), title, description, decisionIds}`,
  `existingTasks[]` (`{elabKey, title, description (first 300 chars), status}` of keyed Tasks
  under the Story), `otherEpicTasks[]` (open Tasks of other Epics built in `<repo>`), `summary`
  `{id, elabKey, action, created, updated}`.
- **Story bead** (`write_story`): type `story`; parent the Epic; title; description; acceptance
  from `story-<slug>.json` `acceptanceCriteria` (empty today); notes `repoPath: <repo>`; metadata
  `elab_key = story:<slug>`, `repoPath = <repo>`, `decision_ids` (compact JSON list, when any),
  and for each of `spec`, `spec_data_model`, `spec_criteria`, `story` whose file exists:
  `artifact_<key>_path` (relative to the project root), `artifact_<key>_meta`
  (`<path>.meta.json`), `artifact_<key>_sha256` (from the `.meta.json`). An existing open Story
  is updated in one `bd update` only where title, description or a metadata key differ.
- **`STEPS.md`**: line for step `spec:<slug>`.
- **Failure result:** `{ok: false, stage, reason, failure: {stage, cause, repositories:
  [{repository, stage, cause, headline}]}}` with stage one of `author`, `story`, `story-write`.

No vault writes, no git commits.

## Steps

1. **deterministic** — Build the brief context once (Python, no script): spec header; the
   three-case target sentence; the detailing pointer (`<recon>`) with the work ids ("specify the
   change for these items, and only these: add = new, modify = from → to, remove = removal") and
   the idle ids ("no specification for these: <id> [status by <bead>]"); when
   `dependenciesCurrent` is false, the pointer to `dependencyChanges.changeFindings` in `<recon>`;
   the UI items grouped by design source; the TRD path; the reading-scope rules (only `<repo>`, no
   fleet survey; evidence continuity; existing code is evidence, not proof; a `done` item
   contradicted by the code is reported, not silently re-specified). For the contracts and
   data-model makers, add the citation rule: cite the views read as `decisionIds` in YAML
   frontmatter; views with `lifecycle_state: effective` are settled, others are checked against
   the TRD.
2. **deterministic** — Reuse check. When step `spec:<slug>` is fresh (`artifactio.plan`; or, when
   an upstream step `trd`, `repo-scoping` or `recon:<slug>` re-ran, the recorded fingerprints of
   its four files still match), skip to step 9 with `resumed: true`. Otherwise, per document:
   a document whose `.meta.json` inputs still match is kept and its maker is not dispatched
   (finer-grained reuse, see Resume points).
3. **agent, in parallel with step 4** — `api-specification-author` (contracts maker).
   Inputs: the step 1 context; for UI items, the instruction per design source (`bundle`: specify
   by reference to the build spec and Section IDs, no new CSS/tokens; `cds`: behaviour and content,
   design from CDS; `none`: the change, no design). Output: `<art>/spec-<slug>.md`. Model `sonnet`
   (frontmatter), effort `medium` (dispatch and frontmatter). Right for contract prose; kept.
4. **agent, in parallel with step 3** — `data-model-specification-author`. Inputs: the step 1
   context and the access patterns (or "derive them"). Output: `<art>/spec-<slug>.data-model.md`.
   Model `fable` (frontmatter; the current shared `fable` block switches a recovered session to
   `opus`), effort `medium`. Kept; see Open questions on `fable`.
5. **deterministic** — Check both documents exist, are non-empty UTF-8 (today
   `jsonartifact.py --document`), then `artifactio.record` each with inputs `[<art>/trd.md,
   <art>/repo-scoping.json, <recon>, <PRD path>]` and phase `spec:<slug>`.
6. **deterministic** — When the repository has `ui` work items:
   `specui.spec_ui_append(<art>/spec-<slug>.md, <uiWork as JSON [{id, designSource, buildSpec,
   sections}]>)` (today `depscore.py spec-ui-append --doc ... --items ...`). It replaces any
   earlier `## UI design sources` section with one line per item. Then `artifactio.record` the
   contracts document again (its bytes changed).
7. **agent** — `acceptance-criteria-writer`, after steps 3 to 6. Inputs: the step 1 context
   without the citation rule, and the two completed document paths (read them, including the UI
   design sources; trace every criterion to its delta/TRD obligation id; a missing document or a
   contradiction is an unresolved input, never invented behaviour). Output:
   `<art>/spec-<slug>.criteria.md` with the two sections (at most 120 criteria, each clause under
   30 words; at most 30 DoD items). Model `sonnet` (frontmatter), effort `low` (dispatch; the
   frontmatter says `medium`). Low is right for derivation from finished documents; keep `low`.
8. **deterministic** — Check the criteria document exists and is non-empty; `artifactio.record`
   it with inputs `[<art>/trd.md, <art>/repo-scoping.json, <recon>, <PRD path>,
   <art>/spec-<slug>.md, <art>/spec-<slug>.data-model.md]`.
9. **deterministic** — Compute `decisionIds`: read the YAML frontmatter `decisionIds` of
   `spec-<slug>.md` and `spec-<slug>.data-model.md`; union, strip, deduplicate in order. (Today
   they come from the makers' accepted metadata JSON; the `meta.description` makes the saved
   documents decisive, so the documents are read.) Skipped on a reused spec set (the saved
   `story-<slug>.json` already holds them).
10. **agent** — `user-story-writer`, after step 8 (skipped on a reused spec set). Inputs: the
    three spec document paths, `<repo>`, the spec header. Task: title and description of the ONE
    Story, in terms of the spec set; a container, no task breakdown, WSJF or priority; runs no
    `bd`. Output: `<art>/story-<slug>.draft.json` `{title, description}`. Model `sonnet`
    (frontmatter), effort `low` (dispatch; frontmatter `medium`). See Open questions on whether
    this session is needed.
11. **deterministic** — Write `<art>/story-<slug>.json` = `{title, description, decisionIds}`:
    title/description from the draft when non-empty, else the default title
    `<repo basename>: <spec title or id>` and description `Spec: <art>/spec-<slug>.md`.
    `artifactio.record` it with inputs `[<art>/spec-<slug>.md, <art>/spec-<slug>.data-model.md,
    <art>/spec-<slug>.criteria.md]`. Skipped on a reused spec set.
12. **deterministic** — Write the Story bead: `beadwrite.write_story(graph, writer, <epic>, <art>,
    slug=<slug>, repo=<repo>, root=<project root>)` and save its result to
    `<art>/story-<slug>.written.json` (today `depscore.py write-story --epic <epic> --dir <art>
    --slug <slug> --repo <repo> --project-root <root> --out <art>/story-<slug>.written.json`, run
    with `-C <beads repo>`). Runs on every run, including a reused spec set, so the bead exists and
    `existingTasks`/`otherEpicTasks` are current for `task-decomposition`. Idempotent: keyed by
    `elab_key`.
13. **deterministic** — When authored in this run: `artifactio.record_step(<epic>,
    "spec:<slug>")`. Return the result.

Relay mapping (every relay call becomes a direct step): `relay.revision` (`jsonartifact.py
--source` fingerprint of inputs) → replaced by `artifactio` input fingerprints in steps 2, 5, 8,
11; `relay.author` (`jsonartifact.py --candidate/--final` probe and acceptance of
`spec-<slug>.contracts-meta.json`, `.model-meta.json`, `.criteria-meta.json`,
`story-<slug>.json` candidates under `<art>/candidates/`) → dropped for the three metadata files
(no consumer; decision ids now come from the documents, step 9) and replaced for the Story by
steps 10 and 11; `relay.documents` (`jsonartifact.py --document`) → steps 5 and 8;
`relay.record` (`<artifact script> record`) → steps 5, 6, 8, 11; `relay.depscore
spec-ui-append` → step 6; `relay.ensure` (`story-<slug>.json`) → step 11; `relay.depscore
write-story` → step 12; the composite's `acceptPhase` → step 13 and `resumeFresh` → step 2. No
`workflow-command-runner` session remains.

Agents accounted for: `api-specification-author` (kept, step 3),
`data-model-specification-author` (kept, step 4), `acceptance-criteria-writer` (kept, step 7),
`user-story-writer` (kept, step 10, see Open questions),
`agent-teams-workforce:workflow-command-runner` (dropped: every call is a deterministic step).
Not dispatched today and not added: `openapi-contract-reviewer`, `spec-decider`,
`definition-of-done-enforcer`, `prd-alignment-verifier` (see Open questions).

## Checks kept

- **Documents exist and are non-empty (steps 5 and 8).** Without it, the Story bead would be
  written with missing `artifact_spec*` metadata and `task-decomposition` would decompose from
  nothing; no later step checks the spec files before Tasks are written to beads.
- **`spec_ui_append` from the detailing, not from the maker (step 6).** Without it, a maker's
  wrong or omitted build-spec path or Section IDs would reach the Task build contracts; nothing
  later re-derives them from the detailing.
- **Story written idempotently by `elab_key` (step 12).** Without it, a rerun would create a second
  Story under the Epic (wrong output in beads), and nothing later deduplicates Stories.
- **Only open Stories are updated (`write_story`).** Without it, a rerun could rewrite a started or
  closed Story's prose and metadata; nothing restores them.
- **One repository per Story.** The Story's `repoPath` and its metadata come from the flow, never
  from a session (the agent's forbidden decisions).

**Checks dropped:**

- Candidate metadata JSON per maker (`*-meta.json`), its schema acceptance through
  `jsonartifact.py`, `artifactcontract.py` submit/checkpoint briefs, and the input "revision"
  hash: no consumer reads the metadata files (searched in `scripts/` and `<driver>`); the
  documents are decisive and `artifactio` fingerprints decide reuse.
- `uiSpec` in the contracts maker's metadata: `spec_ui_append` writes the design sources from the
  detailing, so the maker's copy is unused.
- Input refusal "no artifact directory or beads target": the Python composite always supplies
  them; a missing one raises.
- `persistErrors` collection with "recording never fails the Spec": kept as behaviour (a failed
  record is a warning), dropped as a separate result field (the warning is in the result's
  warnings).
- Returned in-memory `apiSpec`, `dataModelSpec`, `eventContracts`, `errorSpec`, `uiSpec`,
  `outOfRepoFindings: []`, `unresolvedArtifacts: []`, `note`: no consumer branches on them; the
  composite and `task-decomposition` read the documents by path.
- Relay checksum guards, relay files under `<art>/relay/spec-<slug>/`, `settleAgent`,
  `dispatchDeaths`, `dispatchOutcome` and text-matching failure classification: replaced by the
  runner's structured cause (CONTEXT 7.4).
- The `replay: true` argument: replaced by the reuse check of step 2.

## Failure causes

| Point | Cause | Retry reasonable? |
|---|---|---|
| Steps 3, 4, 7, 10: session ends on an API error | `api` | Yes, by `breaker.py`. Completed documents are kept; only the missing ones are redone. |
| Steps 3, 4, 7, 10: quota exhausted | `quota` | Yes, by `breaker.py`, same reuse. |
| Step 5 or 8: a document missing or empty after its session ended normally | `other` | One corrective re-dispatch of that maker naming the missing file is reasonable; then stage `author`, incident-responder. |
| Step 5, 6, 8, 11: `artifactio.record` fails | `other` | No. Non-fatal warning; the cost is that the next run cannot reuse that file, and the Story's `artifact_<key>_sha256` is absent for it. |
| Step 6: `SpecUiError` (items not a JSON list) | `other` | No (a programming error in the flow); stage `author`. |
| Step 10: story draft missing or empty after a normal end | none | Not a failure: step 11 uses the default title and description. |
| Step 11: `story-<slug>.json` cannot be written (`OSError`) | `other` | No; stage `story`. |
| Step 12: `write_story` raises `GraphError` with cause `bd-timeout` or `contention` | that cause | Yes: backoff from about 30 s, doubling, capped at 30 minutes (CONTEXT 7.4). Each attempt re-reads beads, so a Story an interrupted attempt created is updated, not duplicated. |
| Step 12: `write_story` raises any other `GraphError` / `bd` failure | `other` | No; stage `story-write`, incident-responder. |
| Step 13: `record_step` fails | `other` | No; non-fatal warning. |

`relay` has no producer in this flow.

## Resume points

- **R1, the whole spec set** (step `spec:<slug>`: `spec-<slug>.md`, `spec-<slug>.data-model.md`,
  `spec-<slug>.criteria.md`, `story-<slug>.json`, each with `.meta.json`). Upstream steps: `trd`,
  `repo-scoping`, `recon:<slug>`. Fingerprint inputs: `<art>/trd.md`, `<art>/repo-scoping.json`,
  `<recon>`, the PRD file (the step's recorded inputs today). When fresh, a rerun starts no session
  and runs only step 12 (the Story write) and returns.
- **R2, per document inside the step** (new; the current code reaches the same effect through its
  candidate probe for an unchanged input revision):
  - contracts and data-model documents: inputs as R1; a document whose `.meta.json` matches is
    kept, its maker is not dispatched;
  - criteria document: R1 inputs plus the two documents; redone only when one of them changed or
    it is missing;
  - `story-<slug>.json`: inputs are the three spec documents; redone (session 10 and step 11) only
    when one changed or it is missing.
- **R3, the Story bead** is never "redone": `write_story` is idempotent and always runs.
- A rerun after a crash between step 11 and step 12 reruns only step 12.

## Owner rules that apply

- **7.4 Retries:** structured causes from the runner and from `GraphError.cause`; `bd` contention
  backoff 30 s doubling to 30 minutes; one corrective re-dispatch only with the exact missing file;
  saved documents are never redone with unchanged inputs.
- **7.6 Done rule:** the Spec covers exactly the detailing's `work` ids; the Story is the
  repository's container for the Tasks that must cover every `add`/`modify`/`remove` item.
- **7.7 Three-case model:** the brief states the target case and where build items come from.
- **7.9 Who gets asked:** makers decide technical gaps; nothing goes to the owner.
- **7.10 Repositories:** one repository per Spec and Story; the makers read only `<repo>`.
- **7.11 Deterministic over agentic:** UI design sources, decision ids, the Story file and the bead
  write are code; only the four documents' prose is a session.
- **7.14 Facts, not guesses:** briefs carry paths and the item ids, not theories.
- **Hard limits:** no write to arc42 section 2; no secrets; nothing in `apps/marketing/`; no
  destructive bead operation (a Story is created or updated, never deleted).

## Open questions

1. **A repository with no work items.** When the detailing's `work` list is empty, the current
   flow still authors three documents and a Story ("no change to specify"). CONTEXT 7.6 allows a
   recorded "nothing to build" instead. Should this flow skip all sessions and record "nothing to
   build" for the repository (and write no Story)?
2. **Is the `user-story-writer` session needed?** Step 11 already has a deterministic default
   title and description. Should the Story's title/description be deterministic (CONTEXT 7.11),
   dropping one session per repository?
3. **`outOfRepoFindings`.** `user-story-writer.md` lists `outOfRepoFindings` as an output and an
   acceptance criterion, but the workflow's schema allows only `title` and `description` and
   always returns `outOfRepoFindings: []`. Keep the finding (and where does it go: owner inbox,
   incident, a new placement?) or drop it from the agent?
4. **No independent review.** `openapi-contract-reviewer` and `spec-decider` describe a maker,
   checker, decider loop for Spec Authoring, but the current workflow dispatches neither. Keep the
   flow without review, or add one review pass (with the check test applied)?
5. **Skipping makers by surface.** The contracts and data-model makers always run, even when no
   work item has a `service` or `data` surface. Skip a maker (and write a one-line "not
   applicable" document) when the detailing gives it nothing to specify?
6. **`fable` model.** `data-model-specification-author` declares `model: fable`, which the current
   shared `fable` block resolves and escalates to `opus` on recovery. What model does the Python
   runner pass for `fable` (S02)?
7. **`isolation: worktree`** in all four makers' frontmatter, while they write into `<art>` and
   read `<repo>`'s `main`. How does the Python session runner treat it (S02)?
8. **`accessPatterns` input.** The driver never sends it. Drop it, or add a producer?
9. **`write_story`'s internal retry.** `beadwrite.WRITE_BACKOFF = (2, 5)` seconds retries
   `bd-timeout`/`contention` inside the script, shorter than CONTEXT 7.4's 30 s start. Keep the
   inner retry, remove it in favour of the orchestrator's backoff, or align its values?
10. **Recorded inputs of the spec step.** The current inputs omit the target and delta directories
    and the TRD-independent architecture views the makers cite; a changed view that leaves
    `trd.md`, `repo-scoping.json` and `<recon>` unchanged would not invalidate the spec set. Add
    them?
