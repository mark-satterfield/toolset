# Net-effect spec: `spec-authoring` (one repository's Spec set and its Story bead)

Source of intent: `workflows/spec-authoring.js` `meta.description`; agents
`agents/api-specification-author.md`, `data-model-specification-author.md`,
`acceptance-criteria-writer.md`, `user-story-writer.md`; skills `subagent-contract`,
`artifact-handoff`; CONTEXT section 7. Contracts were read from `scripts/portfolio/specui.py`
(`spec-ui-append`), `cdsbundles.py` (`list_bundles`, `bundle_problem`), `beadwrite.py`
(`write_story`), `hierarchy.py` (`read_story`), `depscore.py` (`write-story`, `cds-bundles`),
`<driver>/artifactio.py` (`record`, `step`, `plan`), `<driver>/workitems.py`
(`design_system_args`), the call site in `workflows/prd-to-spec.js` (`specArgs`,
`renderInventory`, `renderUiAuthority`, `authorSpecForRepo`) and the consumer
`workflows/task-decomposition.js`.

Path conventions:
- `<art>` = the Epic's artifact directory,
  `$ATW_CONTROL_REPO/.claude/workflow-runs/artifacts/<epic-key>/` (the epic key is the Epic bead id
  with characters outside `[A-Za-z0-9._-]` replaced by `_`).
- `<slug>` = the repository's artifact slug: the repository path's basename with characters outside
  `[A-Za-z0-9._-]` replaced by `_`, suffixed `-2`, `-3`, ... when two span repositories share a
  basename (assigned once per run, in span order, by the `prd-to-spec` flow).
- `<repo>` = the absolute path of the one repository.
- "placed items" = the build items `repo-scoping` placed in `<repo>`: the `itemIds` of every
  `placements[]` entry of `<art>/repo-scoping.json` whose `repoPath` is `<repo>`, joined to
  `<art>/delta-items.json` for each item's `element`, `views` and, for a prerequisite, `kind` and
  `requiredBy`.

## 1. Purpose

Author the implementation-ready spec set for ONE repository of an Epic's span, from the PRD, the
TRD and the approved target and delta views, for every placed item of that repository. The spec set
says what to build in this repository and how, for each placed item; it records no judgment of
whether code for an item already exists or already meets anything (CONTEXT 7.23): the build
pipeline's tests decide that (CONTEXT 7.19). Every span repository gets a spec set and a Story;
there is no "nothing to build" case (CONTEXT 7.6). The spec set covers: the API/OpenAPI, event and
error contracts; the data model; the acceptance criteria and Definition of Done. The contracts
maker and the data-model maker run in parallel; the criteria maker then reads their completed
documents. For a repository that holds UI (`frontend: true` in its placement), the contracts maker
also gives each UI item its design source (`bundle`: the owner supplied a single-artifact cds bundle
that packages it, and the spec cites that bundle's `spec/build-spec.md` and its Section IDs; `cds`:
it changes design and no bundle packages it, so it is designed with the CDS design system; `none`:
it changes no design), and the flow checks those choices against the supplied bundles and appends a
`## UI design sources` section from the checked result. The saved documents decide; nothing a maker
did not save carries a decision id. One more session authors the ONE Story the Spec pairs with (a
container, single repository); the flow saves `story-<slug>.json` with its title, description and
the decision ids, records every saved document, and writes that ONE Story bead with
`depscore.py write-story`, keyed by its `elab_key`. (The `meta.description` also has the write's
full result land in `story-<slug>.written.json`; its only reader was `task-decomposition.js`, and
the Python `task-decomposition` reads beads itself, so the file is dropped.) When the saved spec
set is reusable, no session runs and only the Story write is repeated.

## 2. Produces and decides

After a successful run:

- `<art>/spec-<slug>.md` exists: the contracts document, one section each for `apiSpec`,
  `eventContracts`, `errorSpec`, and, when the repository holds UI items, one section per UI item
  headed by its id, ending with a `## UI design sources` section written by `spec_ui_append`.
  YAML frontmatter `decisionIds:` lists the architecture views it rests on; every entry resolves to
  a file under `$ATW_ARCH_PATH` (step 5).
- `<art>/spec-<slug>.data-model.md` exists: the data-model specification (stores, keys, indexes,
  item shapes per access pattern), with YAML frontmatter `decisionIds:` (checked the same way).
- `<art>/spec-<slug>.criteria.md` exists: `acceptanceCriteria` (given/when/then, at most 120) and
  `definitionOfDone` (true/false verifiable items, at most 30), each traced to its delta/TRD
  obligation id and source section.
- `<art>/spec-<slug>.ui.json` exists when the repository holds UI items: the checked UI design
  sources (shape under Outputs).
- `<art>/story-<slug>.json` exists: `{title, description, decisionIds}`.
- Each of these files has a `.meta.json` (`artifactio.record`) binding its sha256 to its inputs.
- A Story bead exists under the Epic with `elab_key = story:<slug>` (created, or updated when open
  and its title, description or metadata differ, or left unchanged when not open).
- The step `spec:<slug>` is recorded as passed in `STEPS.md` when authored in this run.
- Decided: every placed item is specified (what to build and how), and every UI item has one design
  source in `bundle | cds | none`, an artifact (`{kind, slug}` as a `bundle.json` names it) for
  `bundle` and `cds`, and for `bundle` the bundle directory, its build spec and the Section IDs it
  builds.
- Decided: the union of decision ids the contracts and data-model documents cite (deduplicated,
  in order).
- Returned to the caller in-process: `story` (`key` = `S<n>` from the caller, `type: "story"`,
  `id` (bead id), `elabKey`, `title`, `descriptionPath` = `<art>/story-<slug>.json#/description`,
  `repoPath`, `parentEpicKey`), `specPaths` (the three spec documents as absolute paths; the
  composite hands exactly these to `task-decomposition` as `specPaths`, which computes their
  cite-as refs itself), `uiPath` (`<art>/spec-<slug>.ui.json`, or null), `decisionIds`,
  `summary` `{created, updated}`, `resumed`.

## 3. Inputs

- **Epic:** Epic bead id (`beads.epicId`), its key/title.
- **Repository:** `<repo>`; the Story key `S<n>` (the repository's index in the span, from the
  `prd-to-spec` flow); `frontend` from its placement in `<art>/repo-scoping.json`.
- **Spec header:** `{id, title, summary, service?, repoPath}`; id and title from the PRD, summary
  "The PRD is the document at <PRD path>".
- **PRD:** the PRD file, by path.
- **TRD:** `<art>/trd.md`, by path only; its summary is a section of the file, which the makers
  read (spec: `<orch>/specs/epic/trd-authoring.md`).
- **Approved target:** `targetDir`, `deltaDir`, `architectureChange` (`none | new | partial`) from
  `<art>/architecture/target.json` (spec: `architecture.md`). The three cases (CONTEXT 7.7):
  `partial` = target views plus a delta folder of the change only; `new` = target views that are
  both future and delta, no delta folder; `none` = one set (the effective views the target's
  `baseline.json` cites in `entries[].documents`), no delta; build work is the gaps
  (`implementationWork` in `baseline.json`: the elements the element status matrix does not show
  as built) and the prerequisites in `closure.json`.
- **Placed items:** from `<art>/repo-scoping.json` and `<art>/delta-items.json` (see Path
  conventions).
- **Design system** (only when `frontend`), from the driver (`<driver>/workitems.py`
  `design_system_args`): `packagesDir` = `$ATW_DESIGN_PACKAGES_DIR` (default
  `docs/product/product-design/ui-design/design-packages/` in the `skillspoke-docs` vault);
  `mocksDir` = `$CUSTOMIZABLE_DESIGN_SYSTEM_MOCKS_DIR`; `shellsDir` =
  `$CUSTOMIZABLE_DESIGN_SYSTEM_SHELLS_DIR`. Each bundle is a directory with `bundle.json`
  `{kind: page|shell|view, slug, shell, created_at, build_spec}`, `spec/build-spec.md`,
  `design/<kind>.html`, `styles/`.
- **Access patterns:** optional list (`accessPatterns` in the `prd-to-spec` arguments; the driver
  sends none today, so the data-model maker derives them).
- **Beads:** read and written by `write_story` (`beadgraph.load` with descriptions, `bd create` /
  `bd update`), central database through `atw-bd` semantics.
- **Project root** (`$SKILLSPOKE_ROOT` / the resume root): artifact paths are recorded in the
  Story's metadata relative to it.

No repository code is compared with the placed items (CONTEXT 7.23).

## 4. Outputs

- **Documents** (written by the makers, one file each): `<art>/spec-<slug>.md`,
  `<art>/spec-<slug>.data-model.md`, `<art>/spec-<slug>.criteria.md` (Markdown; the first two with
  YAML frontmatter `decisionIds: [<arc42-relative view path>#<heading>, ...]`).
- **`<art>/spec-<slug>.bundles.json`** (step 2b, only for a UI repository): the supplied bundles
  `cdsbundles.list_bundles(packagesDir)` lists, for the contracts maker to read by path.
- **`<art>/candidates/spec-<slug>.ui.json`** (written by the contracts maker, only for a UI
  repository): `uiItems[]` (`{item, designSource, reason, artifact?: {kind, slug}, bundle?,
  buildSpec?, sections?}`).
- **`<art>/spec-<slug>.ui.json`** (step 6): the checked `uiItems[]`, same shape, plus `mocksDir`
  and `warnings[]`. Read by step 6 (`spec_ui_append`) and by `task-decomposition`.
- **`<art>/story-<slug>.json`**: `title` (string), `description` (string), `decisionIds`
  (list of strings). Written by the flow from the story maker's result file plus the computed
  decision ids. `read_story` also honours an optional `acceptanceCriteria` list (none is written
  today).
- **`<art>/story-<slug>.draft.json`** (written by the `user-story-writer` session, step 10):
  `{title, description}`; read only by step 11.
- **`.meta.json`** beside each recorded file (`artifactio.record`, phase `spec:<slug>`).
- **`write_story` result** (in-process, not saved): `story` `{id, elabKey, action
  (created|updated|unchanged)}` and `summary` `{created, updated}` feed the returned `story` and
  `summary`.
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

## 5. Steps

1. **deterministic** — Build the brief context once (Python, no script): spec header; the PRD
   path; the three-case target sentence; the placed items (`id`, `element`, delta view paths; for
   a prerequisite, the effective views that say what it must be) with the instruction "specify,
   for each of these items and only these, what to build in this repository and how, from the
   PRD, the TRD and the views; do not judge whether code for it exists or meets anything: the
   build pipeline's tests decide that"; the TRD path; the reading-scope rules (only `<repo>`, no
   fleet survey). For the contracts and data-model makers, add the citation rule: cite the views
   read as `decisionIds` in YAML frontmatter; views with `lifecycle_state: effective` are settled,
   others are checked against the TRD.
2. **deterministic** — Reuse check. The spec set is reusable when its files and their
   `.meta.json` exist and every input recorded in each `.meta.json` hashes as recorded now.
   Nothing else decides it: no upstream-rerun chain, no driver ruling. When reusable, skip to
   step 12 with `resumed: true`. Otherwise, per document: a document whose recorded inputs still
   hash as recorded is kept and its maker is not dispatched (finer-grained reuse, see Resume
   points).
   2b. When `frontend` and `packagesDir` are set: list the supplied bundles with
   `cdsbundles.list_bundles(packagesDir)` (today `depscore.py cds-bundles --packages-dir <dir>`)
   and write `<art>/spec-<slug>.bundles.json`. An absent or empty directory supplies none.
3. **agent, in parallel with step 4** — `api-specification-author` (contracts maker). Every maker
   session in this flow (steps 3, 4, 7, 10) runs inside the session runner's section 2 guard
   (`driver-contract.md` §8).
   Inputs: the step 1 context; for a UI repository, `spec-<slug>.bundles.json`, `mocksDir`,
   `shellsDir` and the design-source rules: `bundle` only when a listed bundle packages the
   artifact the item builds (the newest bundle of a kind and slug is the supplied one); otherwise
   `cds` when it changes design, `none` when it does not; the artifact slug for `cds` is the
   artifact's name in lower-case hyphenated words, matching an existing composed artifact's slug
   when one exists; per design source, how to specify the item (`bundle`: by reference to the build
   spec and Section IDs, no new CSS/tokens; `cds`: behaviour and content, design from CDS; `none`:
   the change, no design). Outputs: `<art>/spec-<slug>.md`, and for a UI repository
   `<art>/candidates/spec-<slug>.ui.json`. Model `sonnet` (frontmatter), effort `medium` (dispatch
   and frontmatter). Right for contract prose; kept.
4. **agent, in parallel with step 3** — `data-model-specification-author`. Inputs: the step 1
   context and the access patterns (or "derive them"). Output: `<art>/spec-<slug>.data-model.md`.
   Model `fable` (frontmatter; the current shared `fable` block switches a recovered session to
   `opus`), effort `medium`. Kept; see QUESTIONS.md on `fable`.
5. **deterministic** — Check both documents exist, are non-empty UTF-8 (today
   `jsonartifact.py --document`). Then check their citations: every `decisionIds` entry in each
   document's YAML frontmatter, with any `#<heading>` removed, must name an existing file relative
   to `$ATW_ARCH_PATH/arc42/` (effective view) or `$ATW_ARCH_PATH/` (target or delta view); the
   heading is not checked. A missing document or unresolved entries get one corrective
   re-dispatch of that document's maker naming the missing path or the exact entries (CONTEXT
   7.4); still failing → stage `author`, cause `other`. Then `artifactio.record` each with inputs
   `[<art>/trd.md, <art>/repo-scoping.json, <art>/delta-items.json, <PRD path>]` and phase
   `spec:<slug>`.
6. **deterministic** — For a UI repository: check the candidate UI file and write
   `<art>/spec-<slug>.ui.json`. The check normalizes rather than refuses, as the detailing's
   normalization of `uiAuthority` does today (`reconfacts.recon_facts`): an unknown design source
   is `cds`; a `bundle` item whose bundle is not usable, is superseded, or whose build spec is not
   the one its `bundle.json` names (`cdsbundles.bundle_problem`) is `cds`; a `bundle`/`cds` item
   with no artifact gets `{kind: page, slug: <item id slugified>}`; an entry for an id that is not
   a placed item is dropped. Each normalization is a warning. A missing or unparseable candidate
   gets one corrective re-dispatch of the contracts maker naming the problem; still failing →
   stage `author`, cause `other`. Record the file (inputs: the candidate's inputs plus
   `spec-<slug>.bundles.json`). Then `specui.spec_ui_append(<art>/spec-<slug>.md, <uiItems as
   JSON [{id, designSource, buildSpec, sections}]>)` (today `depscore.py spec-ui-append --doc ...
   --items ...`). It replaces any earlier `## UI design sources` section with one line per item.
   Then `artifactio.record` the contracts document again (its bytes changed).
7. **agent** — `acceptance-criteria-writer`, after steps 3 to 6. Inputs: the step 1 context
   without the citation rule, and the two completed document paths (read them, including the UI
   design sources; trace every criterion to its delta/TRD obligation id; a missing document or a
   contradiction is an unresolved input, never invented behaviour). Output:
   `<art>/spec-<slug>.criteria.md` with the two sections (at most 120 criteria, each clause under
   30 words; at most 30 DoD items). Model `sonnet` (frontmatter), effort `low` (dispatch; the
   frontmatter says `medium`). Low is right for derivation from finished documents; keep `low`.
8. **deterministic** — Check the criteria document exists and is non-empty; `artifactio.record`
   it with inputs `[<art>/trd.md, <art>/repo-scoping.json, <art>/delta-items.json, <PRD path>,
   <art>/spec-<slug>.md, <art>/spec-<slug>.data-model.md]`.
9. **deterministic** — Compute `decisionIds`: read the YAML frontmatter `decisionIds` of
   `spec-<slug>.md` and `spec-<slug>.data-model.md` (checked in step 5); union, strip, deduplicate
   in order. (Today they come from the makers' accepted metadata JSON; the `meta.description` makes
   the saved documents decisive, so the documents are read.) Skipped on a reused spec set (the
   saved `story-<slug>.json` already holds them).
10. **agent** — `user-story-writer`, after step 8 (skipped on a reused spec set). Inputs: the
    three spec document paths, `<repo>`, the spec header. Task: title and description of the ONE
    Story, in terms of the spec set; a container, no task breakdown, WSJF or priority; runs no
    `bd`. Output: `<art>/story-<slug>.draft.json` `{title, description}`. Model `sonnet`
    (frontmatter), effort `low` (dispatch; frontmatter `medium`). See QUESTIONS.md on whether
    this session is needed.
11. **deterministic** — Write `<art>/story-<slug>.json` = `{title, description, decisionIds}`:
    title/description from the draft when non-empty, else the default title
    `<repo basename>: <spec title or id>` and description `Spec: <art>/spec-<slug>.md`.
    `artifactio.record` it with inputs `[<art>/spec-<slug>.md, <art>/spec-<slug>.data-model.md,
    <art>/spec-<slug>.criteria.md]`. Skipped on a reused spec set.
12. **deterministic** — Write the Story bead: `beadwrite.write_story(graph, writer, <epic>, <art>,
    slug=<slug>, repo=<repo>, root=<project root>)`, used in-process (today `depscore.py
    write-story --epic <epic> --dir <art> --slug <slug> --repo <repo> --project-root <root> --out
    <art>/story-<slug>.written.json`, run with `-C <beads repo>`; the `--out` file is not written).
    Runs on every run, including a reused spec set, so the bead exists and carries the current
    artifact metadata. Idempotent: keyed by `elab_key`.
13. **deterministic** — When authored in this run: `artifactio.record_step(<epic>,
    "spec:<slug>")`. Return the result.

Relay mapping (every relay call becomes a direct step): `relay.revision` (`jsonartifact.py
--source` fingerprint of inputs) → replaced by `artifactio` input fingerprints in steps 2, 5, 6, 8,
11; `relay.author` (`jsonartifact.py --candidate/--final` probe and acceptance of
`spec-<slug>.contracts-meta.json`, `.model-meta.json`, `.criteria-meta.json`,
`story-<slug>.json` candidates under `<art>/candidates/`) → dropped for the three metadata files
(no consumer; decision ids now come from the documents, step 9) and replaced for the Story by
steps 10 and 11; `relay.documents` (`jsonartifact.py --document`) → steps 5 and 8;
`relay.record` (`<artifact script> record`) → steps 5, 6, 8, 11; `relay.depscore
spec-ui-append` → step 6; `relay.ensure` (`story-<slug>.json`) → step 11; `relay.depscore
write-story` → step 12; the composite's `acceptPhase` → step 13; the composite's `resumeFresh`
(`artifactio.py plan` and the upstream-rerun recheck) → dropped, step 2 checks the recorded
inputs. The bundle listing and the design-source normalization that the removed detailing step
(`prd-reconciliation`) ran → steps 2b and 6. No `workflow-command-runner` session remains.

Agents accounted for: `api-specification-author` (kept, step 3, now also choosing the UI design
sources), `data-model-specification-author` (kept, step 4), `acceptance-criteria-writer` (kept,
step 7), `user-story-writer` (kept, step 10, see QUESTIONS.md),
`agent-teams-workforce:workflow-command-runner` (dropped: every call is a deterministic step).
Not dispatched today and not added: `openapi-contract-reviewer`, `spec-decider`,
`definition-of-done-enforcer`, `prd-alignment-verifier` (see QUESTIONS.md).

## 6. Checks kept / Checks dropped

- **Documents exist and are non-empty (steps 5 and 8).** Without it, the Story bead would be
  written with missing `artifact_spec*` metadata and `task-decomposition` would decompose from
  nothing; no later step checks the spec files before Tasks are written to beads.
- **UI design sources checked against the supplied bundles (step 6), and `spec_ui_append` written
  from the checked file, not from the maker's prose.** Without it, a stale bundle or a wrong
  build-spec path or Section IDs would reach the Task build contracts in beads; nothing later
  re-derives them.
- **Story written idempotently by `elab_key` (step 12).** Without it, a rerun would create a second
  Story under the Epic (wrong output in beads), and nothing later deduplicates Stories.
- **Only open Stories are updated (`write_story`).** Without it, a rerun could rewrite a started or
  closed Story's prose and metadata; nothing restores them.
- **One repository per Story.** The Story's `repoPath` and its metadata come from the flow, never
  from a session (the agent's forbidden decisions).
- **Citations resolve (step 5).** Without it a `decisionIds` entry naming no view reaches the
  Story's `decision_ids` in beads and every Task inherits it (`task-decomposition.md`); nothing
  later checks it.
- **Section 2 hard limit:** the session runner's guard around every maker session
  (`driver-contract.md` §8); the four makers hold Write.

**Checks dropped:**

- The per-repository detailing (`prd-reconciliation`) and everything that rode on it: the
  add/modify/remove/"done"/"planned-elsewhere" statuses, the `file:line` evidence of existing code,
  the "a `done` item contradicted by the code is reported" rule, and the upstream dependency check
  (`dependencyChanges`). Elaboration does not judge existing code (CONTEXT 7.10, 7.23); the build
  pipeline's tests decide what already works, and a dependency change shows there.
- Candidate metadata JSON per maker (`*-meta.json`), its schema acceptance through
  `jsonartifact.py`, `artifactcontract.py` submit/checkpoint briefs, and the input "revision"
  hash: no consumer reads the metadata files (searched in `scripts/` and `<driver>`); the
  documents are decisive and `artifactio` fingerprints decide reuse.
- `uiSpec` in the contracts maker's metadata: replaced by the candidate UI file (step 3), which is
  checked (step 6).
- Silent fallback when the bundle listing fails (today: log and treat every UI item as `cds`):
  dropped because it lets a wrong design source reach beads unnoticed; a listing that raises is a
  failure (see Failure causes).
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
- `story-<slug>.written.json`: its only reader was `task-decomposition.js`; the Python
  `task-decomposition` reads the Story's Tasks from beads right before its maker runs
  (`tasks-<slug>.context.json`), which is current even when this step was reused.
- The `trd.summary` input: the TRD is read by path.

## 7. Failure causes

| Point | Cause | Retry reasonable? |
|---|---|---|
| Step 2b, `list_bundles` raises (unreadable packages directory, `OSError`) | `other` | No; stage `author`. An absent or empty directory is not a failure. |
| Steps 3, 4, 7, 10: session ends on an API error | `api` | Yes, by `breaker.py`. Completed documents are kept; only the missing ones are redone. |
| Steps 3, 4, 7, 10: quota exhausted | `quota` | Yes, by `breaker.py`, same reuse. |
| Step 5 or 8: a document missing or empty after its session ended normally | `other` | One corrective re-dispatch of that maker naming the missing file is reasonable; then stage `author`, incident-responder. |
| Step 5: `decisionIds` entries that name no file | `other` | One corrective re-dispatch of that maker naming the exact entries; then stage `author`, incident-responder. |
| Step 6: candidate UI file missing or not JSON | `other` | One corrective re-dispatch of the contracts maker naming the problem; then stage `author`, incident-responder. |
| Step 5, 6, 8, 11: `artifactio.record` fails | `other` | No. Non-fatal warning; the cost is that the next run cannot reuse that file, and the Story's `artifact_<key>_sha256` is absent for it. |
| Step 6: `SpecUiError` (items not a JSON list) | `other` | No (a programming error in the flow); stage `author`. |
| Step 10: story draft missing or empty after a normal end | none | Not a failure: step 11 uses the default title and description. |
| Step 11: `story-<slug>.json` cannot be written (`OSError`) | `other` | No; stage `story`. |
| Step 12: `write_story` raises `GraphError` with cause `bd-timeout` or `contention` | that cause (today `GraphError.cause` is chosen from `bd`'s standard error, which CONTEXT 7.4 does not accept as structured; the structured fact is an open item in QUESTIONS.md) | Yes: backoff from about 30 s, doubling, capped at 30 minutes (CONTEXT 7.4). Each attempt re-reads beads, so a Story an interrupted attempt created is updated, not duplicated. |
| Step 12: `write_story` raises any other `GraphError` / `bd` failure | `other` | No; stage `story-write`, incident-responder. |
| Step 13: `record_step` fails | `other` | No; non-fatal warning. |

`relay` has no producer in this flow.

## 8. Resume points

- **R1, the whole spec set** (step `spec:<slug>`: `spec-<slug>.md`, `spec-<slug>.data-model.md`,
  `spec-<slug>.criteria.md`, `spec-<slug>.ui.json` for a UI repository, `story-<slug>.json`, each
  with `.meta.json`). Fingerprint inputs: `<art>/trd.md`, `<art>/repo-scoping.json`,
  `<art>/delta-items.json`, the PRD file (this list and R2's are the single source,
  `prd-to-spec.md` refers here). When every recorded input hashes as recorded, a rerun starts no
  session and runs only step 12 (the Story write) and returns.
- **R2, per document inside the step** (new; the current code reaches the same effect through its
  candidate probe for an unchanged input revision):
  - contracts and data-model documents: inputs as R1; a document whose `.meta.json` matches is
    kept, its maker is not dispatched;
  - `spec-<slug>.ui.json`: R1 inputs plus `spec-<slug>.bundles.json`; redone with the contracts
    document;
  - criteria document: R1 inputs plus the two documents; redone only when one of them changed or
    it is missing;
  - `story-<slug>.json`: inputs are the three spec documents; redone (session 10 and step 11) only
    when one changed or it is missing.
- **R3, the Story bead** is never "redone": `write_story` is idempotent and always runs.
- A rerun after a crash between step 11 and step 12 reruns only step 12.
- Not fingerprinted for R1, on purpose: the packages directory. A bundle supplied after the spec is
  authored is found when the Task is built (the item's recorded artifact `{kind, slug}` and
  `cds-bundles --design-source` in the Task pipeline), so it does not invalidate the spec set.

## 9. Requirements that apply

- **7.4 Retries:** structured causes from the runner and from `GraphError.cause`; `bd` contention
  backoff 30 s doubling to 30 minutes; one corrective re-dispatch only with the exact missing file;
  saved documents are never redone with unchanged inputs.
- **7.6 Done rule and no "nothing to build":** every span repository gets a spec set and one Story.
  The Spec covers every placed item of the repository; the Story is the repository's container for
  the Tasks that must cover every one of them.
- **7.23 No judgment of existing code:** the spec set says what to build and how; it carries no
  status of existing code, and the build pipeline's tests decide what already works (7.19).
- **7.10 Repositories:** the placed items come from the `polyrepo-steward`'s ruling
  (`repo-scoping`); one repository per Spec and Story; the makers read only `<repo>`.
- **7.24 Requirements, Tasks and tests:** the spec documents carry the requirements' technical
  detail (contracts, data model, criteria) that the Tasks cite; acceptance criteria that unit tests
  cannot check are still written, for human testing.
- **7.7 Three-case model:** the brief states the target case and where build items come from.
- **7.9 Who gets asked:** makers decide technical gaps; nothing goes to the owner.
- **7.11 Deterministic over agentic:** the bundle listing, the design-source check, decision ids,
  the Story file and the bead write are code; only the documents' prose and the design-source
  choice are sessions.
- **7.14 Facts, not guesses:** briefs carry paths and the item ids, not theories.
- **7.16 Hierarchy:** the Story is written under its Epic, keyed by `elab_key`.
- **Hard limits:** no write to arc42 section 2; no secrets; nothing in `apps/marketing/`; no
  destructive bead operation (a Story is created or updated, never deleted).

## 10. Open items

See QUESTIONS.md
