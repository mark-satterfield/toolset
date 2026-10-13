# Index of the Epic pipeline's artifacts and bead writes

Failure handling: bounded transient retries and quota pauses remain. An ordinary item failure is recorded and excluded from selection for the current invocation; other eligible items continue. Setup, code, schema, and runtime type defects stop new dispatch, preserve the original diagnostic, and let current paid steps finish. Named within-step corrective passes remain bounded content work; failed runs do not dispatch repair or diagnosis agents.

Steps S01h and S01i. Every file, vault path and bead write the Epic flows produce, with the step that
produces it and the steps that consume it. A step is cited as `<spec>#<step number>`, the number
in that spec's Steps section; `driver` means the driver at `<control>/ops/sdlc-automation` as
`driver-contract.md` describes it. When a spec and this index disagree, the spec is right and this
index is stale.

Path placeholders:
- `<work>` = `<control>/.claude/workflow-runs/artifacts/<epic-id>/` (the Epic's work directory);
  `<arch-work>` = `<work>/architecture/`.
- `<arch>` = the value of the `ARCH_PATH_ENV` driver environment variable, defined by the
  `pipeline-contracts` skill (`<plugin>/skills/pipeline-contracts/schemas/driver-surface.schema.json`):
  the architecture folder of the `skillspoke-docs` vault.
- `<slug>` = a span repository's artifact slug.
- `<workDir>` = the work directory of an owner-run portfolio flow (`wsjf-scoring`,
  `dependency-assessment`, `task-dependency-assessment`). None of them is part of the Epic
  pipeline.

A step of the Epic's journal is cited by its script key (for example `prd_to_spec.open_run`) or by
its agent. The journal alone decides where a run begins: no file below is read to decide whether a
step of the architecture part runs again.

Every `.meta.json` named below is written by `artifactio.record` beside its file by the spec
authoring and Task decomposition phases and is read by the same phase.

The Format column names each file's contract; it never restates fields. A schema file named there
is under `<plugin>/skills/artifact-handoff/schemas/`.

## Artifacts

### `prd-to-spec` (the composite)

| Path pattern | Producer | Consumers | Format |
|---|---|---|---|
| `<control>/.claude/workflow-runs/step-journals/<bead>.step-journal.json` | `prd-to-spec` (created with every outermost step planned when the file does not exist; every step records in it); an agent that starts or plans steps, through `atw-step-journal`; a spec step and a Task step create the journal of each Story and Task they create | `prd-to-spec` (the next step, each step's inputs, the dispatch result); the build and deploy pipelines (the journals of Tasks and Stories) | JSON: `step-journal.schema.json` of the `pipeline-contracts` skill (`step_journal_contract.Journal`) |
| `<work>/closure-edges.json` | `prd-to-spec#11` (`depscore.py closure-edges --out`) | `prd-to-spec#12` (agent input), `#13` | JSON: `{ edges[{ from, to, reason }], summary.warnings }` |
| `<work>/candidates/task-deps.json` | `prd-to-spec#12` (agent `task-dependency-mapper`; required when the span has two or more repositories) | `prd-to-spec#12` (Python acceptance) | JSON: `task-deps.schema.json` (`task_deps_contract.TaskDeps`) |
| `<work>/task-deps.json` (+ `.meta.json`) | `prd-to-spec#12` (accepted copy) | `prd-to-spec#12` (reuse), `#13` | JSON, same shape |
| `<work>/task-edges/all.json` | `prd-to-spec#13` (`depscore.py write-all-task-edges --out`) | none: retained as diagnostic evidence | JSON: write summary `{ blockers, added, removed, standing, rejected }` |
| `<work>/STEPS.md` | after each phase: `prd-to-spec` (`artifactio.complete_step`), `spec-authoring#13` | `driver` (`artifactio.plan` -> the `resume` argument; `observe.py` accepted and stale steps; an open item in QUESTIONS.md) | text: one completed step id per line |
| `<work>/run.json` | `prd-to-spec#17` | none: read by the driver (handback `detailPath` -> failure evidence and human-action detail, `driver-contract.md` §4) and the owner | JSON: the run record, `<plugin>/orchestrator/core/manifest.py` `RunManifest` |
| the handback (`run.py --handback`, and handbacks the driver builds) | `prd-to-spec` (`<plugin>/orchestrator/run.py`, one atomic write when the flow ends); `driver` (`orchestrated.failed_handback`, for a dispatch that raised or was interrupted) | `driver` (`orchestrated.read_handback`, validated with `handback_contract.validate`; `driver-contract.md` §4) | JSON: `<plugin>/orchestrator/core/handback_contract.py` `HandbackDocument` |
| `<control>/ops/sdlc-automation/state/ledger.jsonl` (events appended) | `driver` (`ledger.append` in `<control>/ops/sdlc-automation/ledger.py`, called by `supervisor.py`, `keeper.py`, `storydeploy.py`, `failures.py`, `execidentity.py`, `telemetry.py`); no Epic flow writes it | `driver` (the `ledger` read functions, called by `outcomes.py`, `observe.py`, `runview.py`, `lane.py`, `repeats.py`, `repeatfail.py`, `keeper.py`, `supervisor.py`, `execidentity.py`, `dashboard.py`; `attemptview.py` interprets the events read) | JSON lines; the event set (`EventType`, `EVENT_TYPES`), the envelope and field-name constants (`KEY_*`) and the typed shape of `handback` events (`HandbackFields`) are defined only by `<control>/ops/sdlc-automation/ledgerevents.py`; the other event types have no typed field shape there |

### The matrix

| Path pattern | Producer | Consumers | Format |
|---|---|---|---|
| `<control>/ops/sdlc-automation/matrix.json` | `atw-matrix` and the matrix modules: step `prd_to_spec.open_run` (PRD row, document rows, expertise), the agents of the architecture team by role, step `atw-matrix check; atw-matrix unapproved` (marks in review), step `atw-matrix approve`; the build pipeline (code state) | the same steps and agents; step `atw-matrix prd --closure` (the repository span) | JSON: `matrix.schema.json` (`matrix_contract.Matrix`) |

### Architecture (the steps of the Architecture container)

| Path pattern | Producer | Consumers | Format |
|---|---|---|---|
| `<arch-work>/context.json` | step `prd_to_spec.open_run` | every step of the Architecture container and step `trd.confirm` (handed through the journal); `aws-solutions-architect` as `context` | JSON: `architecture-context.schema.json` |
| `<arch-work>/state.json` | agent `aws-solutions-architect`, before anything else | `trd-author` (named in the TRD request); `aws-solutions-architect` when launched for "Finish" | JSON: `architecture-state.schema.json` |
| `<arch-work>/result.json` | agent `aws-solutions-architect`; updated in place by its correction, competing-design and "Finish" steps | step `atw-matrix check; atw-matrix unapproved` (criterion answers, conclusion, review signals); every reviewer and the lead as `architecture result` | JSON: `architecture-result.schema.json` |
| a request file for a specialist, a diagram author or the steward (the architect's under `<arch-work>/helpers/`) | `aws-solutions-architect` for each agent it starts; `architecture-team-lead` when it asks for an opinion | the agent asked; the script, which launches from it an agent left running or a specialist the lead planned (artifact `request`) | JSON: `specialist-request.schema.json` |
| the answer file a specialist request names | the design specialist, diagram author or `polyrepo-steward` asked | `aws-solutions-architect` (handed as `answer` in a correction or a "Finish" step); `architecture-team-lead` | JSON: `specialist-answer.schema.json` |
| a TRD request file (under `<arch-work>/helpers/`) | `aws-solutions-architect`: mode `draft` once, then mode `update` | `trd-author`; the script, which launches a `trd-author` left running from it | JSON: `trd-request.schema.json` |
| the answer file a TRD request names | `trd-author` | `aws-solutions-architect` (the obligations with no source) | JSON: `trd-answer.schema.json` |
| a write request file (under `<arch-work>/helpers/`) | `aws-solutions-architect` | `architecture-maintainer`; the script, which launches a maintainer left running from it | JSON: `write-request.schema.json` |
| the result file a write request names | `architecture-maintainer` | `aws-solutions-architect` (entries below architecture level go to the TRD or `notesForSpecs`) | JSON: `write-result.schema.json` |
| `<arch>/arc42/**` except section 2 (edits; `lifecycle_state: effective`, commit and push after review) | `architecture-maintainer` (edits, `in-review`); step `atw-matrix approve` (sets `effective`, commits and pushes in the vault) | every later reader of the effective documents: the architecture team, `trd-author`, the spec authors, and the next Epic's architect | arc42 Markdown; git commits in the vault |
| `<arch-work>/check-<n>.json` | step `atw-matrix check; atw-matrix unapproved` (`<n>` is the number of corrections before it) | `aws-solutions-architect` as `findings`, in the correction step planned when the check is not valid | JSON: `check-result.schema.json` |
| `<arch-work>/review-scope.json` | step `atw-matrix check; atw-matrix unapproved` | step `atw-matrix approve` (the documents to commit) | JSON: `matrix.schema.json` `$defs/ReviewScope` |
| `<arch-work>/review-scope.<reviewer>.json` | step `atw-matrix check; atw-matrix unapproved`, one for each reviewer the criteria file selects | that reviewer as `review scope`; the script, which drops a finding outside it | JSON: `matrix.schema.json` `$defs/ReviewerScope` |
| `<arch-work>/reviews/<reviewer>.json` (a re-check: `<reviewer>.<step>.json`; as returned: `.as-returned.json`) | each selected reviewer, at the same time; the reviewer that raised a finding, for its re-check | `architecture-team-lead` and `aws-solutions-architect` as `findings`; step `atw-matrix approve` (refuses while a finding is unresolved) | JSON: `scope-review.schema.json` |
| `<arch-work>/specialists.json` | the launch of `architecture-team-lead` | `architecture-team-lead` as `specialists` | JSON: `specialists.schema.json` |
| `<arch-work>/routing-<step>.json` | `architecture-team-lead`, before it adds a step | the script (a routing that sends an item to further work adds a step for it) | JSON: `lead-routing.schema.json` |
| a question file for the decider (under `<arch-work>/`) | `architecture-team-lead` (artifact `question` of its own step) | `architecture-decider` as `question` | JSON: `architecture-question.schema.json` |
| `<arch-work>/ruling-<step>.json` | `architecture-decider`, which also records the ruling in the matrix | `architecture-team-lead`; `aws-solutions-architect` as `ruling`; an owner concern in it holds the Epic for the owner | JSON: `architecture-ruling.schema.json` |
| `<arch-work>/approved.json` | step `atw-matrix approve` | none: evidence, and the failure record when an item could not be approved | JSON: `matrixreview.Approved` |

### Repository span (step `atw-matrix prd --closure`)

| Path pattern | Producer | Consumers | Format |
|---|---|---|---|
| `<work>/span-elements.json` | step `atw-matrix prd --closure` (the elements the PRD's features are realized by and what those depend on, not yet built) | the spec steps and the Task steps (artifact `elements`); `hierarchy.closure_task_edges` | JSON: `target-report.schema.json` (`target_contract.DeltaResult`) |
| `<work>/repo-scoping.json` | step `atw-matrix prd --closure` (each element in the repository its matrix row names) | the spec steps and the Task steps (artifact `span`); `beadwrite` | JSON (`placement.schema.json`, `placement_contract.PlacementRuling`) |
| `<work>/repo-creation.json` | step `atw-matrix prd --closure` (deterministic, `polyrepo.py create`), only when the matrix names a repository the inventory lacks | `prd-to-spec` (`createdRepos` in the handback; `driver` `decisions.py`) | JSON: `{ created[{ name, repoPath, template, itemIds[], existed }], failures[{ name, template, itemIds[], error, ownerFact }] }` |
| a new repository (local checkout and GitHub; the steward's manifest, changelog and beads fleet list) | step `atw-matrix prd --closure` (`polyrepo.py create`, from the name the matrix gives and the template that name matches) | `spec-authoring`, `task-decomposition` (as a span repository); the Task pipeline | git repository |

### TRD

| Path pattern | Producer | Consumers | Format |
|---|---|---|---|
| `<work>/trd.md` | `trd-author`, at the architect's request: drafted early, updated in place; confirmed by step `trd.confirm` (every `decisionIds` entry resolves; path and digest on the Epic bead) | `trd-validator` as `trd`; the spec steps and the journals of the Stories and Tasks (artifact `TRD`); `driver` (lane `artifactio.file_in_vault`) | Markdown with YAML front matter `decisionIds` |
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
| `<work>/candidates/spec-<slug>.review.json` | `spec-authoring#8b` (agent `openapi-contract-reviewer`) | `spec-authoring#8b` | JSON (`spec-review.schema.json`, `spec_review_contract.SpecReview`) |
| `<work>/spec-<slug>.review.json` (+ `.meta.json`) | `spec-authoring#8b` (accepted) | `spec-authoring#8b` (the authors' one correction, the ruling) | JSON (`spec-review.schema.json`, `spec_review_contract.SpecReview`) |
| `<work>/candidates/spec-<slug>.<document>.correction.json`, `spec-<slug>.<document>.revision.json` | `spec-authoring#8b` (the agent that wrote the document; only for a document with a finding, a ruling against it, or a corrected source document) | `spec-authoring#8b` | JSON (`spec-correction.schema.json`, `spec_review_contract.SpecCorrection`) |
| `<work>/spec-<slug>.<document>.correction.json`, `spec-<slug>.<document>.revision.json` (+ `.meta.json`) | `spec-authoring#8b` (accepted) | `spec-authoring#8b` (the ruling, for a correction that states a dispute) | JSON (`spec-correction.schema.json`, `spec_review_contract.SpecCorrection`) |
| `<work>/candidates/spec-<slug>.ruling.json` | `spec-authoring#8b` (agent `spec-decider`; only when an author disputes a finding) | `spec-authoring#8b` | JSON (`spec-ruling.schema.json`, `spec_review_contract.SpecRuling`) |
| `<work>/spec-<slug>.ruling.json` (+ `.meta.json`) | `spec-authoring#8b` (accepted) | `spec-authoring#8b` (the authors' revision to its directives) | JSON (`spec-ruling.schema.json`, `spec_review_contract.SpecRuling`) |
| `<work>/spec-<slug>.review-outcome.json` (+ `.meta.json`) | `spec-authoring#8b` (`SpecReviewStep`) | `spec-authoring#8b` on the next run (the review is not repeated for unchanged documents) | JSON: `spec_review.SpecReviewOutcome` |
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
| `beadgraph.write_metadata` | Epic: `artifact_key("trd", "path")`, `artifact_key("trd", "sha256")` | step `trd.confirm` |
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

The steps of the Architecture container, the repository span step, `route-elaboration`,
`prd-validation` and `gate-enforce` write nothing to beads.
