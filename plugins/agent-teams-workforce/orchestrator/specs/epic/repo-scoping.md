# Net-effect spec: `repo-scoping`

Source: `<plugin>/workflows/repo-scoping.js` (`meta.description`), its call site and replay in
`<plugin>/workflows/prd-to-spec.js` (`runRepoScoping`, `misplaced`, `readSavedSpan`), agent
`<plugin>/agents/polyrepo-steward.md`, skill `<plugin>/skills/polyrepo-repo/SKILL.md`, CONTEXT
sections 6 and 7. `<art>` below is the Epic's artifact directory,
`<control>/.claude/workflow-runs/artifacts/<epic-id>/` (`artifactio.working_dir`).

## 1. Purpose

Rule the repository span of one PRD from its approved architecture. Each build item that
`depscore.py arch-delta` lists for the approved target (an element a delta view shows, an
implementation gap of the baseline handoff, or a prerequisite from the architecture step's
closure) is placed in exactly one repository whose code changes for it, or recorded as having no
code in this project. A prerequisite is placed in the repository that deploys it (its closure
entry's `deployedBy`), or in the repository its closure entry names, created when it does not
exist; a prerequisite an open bead of another Epic plans (`state: planned`) is recorded as having
no code here. Each new repository the approved target or a prerequisite names is created by the
`polyrepo-steward`. The span is the distinct repositories the placements name. A span with no
repository means there is no implementation work for this PRD; that is a valid result, not a
failure.

## 2. Produces and decides

After a successful run:

- Every build item id appears exactly once: in one placement or in `noCode`.
- No placement names the control repository (`$ATW_CONTROL_REPO`), the repository that holds the
  architecture (`$ATW_ARCH_PATH` or a parent of it), or a repository under `apps/marketing/`.
- Every `planned` prerequisite is in `noCode` with the bead that plans it as the reason.
- Every repository the target or a prerequisite names for creation either exists (created now or
  by an earlier run of the same PRD, found in the live inventory) or is listed in
  `creationFailures`.
- `<art>/repo-scoping.json` holds the ruling and `<art>/repo-scoping.json.meta.json` records its
  input fingerprints.
- The flow's result carries `repos` (the span, ordered by first placement), `placements`,
  `noCode`, `createdRepos`, `creationFailures`, `spanRationale`, and an empty `repos` when nothing
  has code here.

## 3. Inputs

| Input | Where it comes from |
|---|---|
| Epic id | the composite (`epic.key`, the bead id) |
| PRD path | the composite (`prd.path`, under `$ATW_PRD_DIR`) |
| Build items | `<art>/delta-items.json`, written by `depscore.py arch-delta --delta-dir <deltaDir> --save <art>/delta-items.json` in the composite's Architecture phase. Item fields used: `id`, `element`, `views`, `kind` (`implementation-gap`, `prerequisite`, or absent for a view item), and for a prerequisite `state` (`absent`, `stale`, `planned`), `requiredBy`, `deployedBy`, `plannedBy`, `repository {name, template, reason}`. |
| Approved target | `targetDir` (`<archPath>/target/<subject>/`), `deltaDir` (`<targetDir>/delta/`, present only for a partial change), `architectureChange` (`partial`, `new`, `none`) and `note`, all from the `arch-delta` result |
| Architecture records | `<art>/architecture/decision.md`, `<art>/architecture/target.json` |
| Live repository inventory | `uv run <plugin>/skills/polyrepo-repo/scripts/polyrepo.py inventory --json` |
| Repositories to avoid | the corrective-pass list (section 5, step 6): `{repoPath, reason, itemIds}` |
| Paths that never hold placed work | `$ATW_CONTROL_REPO`, `$ATW_ARCH_PATH`, `$SKILLSPOKE_ROOT/apps/marketing/` (the `marketing-*` repositories) |

No bead field or metadata key is read.

## 4. Outputs

| Output | Format and key fields |
|---|---|
| `<art>/candidates/repo-scoping.json` | the steward's raw result, schema below; kept as the input to the acceptance step |
| `<art>/repo-scoping.json` | accepted ruling. `placements[]: {repoPath, repoName, itemIds[], frontend, rationale, created}`, `noCode[]: {itemId, reason}`, `createdRepos[]: {name, repoPath, template, purpose, itemIds[]}`, `creationFailures[]: {proposedName, itemIds[], error}`, `surveySummary`, `spanRationale`. Read later by `depscore.py saved-span` (`resumefacts.saved_span`), by `beadwrite._no_code` (for `closure-edges`), and named as an input of each `recon:<slug>` and `spec:<slug>` step. |
| `<art>/repo-scoping.json.meta.json` | `artifactio.py record <art>/repo-scoping.json --epic <epic> --phase repo-scoping --inputs <inputs>`: `sha256`, `bytes`, `inputs[]` with each input's hash |
| Flow result to the composite | `{ok, repos, placements, noCode, createdRepos, creationFailures, warnings?, artifactPath, spanRationale, ledger: {phase: 'repo-scoping', beadId, subject, chosen: ['polyrepo-steward'], mode: 'fixed', repoCount, itemCount, createdRepoCount, ok}}`. The driver's `decisions.py` (`_scoping`) renders `placements`, `createdRepos`, `noCode` and `spanRationale` from it. |
| New repositories | created by the steward with `polyrepo.py create`, locally and on GitHub; the polyrepo tool commits its own manifest, changelog and beads fleet list. |

No bead write and no vault write.

## 5. Steps

1. **Refuse a missing target** (deterministic, Python). No `targetDir` → fail at stage `input`,
   cause `other`. An empty item list → succeed with an empty span and the warning "no build item to
   place"; no session is started.
2. **No-implementation short cut** (deterministic, Python; currently in the composite). When the
   `arch-delta` result has `baselineValidated`, `implementationComplete`, `implementationWork == 0`
   and no prerequisite item, write the ruling with every item in `noCode` ("the validated
   architecture assessment requires no implementation work") and an empty span, and start no
   session.
3. **Fingerprint the inputs and look for saved work** (deterministic, Python). Hash the PRD,
   `decision.md`, `target.json`, `delta-items.json`, `targetDir`, `deltaDir` and the avoid list.
   If `<art>/repo-scoping.json` exists and its `.meta.json` inputs match, reuse it (step 7 checks
   still apply to it, so a saved ruling with a placement in a never-placed repository is not
   reused). Otherwise, if `<art>/candidates/repo-scoping.json` exists with a revision sidecar that
   matches this fingerprint and parses, go to step 5 without a session.
4. **Take the inventory** (deterministic). Run `polyrepo.py inventory --json`, write the result to
   `<art>/repo-scoping.inventory.json`. (Today the steward runs it inside its session; running it
   here gives the steward a file path and removes a tool turn.)
5. **Place and provision** (agent `polyrepo-steward`). Inputs, as paths: `delta-items.json`, the
   inventory file, `targetDir`, `deltaDir` and the `architectureChange` case (CONTEXT 7.7: partial
   = target plus delta of the change; new = target views are also the delta; none = the effective
   views the target's `baseline.json` cites, with build items from its `implementationWork` and
   `closure.json`), the avoid list when present, the output path
   `<art>/candidates/repo-scoping.json` and its schema. The brief states the placement rules of
   section 1 and the rules the current prompt states: place by the repository that owns the element
   on its `main`; an element with no code here (external system, or a managed service configured in
   another item's repository) goes in `noCode` with the reason; before creating a repository look
   in the inventory for one that already serves the element, including one an earlier run of this
   PRD created; create only repositories the target or a prerequisite names, with the name,
   template and reason given (or the template whose kind matches the element); on a creation
   failure fix what the error names and try once more, then report it in `creationFailures`;
   change nothing in any repository beyond creating the named ones. Model and effort today: the
   agent's `sonnet` with the workflow's `effort: 'high'` override (the definition says `medium`).
   Keep `sonnet`/`high`: a wrong placement propagates into every later step; S07 measurement may
   lower it. Runs in parallel with `trd-authoring` (the composite starts both after Architecture).
6. **Accept and check the placement** (deterministic, Python). Parse the candidate against the
   schema. Then compute, from the parsed file and `delta-items.json`:
   - ids placed twice, ids not placed at all, ids that are not build items (dropped with a warning);
   - placements in a never-placed repository (control repository, architecture repository,
     `apps/marketing/`);
   - prerequisites placed elsewhere than their `deployedBy`, and `planned` prerequisites placed
     anywhere.
   If any of the first two kinds, or a never-placed repository, or a `planned` prerequisite placed,
   is found: run step 5 **once more** with the exact findings (the ids and the repositories, with
   reasons) as the avoid list and gap feedback. If the second pass still has them, fail at stage
   `repo-scoping`, cause `other`. A prerequisite placed against its `deployedBy` after the
   corrective pass stands with a warning (open question 2).
7. **Save** (deterministic, Python). Write `<art>/repo-scoping.json` (canonical JSON), then
   `artifactio.py record` it with the step 3 inputs. Build the flow result: `repos` in first-
   placement order, `frontend` defaulting to false, `repoName` defaulting to the path basename.
   An empty span is logged ("every item has no code in this project") and returned with `ok: true`.

The relay calls of the current script map as follows: `relayKit.artifactRevision` (jsonartifact.py
`--source`) → step 3 hashing in Python; `relayKit.authorArtifact` probe and accept (jsonartifact.py
`--candidate --final`) → steps 3 and 6 in Python; `relayKit.run ... artifactio.py record` → step 7
called directly; `depscore.py saved-span` (composite) → step 3 reads the file directly. No
`workflow-command-runner` session remains.

## 6. Checks

**Checks kept**

- Every item placed exactly once (step 6). Without it an item is dropped or built twice; nothing
  later sees an unplaced item, since detailing and Task decomposition only receive placed items.
- No placement in the control repository or the architecture repository (step 6, moved here from
  the composite's `misplaced`). Without it Stories and Tasks target the pipeline's own repository or
  the vault; no later step rejects a repository path.
- No placement under `apps/marketing/` (step 6). Hard limit (CONTEXT 6, 7.10).
- A `planned` prerequisite is not placed (step 6). Without it a duplicate of another Epic's planned
  work reaches beads; `task-decomposition` would write Tasks for it.
- Candidate parses against the schema (step 6). Without it the Python cannot read the ruling; a
  parse failure is a failed step, not wrong output.
- Saved-ruling reuse re-applies the never-placed check (step 3). Without it an old ruling made
  before the rule existed is replayed into recon and spec.

**Checks dropped**

- "The run fails when no placement names a repository" (in `meta.description`, not in the code):
  dropped. An empty span means no implementation work (PLAN S01c note, CONTEXT 7.6 "recorded
  nothing to build").
- Unknown item ids: not a failure; ignored with a warning (they change nothing downstream).
- Silent conversion of unplaced items to `noCode` (current code, after the steward session and in
  `readSavedSpan`): replaced by the step 6 corrective pass and then a failure, because it hid
  dropped work.
- `inputBinding.ok` and relay-receipt checks, the `dispatchInterruption`/`dispatchOutcome`
  plumbing, `ART`/`RELAY_RUNNER` presence checks: sandbox and relay workarounds; gone with the
  relay.
- The `recorded.ok`/`persistErrors` path: `artifactio.record` is a direct call; an exception is a
  failed step with its cause.
- A check that each `repoPath` exists on disk: not added. A wrong path fails `prd-reconciliation`
  loudly at `git-main:` hashing; no wrong output is written.

## 7. Failure causes

| Failure point | Cause | Retry reasonable? |
|---|---|---|
| No `targetDir` | `other` | No (the composite's Architecture result is wrong; incident-responder). |
| `polyrepo.py inventory` exits non-zero | `contention` when the tool reports a git lock; otherwise `other` | Contention: yes, backoff from 30 s. Otherwise no. |
| Steward session: API error or overload | `api` | Yes, through `breaker.py`. |
| Steward session: usage or quota limit | `quota` | Yes, through `breaker.py`. |
| Steward session ends with no candidate file, or a candidate that fails the schema | `other` | Once, with the parse error as feedback (clarified instruction); then no. |
| Placement findings remain after the corrective pass | `other` | No; incident-responder. |
| `artifactio.py record` fails | `other` | No. |

Causes are set from the exit status, the session's structured result, or the parse exception at
the point of failure, never from error text. `relay` has no producer in this flow.

## 8. Resume points

| Saved result | Fingerprint inputs | A rerun after it redoes |
|---|---|---|
| `<art>/repo-scoping.inventory.json` | none; it is always retaken when step 5 must run | only the inventory command |
| `<art>/candidates/repo-scoping.json` + revision sidecar | the step 3 fingerprint | nothing before step 6; no steward session |
| `<art>/repo-scoping.json` + `.meta.json` | PRD, `decision.md`, `target.json`, `delta-items.json`, `targetDir`, `deltaDir`, avoid list | nothing; the flow returns the saved ruling |

A changed closure (new prerequisite) changes `delta-items.json`, so the ruling is redone; a
change confined to other Epics' files is not an input and redoes nothing. Repositories created by
an earlier, interrupted run are found again in the inventory, so a rerun does not create them
twice.

## 9. Owner rules that apply

- 7.10: the steward owns placement and creation; Python never picks a repository. No placement in
  `apps/marketing/`.
- 7.7: the three architecture cases decide which documents the steward reads (step 5).
- 7.6: an empty span is "nothing to build", a valid end state for the Epic's done rule.
- 7.4: one corrective pass with exact findings; contention retried with backoff; structured causes.
- 7.11: inventory, fingerprinting, acceptance and every check are code.
- 7.14: the brief gives the steward paths and rules, not a theory of where items belong.
- 7.9: a repository creation that fails for want of GitHub credentials is an owner fact (open
  question 4).

## 10. Open questions

1. **Ownership of the never-placed check and the corrective pass.** This spec moves the
   composite's `misplaced` check, `avoidRepos` re-dispatch and `readSavedSpan` replay into this
   flow. S01b's `prd-to-spec` spec must not keep a second copy; S01h reconciles.
2. **Prerequisite placed against its closure `deployedBy`.** `meta.description` says the run fails;
   the code lets the steward's placement stand with a warning. This spec includes it in the
   corrective feedback and then lets it stand, since the steward owns placement (7.10). Owner or
   S02 to confirm.
3. **Unplaced items after the corrective pass.** `meta.description` says fail; the code records
   them as `noCode`. This spec fails. Confirm.
4. **Creation failures.** Today a failed creation is only a warning, and its items are then
   unplaced. Which creation errors are owner facts (GitHub credentials, organisation permissions)
   that should go to the owner inbox, and which are `other`?
5. **Live inventory as a fingerprint input.** The ruling is not redone when a repository appears
   or is renamed after it was saved. Should the inventory (or the manifest's revision) be a resume
   input?
6. **Driver resume ruling.** `artifactio.py plan` rules freshness from the `.meta.json` inputs.
   Today `record` gets only the PRD, `decision.md` and `target.json`; this spec adds
   `delta-items.json`, `targetDir` and `deltaDir`. S01g/S02 confirm the driver uses the same list.
7. **Could creation be deterministic?** When the target gives name and template, `polyrepo.py
   create` still needs `--space` and `--purpose`. If the target always gave those, creation could be
   a Python step and the steward session could be skipped for a span that needs no judgment.
</content>
</invoke>
