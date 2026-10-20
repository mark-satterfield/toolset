# Index of the Epic pipeline's artifacts and bead writes

Failure handling: bounded transient retries and quota pauses remain. An ordinary item failure is recorded and excluded from selection for the current invocation; other eligible items continue. Setup, code, schema, and runtime type defects stop new dispatch, preserve the original diagnostic, and let current paid steps finish. Named within-step corrective passes remain bounded content work; failed runs do not dispatch repair or diagnosis agents.

Every file, vault path and bead write the Epic flows produce, with the step that produces it and
the steps that consume it. `driver` means the driver at `<control>/ops/sdlc-automation` as
`driver-contract.md` describes it. When a spec and this index disagree, the spec is right and this
index is stale.

Path placeholders:
- `<work>` = `<control>/.claude/workflow-runs/artifacts/<epic-id>/` (the Epic's work directory);
  `<arch-work>` = `<work>/architecture/`.
- `<arch>` = the value of the `ARCH_PATH_ENV` driver environment variable, defined by the
  `pipeline-contracts` skill (`<plugin>/skills/pipeline-contracts/schemas/driver-surface.schema.json`):
  the architecture folder of the `skillspoke-docs` vault.
- `<slug>` = a span repository's artifact slug.
- `<workDir>` = the work directory of an owner-run flow (`wsjf-scoring`,
  `dependency-assessment`, `task-dependency-assessment`, `prd-creation`); `<artifacts.dir>` = the
  artifacts directory a `prd-validation` run names. None of them is part of the Epic pipeline.

A step of the Epic's journal is cited by its script key (for example `prd_to_spec.open_run`) or by
its agent. The journal alone decides where a run begins: no file below is read to decide whether a
step runs again. When a run opens an existing journal, each step without child steps that has not
started and whose script key or agent has no code in the registry is replanned from the lane's
current plan for its position (`journal_run.replan_unhandled`: the key or agent, description and
purpose; its id and inputs stay); a step that has started or is done is never changed. Before the
first step runs, the run checks every step without child steps that is not done against the
registry and fails with one error naming every key that still has no code. A step is handed each file it reads as an artifact of a step its `inputs` name;
the Consumers column gives that artifact's name where the step reads it by name.

The Format column names each file's contract; it never restates fields. A schema file named there
is under `<plugin>/skills/artifact-handoff/schemas/`. A Python name there is the typed definition
of a file only code writes and reads. `<plugin>/skills/artifact-handoff/epic-contracts.md` indexes
the same contracts by artifact, writer and reader.

## Artifacts

### `prd-to-spec` (the composite)

| Path pattern | Producer | Consumers | Format |
|---|---|---|---|
| `<control>/.claude/workflow-runs/step-journals/<bead>.step-journal.json` | `prd-to-spec` (created with every outermost step planned when the file does not exist; every step records in it); an agent that starts or plans steps, through `atw-step-journal`; a spec step and a Task step create the journal of each Story and Task they create | `prd-to-spec` (the next step, each step's inputs, the dispatch result); the build and deploy pipelines (the journals of Tasks and Stories) | JSON: `step-journal.schema.json` of the `pipeline-contracts` skill (`step_journal_contract.Journal`) |
| `<work>/closure-edges.json` | step `beadwrite.closure_task_edges`, the first step of the Task edges container | step `task_edges.listing` (named in the listing); the mapper's step (artifact `closure edges`); step `beadwrite.write_all_task_edges` (`closureEdges` in the dispatch result) | JSON: `closure-edges.schema.json` |
| `<work>/task-deps-inputs.json` | step `task_edges.listing` | the mapper's step (artifact `task dependency listing`) | JSON: `task-dependency-listing.schema.json` |
| `<work>/task-deps.json` | agent `task-dependency-mapper`; its step is planned only when the span has two or more repositories, and its output is checked against `task-deps.schema.json` and then against the span's Task keys | step `beadwrite.write_all_task_edges` (artifact `task dependencies`) | JSON: `task-deps.schema.json` (`task_deps_contract.TaskDeps`) |
| `<work>/task-edges/all.json` | step `beadwrite.write_all_task_edges` | none: retained as diagnostic evidence | JSON: `beadwrite.AllEdgeWrite` |
| `<work>/run.json` | `prd-to-spec` (each session's row when it starts and when it ends; the dispatch's record when the dispatch ends) | none: read by the driver (handback `detailPath` -> failure evidence and human-action detail, `driver-contract.md` §4) and the owner | JSON: the run record, `<plugin>/orchestrator/core/manifest.py` `RunManifest` |
| the handback (`run.py --handback`, and handbacks the driver builds) | `prd-to-spec` (`<plugin>/orchestrator/run.py`, one atomic write when the flow ends); `driver` (`orchestrated.failed_handback`, for a dispatch that raised or was interrupted) | `driver` (`orchestrated.read_handback`, validated with `handback_contract.validate`; `driver-contract.md` §4) | JSON: `<plugin>/orchestrator/core/handback_contract.py` `HandbackDocument` |
| `<control>/ops/sdlc-automation/state/ledger.jsonl` (events appended) | `driver` (`ledger.append` in `<control>/ops/sdlc-automation/ledger.py`, called by `supervisor.py`, `keeper.py`, `storydeploy.py`, `failures.py`, `execidentity.py`, `telemetry.py`); no Epic flow writes it | `driver` (the `ledger` read functions, called by `outcomes.py`, `observe.py`, `runview.py`, `lane.py`, `repeats.py`, `repeatfail.py`, `keeper.py`, `supervisor.py`, `execidentity.py`, `dashboard.py`; `attemptview.py` interprets the events read) | JSON lines; the event set (`EventType`, `EVENT_TYPES`), the envelope and field-name constants (`KEY_*`) and the typed shape of `handback` events (`HandbackFields`) are defined only by `<control>/ops/sdlc-automation/ledgerevents.py`; the other event types have no typed field shape there |

### The matrix

| Path pattern | Producer | Consumers | Format |
|---|---|---|---|
| `<control>/ops/sdlc-automation/matrix.json` | `atw-matrix` and the matrix modules: step `prd_to_spec.open_run` (the Epic's entry with its requirements, document entries, expertise), the agents of the architecture team by role (`put`, `link`, `settle`), the steps that accept their results, step `atw-matrix sync-documents; atw-matrix commit` (lifecycle, the Epic's `reviewLog` link, settled disagreements, the commit); the spec and Task steps (`describedBy` for a cited heading, a dependency between stacks); the driver's Story deploy (the verified mark) | the same steps and agents; step `atw-matrix check; atw-matrix review-scope` (reads only); step `atw-matrix epic --closure` (the repository span: the stack and repository of what the architect's result says the Stories build, and the architecture-side dependencies between them) | JSON: `matrix.schema.json` with the kinds registry `matrix-kinds.json` (`matrix_contract`) |

### Architecture (the steps of the Architecture container)

| Path pattern | Producer | Consumers | Format |
|---|---|---|---|
| `<arch-work>/context.json` | step `prd_to_spec.open_run` | every step of the Architecture container and step `trd.confirm` (handed through the journal); `aws-solutions-architect` as `context` | JSON: `architecture-context.schema.json` |
| `<arch-work>/state.json` | agent `aws-solutions-architect`, before anything else it writes | `aws-solutions-architect` when launched for "Finish" | JSON: `architecture-state.schema.json` |
| `<arch-work>/result.json` | agent `aws-solutions-architect`; updated in place by its correction, competing-design and "Finish" steps | step `atw-matrix check; atw-matrix review-scope` (criterion answers, conclusion, `addedOrChangedElements` for the review log's AWS resources; every conclusion, `no-change-needed` included, goes through it); the lead as `architecture result`; step `atw-matrix epic --closure` (`addedOrChangedElements` and `unchangedWorkElements`: what the Stories build, the elements the design adds or changes and the existing elements it leaves unchanged where the Epic has work) | JSON: `architecture-result.schema.json` |
| a request file for a specialist, a diagram author or the steward (the architect's under `<arch-work>/helpers/`) | `aws-solutions-architect` for each agent it starts; `architecture-team-lead` when it asks for an opinion | the agent asked; the script, which launches from it an agent left running or a specialist the lead planned (artifact `request`) | JSON: `specialist-request.schema.json` |
| the answer file a specialist request names | the design specialist, diagram author or `polyrepo-steward` asked | `aws-solutions-architect` (handed as `answer` in a correction or a "Finish" step); `architecture-team-lead` | JSON: `specialist-answer.schema.json` |
| a TRD request file (under `<arch-work>/helpers/`) | the launch builder of the TRD initial write (`architecture.trd_author`): mode `initial` once, as the first step of the Architecture container; `aws-solutions-architect`: mode `update`, the TRD architecture update and each later update | `trd-author`; the script, which launches a `trd-author` left running from it | JSON: `trd-request.schema.json` |
| the answer file a TRD request names | `trd-author` | `aws-solutions-architect` (the obligations with no source; the TRD initial write's answer is handed to its first step as `answer`); the step that accepts it, which in both modes records for each requirement the answer lists one `constraint` that points at the requirement's heading in the TRD (`trd`, no statement), removes the constraint of each removed id, and records each `noSource` obligation | JSON: `trd-answer.schema.json` |
| a write request file (under `<arch-work>/helpers/`) | `aws-solutions-architect` | `architecture-maintainer`; the script, which launches a maintainer left running from it | JSON: `write-request.schema.json` |
| the result file a write request names | `architecture-maintainer` | `aws-solutions-architect` | JSON: `write-result.schema.json` |
| `<arch>/arc42/**` except section 2, and `<arch>/detailed/**` (edits; `lifecycle_state: effective`, commit and push at promotion) | `architecture-maintainer` (edits; the step that accepts its result sets each document it wrote `in-review` before `sync-documents --paths`); step `atw-matrix sync-documents; atw-matrix commit` (sets `effective`, commits and pushes in the vault) | every later reader of the effective documents: the architecture team, `trd-author`, the spec authors, and the next Epic's architect | arc42 Markdown; git commits in the vault |
| `<arch-work>/review-log.json` (the context's `reviewLogPath`) | agent `aws-solutions-architect`, with the `log-architecture-review` skill's `review_log.py`, updated in place by its correction steps | step `atw-matrix check; atw-matrix review-scope` (`review_log.problems`: a defect goes to the architect as a correction); step `atw-matrix sync-documents; atw-matrix commit` (copies it to `<arch>/review-logs/<epic id>.json`, commits and pushes it in the vault, and links it from the Epic's matrix entry as `reviewLog` with its path and SHA-256) | JSON: `log-architecture-review/schemas/review-log.schema.json` |
| `<arch-work>/checks/<step id>/check.json` | step `atw-matrix check; atw-matrix review-scope` (each check step writes in its own folder) | `aws-solutions-architect` as `findings`, in the correction step planned when the check is not valid | JSON: `check-result.schema.json` |
| `<arch-work>/checks/<step id>/review-scope.json` | step `atw-matrix check; atw-matrix review-scope` | step `atw-matrix sync-documents; atw-matrix commit` (the documents to set effective and commit) | JSON: what `atw-matrix review-scope --epic` prints (`matrixreview.ReviewScope`) |
| `<arch-work>/checks/<step id>/unlinked.json` | step `atw-matrix check; atw-matrix review-scope` | none: evidence of the links with nothing recorded at the other end | JSON: what `atw-matrix epic <id> --unlinked` prints (`matrixquery.EpicView`) |
| `<arch-work>/routing-<step>.json` | `architecture-team-lead`, before it adds a step | the script (a routing that sends an item to further work adds a step for it) | JSON: `lead-routing.schema.json` |
| a question file for the decider (under `<arch-work>/`) | `architecture-team-lead` (artifact `question` of its own step) | `architecture-decider` as `question` | JSON: `architecture-question.schema.json` |
| `<arch-work>/ruling-<step>.json` | `architecture-decider`, which also records the ruling in the matrix | `architecture-team-lead`; `aws-solutions-architect` as `ruling`; an owner concern in it holds the Epic for the owner | JSON: `architecture-ruling.schema.json` |
| `<arch-work>/promoted.json` | step `atw-matrix sync-documents; atw-matrix commit` | none: evidence, and the failure record when a document could not be set effective | JSON, written by `architecture_promotion.py` |

### Repository span (step `atw-matrix epic --closure`)

| Path pattern | Producer | Consumers | Format |
|---|---|---|---|
| `<work>/span-elements.json` | step `atw-matrix epic --closure` (what the Stories build: the architect's `addedOrChangedElements` and its `unchangedWorkElements`, one item per element and stack it is built in, an event in each stack that holds one of its producers) | the spec steps and the Task steps (artifact `elements`); step `beadwrite.closure_task_edges` | JSON: `target-report.schema.json` (`target_contract.DeltaResult`) |
| `<work>/repo-scoping.json` | step `atw-matrix epic --closure` (each thing the Stories build in the repository of the stack the architecture side places it in; a stack that names none is given the name the naming rules give it) | the spec steps and the Task steps (artifact `span`); `beadwrite` | JSON (`placement.schema.json`, `placement_contract.PlacementRuling`) |
| `<work>/repo-creation.json` | step `atw-matrix epic --closure` (deterministic, `polyrepo.py create`), only when a stack a Story builds in has a repository the inventory lacks | `prd-to-spec` (`createdRepos` in the handback; `driver` `decisions.py`) | JSON: `repo_scoping.create_repositories` |
| a new repository (local checkout and GitHub, and the beads fleet list) | step `atw-matrix epic --closure` (`polyrepo.py create --space <the stack's app>`, which takes the template from the name, from the name the stack gives as its repository) | the spec steps and the Task steps (as a span repository); the Task pipeline | git repository |

### TRD

| Path pattern | Producer | Consumers | Format |
|---|---|---|---|
| `<work>/trd.md` | `trd-author`: the TRD initial write, the first step of the Architecture container; the TRD architecture update and later updates at the architect's request, in place; confirmed by step `trd.confirm` (every `decisionIds` entry resolves; path and digest on the Epic bead) | the architect and the detailed design; the spec steps and the journals of the Stories and Tasks (artifact `TRD`), whose build reads it (`trdPath` in the build contract); `driver` (lane `artifactio.file_in_vault`) | Markdown: `document-front-matter.schema.json#/$defs/TrdDocument` |
| `<prd dir>/../trds/<stem>-trd.md` in the vault | `driver` (lane `file_in_vault`, after `ELABORATION_DONE`, `driver-contract.md` §4) | none: read by the owner in the vault | Markdown |

### `spec-authoring`

| Path pattern | Producer | Consumers | Format |
|---|---|---|---|
| `<work>/spec-<slug>.context.json` | step `spec_authoring.context` | the spec authors, the reviewer, the UI steps, step `spec_authoring.story_document` and the decomposer (artifact `repository context`) | JSON: `spec-context.schema.json` |
| `<work>/spec-<slug>.bundles.json` | step `cdsbundles.list_bundles` (frontend repositories only) | the UI sources session and step `spec_authoring.normalize_ui` (artifact `ui bundles`) | JSON: `ui-bundles.schema.json` |
| `<work>/candidates/spec-<slug>.ui.json` | agent `api-specification-author`, in the UI sources step (frontend repositories only) | step `spec_authoring.normalize_ui` (artifact `ui sources as authored`) | JSON (`spec-ui.schema.json`; no generated Python type for the file exists yet; the code reads its items as `recon_contract.UiItem`) |
| `<work>/spec-<slug>.ui.json` | step `spec_authoring.normalize_ui` (checked against the bundles) | the contracts session, step `specui.spec_ui_append`, the decomposer (artifact `ui sources`); the first step of the Story's and each Task's journal | JSON (`spec-ui.schema.json`; no generated Python type for the file exists yet; the code reads its items as `recon_contract.UiItem`) |
| `<work>/spec-<slug>.md` | agent `api-specification-author`; `## UI design sources` appended by step `specui.spec_ui_append`; corrected in place by its author's correction and revision steps | the acceptance-criteria session, the reviewer, the decider, step `spec_authoring.story_document`, step `beadwrite.write_story` (its path and digest on the Story bead), the decomposer; the first step of the Story's and each Task's journal; `driver` (lane `file_in_vault`) | Markdown: `document-front-matter.schema.json#/$defs/SpecDocument` |
| `<work>/spec-<slug>.data-model.md` | agent `data-model-specification-author`; corrected in place by its author's correction and revision steps | the acceptance-criteria session, the reviewer, the decider, step `spec_authoring.story_document`, step `beadwrite.write_story` (its path and digest on the Story bead), the decomposer; the first step of the Story's and each Task's journal; `driver` (lane `file_in_vault`) | Markdown: `document-front-matter.schema.json#/$defs/SpecDocument` |
| `<work>/spec-<slug>.criteria.md` | agent `acceptance-criteria-writer`; corrected in place by its author's correction and revision steps | the reviewer, the decider, step `beadwrite.write_story` (its path and digest on the Story bead), the decomposer; the first step of the Story's and each Task's journal; `driver` (lane `file_in_vault`) | Markdown |
| `<work>/spec-<slug>.review.json` | agent `spec-reviewer` (one step per repository) | each author's correction step and revision step, and the decider (artifact `spec review`) | JSON (`spec-review.schema.json`, `spec_review_contract.SpecReview`) |
| `<work>/spec-<slug>.<document>.correction.json`, `spec-<slug>.<document>.revision.json` | the agent that wrote the document, in a correction step (a document with a finding, or derived from a document that changed) or a revision step (after the ruling) | the decider (artifact `spec correction`) | JSON (`spec-correction.schema.json`, `spec_review_contract.SpecCorrection`) |
| `<work>/spec-<slug>.ruling.json` | agent `review-dispute-decider` (its step is planned only when an author disputes a finding) | each author's revision step (artifact `spec ruling`) | JSON (`spec-ruling.schema.json`, `spec_review_contract.SpecRuling`) |
| `<work>/story-<slug>.json` | step `spec_authoring.story_document` | step `beadwrite.write_story`; the decomposer and the Task steps (artifact `story document`); the first step of the Story's and each Task's journal | JSON: `story-document.schema.json` |
| the filed Spec documents in the vault | `driver` (lane `file_in_vault`) | none: read by the owner in the vault | Markdown |

### `task-decomposition`

| Path pattern | Producer | Consumers | Format |
|---|---|---|---|
| `<work>/tasks-<slug>.context.json` | step `task_decomposition.context` (beads and matrix reads) | the decomposer (artifact `task context`) | JSON: `task-context.schema.json` |
| `<work>/tasks-<slug>.json` | agent `task-decomposer`; amended by step `beadwrite.plan_story_tasks` when it is handed a correction | steps `beadwrite.plan_story_tasks`, `beadwrite.write_task`, `beadwrite.retire_superseded_tasks` and the Task edge steps (artifact `tasks`); the first step of each Task's journal | JSON: `tasks.schema.json` |
| `<work>/tasks-<slug>.gaps.json` | step `beadwrite.plan_story_tasks`, when the plan has a gap | the decomposer's correction step (artifact `task gaps`) | JSON: `task-gaps.schema.json` |
| `<work>/tasks-<slug>.correction.json` | agent `task-decomposer`, in the correction step a plan with a gap plans | the second step `beadwrite.plan_story_tasks` (merged into `tasks-<slug>.json`) | JSON: `tasks-correction.schema.json` |

### Owner-run portfolio and PRD flows (not part of the Epic pipeline, CONTEXT 7.17)

| Path pattern | Producer | Consumers | Format |
|---|---|---|---|
| `<workDir>/score-plan.json` | `wsjf-scoring#1` (`scoring.plan`) | `wsjf-scoring#2`, `#3`, `#7` | JSON: `scoring.Plan` |
| `<workDir>/judge-input-epic.json`, `judge-input-task.json` | `wsjf-scoring#2` (`scoring.judge_input`) | `wsjf-scoring#3` (input), `#5` | JSON: `wsjf-judge-input.schema.json` |
| `<workDir>/prd/<epic-id>.md` | `wsjf-scoring#2` | `wsjf-scoring#3` (input), `#5` | Markdown: `# <title>` + bead description |
| `<workDir>/judgments/epic/<id>.json`, `judgments/task/<key>.json` | `wsjf-scoring#6` (`jsonartifact.py`), from the candidate `judgments/<level>/candidates/<key>.json` the agent `wsjf-scorer` writes in `#5` | `wsjf-scoring#4`, `#7` | JSON: `wsjf-judgment.schema.json` (`#/$defs/EpicJudgment`, `#/$defs/TaskJudgment`) |
| `<workDir>/record.json` | `wsjf-scoring#7` (`scoring.record`) | `wsjf-scoring#9` | JSON: `scoring.Recorded` |
| `<workDir>/score.json` | `wsjf-scoring#8` (`scoring.score`) | `wsjf-scoring#9` | JSON: `scoring.ScoreResult` |
| `<workDir>/assess-plan.json` | `dependency-assessment#1`; `task-dependency-assessment#1` | `dependency-assessment#8`; `task-dependency-assessment#8` | JSON: `depscore.assess_plan` |
| `<workDir>/context/prd/<id>.md`, `context/task/<id>.md`, `context/index.md` | `dependency-assessment#2`; `task-dependency-assessment#2` | the same flow's `#3` (input), `#5` | Markdown |
| `<workDir>/context.json` | `dependency-assessment#2`; `task-dependency-assessment#2` | the same flow's `#3` (input), `#5` | JSON: `dependency-assessment.schema.json` (`#/$defs/EpicContext` in dependency-assessment, `#/$defs/TaskContext` in task-dependency-assessment) |
| `<workDir>/edges.json` | the same flow's `#6` (`jsonartifact.py`), from the candidate `candidates/edges.json` the agent writes in `#5` (`epic-dependency-assessor`; `task-dependency-mapper`) | the same flow's `#4`, `#7`, `#8` | JSON: `epic-edge-proposal.schema.json` (dependency-assessment); `task-edge-proposal.schema.json` (task-dependency-assessment) |
| `<workDir>/reasoning.md` | the same agent step (`#5`) | none: read by the owner | Markdown |
| `<workDir>/validation.json` | the agent's own check of its candidate in `dependency-assessment#5`; `task-dependency-assessment#5` | the same flow's `#10` (named in `stop` when step 7 saved no relay file) | JSON: `edgeset.ValidationReport` |
| `<workDir>/apply-edges.json` (or `apply-edges-dry-run.json`) | `dependency-assessment#8`; `task-dependency-assessment#8` (with `storyEdges`) | the same flow's `#10` | JSON: `edgeset.ApplyResult` (`edgeset.ApplyRefused` when refused) |
| `<workDir>/scoring/` | `dependency-assessment#9`; `task-dependency-assessment#9` (the `wsjf-scoring` workflow) | as in the `wsjf-scoring` rows | as above |
| `<workDir>/request.json`, `intake.json`, `persona.json`, `okrs.json`, `drafts/pass-<n>.md` (the PRD) and `drafts/pass-<n>.json`, `alignment/pass-<n>.json`, `ruling.json` | `prd-creation`: the workflow writes the request; `stakeholder-request-intake-writer`, `feature-persona-writer`, `feature-objective-writer`, `prd-writer`, `prd-alignment-verifier` and `review-dispute-decider` write the others, each from a candidate under `<workDir>/candidates/` the relay validates and publishes | the next agent of the chain; the workflow's return value names the paths | JSON: `prd-creation.schema.json` (one `$defs` entry each: `Request`, `Intake`, `Persona`, `Okrs`, `Draft`, `Alignment`, `DeadlockRuling`); the PRD is Markdown |
| `<artifacts.dir>/prd-validation/<lens>.json` | `prd-validation`: one lens specialist each (`requirement-classifier`, `ambiguity-detector`, `completeness-checker`, `requirements-conflict-detector`, `constraint-extractor`, `domain-boundary-validator`, `requirements-clarifier` and, when a BRD is named, `brd-traceability-auditor`), from a candidate under `candidates/` the relay validates and publishes | the workflow, which merges them | JSON: `prd-validation-analysis.schema.json` (one `$defs` entry per lens: `ClassificationResult`, `AmbiguityResult`, `CompletenessResult`, `ConflictResult`, `ConstraintResult`, `BoundaryResult`, `ClarificationResult`, `TraceabilityResult`) |
| `<artifacts.dir>/prd-validation.json` | `prd-validation`: the workflow merges the lens results into the candidate `candidates/prd-validation.json`, which the relay validates and publishes | the workflow (the verdict and the matrix records) | JSON: `prd-validation-analysis.schema.json` (`#/$defs/Analysis`; `#/$defs/TracedAnalysis` when a BRD is named) |

`route-elaboration`, `prd-validation` and `gate-enforce` produce no artifact in the Epic pipeline. The
workflows above accept agent files and run their commands through the relay, whose contracts
`epic-contracts.md` lists under "Workflow relay".

## Bead writes

Metadata keys and values below are the constants and key groups of the generated
`<plugin>/skills/beads-contract/scripts/bead_metadata.py`; each key's type, required rule and
allowed values are defined only in `<plugin>/skills/beads-contract/schemas/bead-metadata.schema.json`.
`artifact_key(kind, field)` names an artifact key (`ARTIFACT_KINDS` x `ARTIFACT_FIELDS`).

| Command | Fields and metadata keys | Writing step |
|---|---|---|
| `elaboration.start` (the function behind `depscore.py elaboration-start`), with the dispatch's owner token and its reclaim flag | Epic: `KEY_ELABORATION_STATE` = `ELABORATION_IN_PROGRESS`, `KEY_ELABORATION_STATE_AT` = now, `KEY_ELABORATION_STATE_CAUSE` = `CAUSE_STARTED`, `KEY_ELABORATION_STATE_OWNER` = `<token>` | `prd-to-spec`, before the journal's steps run |
| `beadgraph.write_metadata` | Epic: `artifact_key("trd", "path")`, `artifact_key("trd", "sha256")` | step `trd.confirm` |
| `beadwrite.write_story`: `bd create --type story --parent <epic>` or one `bd update` | Story: title, description, acceptance, notes `repoPath: <repo>`; metadata `KEY_ELAB_KEY` (`story:<slug>`), `KEY_REPO_PATH`, `KEY_DECISION_IDS`, and the `path` and `sha256` artifact keys of kinds `spec`, `spec_data_model`, `spec_criteria` and `story` | step `beadwrite.write_story` |
| `bd dep add <dependent> <task> --type blocks`, then `bd delete <ids...> --force` (`beadwrite.retire_superseded_tasks`) | the Story's unstarted, elaboration-written Task beads that no saved Task matches: each `blocks` edge from a Task of another Story onto one is first added onto the written Tasks that cite an item it cited | step `beadwrite.retire_superseded_tasks` |
| `bd create --type task --parent <story> ... --metadata <json> [--deps blocked-by:...]`, `bd update <id> [--title --description] [--set-metadata ...]`, `bd dep add --file -` (`blocks`), `bd dep remove` (`beadwrite.write_task`), in build order, at least one Task per Story, every Task sized | Task: title, description (with the `## Spec contract` block), acceptance, notes `repoPath: <repo>`; metadata `KEY_ELAB_KEY`, `CONTRACT_KEYS` (the Task build contract, `beadwrite.task_metadata`), `KEY_WSJF_SIZE_ESTIMATE`, `KEY_WSJF_SIZE_LOW`, `KEY_WSJF_SIZE_HIGH`, `KEY_WSJF_SIZE_CONFIDENCE` and `KEY_WSJF_CONTENT_HASH`; same-Story `blocks` edges and `blockedByExternal` blockers | step `beadwrite.write_task`, one step per Task, in build order |
| `beadwrite.write_all_task_edges`, with the files of every Story of the span | `blocks` edges between Tasks of different Stories (closure edges and `task-deps.json`, cycle-closing edges dropped) | step `beadwrite.write_all_task_edges` |
| `elaboration.finish` (which calls `scoring.score`) with the write scope limited to the Epic's Tasks | the Epic's Tasks only: the `WSJF_KEYS` the rubric's score row carries, less `scoring.SIZE_JUDGED_KEYS` (`scoring._apply`; the Epic's WSJF keys are not written, CONTEXT 7.17); once every Task is scored, Epic: `KEY_ELABORATION_STATE` = `ELABORATION_DONE`, `KEY_ELABORATION_STATE_AT` = now, `KEY_ELABORATION_STATE_CAUSE` = `CAUSE_DECOMPOSED`, `KEY_ELABORATION_STATE_OWNER` emptied; then `story-edges`: Story `blocks` edges and `KEY_STORY_OWNED_BLOCKERS`, `KEY_STORY_OWNED_BLOCKERS_AT`, `KEY_STORY_EDGE_REASONS` (Stories get no WSJF) | steps `elaboration.score` (the scores) and `elaboration.finish` (the Epic's mark); `storyedges.story_edges` is its own step between them, after step `elaboration.done_rule` |
| `elaboration.release`, with the dispatch's owner token | Epic: `KEY_ELABORATION_STATE_OWNER` emptied (when still this run's token) | `prd-to-spec`, when a dispatch ends before the Epic's mark |
| *Rows below to `storyedges.story_edges` belong to the owner-run portfolio flows, which are not part of the Epic pipeline (CONTEXT 7.17). Two are shared: `scoring.score` and `storyedges.story_edges` also run inside `prd-to-spec`.* | | |
| `scoring.record` (`depscore.py record`): `bd update --set-metadata` | Epic: `KEY_WSJF_UBV`, `KEY_WSJF_TC`, `KEY_WSJF_CONFIDENCE`, `scoring.SIZE_JUDGED_KEYS` (only when its size does not roll up from Tasks) and `KEY_WSJF_CONTENT_HASH`; Task: `scoring.SIZE_JUDGED_KEYS` and `KEY_WSJF_CONTENT_HASH`; adopted items: `KEY_WSJF_CONTENT_HASH` only | `wsjf-scoring#7` |
| `scoring.score` (`depscore.py score`): `bd update --set-metadata` | the `WSJF_KEYS` the rubric's score row carries, less `scoring.SIZE_JUDGED_KEYS` (`scoring._apply`), on every open Epic and Task whose value changed | `wsjf-scoring#8` (also run by `dependency-assessment#9`, `task-dependency-assessment#9`) |
| `edgeset.apply_edges` (`depscore.py apply-edges`): `bd dep add --type tracks`, conversions, removals, `bd update --set-metadata` | Epic `tracks` edges touching the Epic; on each blocked Epic `KEY_SEQ_OWNED_BLOCKERS`, `KEY_SEQ_OWNED_BLOCKERS_AT`, `KEY_SEQ_EDGE_REASONS`, `KEY_SEQ_EDGE_WITHDRAWN`; on the assessed Epic `KEY_SEQ_CONTENT_HASH`, `KEY_SEQ_ASSESSED_AT` | `dependency-assessment#8` |
| `edgeset.apply_edges` with `level="task"` | Task `blocks` edges touching the Task and the same `KEY_SEQ_*` keys on Tasks | `task-dependency-assessment#8` |
| `storyedges.story_edges` | Story `blocks` edges and `KEY_STORY_OWNED_BLOCKERS`, `KEY_STORY_OWNED_BLOCKERS_AT`, `KEY_STORY_EDGE_REASONS` | `task-dependency-assessment#8` (and inside `prd-to-spec`) |
| `elabstate.hold_for_person` | Epic: `KEY_ELABORATION_STATE` = `ELABORATION_AUTHORING`, `KEY_ELABORATION_STATE_AT` = now, `KEY_ELABORATION_STATE_CAUSE` = `CAUSE_AWAITING_HUMAN`, `KEY_ELABORATION_STATE_OWNER` emptied | `driver` (from `requiredHumanActions`, `driver-contract.md` §4); no Epic flow writes it |
| `artifactio.file_in_vault` bead metadata | Epic: `artifact_key("trd", "vault_path")`; each Story: the `vault_path` artifact keys of kinds `spec`, `spec_data_model`, `spec_criteria` | `driver` (lane, after `ELABORATION_DONE`) |
| `elabmark.py --set=<state>` | Epic: `KEY_ELABORATION_STATE`, cause `CAUSE_HUMAN` | the owner's CLI (`driver-contract.md` §2) |

The steps of the Architecture container, the repository span step, `route-elaboration`,
`prd-validation` and `gate-enforce` write nothing to beads.
