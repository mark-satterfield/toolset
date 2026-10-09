# Net-effect spec: `prd-reconciliation` (per-repository detailing of the approved delta)

Source of intent: `workflows/prd-reconciliation.js` `meta.description`; agent
`agents/prd-reality-reconciler.md`; skills `architecture-baseline`, `artifact-handoff`; CONTEXT
section 7. Contracts were read from `scripts/portfolio/reconfacts.py`, `cdsbundles.py`,
`depscore.py` (`recon-facts`, `cds-bundles`), `<driver>/artifactio.py` (`record`, `step`, `plan`)
and the call site in `workflows/prd-to-spec.js` (`reconArgs`, `authorSpecForRepo`).

Path conventions used below: `<art>` = the Epic's artifact directory,
`$ATW_CONTROL_REPO/.claude/workflow-runs/artifacts/<epic-key>/` (the epic key is the Epic bead id
with characters outside `[A-Za-z0-9._-]` replaced by `_`). `<slug>` = the repository's artifact
slug: the repository path's basename with characters outside `[A-Za-z0-9._-]` replaced by `_`,
suffixed `-2`, `-3`, ... when two span repositories share a basename (assigned once per run, in
span order, by the `prd-to-spec` flow). `<repo>` = the absolute path of the one repository.

## Purpose

For ONE repository of an Epic's span, detail the approved architecture delta against the code on
that repository's `main`: give every delta item placed in the repository (one element the delta
shows, or a prerequisite the delta's work rests on) exactly one status — `add`, `modify`,
`remove`, `done` or `planned-elsewhere` — each citing `file:line` evidence (a `planned-elsewhere`
item also names the open bead of another Epic that plans it); give each `ui` item a design source
— `bundle` (a single-artifact cds bundle the owner supplied in the packages directory packages
it; the newest bundle of a kind and slug is the supplied one), `cds` (it changes design and no
bundle packages it) or `none` (it changes no design), and for `bundle` and `cds` items the artifact
(`{kind, slug}` as a `bundle.json` names it) so a mockup supplied later is found when the Task is
built; and report upstream dependency changes. The detailing is saved as `recon-<slug>.json`; the
flow returns only the small facts its callers branch on, and every later session reads the file
by its path. A saved detailing whose inputs are unchanged is reused without a session.

## Produces and decides

After a successful run:

- `<art>/recon-<slug>.json` exists and holds one JSON object with `items`, `evidenceSummary`,
  `uiAuthority`, `dependencyChanges` (shape under Outputs).
- `<art>/recon-<slug>.json.meta.json` exists (written by `artifactio.py record`) and binds the
  file's sha256 to the fingerprints of its inputs, so a later run can tell whether it is reusable.
- The step `recon:<slug>` is recorded as passed in the Epic's `STEPS.md`
  (`artifactio.py step <epic> recon:<slug>`) when the detailing was produced in this run.
- Decided, per placed item, after normalization (`reconfacts.recon_facts`): exactly one status;
  a surface (`ui | service | infra | data | unknown`); for every `ui` item with a work status
  (`add | modify | remove`) one design source in `bundle | cds | none`, an artifact for `bundle`
  and `cds`, and for `bundle` the bundle directory, its build spec and the Section IDs it builds.
- Decided for the repository: whether its upstream dependencies are current
  (`dependenciesCurrent`) and how many invalidating findings exist.
- Returned to the caller (in-process, no file): `reconPath`, `itemCount`, `counts` per status,
  `work` (ids with `add|modify|remove`), `idle` (`{id, status, plannedBy}` of the rest), `uiWork`
  (`{id, designSource, artifact, bundle, buildSpec, sections}`), `bundles` (distinct bundle
  directories cited), `mocksDir`, `dependenciesCurrent`, `dependencyFindings`, `warnings`,
  `resumed` (true when the saved file was reused).

No bead, vault or git write happens in this flow.

## Inputs

- **Epic and PRD:** Epic bead id; PRD id, title and path (the PRD file under `$ATW_PRD_DIR`,
  vault `docs/sdlc/...`).
- **Repository:** `<repo>`, one of the span repositories ruled by `repo-scoping` (spec:
  `<orch>/specs/epic/repo-scoping.md`).
- **Placed items:** the delta items `repo-scoping` placed in `<repo>`: from `<art>/repo-scoping.json`
  `placements[]` whose `repoPath` equals `<repo>`, their `itemIds`, joined to the delta item list
  (`depscore.py arch-delta`, spec: `<orch>/specs/epic/architecture.md` and
  `<orch>/specs/epic/prd-to-spec.md`). Each item: `id`, `element`, `views` (delta view paths), and
  for a prerequisite item `kind: "prerequisite"`, `state` and `closure` (its entry in
  `<target>/closure.json`).
- **UI flag:** `uiRepo` = any placement of `<repo>` has `frontend: true` in `repo-scoping.json`.
- **Approved target:** `targetDir`, `deltaDir`, `architectureChange` (`none | new | partial`) from
  `<art>/architecture/target.json` (spec: `architecture.md`). The three cases (CONTEXT 7.7):
  `partial` = target views plus a delta folder of the change only; `new` = target views that are
  both future and delta, no delta folder; `none` = one set (the effective views the target's
  `baseline.json` cites in `entries[].documents`), no delta; build work is the gaps
  (`implementationWork` in `baseline.json` and the prerequisites in `closure.json`).
- **Survey:** `<art>/architecture/survey.json` (evidence the session reuses; CONTEXT 7.13).
- **Design system** (only when `uiRepo`), from the driver (`<driver>/workitems.py`
  `design_system_args`): `packagesDir` = `$ATW_DESIGN_PACKAGES_DIR` (default
  `docs/product/product-design/ui-design/design-packages/` in the `skillspoke-docs` vault);
  `mocksDir` = `$CUSTOMIZABLE_DESIGN_SYSTEM_MOCKS_DIR`; `shellsDir` =
  `$CUSTOMIZABLE_DESIGN_SYSTEM_SHELLS_DIR`. Each bundle is a directory with `bundle.json`
  `{kind: page|shell|view, slug, shell, created_at, build_spec}`, `spec/build-spec.md`,
  `design/<kind>.html`, `styles/`.
- **Upstream dependencies:** an optional list (`dependencies` in the `prd-to-spec` arguments). The
  driver sends none today (see Open questions); the session then discovers them from the
  repository's manifests, lockfiles and imports on `main`.
- **Beads (read only, by the session):** open Stories and Tasks of other Epics, read with
  `atw-bd list | show | search`, to name a `planned-elsewhere` bead.
- **Code:** `<repo>` at `main`, read with `git -C <repo> grep -n <term> main` and
  `git -C <repo> show main:<path>`.

## Outputs

- **`<art>/recon-<slug>.json`** (written by the session, the only file it writes). One JSON object:
  - `items[]`: `id`, `element`, `status` (`add | modify | remove | done | planned-elsewhere`),
    `from`, `to`, `evidence` (list of strings, each a `file:line` on `main` with what it shows),
    `plannedBy` (bead id; `planned-elsewhere` only), `surface` (`ui | service | infra | data | unknown`).
  - `evidenceSummary`: string.
  - `uiAuthority`: `uiItems[]` (`{item, designSource, reason, artifact?: {kind, slug}, bundle?,
    buildSpec?, sections?}`), `mocksDir`, `artifactsConsulted[]`; empty values when the
    repository holds no UI.
  - `dependencyChanges`: `current` (bool), `changeFindings[]` (`{dependency, change,
    invalidates}`), `evidence` (string).
- **`<art>/recon-<slug>.json.meta.json`** (written by `artifactio.record`): `artifact`, `path`,
  `epic_id`, `phase` (`recon:<slug>`), `created_at`, `updated_at`, `sha256`, `bytes`, `inputs[]`
  (`{path, kind, sha256}`; kinds `file | dir | missing | git-main | arc42-revision`).
- **`STEPS.md`** in `<art>`: line for step `recon:<slug>` (`artifactio.record_step`).
- **Run ledger entry** (returned to the composite, which records it): `phase:
  "prd-reconciliation"`, `subject` (PRD id), `chosen: ["prd-reality-reconciler"]`, `uiCheck`,
  `resumed`, `reconPath`, `itemCount`, the five status counts, `ok`. Whether this survives is the
  driver contract's decision (`<orch>/specs/epic/driver-contract.md`).
- **Facts returned in-process** (listed under Produces and decides). The `prd-to-spec` flow keeps
  them per repository and hands `reconPath`, `work`, `idle`, `uiWork`, `dependenciesCurrent` and
  `dependencyFindings` to `spec-authoring` (`<orch>/specs/epic/spec-authoring.md`) and
  `reconPath` to `task-decomposition` (`<orch>/specs/epic/task-decomposition.md`).

No bead writes, no vault writes, no git commits.

## Steps

1. **deterministic** — Resolve paths: `<art>`, `<slug>`, `recon-<slug>.json`, the placed items,
   `uiRepo`, the target's three-case sentence (from `architectureChange`, `targetDir`,
   `deltaDir`). Python, no script.
2. **deterministic** — Reuse check. When `recon-<slug>.json` and its `.meta.json` exist and the
   step `recon:<slug>` is fresh (`artifactio.plan(<epic>)` `phases["recon:<slug>"].status ==
   "fresh"`, or, when an upstream step re-ran in this run, its recorded input fingerprints still
   match), run step 6 on the saved file. If its result is `ok: true`, return those facts with
   `resumed: true`; no session starts. If the file is not usable, continue at step 3 (it is
   detailed again).
3. **deterministic** — When `uiRepo` and `packagesDir` are set: list the supplied bundles with
   `cdsbundles.list_bundles(packagesDir)` (today `depscore.py cds-bundles --packages-dir <dir>`).
   An absent or empty directory supplies none. Write the listing to
   `<art>/recon-<slug>.bundles.json` so the session reads it by path (no pasted data).
4. **agent** — `prd-reality-reconciler`. One session for the repository.
   - Inputs (paths only in the brief): `<repo>` (read `main` only, no other repository); the
     target/delta directories and the three-case sentence; the placed items (`id`, `element`,
     delta view paths; for a prerequisite its state, the effective views that say what it must
     be, and its closure entry); `<art>/architecture/survey.json`; the PRD path; for a UI
     repository `<art>/recon-<slug>.bundles.json`, `mocksDir`, `shellsDir`; the dependency list or
     the instruction to discover dependencies on `main`.
   - Task (from the agent definition and the `meta.description`): CHECK 1, one entry per placed
     item with one status and `file:line` evidence, surface, and for `ui` items the design source
     rules (`bundle` only when a listed bundle packages the artifact the item builds; otherwise
     `cds` when it changes design, `none` when it does not; artifact slug for `cds` = the
     artifact's name in lower-case hyphenated words, matching an existing composed artifact's
     slug when one exists); CHECK 2, upstream dependency changes. Read-only; existing code is
     evidence to inspect, not proof of correctness (a name, import or mock is not enough for
     `done`).
   - Output file: `<art>/recon-<slug>.json`. The session returns nothing the flow reads; the
     file is the result.
   - Model and effort as the current code uses them: model `opus` (agent frontmatter), effort
     `medium` (dispatch option, also the frontmatter value). Right: this is per-repository code
     reading that decides every downstream Task; the measurement step (S07) checks its cost.
   - Runs in parallel with the detailing of the Epic's other span repositories (the composite
     runs one `prd-reconciliation` → `spec-authoring` chain per repository concurrently). Nothing
     inside this flow runs in parallel.
5. **deterministic** — Record the file: `artifactio.record(<art>/recon-<slug>.json, epic=<epic>,
   phase="recon:<slug>", inputs=[<PRD path>, <art>/architecture/target.json,
   <art>/repo-scoping.json, <art>/architecture/survey.json, "git-main:<repo>"])` (today
   `python3 $ATW_ARTIFACT_SCRIPT record ...`).
6. **deterministic** — Read the facts: `reconfacts.recon_facts(<file>, <placed ids>)` (today
   `depscore.py recon-facts --file <file> --items <ids>`). It normalizes rather than refuses: a
   placed item with no entry is `add`; a repeated entry keeps the first; an entry for an unplaced
   id is ignored; an unknown status maps from a synonym, else `modify`; `planned-elsewhere`
   without `plannedBy` is `done`; an unknown surface is `unknown`; an unknown design source is
   `cds`; a `bundle` item whose bundle is not usable, superseded, or whose build spec is not the
   one its `bundle.json` names is `cds`; a `bundle`/`cds` item with no artifact gets
   `{kind: page, slug: <item id slugified>}`; a missing or non-boolean
   `dependencyChanges.current` is taken as `true`. Each normalization is a warning. `ok: false`
   (with `problem`) only when the file is not one JSON object or has no `items` list. A file that
   is absent or not JSON raises `ReconError`.
7. **deterministic** — When produced in this run and `ok: true`: record the step,
   `artifactio.record_step(<epic>, "recon:<slug>")` (today `python3 $ATW_ARTIFACT_SCRIPT step`).
   Return the facts and the ledger entry.

Relay mapping (every relay call becomes a direct step): `relayKit.depscore ... cds-bundles` →
step 3; `relayKit.depscore ... recon-facts` (fresh and replay) → step 6 (and step 2);
`relayKit.run ... <artifact script> record` → step 5; the composite's `acceptPhase` →
`artifactio.py step` → step 7; the composite's `resumeFresh` → `artifactio.py plan` → step 2.
No `workflow-command-runner` session remains.

Agents accounted for: `prd-reality-reconciler` (kept, step 4).
`agent-teams-workforce:workflow-command-runner` (dropped: every call it ran is a deterministic
step above).

## Checks kept

- **Normalization in `recon_facts` (step 6).** Without it, a placed item the session left out
  would get no status and therefore no Task, and a made-up status, surface or design source would
  reach the Story's spec and the Task build contracts in beads; nothing later re-reads the
  detailing against the placed items. Missing → `add` keeps CONTEXT 7.6 (every placed item reaches
  a Task or is recorded idle).
- **Not-a-detailing (`ok: false`) and unreadable file (`ReconError`).** Without it, an empty or
  foreign file would be handed to `spec-authoring` and `task-decomposition` as the repository's
  detailing and the Epic would be marked done with no work; nothing later checks the shape.
- **Bundle usability inside `recon_facts`** (`cdsbundles.bundle_problem`: absolute path, usable
  `bundle.json`, newest of its kind and slug, build spec named by `bundle.json` and present).
  Without it, a stale or wrong build-spec path is written into `spec-<slug>.md`'s
  `## UI design sources` section by `spec-ui-append`, which nothing re-checks.
- **Read-only session, one repository.** Hard limit (no destructive operations; no writes outside
  the result file; nothing in `apps/marketing/`).

**Checks dropped:**

- Refusals for no repository, no target, no placed item, no artifact directory/slug, no absolute
  `depscore.py` path: the Python composite builds these arguments itself; a missing one is a
  programming error that raises, not a run outcome.
- "More than one repository: detail the first, ignore the rest": one repository per call by
  signature.
- The session's returned `itemCount` and the mismatch log against the file: the file is the only
  result.
- The structured-output schema on the session reply: the reply is not read.
- Relay checksum guards, relay files under `<art>/relay/recon-<slug>/`, `settleAgent` /
  `dispatchDeaths` bookkeeping, `dispatchOutcome` interruption propagation, and text-matching
  failure classification (`dispatchFailureCause`): replaced by the runner's structured cause
  (CONTEXT 7.4).
- "Replay path must be absolute": the path is computed, not passed in.
- Silent fallback when the bundle listing fails (today: log and treat every UI item as `cds`):
  dropped because it lets a wrong design source reach beads unnoticed; a listing that raises is
  now a failure (see Failure causes).

## Failure causes

| Point | Cause | Retry reasonable? |
|---|---|---|
| Step 3, `list_bundles` raises (unreadable packages directory, `OSError`) | `other` | No; stop the repository with stage `detailing`. An absent or empty directory is not a failure. |
| Step 4, session ends on an API error | `api` (from the runner's structured result) | Yes, by the owner's API handling (`breaker.py`). |
| Step 4, session ends on quota exhaustion | `quota` | Yes, by `breaker.py`. |
| Step 4, session ends without writing `recon-<slug>.json` | `other` | No as-is; stage `detailing`, handed to the incident-responder. |
| Step 5, `artifactio.record` fails (file vanished, `git rev-parse main` fails for `git-main:<repo>`) | `other` | No. Non-fatal: the detailing is used; the cost is that a later run cannot reuse it. Logged as a warning in the result. |
| Step 6, `ReconError` (absent or not JSON) | `other` | One corrective re-dispatch of step 4 carrying the exact error is reasonable (clarified feedback); after that, stage `detailing-read`, incident-responder. |
| Step 6, `ok: false` (`problem`) | `other` | One corrective re-dispatch of step 4 carrying the `problem` text; after that, stage `detailing`, incident-responder. |
| Step 7, `artifactio.record_step` fails | `other` | No. Non-fatal warning (STEPS.md is resume bookkeeping). |

`bd-timeout` and `contention` have no producer here (the flow runs no `bd`; the session's own
`atw-bd` reads are inside the session). `relay` has no producer (no relay remains).

## Resume points

- **R1, the saved detailing** (`recon-<slug>.json` + `.meta.json`, step `recon:<slug>`).
  Fingerprint inputs: the PRD file, `<art>/architecture/target.json`, `<art>/repo-scoping.json`,
  `<art>/architecture/survey.json`, and `git-main:<repo>` (the commit `main` points at). Upstream
  steps: `architecture`, `repo-scoping`. A rerun with all fingerprints unchanged starts no session
  and runs only step 6 on the saved file (zero tokens). A rerun after any input changed runs
  steps 3 to 7 (one session). A saved file that fails step 6 is detailed again.
- Nothing inside one detailing is resumable (one session, one file).
- Not fingerprinted, on purpose: the packages directory. A bundle supplied after detailing is
  found when the Task is built (the item's recorded artifact `{kind, slug}` and
  `cds-bundles --design-source` in the Task pipeline), so it does not invalidate the detailing.

## Owner rules that apply

- **7.4 Retries:** structured causes from the runner and from exception types; no text matching;
  one corrective re-dispatch only when it carries the exact problem; a reused detailing is never
  redone.
- **7.6 Done rule:** the `work` list is the contract for this repository: every `add`/`modify`/
  `remove` id must reach a Task or a recorded "nothing to build"; normalization makes a missing
  item `add` so it cannot vanish.
- **7.7 Three-case model:** the brief states which case the target is (`none`, `new`, `partial`)
  and where build items come from in each.
- **7.9 Who gets asked:** the session decides technical gaps itself (`subagent-contract`); nothing
  in this flow goes to the owner.
- **7.10 Repositories:** the repository and its placed items come from the `polyrepo-steward`'s
  ruling (`repo-scoping`); the session reads only this repository.
- **7.11 Deterministic over agentic:** bundle listing, normalization, recording and reuse are
  code; only the status judgment and dependency check are a session.
- **7.13 Saved work:** the architecture survey is handed to the session as evidence to reuse.
- **7.14 Facts, not guesses:** the brief carries paths, the item list and the expected file, no
  theory about statuses.
- **Hard limits:** read-only session; no write to arc42 section 2; no secrets; nothing in
  `apps/marketing/`.

## Open questions

1. **Citation rule vs normalization.** The session brief says "An item with no citation fails the
   run", but `recon_facts` only warns when a work or `done` status cites no `file:line`. Should an
   uncited `done` (which suppresses a Task) fail, trigger the corrective re-dispatch, or stay a
   warning?
2. **`git-main:<repo>` as a fingerprint input.** Any commit to `<repo>`'s `main` (including Tasks
   of this same Epic merged later) makes the detailing stale and costs a fresh opus session on the
   next elaboration rerun. Is that intended, or should the fingerprint be narrowed (for example
   to the files the evidence cites)?
3. **Target and delta views are not fingerprinted directly.** Inputs cover
   `architecture/target.json` but not the files under `targetDir`/`deltaDir`; a rewrite of a view
   that leaves `target.json` byte-identical would not invalidate the detailing. Should the
   directories be added as inputs (`artifactio` hashes a directory)?
4. **`dependencies` input.** The driver never sends `dependencies` to `prd-to-spec` (no producer
   in `<driver>`). Drop the input and always have the session discover dependencies, or add a
   producer?
5. **`isolation: worktree` in the agent frontmatter.** `prd-reality-reconciler` declares
   `isolation: worktree` but must write `<art>/recon-<slug>.json` outside any worktree and read
   `<repo>`'s `main`. How does the Python session runner treat this field (S02)?
6. **Run ledger entry.** Is the per-step ledger object (`phase: "prd-reconciliation"`, counts)
   still recorded anywhere after the rewrite, or replaced by driver ledger events? Settled in
   `driver-contract.md`.
7. **Corrective re-dispatch.** The current code never re-dispatches; this spec allows one
   corrective re-dispatch carrying the exact `ReconError`/`problem`. Confirm in S02.
