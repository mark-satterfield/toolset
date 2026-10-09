# Net-effect spec: `architecture`

Source of intent: `export const meta` of `<plugin>/workflows/architecture.js`, the agent
definitions under `<plugin>/agents/`, the `architecture-baseline` and `artifact-handoff` skills,
and `CONTEXT.md`. The JavaScript was read only for contracts (file names, JSON shapes, script
subcommands and result fields). Paths below use:

- `<arch>` = the architecture root (`$ATW_ARCH_PATH`; today
  `/Users/msat1971/projects/SkillSpoke/skillspoke-docs/docs/tech/architecture`), holding `arc42/`,
  `target/`, `built/` and `reference/`.
- `<art>` = the Epic's artifacts directory,
  `<control>/.claude/workflow-runs/artifacts/<epic-id>/`.
- `<work>` = `<art>/architecture/`.
- `<portfolio>` = `<plugin>/scripts/portfolio/`.

## 1. Purpose

The architecture step runs for every PRD and is never skipped. It assesses the effective
architecture in arc42 against the PRD, capability by capability, using the code on each repository's
`main` (including CDK), arc42 review states, open work in beads and AWS guidance. It also checks that
section 2 constraints and non-effective arc42 content (in-review views, open targets, build records)
are represented in the effective views. Where the effective architecture falls short, a team of
writers builds out a target from the non-effective documents, the code and the AWS MCP Server. The
team works under independent review, and the architecture-decider approves the result. Each
capability gets an explicit current-to-target action: retain, change, replace, add or retire. There
is no fixed specialty or proposal quota. The approved target and its delta are integrated into the
canonical arc42 views, independently checked and set effective, and superseded content is corrected or
removed. The Closure phase then walks the effective views from every build item to the elements its
work rests on. It writes each element that is not built and current as a prerequisite. Valid saved
work is kept, and only the inputs or evidence that changed are refreshed.

## 2. Produces and decides

After a successful run, all of the following are true:

1. `<work>/survey.json` and `<work>/survey.md` hold an accepted survey (SURVEY_SCHEMA, section 4)
   for the current inputs, sealed by `<work>/survey.json.baseline-inputs.json`. The survey has:
   - the target `subject`;
   - one `capabilities` entry per capability the PRD needs;
   - one `baseline` assessment entry per capability, with `designAction`, `documentationAction`,
     `implementationAction`, `disposition` and evidence refs;
   - the `coverage` rows.
2. The subject folder name is derived deterministically from the subject: lower-case, hyphens, with
   dates and the Epic, PRD and bead names removed (`archstate.subject_folder` / `subject_name`). Only
   a subject that leaves a non-empty folder name is used.
3. The design scope is fixed: the union of the assessment's `designWork` (designAction `modify`/`new`),
   `docWork` (documentationAction not `none`) and `unknowns`. An empty scope with a valid assessment
   means **check-only**: no writer runs.
4. One of the owner's three architecture cases (CONTEXT 7.7) is recorded as `architectureChange` in
   `target/<subject>/baseline.json`:
   - `none`: no architecture change. There is one set, the cited effective views
     (`entries[].documents`), with the note that current and future are the same. There is no delta.
   - `new`: an entirely new architecture. The target views are both the future and the delta, with
     no `delta/` folder.
   - `partial`: a partial change. The future set plus `delta/` holding the change alone.
   - `pending` exists only on a seeded draft before the writers have authored views. It never
     reaches a written target.
   In every case `baseline.json` carries `implementationWork` (the gaps between the future set and
   the code on `main`). So something always reaches the TRD and the Tasks.
5. Writers author views before any reviewer reviews them. Within a round the writers run in the order
   the coordinator lists them, and the last writer folds the others' contributions into its views
   (it is the round's reconciler). No `designOwner` field is stored. A legacy plan that carries one
   has it ignored.
6. `<work>/decision.json` / `decision.md` hold the decider's verdict: `approve` (with `choices`),
   `return` (with `returnTo`) or `owner-concern`. Only two kinds of concern reach the owner:
   `business-conflict` (two business requirements no design can satisfy together) and
   `architecture-conflict` (section 2 constraints that contradict each other or cannot be met with the
   PRD). Any other concern goes back to the team.
7. `<arch>/target/<subject>/` holds the approved draft with every view `lifecycle_state: in-review`.
   It also holds `baseline.json`: `version`, `arc42Revision`, `survey`, `surveySha256`,
   `designChanged`, `documentationChanged`, `entries`, `implementationWork`, `approvalFiles`,
   `architectureChange` and `note`. `<work>/target.json` holds the full `arch-target` report.
8. The effective version reflects the approved target. There are two ways to get there:
   - **Integration** (a design or documentation change, or any authored draft). The
     architecture-maintainer edits `arc42/` and the architecture-conformance-reviewer checks it. After
     at most 2 corrections, only the files the review found conforming are set
     `lifecycle_state: effective`. The others stay `in-review` and are reported as residual
     `openItems`.
   - **Publication only** (no design or documentation change and no authored draft). The in-review
     views the assessment marked `validate-existing` (`approvalFiles`) are set effective without a
     maintainer.
   Either way the changed files are committed (and pushed) in the vault repository with
   `docs(architecture): integrate the approved target for <subject>` or
   `docs(architecture): approve existing views for <subject>`.
9. Section 2 (`<arch>/arc42/02-architecture-constraints/`) is byte-identical to the start of the run.
   If any session changes it, the session runner's guard (`driver-contract.md` §8) restores it from
   the copy taken before that session and the run fails (hard limit).
10. `<arch>/target/<subject>/closure.json` holds the checked prerequisite closure:
    - `prerequisites[]`: each has `element`, `state` (`absent` | `stale` | `planned`), `views`,
      `requiredBy`, `requires`, `evidence`, `deployedBy`, `plannedBy`, `repository` and `reason`.
    - `rootEdges[]`, `satisfied[]`, `version` and `roots`.
    - There is no cycle. Every `planned` prerequisite is planned by an open bead.
    The path is `target/<subject>/closure.json` (beside `baseline.json`), not `delta/closure.json`:
    the code writes it there (`archclosure.write_closure`) and every Epic spec reads it there. The
    `meta.description` and PLAN S01a say `delta/`; see Open questions.
    `depscore.py arch-delta` later lists these entries as `prerequisite` items.
11. The step returns a result. On success it has `ok: true`, `subject`, `subjectName`, `targetDir`,
    `deltaDir`, `architectureChange`, `closure {path, workPath, prerequisites}`, `targetPath`,
    `surveyPath`, `decisionPath`, `architectureUpdate` (counts), `architectureUpdatePath`,
    `ledgerPath`, `rounds`, `openItems` and `noArchitectureChange` (publication-only path). On failure
    it has `{ok: false, stage, reason, cause}`, plus `requiredHumanActions` for the two owner-fact
    stages, `owner-concern` and `no-arch-path`.
12. The step writes nothing to beads. It only reads them: the survey and closure sessions read them
    through `atw-bd`, and `arch-closure` reads bead status.

## 3. Inputs

| Input | Source |
|---|---|
| Architecture root | `archPath` arg (driver sets it from `$ATW_ARCH_PATH`). Under it: `arc42/`, `arc42/02-architecture-constraints/` (owner, read-only), `arc42/04-solution-strategy/README.md`, `target/<subject>/` (open targets), `built/<subject>/`, `reference/architecture-documentation-model.md` (MODEL), `reference/diagram-and-model-types.md` (MENU) |
| PRD | `prd.path` (a vault file under `docs/sdlc/`) or `prd.body`; `prd.id`, `prd.title` |
| Epic | `epic.id` (`ssbd-…`); its prefix, `prd.id` and the PRD file's base name are the names a subject may not carry (`--forbid`) |
| Subject override | optional `subject` arg (`architectureSubject` on the composite) |
| Round bound | optional `maxRounds` (default 6; the composite passes `maxArchitectureRounds`) |
| Beads | the central beads database (`depscore.repo`, the composite's `emitTarget`), read-only, through `atw-bd` in sessions and `bead_status` in `arch-closure` |
| Artifact recorder | `artifacts {dir, relDir, epicId, script, phase: 'architecture', inputs, beadId}`; `script` is `<driver>/artifactio.py` (`$ATW_ARTIFACT_SCRIPT`). `inputs` are the PRD path plus `arc42-revision:{"dir":"<arch>/arc42","record":"<work>/arc42-revision.json"}` |
| Repositories | each repository's local checkout and its `main` (read with `git -C <repo> show/grep main:…`), as named by the polyrepo-steward |
| Repository deployments | per repository: the elements its `main` deploys or publishes (polyrepo-steward, Closure only) |
| AWS guidance | the AWS MCP Server documentation tools and `aws-core:*` skills (sessions only; no AWS account calls) |
| Schemas | `<plugin>/skills/artifact-handoff/schemas/architecture-writer.schema.json`, `architecture-review.schema.json`, `architecture-baseline.schema.json`, `checkpoint.schema.json`; the survey, coordinator, decision, maintain, conformance, repositories, deployments and closure schemas are defined in the workflow today (section 4 lists their fields) |

Unused args: `repoPath` and `seedRepos` are accepted by the JS and never read. Drop them.

## 4. Outputs

### Files under `<work>/` (all JSON unless stated)

| File | Written by | Key fields / purpose | Resume point? |
|---|---|---|---|
| `arc42-revision.json` | `archrevision.check` / `mark` | `{archRoot, revision, files{rel: sha256}, views{rel: sha256}, integrating, recordedAt}`. `views` are the arc42 files `survey.json`, `ledger.json`, `decision.json` name by absolute path, plus the files `draft/` holds copies of | binds all saved work to arc42 (step 2) |
| `tree-start.json` | `archstate.snapshot_tree` | per-file hashes of `arc42/`, `target/`, `built/` at start | no (diagnostic only; see Checks dropped) |
| `survey.json` | prd-reality-reconciler, accepted | SURVEY_SCHEMA: `subject`, `subjectReason`, `capabilities[] {name, requirements[], effectiveViews[], code[], openBeads[], openTargets[], notes?}`, `baseline[]` (architecture-baseline.schema.json: `id, kind, requirements, subjects, documents[{path,version,lifecycle_state}], code{state, behaviorEvidenceRefs, infrastructureEvidenceRefs}, awsGuidance, designAction, documentationAction, implementationAction, rationale, conflicts, current, target, disposition, suitabilityEvidenceRefs`), `openTargets[]`, `businessConflicts[{requirements, why}]`, `coverage[]` (COVERAGE rows: `id, subject, scope, obligation, sources, views, status, action, reason, evidenceRefs[{path,heading,repo,revision,url}], disposition, dispositionReason`), `summary` | **yes** (the most expensive artifact, about 850k tokens) |
| `survey.json.baseline-inputs.json` | `archbaseline.survey_freshness(seal=True)` | `{revision, surveySha256, contextSha, inputs[], repos[]}` | the survey's seal |
| `survey.json.receipt` | `jsonartifact.py` acceptance | integrity receipt of the accepted bytes | legacy; read leniently |
| `survey.md` | prd-reality-reconciler | readable survey | with `survey.json` |
| `*.meta.json` (beside `survey.json`, `survey.md`, `decision.md`, `architecture-update.json`, …) | `artifactio.py record` | `{artifact, path, epic_id, phase, created_at, updated_at, sha256, bytes, inputs}` | read by the composite's phase-level reuse (S01b) |
| `candidates/` | session submission helpers | in-progress candidate files and `*.progress.json` checkpoints | replaced (see section 8) |
| `plans/round<n>-plan-0.json` | coordinator, accepted | COORDINATOR_SCHEMA: `readyForDecision, reason, dispatches[{agentType, role, task, selectionReason, repairIds, files, answers, coverageIds, claimIds, claimFiles}], overlaps[{files, claimIds, agentTypes, reason}]` | **yes** |
| `rounds/r<n>-<seq>-<role>-<agentType>.json` | each writer/reviewer, accepted | writers: architecture-writer.schema.json (`files, claims[{claimId, claim, file, citation, supersedes, evidenceRefs}], answers[{findingId, response: fixed\|disputed, evidence}], repairAnswers?, businessConflicts, coverage, summary`); reviewers: architecture-review.schema.json (`findings[{claimId, claim, file, verdict, evidence, owner}], coverageChecks[{id, verdict, evidence}], resolutions[{findingId, verdict: accepted\|rejected, evidence}], repairChecks?, estimates?, summary`) | **yes**, one per dispatch |
| `ledger.json` | `archresume.resume_facts` | `contractVersion: 2, historicalAuthoring, assignments, roundPlans, claims, findings, savedResults, repairRequests, coverage…, coverageRevision`. Folded from `rounds/` and `plans/`. Sessions read it by path | derived (rebuilt on every read) |
| `draft/` | writers; `arch-target --seed` writes `draft/baseline.json` | arc42 section layout plus `delta/`; never `02-architecture-constraints/` | yes (the writers' views) |
| `target-check.json` | `arch-target --dry-run --out` | full dry-run report (`subject`, `subjectRefusals`, `draftWritten`, …) | no (recomputed) |
| `decision.json`, `decision.md` | architecture-decider, accepted | DECISION_SCHEMA: `round, verdict: approve\|return\|owner-concern, diligence[{check, present, where}], choices[{dispute, chosen, why}], returnTo[{agentType, missing}], ownerConcerns[{kind: business-conflict\|architecture-conflict, concern, evidence}], summary` | **yes** |
| `target.json` | `arch-target --out` | full target report (`targetDir, deltaDir, files, deltaFiles, architectureChange, note, designChanged, documentationChanged, implementationWork, approvalFiles, draftWritten`) | read by the composite (`depscore.py saved-target`, which also reports `ok` and `closureSaved`; the composite reuses the phase only when both are true) and by `prd-reconciliation`, `spec-authoring`, `trd-authoring` |
| `integrate-before.json` | `snapshot_tree` | tree hashes before integration | yes (integration measurement baseline) |
| `tree-last.json` | `arch-integration-files --save-last` | tree hashes after the last measurement | yes |
| `integration-files.json` | `arch-integration-files --files-out` | `touched[]`, `deleted[]`, `all[]`, `unreported[]`, `section2[]`, `outside[]`, `changedSinceLast[]` | yes |
| `architecture-update.json` | architecture-maintainer (accepted), or written directly on the publication-only path | MAINTAIN_SCHEMA: `changedFiles, createdFiles, deletedFiles, viewsChecked[{element, view, action: updated\|deleted\|added\|unaffected}], constraintIssues[], contradictions[], summary` | **yes** |
| `conformance-<n>.json` | architecture-conformance-reviewer, accepted | CONFORMANCE_SCHEMA: `conforms, reviewedFiles[], findings[{file, finding, evidence}], coverageChecks[{id, verdict, evidence}], summary` | **yes** (last one) |
| `closure-roots.json` | `arch-delta --roots-only --save` | the build roots: `items[{id, element, kind, views, requires…}]`, `architectureChange`, `note` | yes (deterministic) |
| `closure-deployments.json` | polyrepo-steward, accepted | `repositories[{name, path, lifecycle, deploys[{element, kind, evidence}]}], summary` | **yes** |
| `closure.json` | prd-reality-reconciler (CLOSURE mode), accepted | CLOSURE_SCHEMA: `prerequisites[]` (fields in section 2.10), `rootEdges[{item, requires, evidence}]`, `satisfied[{element, deployedBy, evidence}]`, `summary` | **yes** |
| `relay/`, `*.relay` files | relay plumbing | none needed | **dropped** |

### Vault writes (`skillspoke-docs` repository)

- `<arch>/target/<subject>/…`: an existing folder is replaced wholesale (`arch-target`). Views are
  `in-review`, plus `baseline.json`.
- `<arch>/target/<subject>/closure.json` (`arch-closure`).
- `<arch>/arc42/**` except section 2: the maintainer's edits, then `lifecycle_state: effective` on
  reviewed files (`arch-approve`).
- Commit and push of the integrated (or approved) files, staging only those paths (`arch-commit`).
  The `target/<subject>/` folder is not committed by this step. Its removal after elaboration is the
  composite's `arch-target-remove` (S01b).

### Bead writes

None.

## 5. Steps

`deterministic` steps become direct Python calls: imports of `<portfolio>` modules, or a subprocess
for `depscore.py` where an import is not clean. **No step starts a session to run a script.** Every
relay call (`relayKit.depscore`, `relayKit.run`, `relayKit.ensureJson`,
`relayKit.artifactRevision`, `relayKit.acceptArtifact` probes/accepts, `recordFiles`) becomes the
Python call named below. Agent sessions get file paths, never pasted data. Each session writes its
result file, and Python validates and accepts it.

Model and effort: "current" is what the JS passes as `effort`. The model comes from the agent's
frontmatter. Agents with `model: fable` are rerun on `opus` by the driver's fable recovery today
(merged question Q1 in `driver-contract.md`).

Every agent session in this flow runs inside the session runner's section 2 guard
(`driver-contract.md` §8): section 2 is fingerprinted and copied before the session and restored,
with a failure at stage `constraints-written`, if the session changed it.

**Preparation**

1. *deterministic: refuse missing input.* No architecture root → `stage: no-arch-path`, with one
   `requiredHumanActions` entry naming `ATW_ARCH_PATH` (owner configuration; the composite returns it
   and the driver holds the Epic for the owner). No PRD path or body, no Epic id, no artifacts
   directory → `stage: input`, cause `other` (a driver defect for the incident-responder).
2. *deterministic: bind saved work to arc42* with `archrevision.check(arch, work, stale_root=<art>)`.
   It returns `status: new | current | integrating | stale`.
   - `stale`: a view the saved survey, ledger or decision cites, or a draft copy, changed in `arc42/`.
     Everything in `<work>` is then moved to `<art>/stale-<timestamp>/architecture/` and the
     step restarts from the survey (see Open question 2). This is the one mechanism that sets stale
     architecture work aside; `prd-to-spec.md` §8 refers here.
   - `integrating`: this step's own interrupted integration. The work is current.
3. *(removed)* The section 2 fingerprint and copy at the start of the run is replaced by the
   session runner's guard around each session (above).
4. *deterministic: fold saved state* with `archresume.resume_facts(work, roster=ROSTER)`. This writes
   `ledger.json` and returns survey, baseline, coverage, rounds (`last`, `resumeRound`,
   `pendingPlan`, `openFindings`, `unreviewedClaims`, `writers`, `readyForDecision`), `decision`,
   `repairs` and `integration` facts. In the new code, run this after each step that saves round
   results rather than as a separate relay round trip.

**Survey**

5. *deterministic: survey freshness* with `archbaseline.survey_freshness(survey.json,
   inputs=[prd.path, MODEL, MENU, <arch>/arc42/02-architecture-constraints], context_sha=…)`. A survey
   that is `current` and has a non-empty `subject` is reused, and steps 6 to 8 are skipped. The binding
   covers:
   - the inputs;
   - every document and absolute evidence path the assessment cites (`.md` by view content, others by
     sha256);
   - the `main^{tree}` of every repository the survey cites;
   - the cited evidence state;
   - the baseline schema;
   - `contextSha` = sha256 of `relay.canonical({prdBody: prd.body or "", schema: SURVEY_SCHEMA})`.
   The new code must reproduce this exactly or the three saved surveys (CONTEXT 7.13) read as stale
   (see Open questions 3 and Q7).
6. *agent: polyrepo-steward*, list repositories `{name, path, role, lifecycle}`. Current: sonnet,
   effort `low`, inline schema. New: write `<work>/repositories.json`. Runs only when the survey must
   be produced. Correctness of the agent choice: see merged question Q17 (this may be deterministic
   from the steward's manifest).
7. *agent: prd-reality-reconciler (SURVEY mode).*
   - Inputs (paths): the PRD, `<arch>` (with MODEL, MENU and section 2), `repositories.json`, the
     beads database (read-only), the survey schema file, and the prior `survey.json` if any (retain
     valid evidence).
   - Output: `survey.json` + `survey.md`.
   - Current: opus, effort `medium`. That is right: this is the expensive assessment, and lowering it
     risks a wrong scope.
8. *deterministic: accept the survey.*
   - Parse JSON and validate SURVEY_SCHEMA.
   - Record `survey.md` and `survey.json` with `artifactio.record(…, phase='architecture',
     inputs=artifacts.inputs)`.
   - Seal with `survey_freshness(seal=True)`; `current` must be true, meaning the survey carries an
     assessment.
   - Re-fold with step 4.
9. *deterministic: subject check* with `archstate.write_target(draft, arch_root, subject,
   forbid, dry_run=True, baseline=survey.json)` → `target-check.json`. The subject is the `subject`
   arg, else `survey.subject`, else the PRD file base name (with the PRD base name not forbidden in
   that last case). Subject refusals → `stage: survey` (deterministic).

**Check (review-only), when item 3 of section 2 gives check-only**

10. *deterministic: seed the draft* with `write_target(…, seed=True)` → `draft/baseline.json`
    (`architectureChange` `none` or `pending`), then a dry-run check.
11. *agent: architecture-boundary-guardian* (the fixed Check plan; no coordinator).
    - Task: verify every `coverage` row in `ledger.json` against the effective views and the code on
      `main`; verify the `validate-existing` capabilities (`designReview`); report every section 2
      constraint or non-effective arc42 document that applies and is not represented, as a finding.
    - Inputs: PRD, `survey.*`, `ledger.json`, `draft/`, `<arch>`.
    - Output: `rounds/r1-1-reviewer-architecture-boundary-guardian.json` (review schema).
    - Current: sonnet (frontmatter `effort: low`), dispatched at `medium`.
    - Saved as round 1's plan through `resume_facts(plan=…)`.
12. *Recheck, once.* If the Check leaves open findings, re-run steps 6 to 8 with the RECHECK brief
    (prd-reality-reconciler reads the findings in `ledger.json` and `rounds/`, and sets
    `designAction`/`documentationAction` on the capabilities they concern). The subject is kept. If
    the reassessed survey now has a design scope, the rounds below run. Otherwise the findings go to
    the decider.

**Rounds, when the design scope is non-empty (or after a recheck that produced one)**

13. *agent: architecture-decision-workflow-coordinator*, round plan for round n.
    - Inputs (paths): PRD, `survey.*`, `draft/`, `rounds/`, `ledger.json`, `decision.json` (when
      returned or when team notes exist).
    - Inline facts in the brief: round n of the limit; the roster with each agent's coverage; the
      design scope with requirement ids; open notes (open repairs, repair checks needed, coverage
      gaps, unanswered or awaiting-resolution findings with owners, claims without a reviewer verdict
      per writer); agents returned to by the decider; dispatches refused or silent last round.
    - Output: `plans/round<n>-plan-0.json` (COORDINATOR_SCHEMA).
    - Current: sonnet, effort `medium`. That is right: routing only.
14. *deterministic: settle the plan.* All of these steps are kept:
    - Drop a dispatch whose agent is not on the roster.
    - Run each agent in its roster role.
    - Drop a writer dispatch naming a draft file with `..` or `02-architecture-constraints`.
    - Merge duplicate dispatches of one agent.
    - Keep in a writer's `answers` only open findings it owns. Assign unowned findings the
      coordinator named, and record the assignment.
    - Re-send a finding a writer left unanswered once, with that fact stated in its task. After
      that it stays open for the decider.
    - **Add writers when needed:** when the assessment names design or documentation work that no
      writer has authored and the plan has no writer, add one writer per such capability, ahead of
      the reviewers. The writer is chosen by the capability's `kind`: behavior →
      integration-pattern-architect, infrastructure → cdk-infrastructure-designer, documentation →
      architecture-diagram-author.
    - Order the plan as writers in the listed order, then reviewers.
    - Save the plan with `resume_facts(plan=…)`. If a saved pending plan exists, it stands and the new
      one is set aside (`planKept`).
    - If no dispatch remains, the decider rules (step 17).
15. *agents: writers, sequentially in plan order* (roster roles `proposer`, `diagram`).
    - Proposers (current effort `high`, model fable): integration-pattern-architect,
      persistence-architecture-specialist, security-architecture-designer, cdk-infrastructure-designer,
      event-schema-designer, api-contract-designer, graphql-schema-designer, domain-event-modeler,
      bounded-context-mapper.
    - Diagram authors (current effort `medium`, model sonnet): architecture-diagram-author,
      c4-diagram-author, uml-diagram-author.
    - Each writer receives: PRD, `survey.*`, `ledger.json` (its plan entry: task, owned files, answers,
      coverage ids, repair ids), `rounds/`, `draft/`, `<arch>`, MODEL, MENU and the writer schema. The
      writer listed last is told that it reconciles: it folds the other writers' settled
      contributions into its assigned views and identifies cross-view repairs.
    - Each writes its owned `draft/` files and `rounds/r<n>-<seq>-<role>-<agent>.json`.
    - Python validates each result before starting the next writer. Then it folds the ledger (step 4).
16. *agents: reviewers, in parallel.* Before them, deterministic: seed the draft and run the dry-run
    check (step 10). Reviewers then read the draft, or the canonical views if the draft could not be
    written.
    - Roster roles `reviewer` (architecture-pattern-challenger, architecture-tradeoff-skeptic,
      architecture-boundary-guardian, operational-readiness-reviewer, failure-mode-analyst) and
      `cost` (cost-architecture-reviewer, cost-impact-reviewer). Current effort is `medium` for all.
      The models are fable, sonnet and opus per frontmatter; operational-readiness-reviewer is opus
      with frontmatter effort `low`.
    - Each receives the same paths plus its `assignedClaims` / `claimFiles` / coverage ids / repair ids
      in the plan entry.
    - Output: `rounds/r<n>-<seq>-<role>-<agent>.json` (review schema; cost reviewers add `estimates`).
    - Then fold the ledger. The round counts as complete when every plan dispatch has a saved result
      file. `ready` = the coordinator's `readyForDecision`, or the round limit was passed.
17. *agent: architecture-decider.*
    - Inputs: PRD, `survey.*`, `rounds/`, `ledger.json`, `draft/` (seeded first, as in step 10),
      `<arch>/arc42`, `<arch>/target/`, plus the open notes as in step 13.
    - Output: `decision.json` + `decision.md`, then recorded with `artifactio.record`.
    - Current: opus, effort `high`. That is right: approval authority.
    The verdict leads to one of these:
    - `approve`: go to step 19.
    - `owner-concern` where every concern is `business-conflict` or `architecture-conflict`: return
      `stage: owner-concern` with `requiredHumanActions`, built as follows:
      - one action per concern, naming its kind, the concern and its evidence;
      - one more action telling the owner to delete `decision.json` once the PRD or section 2 says
        which side holds.
      A saved decision of this kind holds the Epic again on every rerun.
    - `owner-concern` with other kinds, or with no concerns named: back to the team. The next
      coordinator brief points at `ownerConcerns` in `decision.json`.
    - `return`: the agents in `returnTo` (and open repairs) go into the next coordinator brief.
    - `return` with no unresolved repair and nobody named: ask the decider once more, telling it that
      the return was not actionable and where the resolution evidence is (CONTEXT 7.4, clarified
      instructions). If it repeats a non-actionable return, fail at `stage: decide`, cause `other`,
      for the incident-responder. The target is never taken as approved without the decider's
      `approve`: neither the `meta.description` nor the `architecture-decider` definition provides
      an approval the decider did not give.
18. *Loop bounds.* At `lastRound >= maxRounds` (6) the decider rules on the target as the team left
    it. Past that, each return gets one more round. At `2 × maxRounds` → `stage: rounds`
    failure. These bounds come from the JavaScript, not from the intent; they stay only with an
    owner reason (Open question 6).
19. *(removed)* The section 2 check after the rounds is the session runner's guard around each
    session.

**Target**

20. *deterministic: write the target* with `write_target(draft, arch_root, subject, forbid,
    baseline=survey.json)`, saving the report as `target.json`.
    - Refusals stop the run with `stage: target`: no folder name left, a draft file in section 2, no
      authored view while design or documentation work is named, or a survey with no assessment.
    - A new-looking draft whose views show elements the effective version shows is written as
      `partial`, with those views copied to `delta/`.

**Integrate: publication only**, when `designChanged` and `documentationChanged` are false and
`draftWritten` is false

21. *deterministic:*
    - `archrevision.mark('integrating')`.
    - `archstate.promote(approvalFiles, arch_root=<arch>/arc42, reviewed=approvalFiles)`; any
      `refused` → `stage: approve`.
    - `commit_integration(<arch>/arc42, approvalFiles, message=…)`; not ok → `stage: commit`.
    - Write `architecture-update.json` as the publication receipt (`changedFiles` = approvalFiles,
      `viewsChecked` one per file with `action: updated`), and record it.
    - `archrevision.mark('integrated')`.
    - Go to Closure.

**Integrate: full integration**, otherwise

22. *deterministic:* `archrevision.mark('integrating')`. Then `snapshot_tree` → `integrate-before.json`,
    unless one is already saved.
23. *agent: architecture-maintainer.*
    - Inputs: `target/<subject>/` (and `delta/` for partial), `decision.json`, `ledger.json` (approved
      coverage rows), `survey.json`, PRD, `<arch>`, MODEL, MENU.
    - Task: the model's step 5 integration. For every element added, changed or removed, update or
      delete every effective view that shows it at every scope, and add new views. Leave
      `lifecycle_state` and `target/` untouched. Record each coverage row id in `viewsChecked`.
    - A RESUMING variant is used when `architecture-update.json` exists without a conforming review.
    - Output: `architecture-update.json` (MAINTAIN_SCHEMA).
    - Current: sonnet, effort `medium`.
    - Skipped when a saved update plus a conforming last review exist.
24. *deterministic: measure* with `archfiles.integration_files(arch, before=integrate-before.json,
    report=architecture-update.json, files_out=integration-files.json, save_last=tree-last.json)`.
    - `section2 > 0` → the runner guard has already restored and failed the session; any
      remaining count fails `stage: integrate` (deterministic, hard limit).
    - `unreported` files are added to the review list.
    - `outside` (outside `arc42/`) is recorded as a note.
25. *agent: architecture-conformance-reviewer.*
    - Inputs: the target and delta, `architecture-update.json`, `integration-files.json` (`touched`,
      `deleted`), `decision.json`, `ledger.json` (approved coverage rows), `<arch>`, and on later
      passes the previous review.
    - Output: `conformance-<n>.json`.
    - Current: sonnet, frontmatter `effort: low`, dispatched at `medium`.
26. *deterministic: review check* with `archfiles.review_check(review, files, coverage rows)`.
    - A touched file missing from `reviewedFiles` is a finding (`missed`).
    - An approved coverage row without a verified check is a finding (`coverageUnverified`).
    - `conforms` = reviewer says so, and no finding of either kind.
27. *Correction loop, at most 2 passes.* Each pass:
    - agent: architecture-maintainer (CORRECTING), with the review's findings by path, writing
      `architecture-update.json`;
    - deterministic: measure with `accumulate=True` and `last=tree-last.json` (the section 2
      count as in step 24);
    - if `changedSinceLast == 0`: stop; the findings stand as residuals;
    - otherwise review again (steps 25 and 26).
28. *deterministic:*
    - `promote(touched, reviewed=conformance.reviewedFiles)`. Any `refused` → `stage: approve`. Files
      in `unreviewed`/`failed` stay `in-review` and are reported.
    - `commit_integration(arc42, all, message=…)`, which commits and pushes. A failure →
      `stage: commit`.
    - `archrevision.mark('integrated')`.

**Closure (never skipped; runs after either Integrate path)**

29. *deterministic:* `archstate.delta_items(deltaDir, with_closure=False)` → save
    `closure-roots.json`. Refusals are recorded and the run carries on with the listed items.
30. *agent: polyrepo-steward* lists what each repository's `main` deploys or publishes, with
    file:line, named as arc42 names the element.
    - Output: `closure-deployments.json`.
    - Current: sonnet, effort `medium`.
    - It does not read the roots, so it can start in parallel with step 22 (see Open question 5).
31. *agent: prd-reality-reconciler (CLOSURE mode).*
    - Inputs: PRD, `<arch>`, `closure-roots.json`, `closure-deployments.json`, beads (read-only), the
      closure schema.
    - Output: `<work>/closure.json`.
    - Current: opus, effort `medium`.
32. *deterministic:* `archclosure.write_closure(<work>/closure.json, deltaDir, status_of=bead_status)`
    writes `target/<subject>/closure.json`.
    - Refused (a cycle, or not a closure object) → one corrective pass of step 31. The brief carries
      the exact refusals and the path of the refused check result.
    - Refused again → `stage: closure`.
33. Return the result (section 2, item 11).

**Agents accounted for.**
- Kept:
  - polyrepo-steward (steps 6, 30)
  - prd-reality-reconciler (steps 7, 12, 31)
  - architecture-boundary-guardian (step 11, and as a roster reviewer)
  - architecture-decision-workflow-coordinator (step 13)
  - the 9 proposers and 3 diagram authors (step 15)
  - the 5 reviewers and 2 cost reviewers (step 16)
  - architecture-decider (step 17)
  - architecture-maintainer (steps 23, 27)
  - architecture-conformance-reviewer (step 25)
- Dropped: workflow-command-runner (every one of its calls is a deterministic step above).
- Merged: none.
- Not dispatched: the agents the coordinator's definition lists but the roster does not offer
  (ubiquitous-language-writer, architecture-fitness-function-author). They stay out unless S02 adds
  them to the roster.

**Parallelism summary.**
- Reviewers within a round run in parallel; everything else in a round is sequential.
- Step 6 (repositories) can run alongside steps 2 to 5 when a survey is needed.
- Step 30 can overlap steps 22 to 28.
- All deterministic steps are local and fast.

## 6. Checks kept / Checks dropped

**Kept**

- *Missing architecture root, PRD or Epic → refuse.* Without them nothing can be assessed. The missing
  architecture root is the one owner fact (configuration): its own stage `no-arch-path`, so the
  composite returns owner facts only in that case and never for a driver defect (`stage: input`).
- *Section 2 unchanged by any session.* Hard limit (CONTEXT 6): the session runner's guard around
  every session (`driver-contract.md` §8) replaces this flow's own before-and-after snapshot. A
  session can write anywhere, and nothing later notices a changed constraint.
- *`arch-target` refusals.*
  - A subject with no name left: it would create a mis-named `target/` folder that every later phase
    reads.
  - A section 2 file in the draft: hard limit.
  - No authored view while design work is named: it would write an empty target and send no design to
    the TRD and Specs, and no later step re-derives it.
  - A survey with no assessment.
- *Subject check before the rounds* (the same refusal, moved earlier). It is the same check as at
  target write. Running it first avoids spending a full set of rounds on a subject that will be refused.
- *Draft file paths in a writer's plan entry must stay inside `draft/` and outside section 2.* A
  writer told to own `../arc42/…` would edit the effective version before approval. The only later
  detection (the tree snapshot after the rounds) merely logs.
- *Roster membership of coordinator dispatches.* An unknown agent cannot be dispatched. Dropping it
  keeps the plan runnable.
- *Schema validation of every accepted agent result file.* The results are folded by Python into the
  ledger, target and closure. A malformed file would silently drop claims, findings or prerequisites
  that nothing later recovers. This is done once, in Python, at acceptance.
- *Conformance review covers every touched file, and every approved coverage row has a verified check*
  (`review_check`). Without it, unreviewed views are set `effective` in the vault, and nothing later
  re-reviews effective views.
- *`promote` sets effective only the files the review names, and refuses section 2 or out-of-root
  paths.* Same reason, plus the hard limit.
- *`integration_files` measures what was actually written (`unreported`, `section2`, `outside`).* The
  maintainer's report can omit files. Unreported files would be committed or set effective without
  review.
- *`arch-closure` cycle refusal and the planned-by-open-bead rule.* A `requires` cycle becomes cyclic
  Task `blocks` edges in beads. A prerequisite planned by a closed bead would produce no Task and a
  blocker that never clears. Nothing later recomputes either.
- *Decision owner-concern filter* (only `business-conflict` / `architecture-conflict` reach the
  owner). This is owner rule CONTEXT 7.9, not a check: everything else goes back to the team.
- *Rounds bound (`maxRounds`, hard stop at 2×).* This is a stop condition for spend, not a quality
  check, carried from the JavaScript; it stays only with an owner reason (Open question 6).

**Dropped**

- *The whole checked relay*: argv sha256, RELAY64 envelopes, checksums, relay files, `relay-read`
  recovery, `relayrun.py`, `workflow-command-runner` sessions. Python calls the code directly.
- *Candidate/probe/accept/receipt protocol*: `probeArtifact`, `acceptArtifact` via
  `jsonartifact.py`/`artifactpublish.py`, research-recovery receipts, `artifactcontract.py`
  submit/checkpoint in every brief. These exist because the sandbox cannot read files. Python reads
  the session's result file and validates it once (kept above). Reuse is decided by the input
  fingerprint (section 8).
- *`sourceRevision` through `jsonartifact.py --source` per dispatch.* Python hashes inputs directly.
- *`dispatchFailureCause` regex over error text.* CONTEXT 7.4 forbids classifying by text. The session
  runner's structured result (exit status and fields) sets the cause.
- *Re-sending a dispatch that returned nothing, unchanged ("twice"), and saving a placeholder
  "NO RESULT" file.* Rerunning with nothing changed is not a reasonable retry (CONTEXT 7.4). `api` and
  `quota` causes pause for the driver's breaker. Any other cause goes to the incident-responder. A
  missing result is not papered over.
- *Tree snapshot after the rounds that only logs a diff count* (`tree-start.json` diff). It changes
  nothing. Drop it unless S02 wants the count as a ledger note.
- *Overlap warnings, survey/assessment warning counts, "plan kept" logs* as control flow. These are
  informational. Python may record them as notes. They decide nothing.
- *Separate per-file `recordFiles` runner sessions.* `artifactio.record` is called directly. It is
  provenance, not a check.
- *`ARCH_WHERE`, `INPUTS_RULE`, `PRD_RULE`, `COVERAGE_RULE`, `DESIGN_REVIEW_STANDARD` pasted into every
  brief, and the owned skill contracts the fable block concatenates into every prompt.* They become
  references to the agent definition and its skills (`architecture-baseline`, `subagent-contract`),
  per CONTEXT 5 (minimal context, paths not pasted data). S02 decides what, if anything, stays inline.
- *"A repeated non-actionable return is taken as approval."* No source in intent; a repeated
  non-actionable return fails at `decide` for the incident-responder (step 17).
- *This flow's own section 2 snapshot at the start (step 3) and check after the rounds (step 19).*
  Replaced by the session runner's one guard around every session (`driver-contract.md` §8).

## 7. Failure causes

| Failure point | `stage` | Cause | Retry? |
|---|---|---|---|
| Missing archPath | `no-arch-path` | none: owner facts (`requiredHumanActions`) | No; the driver holds the Epic for the owner |
| Missing PRD, Epic or artifacts dir | `input` | `other` | No; a driver bug for the incident-responder |
| `archrevision.check` cannot read `arc42/` | `survey` | `other` | No; incident |
| Section 2 snapshot or copy fails (the runner's guard) | stage of the step | `other` | No; incident |
| `resume_facts` raises `ResumeError` (saved file unreadable later) | `resume` | `other` | No (deterministic); incident |
| Session ends with API error or overload (structured from the session runner) | stage of the step | `api` | Yes: the driver's breaker (`breaker.py`) |
| Session hits usage or quota limit | stage of the step | `quota` | Yes: breaker |
| Session ends without a valid result file (schema invalid or absent), not api/quota | stage of the step | `other` | No unchanged rerun. One rerun is reasonable only with the specific validation errors in the brief (clarified instructions); then incident |
| Survey has no assessment after acceptance | `survey` | `other` | One rerun with the seal's `errors` in the brief; then incident |
| Subject refused | `survey` | `other` | No. Deterministic; the composite reports it (an owner `subject` override fixes it) |
| Coordinator writes no plan | `rounds` | `other` / `api` / `quota` | As above |
| Round dispatch unfinished (interrupted) | `rounds`, `resumable: true` | from the session | Resume reruns only the missing dispatches (section 8) |
| Decider writes no decision | `decide` | as above | As above |
| Decider owner-concern (business or section 2) | `owner-concern` | none: an owner hold, not a failure | No; owner acts and deletes `decision.json` |
| Decider repeats a non-actionable return after the one re-ask | `decide` | `other` | No; incident |
| Rounds exceed 2× limit | `rounds` | `other` | No; incident |
| Section 2 written by a session | `constraints-written` | `other` | No; restored, incident |
| `write_target` refusal | `target` | `other` | No; incident (the approved draft is wrong) |
| `promote` refused files | `approve` | `other` | No; incident |
| `commit_integration` fails on a git lock or non-fast-forward push | `commit` | `contention` | Yes: backoff 30 s doubling, cap 30 min |
| `commit_integration` fails otherwise | `commit` | `other` | No; incident |
| Integration measurement fails | `integrate` | `other` | No; incident |
| Integration wrote section 2 | `integrate` | `other` | No; restored, incident |
| Conformance reviewer or review check gives no result | `integrate` | from the session, or `other` | As above |
| `arch-closure` bead status read times out (`bd`/Dolt) | `closure` | `bd-timeout` (structured fact: merged question Q5 in `driver-contract.md`) | Yes: backoff as for contention |
| Closure refused twice | `closure` | `other` | No; incident |

`relay` has no producer in this flow after the rewrite.

## 8. Resume points

Rule: a rerun redoes no step whose saved result exists and whose input fingerprint is unchanged. It
starts no session before the first step that needs one. Fingerprints are computed in Python and
stored beside each result as `<result>.meta.json` by `artifactio.record` (the one input-record
format of every Epic flow), except the survey, whose existing seal
(`survey.json.baseline-inputs.json`) stays because the saved surveys carry it (CONTEXT 7.13). The
input lists below are the single source; `prd-to-spec.md` refers here.

| Saved result | Fingerprint inputs | A rerun after it redoes |
|---|---|---|
| `arc42-revision.json` | per-file arc42 hashes of the views the saved work cites | nothing, while the cited views are unchanged |
| `survey.json` (+ seal) | the `survey_freshness` binding (step 5): PRD, MODEL, MENU, section 2 folder, cited documents and evidence, cited repositories' `main^{tree}`, `contextSha` | nothing: Survey is skipped, **no session starts** |
| `repositories.json` | none (the steward's live facts); reused within a run | only when the survey reruns |
| `plans/round<n>-plan-0.json` | `ledger.json` + `survey.json` + PRD + n | nothing for that round's plan; a saved pending plan is resumed as is |
| `rounds/r<n>-<seq>-…json` | writer: PRD + `survey.json` + its plan entry; reviewer: the same + `draft/` | only the dispatches of the pending plan with no saved result |
| `decision.json` (`approve`) | `draft/` + `ledger.json` + `survey.json` + PRD + round + correction text | nothing, when no round ran after it (`decision.round >= lastRound` and no pending plan) |
| `decision.json` (owner-concern of owner kinds) | same | holds the Epic again; no session |
| `target/<subject>/`, `target.json` | `draft/` + `survey.json` | rewritten deterministically (cheap; no session) |
| `integrate-before.json` | taken once per integration | kept; later measurements diff against it |
| `architecture-update.json` + last `conformance-<n>.json` with `conforms: true` | target dir + delta + `decision.json` + `survey.json` + PRD | nothing: the maintainer and reviewer are skipped; `review_check` re-runs (deterministic) |
| `architecture-update.json` without a conforming review | same | maintainer RESUMING pass, then review |
| `closure-roots.json` | target dir | recomputed (deterministic) |
| `closure-deployments.json` | `closure-roots.json` (today); see Open question 5 | nothing |
| `<work>/closure.json` + `target/<subject>/closure.json` | roots + deployments + `arc42/` + PRD | nothing |

The saved work of `ssbd-mb689`, `ssbd-hdqid` and `ssbd-guuuz` (CONTEXT 7.13) must be read in place:
- `survey.json`, `survey.md`, their `.meta.json`, `survey.json.baseline-inputs.json`,
  `survey.json.receipt`;
- `plans/`, `candidates/`, `ledger.json`;
- `target-check.json`, `arc42-revision.json`, `tree-start.json`.

Of these, `candidates/` only matters if it holds a complete result for a dispatch whose final file
is missing. The new runner may promote such a candidate after schema validation, or ignore it (see
Open question 8). `relay/` is ignored.

## 9. Owner rules that apply

- **7.7 Three-case model.** It is decided deterministically by `archstate` from the draft and the
  assessment (`none` / `new` / `partial`), recorded in `baseline.json` with its note. The no-change
  case still carries `implementationWork`, and the Closure always runs, so something reaches the TRD
  and Tasks. Writers run before reviewers in every round. The last listed writer reconciles. No
  `designOwner` is stored, and a legacy one is ignored.
- **6 hard limits.**
  - Section 2: the session runner's fingerprint, copy and restore guard (`driver-contract.md` §8);
    the `integration_files` section 2 count; `promote` and `write_target` refusals; and briefs that
    say nothing is written there.
  - No secret exposure: the sessions read code and views only.
  - No destructive operation other than replacing `target/<subject>/` (this step's own folder) and
    moving stale saved work aside (`stale-<timestamp>/`, kept, not deleted).
  - Nothing in `apps/marketing/`: the polyrepo-steward's inventory is the source; a closure entry
    naming a marketing repository cannot become work, because `repo-scoping` rejects any placement
    under `apps/marketing/`, prerequisites included (`repo-scoping.md` step 6).
- **7.4 Retries.** Structured causes come from the session runner and the script results. There are
  no unchanged reruns. Clarified reruns are allowed: an unanswered finding is re-sent once with the
  omission named, and the decider is re-asked once after a non-actionable return (a repeat goes to
  the incident-responder). Git push contention backs off.
- **7.9 Who gets asked what.** Only `business-conflict` and `architecture-conflict` (stage
  `owner-concern`) and a missing architecture root (stage `no-arch-path`) reach the owner, as
  `requiredHumanActions`; the composite returns them and the driver writes the owner inbox and the
  hold. Every technical gap is decided by the team or the decider.
- **7.10 Repositories.** Repository facts come from the polyrepo-steward. The prd-reality-reconciler
  never looks for repositories itself.
- **7.11 Deterministic over agentic.** Subject naming, case detection, target writing, approval,
  commit, measurement, review coverage, closure checking and delta listing are code.
- **7.13 Saved work.** Section 8.
- **7.14 Briefs.** Briefs carry paths and the expected outcome. The ledger's open items are facts with
  file locations, never theories.

## 10. Open questions

**Q7 [S02] (merged; also asked in `prd-reconciliation.md`). Is any commit on a cited repository's
`main` meant to invalidate saved work, or should code evidence be bound per cited file?** The
survey seal binds the `main^{tree}` of every repository the survey cites, and the detailing records
`git-main:<repo>`, so any commit (including Tasks of the same Epic merged later) invalidates the
about 850k-token survey or costs a fresh opus detailing session.

**Q17 [S02] (merged; also asked in `repo-scoping.md`). Can repository facts come from the steward's
manifest (`.polyrepo/manifest.yaml` through the `polyrepo` tool) deterministically instead of a
polyrepo-steward session?** This covers the Survey's repository list (step 6), and in
`repo-scoping` the creation of a repository the target names with name and template (`polyrepo.py
create` still needs `--space` and `--purpose`); `repo-scoping.md` step 4 already takes the
inventory in code. The Closure's deployments inventory (step 30) needs reading code and likely
stays an agent.

1. **[S02] Closure path fallback.** Settled: the contract is `target/<subject>/closure.json`
   (`archclosure.write_closure` writes it there, `merge_closure` and `resumefacts.saved_target`
   read it there, and every Epic spec agrees). The discrepancy: the architecture `meta.description`
   ("writes those ... to delta/closure.json") and PLAN S01a ("Closure output (`delta/closure.json`)")
   say `delta/`; S08 corrects the meta description. Open: does the `delta/closure.json` fallback
   read (`merge_closure`, `resumefacts.saved_target`) stay for old saved targets?
2. **[S02] Stale saved work.** `archrevision.check` moves all of `<work>`, including the about
   850k-token survey, aside when any arc42 view the survey, ledger, decision or draft cites changed.
   Should the new flow instead re-run only the parts bound to the changed views? For example: keep
   the survey when its own seal is still current, and drop only the rounds and decision.
3. **[S02] Survey `contextSha`.** `contextSha` includes SURVEY_SCHEMA's canonical JSON. Must the new
   code reproduce the JS schema byte-for-byte, or reuse the saved `contextSha`, to keep the three
   saved surveys current? (The `main^{tree}` half of the old question is Q7 above.)
5. **[S02] Deployments inventory binding.** Today it is fingerprinted only to `closure-roots.json`,
   yet its content depends on every repository's `main`. What should invalidate it? Can it run in
   parallel with the integration?
6. **[owner] Round limits.** `maxRounds = 6` and the hard stop at 12 rounds come from the
   JavaScript, not from the `meta.description` or the agent definitions. They are a spend bound.
   Are they wanted, and at what values? (A repeated non-actionable return is no longer taken as
   approval: settled, S01h finding 30.)
7. **[S02] Effort.** The code passes `medium` to architecture-conformance-reviewer,
   architecture-boundary-guardian (Check) and operational-readiness-reviewer, whose frontmatter says
   `low`. Which wins? (The `fable` half of the old question is merged question Q1 in
   `driver-contract.md`.)
8. **[S02] `candidates/` in saved work.** Promote a complete, schema-valid candidate whose final file
   is missing, or ignore `candidates/` entirely?
10. **[S02] Inline brief text.** Which of today's inline rule blocks (`ARCH_WHERE`, `DRAFT_RULES`,
    `COVERAGE_RULE`, `DESIGN_REVIEW_STANDARD`, the RECHECK block) are already covered by the agent
    definitions and skills, and which must move into them before the briefs shrink to paths?
11. **[S02] Schemas defined only in the JS.** SURVEY, COORDINATOR, DECISION, MAINTAIN, CONFORMANCE,
    REPOSITORIES, DEPLOYMENTS and CLOSURE are defined only in `architecture.js`. Where do they live
    in the new code? Do they become files under `skills/artifact-handoff/schemas/` beside the
    writer, review and baseline schemas?
- Old question 4 (repository listing) is Q17 above.
- Old question 9 (marketing repositories): settled by `repo-scoping.md` step 6, which rejects any
  placement under `apps/marketing/`, prerequisites included.
