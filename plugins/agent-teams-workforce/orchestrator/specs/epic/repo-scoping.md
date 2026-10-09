# Net-effect spec: `repo-scoping`

Source: `<plugin>/workflows/repo-scoping.js` (`meta.description`), its call site and replay in
`<plugin>/workflows/prd-to-spec.js` (`runRepoScoping`, `misplaced`, `readSavedSpan`), agent
`<plugin>/agents/polyrepo-steward.md`, skill `<plugin>/skills/polyrepo-repo/SKILL.md`, CONTEXT
sections 6 and 7 (7.10 sets the order of this flow; 7.25 the element status matrix). `<art>` below
is the Epic's artifact directory, `<control>/.claude/workflow-runs/artifacts/<epic-id>/`
(`artifactio.working_dir`).

## 1. Purpose

Rule the repository span of one PRD from its approved architecture, in two separate steps in this
order (CONTEXT 7.10):

- **Placement (part A).** The list of elements the change needs comes from the approved delta:
  each build item `depscore.py arch-delta` lists (an element a delta view shows, an element of the
  future set the element status matrix does not show as built (`implementationWork`), or a
  prerequisite from the architecture step's Closure). The
  `polyrepo-steward` places each element in exactly one repository, or records that the element
  has no code in this project. Where the repository an element belongs in does not exist yet, the
  steward names it as a missing repository, with its name and template. The steward creates
  nothing in this step.
- **Creation (part B).** A separate, later, deterministic step creates each missing repository the
  steward named, from the name and template it gave, with the `polyrepo` tool. A missing
  repository is work to build, not an error to report (CONTEXT 7.20).

The span is the distinct repositories the placements name, and it always names at least one: every
Epic gets Stories and Tasks, so a span with no repository is a failure, never a "nothing to build"
result (CONTEXT 7.6). Nothing in this flow reads repository code to judge whether an element is
built (CONTEXT 7.23): what is already built is the element status matrix's record (CONTEXT 7.25),
and the build pipeline's tests decide what already works.

## 2. Produces and decides

After a successful run:

- Every build item id appears exactly once: in one placement or in `noCode`.
- No placement names the control repository (`$ATW_CONTROL_REPO`), the repository that holds the
  architecture (`$ATW_ARCH_PATH` or a parent of it), or a repository under `apps/marketing/`.
- Every placement names either an existing repository from the inventory or a missing repository
  the ruling lists in `missingRepos` with a name and a template.
- Every missing repository exists after part B (created now, or by an earlier run of the same PRD
  and found in the live inventory), and every placement that named it carries its path.
- The span names at least one repository.
- `<art>/repo-scoping.json` holds the accepted placement ruling and
  `<art>/repo-scoping.json.meta.json` records its input fingerprints.
- `<art>/repo-creation.json` holds the result of part B (written also when no repository was
  missing, with an empty list).
- The flow's result carries `repos` (the span as absolute paths, ordered by first placement),
  `placements` (with every `repoPath` set), `noCode`, `createdRepos`, `spanRationale`.

## 3. Inputs

| Input | Where it comes from |
|---|---|
| Epic id | the composite (`epic.key`, the bead id) |
| PRD path | the composite (`prd.path`, under `$ATW_PRD_DIR`) |
| Build items | `<art>/delta-items.json`, written by `depscore.py arch-delta --delta-dir <deltaDir> --save <art>/delta-items.json` in the composite's step 7 (`prd-to-spec.md`), after its Architecture phase. Item fields used: `id`, `element`, `views`, `kind` (`implementation-gap`, `prerequisite`, or absent for a view item), and for a prerequisite `requiredBy` and `repository` (the repository its element status matrix row names, when the row names one; `architecture.md` section 2 item 10). |
| Approved target | `targetDir` (`<archPath>/target/<subject>/`), `deltaDir` (`<targetDir>/delta/`, present only for a partial change), `architectureChange` (`partial`, `new`, `none`) and `note`, all from the `arch-delta` result |
| Architecture records | `<art>/architecture/decision.md`, `<art>/architecture/target.json` |
| Element status matrix | the rows for the build items' elements: repository, state (`unknown`, `built`, `deployed`), and the Task and commit that last changed the element (CONTEXT 7.25; its storage, row format and matching rule: QUESTIONS.md item 32e). Read only. Seeded once with every repository, the CDK stacks each holds and their expected content, state `unknown` (PLAN S05a); only the build pipeline sets `built` or `deployed`. |
| Live repository inventory | `uv run <plugin>/skills/polyrepo-repo/scripts/polyrepo.py inventory --json` |
| Repositories to avoid | the corrective-pass list (section 5, step 6): `{repoPath or repoName, reason, itemIds}` |
| Paths that never hold placed work | `$ATW_CONTROL_REPO`, `$ATW_ARCH_PATH`, `$SKILLSPOKE_ROOT/apps/marketing/` (the `marketing-*` repositories) |

No bead field or metadata key is read. No repository's code is read.

## 4. Outputs

| Output | Format and key fields |
|---|---|
| `<art>/repo-scoping.inventory.json` | step 4: the `polyrepo.py inventory --json` result, read by the steward session |
| `<art>/candidates/repo-scoping.json` | the steward's raw placement result, schema below; validated once by step 6 and not reused on its own |
| `<art>/repo-scoping.json` | accepted placement ruling. `placements[]: {repoPath (null for a missing repository), repoName, itemIds[], frontend, rationale}`, `missingRepos[]: {name, template, purpose, itemIds[]}`, `noCode[]: {itemId, reason}`, `spanRationale`. Read later by this flow's own reuse step (step 3) and by part B, by `beadwrite._no_code` (for `depscore.py closure-edges`), by `spec-authoring` (the placed items and `frontend` of its repository) and `task-decomposition` (the placed items of its repository; every repository's placements for the items a Task requires), and named as an input of each `spec:<slug>` and `tasks:<slug>` step. |
| `<art>/repo-scoping.json.meta.json` | `artifactio.record(<art>/repo-scoping.json, epic, phase="repo-scoping", inputs=<step 3 inputs>)`: `sha256`, `bytes`, `inputs[]` with each input's hash (the one input-record format of every Epic flow) |
| `<art>/repo-creation.json` | part B's result: `created[]: {name, repoPath, template, itemIds[], existed}` (`existed` true when an earlier run had created it and the inventory found it), `failures[]: {name, template, itemIds[], error, ownerFact}`. Recorded with `artifactio.record` (inputs: `repo-scoping.json`). |
| Flow result to the composite | `{ok, repos, placements, noCode, createdRepos, warnings?, artifactPath, creationPath, spanRationale, ledger: {phase: 'repo-scoping', beadId, subject, chosen: ['polyrepo-steward'], mode: 'fixed', repoCount, itemCount, createdRepoCount, ok}}`. `placements` here carry the created repositories' paths; `createdRepos` is `repo-creation.json` `created`. The driver's `decisions.py` (`_scoping`) renders `placements`, `createdRepos`, `noCode` and `spanRationale` from it. |
| New repositories | created by part B with `polyrepo.py create`, locally and on GitHub; the polyrepo tool commits its own manifest, changelog and beads fleet list. |

No bead write and no vault write.

## 5. Steps

### Part A: placement

1. **Refuse a missing target** (deterministic, Python). No `targetDir` → fail at stage `input`,
   cause `other`. An empty item list → fail at stage `input`, cause `other`, with no session: the
   architecture step lists build items in every case (CONTEXT 7.7), so an empty list is a defect
   for the incident-responder, not a "nothing to build" result.
2. *(removed)* **No-implementation short cut.** Today, when the `arch-delta` result has
   `baselineValidated`, `implementationComplete`, `implementationWork == 0` and no prerequisite
   item, every item goes to `noCode` and the span is empty. There is no "nothing to build" outcome
   (CONTEXT 7.6): code that already meets the requirements still gets Stories and Tasks, and the
   build pipeline's tests decide that nothing changes. The items are placed like any others.
3. **Fingerprint the inputs and look for saved work** (deterministic, Python). Inputs: the PRD,
   `decision.md`, `target.json`, `delta-items.json`, `targetDir`, `deltaDir`, and the element
   status matrix rows of the build items' elements. The ruling is reusable when
   `<art>/repo-scoping.json` exists and every input recorded in its `.meta.json` hashes as
   recorded; the step 6 checks are applied to it again, so a saved ruling with a finding (for
   example a placement in a never-placed repository) is not reused. This is the only reuse test:
   there is no separate saved-span read and no candidate reuse. A reused ruling goes on to part B.
4. **Take the inventory** (deterministic). Run `polyrepo.py inventory --json`, write the result to
   `<art>/repo-scoping.inventory.json`. (Today the steward runs it inside its session; running it
   here gives the steward a file path and removes a tool turn.)
5. **Place** (agent `polyrepo-steward`). Inputs, as paths: `delta-items.json`, the inventory file,
   the element status matrix rows of the build items' elements (written to a file the brief names),
   `targetDir`, `deltaDir` and the `architectureChange` case (CONTEXT 7.7: partial = target plus
   delta of the change; new = target views are also the delta; none = the effective views the
   target's `baseline.json` cites, with build items from its `implementationWork` and
   `closure.json`), the avoid list when present, the output path
   `<art>/candidates/repo-scoping.json` and its schema. The brief states the rules:
   - place each element in the one repository that holds it or will hold it, from the inventory,
     the steward's own records and the matrix row (an element whose row names a repository goes
     there unless the target moves it);
   - an element with no code in this project (an external system, or a managed service configured
     in another item's repository) goes in `noCode` with the reason; an element of this PRD is
     never put in `noCode` because the repository that would hold it is missing or because code
     for it may already exist;
   - before naming a missing repository, look in the inventory for one that already serves the
     element, including one an earlier run of this PRD created;
   - name a missing repository with the name, template and purpose the approved target gives, or,
     when the target names none, a name that follows the project's naming convention and the
     template whose kind matches the element; list it in `missingRepos` and place its items with
     `repoName` set and `repoPath` null;
   - create nothing and change nothing in any repository (creation is part B);
   - a placement never makes one repository depend on another (CONTEXT 7.10, section 9).
   Model and effort today: the agent's `sonnet` with the workflow's `effort: 'high'` override (the
   definition says `medium`). Keep `sonnet`/`high`: a wrong placement propagates into every later
   step. Runs in parallel with `trd-authoring` (the composite starts
   both after Architecture). The session runs inside the session runner's section 2 guard
   (`driver-contract.md` §8).
6. **Accept and check the placement** (deterministic, Python). Parse the candidate once, strictly,
   against the schema. Then compute, from the parsed file, `delta-items.json` and the inventory:
   - ids placed twice, ids not placed at all, ids that are not build items (dropped with a warning);
   - placements in a never-placed repository (control repository, architecture repository,
     `apps/marketing/`), including a missing repository whose name is a `marketing-*` name;
   - placements whose `repoPath` is null and whose `repoName` is not in `missingRepos`, and
     `missingRepos` entries with no name or no template, or whose name the inventory already holds;
   - items placed elsewhere than the repository their matrix row names;
   - an empty span (no placement names a repository).
   If any of the first two kinds, a never-placed repository, an unlisted or incomplete missing
   repository, or an empty span is found: run step 5 **once more** with the exact findings (the
   ids and the repositories, with reasons) as the avoid list and gap feedback. If the second pass
   still has them, fail at stage `repo-scoping`, cause `other`. An item placed elsewhere than its
   matrix row's repository stands with a warning (an open item in QUESTIONS.md).
7. **Save** (deterministic, Python). Write `<art>/repo-scoping.json` (canonical JSON), then
   `artifactio.record` it with the step 3 inputs.

### Part B: creation

8. **Create the missing repositories** (deterministic, Python; runs after step 7, also on a
   reused ruling). For each `missingRepos` entry, in ruling order:
   - look the name up in a fresh `polyrepo.py inventory --json`; when it is there (an earlier,
     interrupted run created it), record it with `existed: true` and its path;
   - otherwise run `polyrepo.py create` with the entry's name and template, and record the path
     its result gives;
   - a create that fails is recorded in `failures` with its error and whether it is an owner fact.
   Write `<art>/repo-creation.json` and record it. No agent session runs in part B.
9. **Settle the span** (deterministic, Python). Any `failures` entry: an owner fact (for example
   missing GitHub credentials or organisation permission) is returned as `requiredHumanActions`
   (CONTEXT 7.9), and the run stops at stage `repo-creation` with no cause; any other failure
   fails the run at stage `repo-creation`, cause `other` (incident-responder). Otherwise fill every
   placement's `repoPath` from `repo-creation.json`, build `repos` in first-placement order,
   `frontend` defaulting to false, `repoName` defaulting to the path basename, and return the
   flow result. The composite takes this span as final: it runs no placement check of its own.

The relay calls of the current script map as follows: `relayKit.artifactRevision` (jsonartifact.py
`--source`) → step 3 hashing in Python; `relayKit.authorArtifact` probe and accept (jsonartifact.py
`--candidate --final`) → step 6 in Python; `relayKit.run ... artifactio.py record` → steps 7 and 8
called directly; `depscore.py saved-span` and the `misplaced` check (composite) → steps 3 and 6
of this flow. Repository creation, which the steward did inside its session today, is part B. No
`workflow-command-runner` session remains.

## 6. Checks

**Checks kept**

- Every item placed exactly once (step 6). Without it an item is dropped or built twice; nothing
  later sees an unplaced item, since spec authoring and Task decomposition only receive placed
  items.
- No placement in the control repository or the architecture repository (step 6, moved here from
  the composite's `misplaced`; the composite keeps no copy). Without it Stories and Tasks target
  the pipeline's own repository or the vault; no later step rejects a repository path.
- No placement under `apps/marketing/`, and no missing repository with a `marketing-*` name (step
  6). Hard limit (CONTEXT 6, 7.10).
- Every placement in a missing repository names an entry of `missingRepos` with a name and a
  template (step 6). Without it part B has nothing to create and the items land in no repository;
  nothing later notices until the build pipeline fails.
- Candidate parses against the schema (step 6). Without it the Python cannot read the ruling; a
  parse failure is a failed step, not wrong output.
- Saved-ruling reuse re-applies the step 6 checks (step 3). Without it an old ruling made
  before the rule existed is replayed into spec authoring and Task decomposition.
- Section 2 hard limit: the session runner's guard around the steward session
  (`driver-contract.md` §8); the steward holds every tool.
- An empty span fails (step 6, in `meta.description`, not in today's code): every Epic gets
  Stories and Tasks (CONTEXT 7.6); without the check the Epic is marked done with nothing built,
  and nothing later notices.
- A creation failure stops the run (step 9): the items placed in that repository would otherwise
  get Stories and Tasks in a repository that does not exist.

**Checks dropped**

- The no-implementation short cut (step 2) and the "empty span is valid" rule: CONTEXT 7.6.
- The `planned` prerequisite rule (a prerequisite another Epic's open bead plans goes in `noCode`)
  and placement by the Closure's `deployedBy`: the Closure no longer produces either (it reads the
  element status matrix, `architecture.md` section 2 item 10). Every element the matrix does not
  show as built is placed and gets Tasks in this Epic; where an open Task of another Epic in the
  same repository overlaps, `task-decomposition` adds a `blocks` edge onto it as well
  (`blockedByExternal`).
- Unknown item ids: not a failure; ignored with a warning (they change nothing downstream).
- Silent conversion of unplaced items to `noCode` (current code, after the steward session and in
  the composite's `readSavedSpan`): replaced by the step 6 corrective pass and then a failure,
  because it hid dropped work.
- The steward's own retry of a failed creation inside its session: creation is part B, a script;
  a failure that is not an owner fact goes to the incident-responder.
- Template existence at placement: not added; `polyrepo.py create` fails loudly with the template
  named, and part B stops the run.
- The candidate-with-revision-sidecar resume (`jsonartifact.py --candidate` with an input
  revision): a sandbox workaround; the candidate is validated once in step 6 and only the accepted
  `repo-scoping.json` with its `.meta.json` is a resume point.
- `inputBinding.ok` and relay-receipt checks, the `dispatchInterruption`/`dispatchOutcome`
  plumbing, `ART`/`RELAY_RUNNER` presence checks: sandbox and relay workarounds; gone with the
  relay.
- The `recorded.ok`/`persistErrors` path: `artifactio.record` is a direct call; an exception is a
  failed step with its cause.
- A check that each existing `repoPath` exists on disk: not added. The inventory is the source of
  the paths, and a wrong path fails `spec-authoring` loudly when it records its inputs; no wrong
  output is written.

## 7. Failure causes

| Failure point | Cause | Retry reasonable? |
|---|---|---|
| No `targetDir`, or an empty item list | `other` | No (the composite's Architecture result is wrong; incident-responder). |
| `polyrepo.py inventory` exits non-zero | `contention` when the tool's structured result reports a git lock (the field is S02's to name; never matched from error text); otherwise `other` | Contention: yes, backoff from 30 s. Otherwise no. |
| Steward session: API error or overload | `api` | Yes, through `breaker.py`. |
| Steward session: usage or quota limit | `quota` | Yes, through `breaker.py`. |
| Steward session ends with no candidate file, or a candidate that fails the schema | `other` | Once, with the parse error as feedback (clarified instruction); then no. |
| Placement findings remain after the corrective pass (incl. an empty span) | `other` | No; incident-responder. |
| `polyrepo.py create` fails for want of an owner fact (GitHub credentials, organisation permission) | none: `requiredHumanActions` | No; the driver holds the Epic for the owner (CONTEXT 7.9). |
| `polyrepo.py create` fails on a git lock | `contention` (structured fact as for the inventory) | Yes, backoff from 30 s. |
| `polyrepo.py create` fails otherwise | `other` | No; incident-responder. |
| `artifactio.py record` fails | `other` | No. |

Causes are set from the exit status, the session's structured result, the tool's JSON result or
the parse exception at the point of failure, never from error text. `relay` has no producer in
this flow.

## 8. Resume points

| Saved result | Fingerprint inputs | A rerun after it redoes |
|---|---|---|
| `<art>/repo-scoping.inventory.json` | none; it is always retaken when step 5 must run | only the inventory command |
| `<art>/repo-scoping.json` + `.meta.json` | PRD, `decision.md`, `target.json`, `delta-items.json`, `targetDir`, `deltaDir`, the element status matrix rows of the build items' elements (this list is the single source; `prd-to-spec.md` refers here) | no session; part B runs again |
| `<art>/repo-creation.json` + `.meta.json` | `repo-scoping.json` | nothing new: every repository it lists is found again in the inventory (`existed: true`), so none is created twice |

An interrupted run leaves at most a candidate with no accepted ruling; the rerun starts the
steward session again (one session; no partial result is trusted). A run interrupted inside part B
leaves some repositories created; the rerun's step 8 finds them in the inventory and creates only
the rest.

A changed closure (new prerequisite) changes `delta-items.json`, so the ruling is redone; a
change confined to other Epics' files is not an input and redoes nothing.

## 9. Requirements that apply

- 7.10: the order is the owner's: the elements come from the approved delta (`delta-items.json`),
  the steward places them and names missing repositories (part A), and a separate, later step
  creates the missing repositories from the name and template the steward gave (part B, a
  script). Python never picks a repository. No placement in `apps/marketing/`. "Repositories never
  depend on repositories": this flow records no repository-to-repository dependency. Each item is
  placed in the one repository whose code changes for it, never in the repository that consumes
  it; the order between repositories is carried only by Task `blocks` edges (build order,
  `prd-to-spec.md` steps 11 to 13), not by a dependency of one repository's code on another's. A
  new repository is created standalone from its template. How the rule constrains code inside a
  repository (imports, packages) is enforced by the build pipeline, not by the Epic flows.
- 7.25: the element status matrix is read, never written: an element's row names the repository
  the seeding or the build pipeline recorded for it. An element with no row reads `unknown`, and
  the steward places it from the inventory and its own records.
- 7.23: no code is read to judge what is built; an element is never left unplaced because code for
  it may exist.
- 7.7: the three architecture cases decide which documents the steward reads (step 5); every case
  has build items to place.
- 7.6: there is no "nothing to build" outcome; the span always names at least one repository, and
  the no-implementation short cut is gone (steps 1, 2, 6).
- 7.20: a missing repository, like any missing prerequisite, is created as part of the Epic's work
  (part B); a creation failure stops the run, as an owner fact or for the incident-responder.
- 7.4: one corrective pass with exact findings; contention retried with backoff; structured causes.
- 7.11: inventory, fingerprinting, acceptance, every check and repository creation are code; only
  the placement judgment is a session.
- 7.14: the brief gives the steward paths and rules, not a theory of where items belong.
- 7.9: a repository creation that fails for want of GitHub credentials or organisation permission
  is an owner fact, returned as `requiredHumanActions`; every other failure goes to the
  incident-responder.

## 10. Open items

See QUESTIONS.md
