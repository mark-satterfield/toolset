# Index of the Epic pipeline's artifacts and bead writes

Failure handling: bounded transient retries and quota pauses remain. An ordinary item failure is recorded and excluded from selection for the current invocation; other eligible items continue. Setup, code, schema, and runtime type defects stop new dispatch, preserve the original diagnostic, and let current paid steps finish. Named within-step corrective passes remain bounded content work; failed runs do not dispatch repair or diagnosis agents.

Steps S01h and S01i. Every file, vault path and bead write the Epic flows produce, with the step that
produces it and the steps that consume it. A step is cited as `<spec>#<step number>`, the number
in that spec's Steps section; `driver` means the driver at `<control>/ops/sdlc-automation` as
`driver-contract.md` describes it. When a spec and this index disagree, the spec is right and this
index is stale.

Path placeholders:
- `<work>` = `<control>/.claude/workflow-runs/artifacts/<epic-id>/` (the Epic's artifact directory,
  `<art>` in some specs); `<arch-work>` = `<work>/architecture/`.
- `<arch>` = the value of the `ARCH_PATH_ENV` driver environment variable, defined by the
  `pipeline-contracts` skill (`<plugin>/skills/pipeline-contracts/schemas/driver-surface.schema.json`):
  the architecture folder of the `skillspoke-docs` vault.
- `<slug>` = a span repository's artifact slug; `<subject>` = the target's folder name.
- `<workDir>` = the work directory of an owner-run portfolio flow (`wsjf-scoring`,
  `dependency-assessment`, `task-dependency-assessment`). None of them is part of the Epic
  pipeline: Epic scoring and Epic dependency assessment belong to the future readiness process
  (CONTEXT 7.17), and `task-dependency-assessment` is deleted in S08.

Open items live only in QUESTIONS.md.

Every `.meta.json` named below is written by `artifactio.record` beside its file and is read by
the same flow's reuse step (the one input-record format, `driver-contract.md` §8); where it has
another reader, the row says so.

The element status matrix (CONTEXT 7.25) is written by no Epic flow: it is seeded once with state
`unknown` (PLAN S05a), and only the build pipeline sets `built` or `deployed`. The Epic flows read
it in `architecture#5`, `#7` (the survey, through `survey-matrix.json`), `architecture#32` (the
Closure) and `repo-scoping#3`, `#5`, `#6` (placement). Its tracked location and snapshot contract are settled in DESIGN.md section 10; the matrix and
snapshot are listed below.

The `prd-reconciliation` step and its files (`recon-<slug>.json`, `recon-<slug>.bundles.json`) are
removed (CONTEXT 7.10, 7.23). The per-repository detailing contract they carried is defined only by
`<plugin>/skills/artifact-handoff/schemas/recon.schema.json` (Python: `recon_contract.py`; driver:
`ops/sdlc-automation/reconcontract.py`).

The Format column names each file's contract; it never restates fields. A schema file named there
is under `<plugin>/skills/artifact-handoff/schemas/`.

## Artifacts

### `prd-to-spec` (the composite)

| Path pattern | Producer | Consumers | Format |
|---|---|---|---|
| `<work>/delta-items.json` | `prd-to-spec#7` (`depscore.py arch-delta --save`) | `repo-scoping#1`, `#3` (input), `#5`, `#6`; `trd-authoring#2` (input), `#3`; `spec-authoring#1` (placed items joined to it), `#5`, `#8` (input); `task-decomposition#2` (input), `#5`, `#9`, `#10`; `prd-to-spec#11` (`closure-edges`) | JSON: `target-report.schema.json` (`target_contract.DeltaResult`; the implementation-work facts come from the element status matrix) |
| `<work>/closure-edges.json` | `prd-to-spec#11` (`depscore.py closure-edges --out`) | `prd-to-spec#12` (agent input), `#13` | JSON: `{ edges[{ from, to, reason }], summary.warnings }` |
| `<work>/candidates/task-deps.json` | `prd-to-spec#12` (agent `task-dependency-mapper`; required when the span has two or more repositories) | `prd-to-spec#12` (Python acceptance) | JSON: `task-deps.schema.json` (`task_deps_contract.TaskDeps`) |
| `<work>/task-deps.json` (+ `.meta.json`) | `prd-to-spec#12` (accepted copy) | `prd-to-spec#12` (reuse), `#13` | JSON, same shape |
| `<work>/task-edges/all.json` | `prd-to-spec#13` (`depscore.py write-all-task-edges --out`) | none: retained as diagnostic evidence | JSON: write summary `{ blockers, added, removed, standing, rejected }` |
| `<work>/STEPS.md` | after each phase: `prd-to-spec` (`artifactio.complete_step`), `spec-authoring#13` | `driver` (`artifactio.plan` -> the `resume` argument; `observe.py` accepted and stale steps; an open item in QUESTIONS.md) | text: one completed step id per line |
| `<work>/run.json` | `prd-to-spec#17` | none: read by the driver (handback `detailPath` -> failure evidence and human-action detail, `driver-contract.md` §4) and the owner | JSON: the run record, `<plugin>/orchestrator/core/manifest.py` `RunManifest` |
| the handback (`run.py --handback`, and handbacks the driver builds) | `prd-to-spec` (`<plugin>/orchestrator/run.py`, one atomic write when the flow ends); `driver` (`orchestrated.failed_handback`, for a dispatch that raised or was interrupted) | `driver` (`orchestrated.read_handback`, validated with `handback_contract.validate`; `driver-contract.md` §4) | JSON: `<plugin>/orchestrator/core/handback_contract.py` `HandbackDocument` |
| `<control>/ops/sdlc-automation/state/ledger.jsonl` (events appended) | `driver` (`ledger.append` in `<control>/ops/sdlc-automation/ledger.py`, called by `supervisor.py`, `keeper.py`, `storydeploy.py`, `failures.py`, `execidentity.py`, `telemetry.py`); no Epic flow writes it | `driver` (the `ledger` read functions, called by `outcomes.py`, `observe.py`, `runview.py`, `lane.py`, `repeats.py`, `repeatfail.py`, `keeper.py`, `supervisor.py`, `execidentity.py`, `dashboard.py`; `attemptview.py` interprets the events read) | JSON lines; the event set (`EventType`, `EVENT_TYPES`), the envelope and field-name constants (`KEY_*`) and the typed shape of `handback` events (`HandbackFields`) are defined only by `<control>/ops/sdlc-automation/ledgerevents.py`; the other event types have no typed field shape there |
| `<arch>/target/<subject>/` (deletion, committed in the vault) | `prd-to-spec#15` (`depscore.py arch-target-remove`) | none: the removal is the end state | git commit in the vault repository |

### Matrix and run inputs (DESIGN sections 4 and 10)

| Path pattern | Producer | Consumers | Format |
|---|---|---|---|
| `<control>/ops/sdlc-automation/element-matrix.json` | seed/build Python only | dispatch snapshot | JSON matrix, DESIGN 10 |
| `<work>/matrix-snapshot.json` | Python dispatch snapshot | Closure classification; placement | JSON matrix snapshot, DESIGN 10 |

### `architecture`

| Path pattern | Producer | Consumers | Format |
|---|---|---|---|
| `<arch-work>/arc42-revision.json` | `architecture#2` (`archrevision.check`), updated by `#21`, `#22`, `#28` (`archrevision.mark`) | `architecture#2` (next run); `driver` (`arc42-revision` input kind of the `architecture` step's record) | JSON: `{ archRoot, revision, files{}, views{}, integrating, recordedAt }` |
| `<work>/stale-<timestamp>/architecture/` | `architecture#2` (moves stale saved work aside) | none: kept, not deleted, for the owner | the moved files |
| `<arch-work>/repositories.json` | `architecture#6` (Python inventory; DESIGN 11.1) | `architecture#7` | JSON: `[{ name, path, role, lifecycle }]` |
| `<arch-work>/survey.json`, `survey.md` (+ `.meta.json`) | `architecture#7` (agent `prd-reality-reconciler`, SURVEY), accepted `#8` | `architecture#5`, `#9`, `#11`, `#12`, `#13`, `#15`, `#16`, `#17`, `#20`, `#23`; `trd-authoring#2` (input), `#3`; `prd-to-spec#5` (`saved-target`) | JSON (`survey.schema.json`) and Markdown |
| `<arch-work>/survey-matrix.json` (retired by DESIGN 3.6) | `architecture` before `#7` (Python: the element status matrix rows of the listed repositories) | `architecture#7`; `architecture#5` (seal input) | JSON: matrix rows |
| the survey's seal beside `<arch-work>/survey.json` (`contracts.survey_seal_path`) | `architecture#8` (`survey_freshness(seal=True)`) | `architecture#5` | JSON: `<plugin>/scripts/portfolio/contracts.py` `SurveySeal` |
| `<arch-work>/ledger.json` | `architecture#4` (`archresume.resume_facts`, after every saving step) | `architecture#11`, `#13`, `#15`, `#16`, `#17`, `#23`, `#25` | JSON (contract version 2) |
| `<arch-work>/plans/round<n>-plan-0.json` | `architecture#13` (agent coordinator), settled `#14` | `architecture#4`, `#14`, `#15`, `#16` | JSON (`coordinator-plan.schema.json`) |
| `<arch-work>/rounds/r<n>-<seq>-<role>-<agent>.json` | `architecture#11` (boundary guardian), `#15` (writers), `#16` (reviewers) | `architecture#4`, `#13`, `#17` | JSON (`architecture-writer.schema.json` or `architecture-review.schema.json`) |
| `<arch-work>/draft/` (views, `delta/`, `draft/baseline.json`) | `architecture#15` (writers); seed `#10` (`arch-target --seed`) | `architecture#16`, `#17`, `#20` | arc42 Markdown views, JSON baseline |
| `<arch-work>/target-check.json` | `architecture#9`, `#10` (dry-run check) | `architecture#9` (subject refusals, in-process); file: none, retained as diagnostic evidence | JSON: dry-run report (`target-report.schema.json`, `target_contract.TargetResult`) |
| `<arch-work>/decision.json`, `decision.md` (+ `.meta.json`) | `architecture#17` (agent `architecture-decider`) | `architecture#2` (cited views), `#13`, `#23`, `#25`; `repo-scoping#3` (input); `trd-authoring#2` (input), `#3` | JSON (`decision.schema.json`) and Markdown |
| `<arch-work>/target.json` | `architecture#20` (`arch-target --out`) | `prd-to-spec#5` (`saved-target`); `repo-scoping#3` (input); `trd-authoring#2` (input); `spec-authoring#1` | JSON: target report (`target-report.schema.json`, `target_contract.TargetResult`) |
| `<arch>/target/<subject>/` (views, `delta/`, `baseline.json`) | `architecture#20` (`write_target`) | `prd-to-spec#7` (`arch-delta`); `architecture#23`, `#25`, `#29`; `repo-scoping#5`; `trd-authoring#2` (input), `#3`; `spec-authoring#3`, `#4`; deleted by `prd-to-spec#15` | arc42 Markdown (`lifecycle_state: in-review`), JSON baseline |
| `<arch-work>/integrate-before.json` | `architecture#22` | `architecture#24` | JSON: tree hashes |
| `<arch-work>/tree-last.json` | `architecture#24` | `architecture#27` | JSON: tree hashes |
| `<arch-work>/integration-files.json` | `architecture#24` | `architecture#25`, `#26`, `#28` | JSON: `{ touched, deleted, all, unreported, section2, outside, changedSinceLast }` |
| `<arch-work>/architecture-update.json` (+ `.meta.json`) | `architecture#23`, `#27` (agent `architecture-maintainer`), or `#21` (publication receipt) | `architecture#24`, `#25`; `architecture#4` (`archresume.resume_facts`, `<plugin>/scripts/portfolio/archresume.py`); `<plugin>/scripts/portfolio/resumefacts.py`; `trd-authoring#2` (input) | JSON (`maintain.schema.json`; no generated Python type exists yet) |
| `<arch-work>/conformance-<n>.json` | `architecture#25` (agent `architecture-conformance-reviewer`) | `architecture#26`, `#27`, `#28` | JSON (`conformance.schema.json`) |
| `<arch>/arc42/**` except section 2 (edits, `lifecycle_state: effective`, commit and push) | `architecture#23`, `#27` (edits), `#21`, `#28` (`promote`, `commit_integration`) | every later reader of effective views: `trd-authoring#2` (`arch-views` input), `#3`; the makers of `spec-authoring#3`, `#4`; `architecture#31` (the Closure walk); the next run's `architecture#2` | arc42 Markdown; git commits in the vault |
| `<arch-work>/closure-roots.json` | `architecture#29` (`delta_items(with_closure=False)`) | `architecture#31` | JSON: build roots (`target-report.schema.json`, `target_contract.DeltaResult`) |
| `<arch-work>/closure-walk.json` | `architecture#31` (agent `prd-reality-reconciler`, CLOSURE walk) | `architecture#32` | JSON (`closure-walk.schema.json`; no generated Python type exists yet) |
| `<arch-work>/closure.json` | `architecture#32` (Python: the walk joined to the element status matrix) | `architecture#32` (`write_closure`) | JSON (`closure.schema.json`; no generated Python type exists yet) |
| `<arch>/target/<subject>/closure.json` | `architecture#32` (`archclosure.write_closure`) | `prd-to-spec#5` (`saved-target` `closureSaved`), `#7` (`arch-delta` lists prerequisites); `repo-scoping#5`; `trd-authoring#3`; `spec-authoring#1` (none-case build work) | JSON (`closure.schema.json`; no generated Python type exists yet) |
| `<arch-work>/tree-start.json`, the legacy survey receipt (`jsonartifact.receipt_path`), `candidates/` (legacy) | the JavaScript (not produced by the new flow) | `architecture` saved work read in place (CONTEXT 7.13; `candidates/` is an open item in QUESTIONS.md) | JSON |

### `repo-scoping`

| Path pattern | Producer | Consumers | Format |
|---|---|---|---|
| `<work>/repo-scoping.inventory.json` | `repo-scoping#4` (`polyrepo.py inventory --json`) | `repo-scoping#5`, `#6` | JSON: live repository inventory |
| `<work>/candidates/repo-scoping.json` | `repo-scoping#5` (agent `polyrepo-steward`, placement only) | `repo-scoping#6` | JSON (`placement.schema.json`, `placement_contract.PlacementRuling`) |
| `<work>/repo-scoping.json` (+ `.meta.json`) | `repo-scoping#7` | `repo-scoping#3`, `#8`, `#9`; `spec-authoring#1`, `#5`, `#8` (input); `task-decomposition#2` (input), `#5`, `#9`, `#10`; `prd-to-spec#11` (`closure-edges`, incl. `beadwrite._no_code`) | JSON (`placement.schema.json`, `placement_contract.PlacementRuling`) |
| `<work>/repo-creation.json` (+ `.meta.json`) | `repo-scoping#8` (deterministic, `polyrepo.py create`) | `repo-scoping#9`; `prd-to-spec` (`createdRepos` in the handback; `driver` `decisions.py`) | JSON: `{ created[{ name, repoPath, template, itemIds[], existed }], failures[{ name, template, itemIds[], error, ownerFact }] }` |
| a new repository (local checkout and GitHub; the steward's manifest, changelog and beads fleet list) | `repo-scoping#8` (`polyrepo.py create`, from the name and template the steward named) | `spec-authoring`, `task-decomposition` (as a span repository); the Task pipeline | git repository |

### `trd-authoring`

| Path pattern | Producer | Consumers | Format |
|---|---|---|---|
| `<work>/trd.md` (+ `.meta.json`) | `trd-authoring#3` (agent `trd-author`), checked `#4`, `#5`, recorded `#6` | `spec-authoring#1`, `#3`, `#4`, `#5` (input), `#7`; `driver` (lane `artifactio.file_in_vault`; `observe.py` "TRD filed") | Markdown with YAML frontmatter `decisionIds` |
| `<prd dir>/../trds/<stem>-trd.md` in the vault | `driver` (lane `file_in_vault`, after `ELABORATION_DONE`, `driver-contract.md` §4) | none: read by the owner in the vault | Markdown |

### `spec-authoring`

| Path pattern | Producer | Consumers | Format |
|---|---|---|---|
| `<work>/spec-<slug>.bundles.json` | `spec-authoring#2b` (`cdsbundles.list_bundles`; UI repositories only) | `spec-authoring#3`, `#6` (input) | JSON: supplied bundles |
| `<work>/candidates/spec-<slug>.ui.json` | `spec-authoring#3` (agent `api-specification-author`; UI repositories only) | `spec-authoring#6` | JSON (`spec-ui.schema.json`; no generated Python type for the file exists yet; the code reads its items as `recon_contract.UiItem`) |
| `<work>/spec-<slug>.ui.json` (+ `.meta.json`) | `spec-authoring#6` (checked against the bundles) | `spec-authoring#6` (`spec_ui_append`); `task-decomposition#2` (input), `#6`, `#9` | JSON (`spec-ui.schema.json`; no generated Python type for the file exists yet; the code reads its items as `recon_contract.UiItem`) |
| `<work>/spec-<slug>.md` (+ `.meta.json`) | `spec-authoring#3` (agent `api-specification-author`); `## UI design sources` appended `#6` | `spec-authoring#5`, `#7`, `#9`, `#10`, `#11` (input); `task-decomposition#2` (input), `#6`, `#10`; `driver` (lane `file_in_vault`) | Markdown with YAML frontmatter `decisionIds` |
| `<work>/spec-<slug>.data-model.md` (+ `.meta.json`) | `spec-authoring#4` (agent `data-model-specification-author`) | `spec-authoring#5`, `#7`, `#9`, `#10`, `#11` (input); `task-decomposition#2` (input), `#6`, `#10`; `driver` (lane `file_in_vault`) | Markdown with YAML frontmatter `decisionIds` |
| `<work>/spec-<slug>.criteria.md` (+ `.meta.json`) | `spec-authoring#7` (agent `acceptance-criteria-writer`) | `spec-authoring#10`, `#11` (input); `task-decomposition#2` (input), `#6`, `#10`; `driver` (lane `file_in_vault`) | Markdown |
| `<work>/story-<slug>.draft.json` (retired by DESIGN 11.5) | historical JavaScript only; no new producer | `spec-authoring#11` | JSON: `{ title, description }` |
| `<work>/story-<slug>.json` (+ `.meta.json`) | `spec-authoring#11` | `spec-authoring#12` (`write_story`); `task-decomposition#2` (input), `#6`, `#9`, `#10` | JSON: `{ title, description, decisionIds }` |
| the filed Spec documents in the vault | `driver` (lane `file_in_vault`) | none: read by the owner in the vault | Markdown |

### `task-decomposition`

| Path pattern | Producer | Consumers | Format |
|---|---|---|---|
| `<work>/tasks-<slug>.items.json` | `task-decomposition#5` (from `repo-scoping.json` and `delta-items.json`) | `task-decomposition#6`, `#10` | JSON: `{ items[{ id, element, views, requires, kind }] }` |
| `<work>/tasks-<slug>.context.json` | `task-decomposition#5` (beads read) | `task-decomposition#6` | JSON: `{ existingTasks[], otherEpicTasks[] }` |
| `<work>/candidates/tasks-<slug>.json` | `task-decomposition#6` (agent `task-decomposer`) | `task-decomposition#7` | JSON: decomposition schema |
| `<work>/tasks-<slug>.json` (+ `.meta.json`) | `task-decomposition#7`, amended `#11`, recorded `#8` | `task-decomposition#2`, `#9`, `#10`, `#11`; `prd-to-spec#11` (`closure-edges`), `#12` (agent input and `task-deps` input), `#13` | JSON: `{ tasks[], testStrategy, rationale, edges[], scores[], notes }` |
| `<work>/candidates/tasks-<slug>.correction.json` | `task-decomposition#10` (agent `task-decomposer`) | `task-decomposition#10` (Python acceptance) | JSON: `{ tasks[], edges[], scores[] }` (no `noWork`; `scores` also for saved Task keys named as unsized) |
| `<work>/tasks-<slug>.correction.json` (+ `.meta.json`) | `task-decomposition#10` | `task-decomposition#11` (merged into `tasks-<slug>.json`); otherwise evidence in the failure record | JSON, same shape |

### Owner-run portfolio flows (not part of the Epic pipeline: future readiness process, CONTEXT 7.17; `task-dependency-assessment` deleted in S08)

| Path pattern | Producer | Consumers | Format |
|---|---|---|---|
| `<workDir>/score-plan.json` | `wsjf-scoring#1` (`scoring.plan`) | `wsjf-scoring#2`, `#3`, `#7` | JSON: `{ judge, adopt, fingerprints, summary }` |
| `<workDir>/judge-input-epic.json`, `judge-input-task.json` | `wsjf-scoring#2` (`scoring.judge_input`) | `wsjf-scoring#4`, `#5`, `#6` (input) | JSON: `{ level, items, referenceJobs, summary }` |
| `<workDir>/prd/<epic-id>.md` | `wsjf-scoring#2` | `wsjf-scoring#4`, `#6` (input) | Markdown: `# <title>` + bead description |
| `<workDir>/judgments/<level>/<key>.input.json` | `wsjf-scoring#3` | `wsjf-scoring#3` (reuse), `#6` (input) | JSON: `{ <id>: <judging fingerprint> }` |
| `<workDir>/judgments/epic/<id>.json`, `judgments/task/<key>.json` (+ `.meta.json`) | `wsjf-scoring#4`, `#5` (agent `wsjf-scorer`), recorded `#6` | `wsjf-scoring#3`, `#7` | JSON: `{ rubric, scores[], unscored[] }` |
| `<workDir>/record.json` | `wsjf-scoring#7` (`scoring.record`) | `wsjf-scoring#9` | JSON: `{ written, adopted, rejected, missing, unreadable, summary }` |
| `<workDir>/score.json` | `wsjf-scoring#8` (`scoring.score`) | `wsjf-scoring#9` | JSON: `{ epics[], tasks[], unscored, incomplete, cycles, summary }` |
| `<workDir>/assess-plan.json` | `dependency-assessment#1`; `task-dependency-assessment#1` | `dependency-assessment#8`; `task-dependency-assessment#8` | JSON: `{ level, scope, unassessed, fingerprints, summary }` |
| `<workDir>/context/prd/<id>.md`, `context/task/<id>.md`, `context/index.md` | `dependency-assessment#2`; `task-dependency-assessment#2` | the same flow's `#3` (input), `#4`, `#7` | Markdown |
| `<workDir>/context.json` | `dependency-assessment#2`; `task-dependency-assessment#2` | the same flow's `#3` (input), `#4`, `#7` | JSON: `{ epic\|task, standing[], withdrawn[], corpusDir, indexPath, summary }` |
| `<workDir>/edges.json` (+ `.meta.json`) | `dependency-assessment#4`, `#7` (agent `epic-sequencer`); `task-dependency-assessment#4`, `#7` (agent `task-dependency-mapper`); recorded `#5` | the same flow's `#3`, `#6`, `#8` | JSON: `{ edges[], withdrawn[] }` |
| `<workDir>/reasoning.md` | the same agent steps (`#4`, `#7`) | none: read by the owner | Markdown |
| `<workDir>/validation.json` | `dependency-assessment#6`; `task-dependency-assessment#6` | the same flow's `#7`, `#10` (Epic) / `#11` (Task) | JSON: `edgeset.validate` result |
| `<workDir>/apply-edges.json` (or `apply-edges-dry-run.json`) | `dependency-assessment#8`; `task-dependency-assessment#8` (with `storyEdges` from `#9`) | the same flow's `#10` (Epic) / `#11` (Task) | JSON: `edgeset.apply_edges` result |
| `<workDir>/scoring/` | `dependency-assessment#9`; `task-dependency-assessment#10` (the `wsjf-scoring` flow in-process) | as in the `wsjf-scoring` rows | as above |

`route-elaboration`, `prd-validation` and `gate-enforce` produce no artifact in the Epic pipeline.

## Bead writes

Metadata keys and values below are the constants and key groups of the generated
`<plugin>/skills/beads-contract/scripts/bead_metadata.py`; each key's type, required rule and
allowed values are defined only in `<plugin>/skills/beads-contract/schemas/bead-metadata.schema.json`.
`artifact_key(kind, field)` names an artifact key (`ARTIFACT_KINDS` x `ARTIFACT_FIELDS`).

| Command | Fields and metadata keys | Writing step |
|---|---|---|
| `depscore.py elaboration-start --epic <id> --owner <token> [--reclaim]` | Epic: `KEY_ELABORATION_STATE` = `ELABORATION_IN_PROGRESS`, `KEY_ELABORATION_STATE_AT` = now, `KEY_ELABORATION_STATE_CAUSE` = `CAUSE_STARTED`, `KEY_ELABORATION_STATE_OWNER` = `<token>` | `prd-to-spec#3` |
| `beads-contract.py metadata set <epic> ...` | Epic: `artifact_key("trd", "path")`, `artifact_key("trd", "sha256")` | `trd-authoring#7` |
| `depscore.py write-story` (`beadwrite.write_story`): `bd create --type story --parent <epic>` or one `bd update` | Story: title, description, acceptance, notes `repoPath: <repo>`; metadata `KEY_ELAB_KEY` (`story:<slug>`), `KEY_REPO_PATH`, `KEY_DECISION_IDS`, and the `path`, `meta` and `sha256` artifact keys of kinds `spec`, `spec_data_model`, `spec_criteria` and `story` | `spec-authoring#12` |
| `bd delete <ids...> --force` (`beadwrite.replace_tasks`) | the Story's unstarted, elaboration-written Task beads (and their edges) | `task-decomposition#4` (case `replaced` only) |
| `bd create --type task --parent <story> ... --metadata <json> [--deps blocked-by:...]`, `bd update <id> [--title --description] [--set-metadata ...]`, `bd dep add --file -` (`blocks`), `bd dep remove` (`beadwrite.write_task`), in build order, at least one Task per Story, every Task sized | Task: title, description (with the `## Spec contract` block), acceptance, notes `repoPath: <repo>`; metadata `KEY_ELAB_KEY`, `CONTRACT_KEYS` (the Task build contract, `beadwrite.task_metadata`), `KEY_WSJF_SIZE_ESTIMATE`, `KEY_WSJF_SIZE_LOW`, `KEY_WSJF_SIZE_HIGH`, `KEY_WSJF_SIZE_CONFIDENCE` and `KEY_WSJF_CONTENT_HASH`; same-Story `blocks` edges and `blockedByExternal` blockers | `task-decomposition#9` (again after `#11`) |
| `depscore.py write-all-task-edges --epic <id> --dir <work> --repos <span>` | `blocks` edges between Tasks of different Stories (closure edges and `task-deps.json`, cycle-closing edges dropped) | `prd-to-spec#13` |
| the `elaboration-finish` logic (`elaboration.finish`, `scoring.score`) with the write scope limited to the Epic's Tasks | the Epic's Tasks only: the `WSJF_KEYS` the rubric's score row carries, less `scoring.SIZE_JUDGED_KEYS` (`scoring._apply`; the Epic's WSJF keys are not written, CONTEXT 7.17); once every Task is scored, Epic: `KEY_ELABORATION_STATE` = `ELABORATION_DONE`, `KEY_ELABORATION_STATE_AT` = now, `KEY_ELABORATION_STATE_CAUSE` = `CAUSE_DECOMPOSED`, `KEY_ELABORATION_STATE_OWNER` emptied; then `story-edges`: Story `blocks` edges and `KEY_STORY_OWNED_BLOCKERS`, `KEY_STORY_OWNED_BLOCKERS_AT`, `KEY_STORY_EDGE_REASONS` (Stories get no WSJF) | `prd-to-spec#14` |
| `depscore.py elaboration-release --epic <id> --owner <token>` | Epic: `KEY_ELABORATION_STATE_OWNER` emptied (when still this run's token) | `prd-to-spec#16` |
| *Rows below to `storyedges.story_edges` belong to the owner-run portfolio flows, which are not part of the Epic pipeline (CONTEXT 7.17); `task-dependency-assessment` is deleted in S08. Two are shared: `scoring.score` and `storyedges.story_edges` also run inside `prd-to-spec#14`.* | | |
| `scoring.record` (`depscore.py record`): `bd update --set-metadata` | Epic: `KEY_WSJF_UBV`, `KEY_WSJF_TC`, `KEY_WSJF_CONFIDENCE`, `scoring.SIZE_JUDGED_KEYS` (only when its size does not roll up from Tasks) and `KEY_WSJF_CONTENT_HASH`; Task: `scoring.SIZE_JUDGED_KEYS` and `KEY_WSJF_CONTENT_HASH`; adopted items: `KEY_WSJF_CONTENT_HASH` only | `wsjf-scoring#7` |
| `scoring.score` (`depscore.py score`): `bd update --set-metadata` | the `WSJF_KEYS` the rubric's score row carries, less `scoring.SIZE_JUDGED_KEYS` (`scoring._apply`), on every open Epic and Task whose value changed | `wsjf-scoring#8` (also run by `dependency-assessment#9`, `task-dependency-assessment#10`) |
| `edgeset.apply_edges` (`depscore.py apply-edges`): `bd dep add --type tracks`, conversions, removals, `bd update --set-metadata` | Epic `tracks` edges touching the Epic; on each blocked Epic `KEY_SEQ_OWNED_BLOCKERS`, `KEY_SEQ_OWNED_BLOCKERS_AT`, `KEY_SEQ_EDGE_REASONS`, `KEY_SEQ_EDGE_WITHDRAWN`; on the assessed Epic `KEY_SEQ_CONTENT_HASH`, `KEY_SEQ_ASSESSED_AT` | `dependency-assessment#8` |
| `edgeset.apply_edges` with `level="task"` | Task `blocks` edges touching the Task and the same `KEY_SEQ_*` keys on Tasks | `task-dependency-assessment#8` |
| `storyedges.story_edges` | Story `blocks` edges and `KEY_STORY_OWNED_BLOCKERS`, `KEY_STORY_OWNED_BLOCKERS_AT`, `KEY_STORY_EDGE_REASONS` | `task-dependency-assessment#9` (and inside `prd-to-spec#14`) |
| `elabstate.hold_for_person` | Epic: `KEY_ELABORATION_STATE` = `ELABORATION_AUTHORING`, `KEY_ELABORATION_STATE_AT` = now, `KEY_ELABORATION_STATE_CAUSE` = `CAUSE_AWAITING_HUMAN`, `KEY_ELABORATION_STATE_OWNER` emptied | `driver` (from `requiredHumanActions`, `driver-contract.md` §4); no Epic flow writes it |
| `artifactio.file_in_vault` bead metadata | Epic: `artifact_key("trd", "vault_path")`; each Story: the `vault_path` artifact keys of kinds `spec`, `spec_data_model`, `spec_criteria` | `driver` (lane, after `ELABORATION_DONE`) |
| `elabmark.py --set=<state>` | Epic: `KEY_ELABORATION_STATE`, cause `CAUSE_HUMAN` | the owner's CLI (`driver-contract.md` §2) |

`architecture`, `repo-scoping`, `route-elaboration`, `prd-validation` and `gate-enforce` write
nothing to beads.
