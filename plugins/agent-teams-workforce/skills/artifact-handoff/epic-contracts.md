# Epic artifact contracts

The index of the contracts of every file Epic elaboration, and the PRD and portfolio workflows
before it, hand from one party to another. Each row names the artifact, who writes it, who reads
it, and its contract file. The contract file is the one definition: its descriptions say what each
member holds, what it means and when the file is complete. This index restates none of it.

Find your assigned artifact below and read its contract file, never a copy of it. A schema file
named here is under this skill's `schemas/` folder unless its path says otherwise. A JSON schema is
never pasted into a brief: a brief names the contract file by path, and the checkpoint commands
bind the producer to it with `--schema <path>`. Python validates every accepted file against its
contract; a structurally valid file is not automatically a correct one.

All architecture agents also read effective-architecture/review-standard.md, which holds every
criterion a document is judged by. `aws-solutions-architect` is responsible for the architecture
an Epic needs; its team's files are in the Architecture table.

A row whose contract is a Python name has no agent writer and no agent reader: code alone
produces and reads it, and the typed module named is its one definition.

## Briefs, journals and results

| Artifact | Writer | Readers | Contract |
|---|---|---|---|
| brief: the prompt of an agent session | the orchestrator (`orchestrator/core/agent_context.py`) | every agent session the orchestrator starts | `agent-brief.schema.json` |
| step journal: `<bead>.step-journal.json` | the orchestrator; an agent only through `atw-step-journal` | the orchestrator; the build and deploy pipelines | `skills/pipeline-contracts/schemas/step-journal.schema.json` |
| helper steps: the child steps a lead agent adds for its helpers, and their files | a lead agent, through `atw-step-journal` | its helpers; the script that runs the journal | `skills/pipeline-contracts/schemas/helper-steps.schema.json` |
| handback line: the last line of a headless dispatcher session | the headless dispatcher session | the driver | `skills/pipeline-contracts/schemas/handback-line.schema.json` |
| handback: the orchestrator's result document | `orchestrator/run.py` | the driver | `orchestrator/core/handback_contract.py` `HandbackDocument` |
| run manifest: `<work>/run.json` | the orchestrator | the driver; the owner | `orchestrator/core/manifest.py` `RunManifest` |
| ledger events: `state/ledger.jsonl` | the driver | the driver | `<control>/ops/sdlc-automation/ledgerevents.py` |

## Workflow relay

The PRD and portfolio workflows run their commands and accept agent files through the relay
(`scripts/shared-blocks/relay.js`).

| Artifact | Writer | Readers | Contract |
|---|---|---|---|
| checkpoint sidecar of a candidate file | `scripts/portfolio/artifactcontract.py` | `scripts/portfolio/jsonartifact.py` | `checkpoint.schema.json` |
| artifact reference: what a producer session returns | the producer session | the workflow script | `artifact-reference.schema.json` |
| relay command result | `workflow-command-runner` | the workflow script | `relay-command-result.schema.json` |
| relay registered result | `workflow-command-runner` | the workflow script | `relay-registered-result.schema.json` |

## Architecture

| Artifact | Writer | Readers | Contract |
|---|---|---|---|
| architecture context: `<arch-work>/context.json` | step `prd_to_spec.open_run` | `aws-solutions-architect` (as `context`); the architecture steps | `architecture-context.schema.json` |
| architecture state: `<arch-work>/state.json` | `aws-solutions-architect` | `aws-solutions-architect` | `architecture-state.schema.json` |
| architecture result: `<arch-work>/result.json` | `aws-solutions-architect` | the check step; `architecture-team-lead`; the span step | `architecture-result.schema.json` |
| specialist request | `aws-solutions-architect`; `architecture-team-lead` | the design specialist, diagram author or `polyrepo-steward` asked | `specialist-request.schema.json` |
| specialist answer | the agent asked | `aws-solutions-architect`; `architecture-team-lead` | `specialist-answer.schema.json` |
| TRD request | the script, for the TRD initial write (mode `initial`); `aws-solutions-architect`, for each update | `trd-author` | `trd-request.schema.json` |
| TRD answer | `trd-author` | `aws-solutions-architect`; the step that accepts it, which records each requirement in the matrix as a `trd` pointer | `trd-answer.schema.json` |
| write request | `aws-solutions-architect` | `architecture-maintainer` | `write-request.schema.json` |
| write result | `architecture-maintainer` | `aws-solutions-architect` | `write-result.schema.json` |
| architecture documents (views, standards and policies): `<arch>/arc42/**` except section 2, and the detailed architecture `<arch>/detailed/**` | `architecture-maintainer` | the architecture team, `trd-author`, the spec authors | `skills/arc42/references/arc42-section-model.md`; `document-front-matter.schema.json#/$defs/ArchitectureView` and `#/$defs/ArchitectureStandard`; the architecture and design criteria of `skills/effective-architecture/review-standard.md` |
| check result: `<arch-work>/checks/<step id>/check.json` | the check step | `aws-solutions-architect` (as `findings`) | `check-result.schema.json` |
| review log: `<arch-work>/review-log.json` (the context's `reviewLogPath`) | `aws-solutions-architect` | the check step (`review_log.problems`); the promotion step, which files it at `<arch>/review-logs/<epic id>.json` and links it from the Epic's matrix entry as `reviewLog` | `skills/log-architecture-review/schemas/review-log.schema.json` |
| review scope: `<arch-work>/checks/<step id>/review-scope.json` | the check step (what `atw-matrix review-scope --epic` prints) | the promotion step | `scripts/portfolio/matrixreview.py` `ReviewScope` |
| unlinked links: `<arch-work>/checks/<step id>/unlinked.json` | the check step (what `atw-matrix epic <id> --unlinked` prints) | none: evidence | `scripts/portfolio/matrixquery.py` `EpicView` |
| lead routing: `<arch-work>/routing-<step>.json` | `architecture-team-lead` | the script | `lead-routing.schema.json` |
| architecture question | `architecture-team-lead` | `architecture-decider` | `architecture-question.schema.json` |
| architecture ruling: `<arch-work>/ruling-<step>.json` | `architecture-decider` | `architecture-team-lead`; `aws-solutions-architect` | `architecture-ruling.schema.json` |
| promoted documents: `<arch-work>/promoted.json` | the promotion step | none: evidence | `orchestrator/flows/architecture_promotion.py` |
| matrix: `matrix.json` | `atw-matrix`, by the session's role | `atw-matrix` | `matrix.schema.json` with `matrix-kinds.json` |

## TRD

| Artifact | Writer | Readers | Contract |
|---|---|---|---|
| TRD: `<work>/trd.md` | `trd-author` | `aws-solutions-architect`; the spec authors, reviewer and decider; the Story and Task journals | `document-front-matter.schema.json#/$defs/TrdDocument`, each requirement `architecture-result.schema.json#/$defs/TrdRequirement`; the technical-requirement criteria of `skills/effective-architecture/review-standard.md` |

## Repository span

| Artifact | Writer | Readers | Contract |
|---|---|---|---|
| span: `<work>/repo-scoping.json` | the span step | the spec and Task steps; the spec authors; `task-decomposer` | `placement.schema.json` |
| elements: `<work>/span-elements.json` | the span step | the spec and Task steps; the spec authors; `task-decomposer` | `target-report.schema.json#/$defs/DeltaResult` |
| repository creation: `<work>/repo-creation.json` | the span step | the orchestrator's handback | `orchestrator/flows/repo_scoping.py` `create_repositories` |

## Specs and Stories

| Artifact | Writer | Readers | Contract |
|---|---|---|---|
| repository context: `<work>/spec-<slug>.context.json` | step `spec_authoring.context` | the spec authors; `spec-reviewer`; `task-decomposer` | `spec-context.schema.json` |
| ui bundles: `<work>/spec-<slug>.bundles.json` | step `cdsbundles.list_bundles` | `api-specification-author`; step `spec_authoring.normalize_ui` | `ui-bundles.schema.json` |
| ui sources: `<work>/candidates/spec-<slug>.ui.json`, then `<work>/spec-<slug>.ui.json` | `api-specification-author`, then step `spec_authoring.normalize_ui` | the contracts session; `task-decomposer` | `spec-ui.schema.json` |
| contracts document: `<work>/spec-<slug>.md` | `api-specification-author` | `acceptance-criteria-writer`; `spec-reviewer`; `review-dispute-decider`; `task-decomposer` | `document-front-matter.schema.json#/$defs/SpecDocument`; the specs-and-Tasks criteria of `skills/effective-architecture/review-standard.md` |
| data-model document: `<work>/spec-<slug>.data-model.md` | `data-model-specification-author` | `acceptance-criteria-writer`; `spec-reviewer`; `review-dispute-decider`; `task-decomposer` | `document-front-matter.schema.json#/$defs/SpecDocument`; the specs-and-Tasks criteria of `skills/effective-architecture/review-standard.md` |
| criteria document: `<work>/spec-<slug>.criteria.md` | `acceptance-criteria-writer` | `spec-reviewer`; `review-dispute-decider`; `task-decomposer` | the specs-and-Tasks criteria of `skills/effective-architecture/review-standard.md`; Tasks cite its ids as `tasks.schema.json` states |
| spec review: `<work>/spec-<slug>.review.json` | `spec-reviewer` | the three spec authors; `review-dispute-decider` | `spec-review.schema.json` |
| spec correction and revision: `<work>/spec-<slug>.<document>.correction.json`, `.revision.json` | the author of the document | `review-dispute-decider` | `spec-correction.schema.json` |
| spec ruling: `<work>/spec-<slug>.ruling.json` | `review-dispute-decider` | the three spec authors | `spec-ruling.schema.json` |
| Story document: `<work>/story-<slug>.json` | step `spec_authoring.story_document` | step `beadwrite.write_story`; `task-decomposer` | `story-document.schema.json` |
| filed documents in the vault | the driver (`artifactio.file_in_vault`) | the owner | the driver's `artifactio.py` |

## Tasks

| Artifact | Writer | Readers | Contract |
|---|---|---|---|
| task context: `<work>/tasks-<slug>.context.json` | step `task_decomposition.context` | `task-decomposer` | `task-context.schema.json` |
| Tasks file: `<work>/tasks-<slug>.json` | `task-decomposer` | the Task bead steps; `task-dependency-mapper` | `tasks.schema.json` |
| task gaps: `<work>/tasks-<slug>.gaps.json` | step `beadwrite.plan_story_tasks` | `task-decomposer` | `task-gaps.schema.json` |
| Tasks correction: `<work>/tasks-<slug>.correction.json` | `task-decomposer` | step `beadwrite.plan_story_tasks` | `tasks-correction.schema.json` |
| closure edges: `<work>/closure-edges.json` | step `beadwrite.closure_task_edges` | `task-dependency-mapper`; step `beadwrite.write_all_task_edges` | `closure-edges.schema.json` |
| task dependency listing: `<work>/task-deps-inputs.json` | step `task_edges.listing` | `task-dependency-mapper` | `task-dependency-listing.schema.json` |
| task dependencies: `<work>/task-deps.json` | `task-dependency-mapper` | step `beadwrite.write_all_task_edges` | `task-deps.schema.json` |
| Task edges written: `<work>/task-edges/all.json` | step `beadwrite.write_all_task_edges` | none: evidence | `scripts/portfolio/beadwrite.py` `AllEdgeWrite` |

## PRD and portfolio workflows

These are owner-run workflows, not Epic elaboration. Their files are in the run's `<workDir>` (or
`<artifacts.dir>`).

| Artifact | Writer | Readers | Contract |
|---|---|---|---|
| prd-creation request, intake, persona, objectives, draft record, alignment verdict and deadlock ruling | the workflow; `stakeholder-request-intake-writer`; `feature-persona-writer`; `feature-objective-writer`; `prd-writer`; `prd-alignment-verifier`; `review-dispute-decider` | the next agent of the chain; the workflow | `prd-creation.schema.json` (one `$defs` entry each) |
| prd-validation analysis | `prd-validation-analyst` | the workflow | `prd-validation-analysis.schema.json` |
| assessment context: `<workDir>/context.json` | `depscore.py assess-context` | `epic-dependency-assessor`; `task-dependency-mapper` | `dependency-assessment.schema.json` (`$defs/EpicContext`, `$defs/TaskContext`) |
| Epic edge proposal: `<workDir>/edges.json` | `epic-dependency-assessor` | the dependency-assessment workflow | `epic-edge-proposal.schema.json` |
| Task edge proposal: `<workDir>/edges.json` | `task-dependency-mapper` | the task-dependency-assessment workflow | `task-edge-proposal.schema.json` |
| WSJF judge input: `<workDir>/judge-input-<level>.json` | `depscore.py judge-input` | `wsjf-scorer` | `wsjf-judge-input.schema.json` |
| WSJF judgment: `<workDir>/judgments/<level>/<key>.json` | `wsjf-scorer` | `depscore.py record` | `wsjf-judgment.schema.json` |

## built-comparison

Schema: [built-comparison.schema.json](schemas/built-comparison.schema.json).

Fields and interpretation: differences, each with the element, the code location, the approved heading, the difference and the built-difference document written for it; filesWritten. `built-architecture-comparer` writes it for one Story. An empty differences list means the code the Story built matches the approved architecture.
