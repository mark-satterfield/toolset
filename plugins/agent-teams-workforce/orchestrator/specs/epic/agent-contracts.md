# Epic agent contracts

Failure handling: bounded transient retries and quota pauses remain. An ordinary item failure is recorded and excluded from selection for the current invocation; other eligible items continue. Setup, code, schema, and runtime type defects stop new dispatch, preserve the original diagnostic, and let current paid steps finish. Named within-step corrective passes remain bounded content work; failed runs do not dispatch repair or diagnosis agents.

Every contract an agent produces or consumes lives as a JSON Schema in the artifact-handoff
skill; a contract only code produces and consumes lives in one typed Python module in the
producer's repository, named in the Rules column with Skill `none`. This table names each
contract's one place and restates none of its fields. An agent of a contract loads a contract
skill: artifact-handoff, or architecture-baseline, which holds the criteria of every level and
points the architecture team to the same schemas folder. `polyrepo-steward` loads neither: its
definition names the schemas folder for the one request it answers. An artifact Python produces
has no agent reviewer. The rows of the owner-run portfolio workflows carry the contract
`out-of-scope`: no Epic session produces or reads them.

## Agents

| Agent | Definition | Skills | Produces | Reads |
|---|---|---|---|---|
| aws-solutions-architect | agents/aws-solutions-architect.md | agent-teams-workforce:architecture-baseline, agent-teams-workforce:subagent-contract, agent-teams-workforce:senior-architect, agent-teams-workforce:aws-solution-architect, agent-teams-workforce:aws-serverless-eda, agent-teams-workforce:senior-security, agent-teams-workforce:graphrag-lookup | architecture-state,architecture-result,specialist-request,trd-request,write-request | architecture-context,check-result,scope-review,specialist-answer,trd-answer,write-result,architecture-ruling,architecture-views |
| architecture-team-lead | agents/architecture-team-lead.md | agent-teams-workforce:architecture-baseline, agent-teams-workforce:subagent-contract | lead-routing,specialist-request,architecture-question | scope-review,architecture-result,specialists,specialist-answer,architecture-ruling |
| integration-pattern-architect | agents/integration-pattern-architect.md | agent-teams-workforce:subagent-contract, agent-teams-workforce:senior-architect, agent-teams-workforce:aws-serverless-eda, agent-teams-workforce:architecture-baseline | specialist-answer | specialist-request,architecture-views |
| persistence-architecture-specialist | agents/persistence-architecture-specialist.md | agent-teams-workforce:subagent-contract, agent-teams-workforce:dynamodb, agent-teams-workforce:database-schema-designer, agent-teams-workforce:architecture-baseline | specialist-answer | specialist-request,architecture-views |
| security-architecture-designer | agents/security-architecture-designer.md | agent-teams-workforce:subagent-contract, agent-teams-workforce:senior-security, agent-teams-workforce:iam, agent-teams-workforce:secrets-manager, agent-teams-workforce:architecture-baseline | specialist-answer | specialist-request,architecture-views |
| cdk-infrastructure-designer | agents/cdk-infrastructure-designer.md | agent-teams-workforce:subagent-contract, agent-teams-workforce:aws-cdk-development, agent-teams-workforce:resource-naming, agent-teams-workforce:architecture-baseline | specialist-answer | specialist-request,architecture-views |
| event-schema-designer | agents/event-schema-designer.md | agent-teams-workforce:subagent-contract, agent-teams-workforce:aws-serverless-eda, agent-teams-workforce:eventbridge, agent-teams-workforce:architecture-baseline, agent-teams-workforce:skillspoke-events | specialist-answer | specialist-request,architecture-views |
| api-contract-designer | agents/api-contract-designer.md | agent-teams-workforce:subagent-contract, agent-teams-workforce:api-design-reviewer, agent-teams-workforce:architecture-baseline | specialist-answer | specialist-request,architecture-views |
| graphql-schema-designer | agents/graphql-schema-designer.md | agent-teams-workforce:subagent-contract, agent-teams-workforce:api-design-reviewer, agent-teams-workforce:architecture-baseline | specialist-answer | specialist-request,architecture-views |
| domain-event-modeler | agents/domain-event-modeler.md | agent-teams-workforce:subagent-contract, agent-teams-workforce:aws-serverless-eda, agent-teams-workforce:architecture-baseline, agent-teams-workforce:skillspoke-events | specialist-answer | specialist-request,architecture-views |
| bounded-context-mapper | agents/bounded-context-mapper.md | agent-teams-workforce:subagent-contract, agent-teams-workforce:senior-architect, agent-teams-workforce:architecture-baseline | specialist-answer | specialist-request,architecture-views |
| architecture-diagram-author | agents/architecture-diagram-author.md | agent-teams-workforce:subagent-contract, agent-teams-workforce:architecture-diagramming, agent-teams-workforce:c4-diagramming, agent-teams-workforce:uml-diagramming, agent-teams-workforce:architecture-baseline | specialist-answer | specialist-request,architecture-views |
| c4-diagram-author | agents/c4-diagram-author.md | agent-teams-workforce:subagent-contract, agent-teams-workforce:architecture-diagramming, agent-teams-workforce:c4-diagramming, agent-teams-workforce:architecture-baseline | specialist-answer | specialist-request,architecture-views |
| uml-diagram-author | agents/uml-diagram-author.md | agent-teams-workforce:subagent-contract, agent-teams-workforce:architecture-diagramming, agent-teams-workforce:uml-diagramming, agent-teams-workforce:architecture-baseline | specialist-answer | specialist-request,architecture-views |
| architecture-pattern-challenger | agents/architecture-pattern-challenger.md | agent-teams-workforce:subagent-contract, agent-teams-workforce:senior-architect, agent-teams-workforce:aws-solution-architect, agent-teams-workforce:architecture-baseline | scope-review | review-scope,architecture-result,architecture-views,trd-document |
| architecture-tradeoff-skeptic | agents/architecture-tradeoff-skeptic.md | agent-teams-workforce:subagent-contract, agent-teams-workforce:senior-architect, agent-teams-workforce:architecture-baseline | scope-review | review-scope,architecture-result,architecture-views,trd-document |
| architecture-boundary-guardian | agents/architecture-boundary-guardian.md | agent-teams-workforce:subagent-contract, agent-teams-workforce:senior-architect, agent-teams-workforce:architecture-baseline | scope-review | review-scope,architecture-result,architecture-views,trd-document |
| operational-readiness-reviewer | agents/operational-readiness-reviewer.md | agent-teams-workforce:subagent-contract, agent-teams-workforce:observability-designer, agent-teams-workforce:architecture-baseline | scope-review | review-scope,architecture-result,architecture-views,trd-document |
| failure-mode-analyst | agents/failure-mode-analyst.md | agent-teams-workforce:subagent-contract, agent-teams-workforce:senior-architect, agent-teams-workforce:observability-designer, agent-teams-workforce:architecture-baseline | scope-review | review-scope,architecture-result,architecture-views,trd-document |
| cost-architecture-reviewer | agents/cost-architecture-reviewer.md | agent-teams-workforce:subagent-contract, agent-teams-workforce:aws-cost-operations, agent-teams-workforce:architecture-baseline | scope-review | review-scope,architecture-result,architecture-views,trd-document |
| cost-impact-reviewer | agents/cost-impact-reviewer.md | agent-teams-workforce:subagent-contract, agent-teams-workforce:aws-cost-operations, agent-teams-workforce:architecture-baseline | scope-review | review-scope,architecture-result,architecture-views,trd-document |
| trd-validator | agents/trd-validator.md | agent-teams-workforce:subagent-contract, agent-teams-workforce:validation-protocol, agent-teams-workforce:architecture-baseline | scope-review | review-scope,architecture-result,trd-document |
| architecture-decider | agents/architecture-decider.md | agent-teams-workforce:architecture-baseline, agent-teams-workforce:subagent-contract, agent-teams-workforce:validation-protocol, agent-teams-workforce:senior-architect, agent-teams-workforce:aws-solution-architect | architecture-ruling | architecture-question |
| architecture-maintainer | agents/architecture-maintainer.md | agent-teams-workforce:architecture-baseline, agent-teams-workforce:subagent-contract, agent-teams-workforce:arc42-maintain, agent-teams-workforce:c4-diagramming, agent-teams-workforce:uml-diagramming | write-result,architecture-views | write-request,architecture-views |
| trd-author | agents/trd-author.md | agent-teams-workforce:subagent-contract, agent-teams-workforce:architecture-baseline | trd-document,trd-answer | trd-request,architecture-state,architecture-views |
| polyrepo-steward | agents/polyrepo-steward.md | agent-teams-workforce:subagent-contract, agent-teams-workforce:graphrag-lookup, polyrepo-repo, polyrepo-info, polyrepo-governance, polyrepo-beads | specialist-answer | specialist-request,matrix |
| api-specification-author | agents/api-specification-author.md | agent-teams-workforce:subagent-contract, agent-teams-workforce:validation-protocol, agent-teams-workforce:api-design-reviewer, agent-teams-workforce:artifact-handoff, agent-teams-workforce:skillspoke-events, agent-teams-workforce:architecture-baseline | spec-document,spec-ui,spec-correction | trd-document,placement,architecture-views,span-elements,spec-review,spec-ruling |
| data-model-specification-author | agents/data-model-specification-author.md | agent-teams-workforce:subagent-contract, agent-teams-workforce:validation-protocol, agent-teams-workforce:dynamodb, agent-teams-workforce:database-schema-designer, agent-teams-workforce:artifact-handoff, agent-teams-workforce:architecture-baseline | data-model-document,spec-correction | trd-document,placement,architecture-views,span-elements,spec-review,spec-ruling |
| acceptance-criteria-writer | agents/acceptance-criteria-writer.md | agent-teams-workforce:subagent-contract, agent-teams-workforce:validation-protocol, agent-teams-workforce:senior-qa, agent-teams-workforce:artifact-handoff | criteria-document,spec-correction | trd-document,spec-document,data-model-document,spec-review,spec-ruling |
| openapi-contract-reviewer | agents/openapi-contract-reviewer.md | agent-teams-workforce:subagent-contract, agent-teams-workforce:validation-protocol, agent-teams-workforce:api-design-reviewer, agent-teams-workforce:skillspoke-events, agent-teams-workforce:artifact-handoff, agent-teams-workforce:architecture-baseline | spec-review | spec-document,data-model-document,criteria-document,trd-document |
| spec-decider | agents/spec-decider.md | agent-teams-workforce:subagent-contract, agent-teams-workforce:validation-protocol, agent-teams-workforce:senior-architect, agent-teams-workforce:cove-prompt-design, agent-teams-workforce:artifact-handoff, agent-teams-workforce:architecture-baseline | spec-ruling | spec-review,spec-correction,spec-document,data-model-document,criteria-document,trd-document |
| task-decomposer | agents/task-decomposer.md | agent-teams-workforce:subagent-contract, agent-teams-workforce:validation-protocol, agent-teams-workforce:beads-contract, agent-teams-workforce:graphrag-lookup, agent-teams-workforce:artifact-handoff, agent-teams-workforce:wsjf | tasks,tasks-correction | story,placement,span-elements,spec-document,data-model-document,criteria-document,spec-ui |
| task-dependency-mapper | agents/task-dependency-mapper.md | agent-teams-workforce:subagent-contract, agent-teams-workforce:validation-protocol, agent-teams-workforce:beads-contract, agent-teams-workforce:artifact-handoff | task-deps | tasks,closure-edges |

## Agents no Epic step starts

A script step writes the Story document, so no step starts user-story-writer (DESIGN 11.5).
prd-validation-analyst, filing-clerk, advantage-evaluator, phase-gate-enforcer, wsjf-scorer and
epic-sequencer are started by their own workflows or by a person. No Epic step starts
architecture-fitness-function-author or ubiquitous-language-writer. built-architecture-comparer and
architecture-conformance-reviewer are started by the built-version workflow.
workflow-command-runner is never an Epic session.

## Artifacts

Paths reproduce INDEX.md exactly. Python means no agent producer or reviewer at that edge.
An `out-of-scope` row is listed for coverage and is no Epic contract.

| Artifact | Contract | Producers | Reviewers or consumers | Skill | Rules |
|---|---|---|---|---|---|
| `<control>/.claude/workflow-runs/step-journals/<bead>.step-journal.json` | step-journal | python | python | none | `<plugin>/skills/pipeline-contracts/scripts/step_journal_contract.py` `Journal` |
| `<control>/ops/sdlc-automation/matrix.json` | matrix | python | python | artifact-handoff `schemas/matrix.schema.json` | matrix (`matrix_contract.Matrix`) |
| `<arch-work>/context.json` | architecture-context | python | aws-solutions-architect | architecture-baseline `schemas/architecture-context.schema.json` | architecture-context (`architecture_work_contract.ArchitectureContext`) |
| `<arch-work>/state.json` | architecture-state | aws-solutions-architect | trd-author | architecture-baseline `schemas/architecture-state.schema.json` | architecture-state (`architecture_work_contract.ArchitectureState`) |
| `<arch-work>/result.json` | architecture-result | aws-solutions-architect | architecture-pattern-challenger,architecture-tradeoff-skeptic,architecture-boundary-guardian,operational-readiness-reviewer,failure-mode-analyst,cost-architecture-reviewer,cost-impact-reviewer,trd-validator,architecture-team-lead | architecture-baseline `schemas/architecture-result.schema.json` | architecture-result (`architecture_work_contract.ArchitectureResult`) |
| a request file for a specialist, a diagram author or the steward (the architect's under `<arch-work>/helpers/`) | specialist-request | aws-solutions-architect,architecture-team-lead | integration-pattern-architect,persistence-architecture-specialist,security-architecture-designer,cdk-infrastructure-designer,event-schema-designer,api-contract-designer,graphql-schema-designer,domain-event-modeler,bounded-context-mapper,architecture-diagram-author,c4-diagram-author,uml-diagram-author | architecture-baseline `schemas/specialist-request.schema.json` | specialist-request (`architecture_work_contract.SpecialistRequest`) |
| the answer file a specialist request names | specialist-answer | integration-pattern-architect,persistence-architecture-specialist,security-architecture-designer,cdk-infrastructure-designer,event-schema-designer,api-contract-designer,graphql-schema-designer,domain-event-modeler,bounded-context-mapper,architecture-diagram-author,c4-diagram-author,uml-diagram-author | aws-solutions-architect,architecture-team-lead | architecture-baseline `schemas/specialist-answer.schema.json` | specialist-answer (`architecture_work_contract.SpecialistAnswer`) |
| a TRD request file (under `<arch-work>/helpers/`) | trd-request | aws-solutions-architect | trd-author | architecture-baseline `schemas/trd-request.schema.json` | trd-request (`architecture_work_contract.TrdRequest`) |
| the answer file a TRD request names | trd-answer | trd-author | aws-solutions-architect | architecture-baseline `schemas/trd-answer.schema.json` | trd-answer (`architecture_work_contract.TrdAnswer`) |
| a write request file (under `<arch-work>/helpers/`) | write-request | aws-solutions-architect | architecture-maintainer | architecture-baseline `schemas/write-request.schema.json` | write-request (`architecture_work_contract.WriteRequest`) |
| the result file a write request names | write-result | architecture-maintainer | aws-solutions-architect | architecture-baseline `schemas/write-result.schema.json` | write-result (`architecture_work_contract.WriteResult`) |
| `<arch>/arc42/**` except section 2 (edits; `lifecycle_state: effective`, commit and push after review) | architecture-views | architecture-maintainer | aws-solutions-architect,integration-pattern-architect,persistence-architecture-specialist,security-architecture-designer,cdk-infrastructure-designer,event-schema-designer,api-contract-designer,graphql-schema-designer,domain-event-modeler,bounded-context-mapper,architecture-diagram-author,c4-diagram-author,uml-diagram-author,architecture-pattern-challenger,architecture-tradeoff-skeptic,architecture-boundary-guardian,operational-readiness-reviewer,failure-mode-analyst,cost-architecture-reviewer,cost-impact-reviewer,trd-author,api-specification-author,data-model-specification-author | artifact-handoff | architecture-views |
| `<arch-work>/check-<n>.json` | check-result | python | aws-solutions-architect | architecture-baseline `schemas/check-result.schema.json` | check-result (`architecture_work_contract.CheckResult`) |
| `<arch-work>/review-scope.json` | review-scope | python | python | none | review-scope (`<plugin>/scripts/portfolio/matrixreview.py` `ReviewScope`) |
| `<arch-work>/review-scope.<reviewer>.json` | review-scope | python | architecture-pattern-challenger,architecture-tradeoff-skeptic,architecture-boundary-guardian,operational-readiness-reviewer,failure-mode-analyst,cost-architecture-reviewer,cost-impact-reviewer,trd-validator | none | review-scope (`orchestrator/flows/architecture_check.py` `ReviewerScope`: `bead`, `epic`, `reviewer`, `groups`, `criteria`, `documents`, `trd`, `signals`) |
| `<arch-work>/reviews/<reviewer>.json` (a re-check: `<reviewer>.<step>.json`; as returned: `.as-returned.json`) | scope-review | architecture-pattern-challenger,architecture-tradeoff-skeptic,architecture-boundary-guardian,operational-readiness-reviewer,failure-mode-analyst,cost-architecture-reviewer,cost-impact-reviewer,trd-validator | architecture-team-lead,aws-solutions-architect | architecture-baseline `schemas/scope-review.schema.json` | scope-review (`architecture_work_contract.ScopeReview`) |
| `<arch-work>/specialists.json` | specialists | python | architecture-team-lead | architecture-baseline `schemas/specialists.schema.json` | specialists (`architecture_work_contract.SpecialistList`) |
| `<arch-work>/routing-<step>.json` | lead-routing | architecture-team-lead | python | architecture-baseline `schemas/lead-routing.schema.json` | lead-routing (`architecture_work_contract.LeadRouting`) |
| a question file for the decider (under `<arch-work>/`) | architecture-question | architecture-team-lead | architecture-decider | architecture-baseline `schemas/architecture-question.schema.json` | architecture-question (`architecture_work_contract.UnsettledMatter`) |
| `<arch-work>/ruling-<step>.json` | architecture-ruling | architecture-decider | architecture-team-lead,aws-solutions-architect | architecture-baseline `schemas/architecture-ruling.schema.json` | architecture-ruling (`architecture_work_contract.ArchitectureRuling`) |
| `<arch-work>/promoted.json` | promoted-documents | python | python | none | `<plugin>/orchestrator/flows/architecture_promotion.py` |
| `<work>/trd.md` | trd-document | trd-author | trd-validator,api-specification-author,data-model-specification-author,acceptance-criteria-writer,openapi-contract-reviewer,spec-decider | artifact-handoff | trd-document |
| `<work>/span-elements.json` | span-elements | python | api-specification-author,data-model-specification-author,task-decomposer | artifact-handoff `schemas/target-report.schema.json` | span-elements (`target_contract.DeltaResult`) |
| `<work>/repo-scoping.json` | placement | python | api-specification-author,data-model-specification-author,task-decomposer | artifact-handoff `schemas/placement.schema.json` | placement (`placement_contract.PlacementRuling`) |
| `<work>/closure-edges.json` | closure-edges | python | task-dependency-mapper | artifact-handoff | closure-edges |
| `<work>/task-deps.json` | task-deps | task-dependency-mapper | python | artifact-handoff | task-deps |
| `<work>/task-edges/all.json` | task-edges | python | python | artifact-handoff | task-edges |
| the handback (`run.py --handback`, and handbacks the driver builds) | handback | python | python | none | `<plugin>/orchestrator/core/handback_contract.py` `HandbackDocument` |
| `<work>/run.json` | run-manifest | python | python | none | `<plugin>/orchestrator/core/manifest.py` `RunManifest` |
| `<control>/ops/sdlc-automation/state/ledger.jsonl` (events appended) | events | python | python | none | `<control>/ops/sdlc-automation/ledgerevents.py` |
| `<work>/repo-creation.json` | repo-creation | python | python | artifact-handoff | repo-creation |
| a new repository (local checkout and GitHub; the steward's manifest, changelog and beads fleet list) | repo-creation | python | python | artifact-handoff | repo-creation |
| `<prd dir>/../trds/<stem>-trd.md` in the vault | trd-document | python | api-specification-author,data-model-specification-author,acceptance-criteria-writer | artifact-handoff | trd-document |
| `<work>/spec-<slug>.bundles.json` | bundles | python | python | artifact-handoff | bundles |
| `<work>/candidates/spec-<slug>.ui.json` | spec-ui | api-specification-author | task-decomposer | artifact-handoff | spec-ui |
| `<work>/spec-<slug>.ui.json` | spec-ui | python | task-decomposer | artifact-handoff | spec-ui |
| `<work>/spec-<slug>.md` | spec-document | api-specification-author | acceptance-criteria-writer,task-decomposer,openapi-contract-reviewer,spec-decider | artifact-handoff | spec-document |
| `<work>/spec-<slug>.data-model.md` | data-model-document | data-model-specification-author | acceptance-criteria-writer,task-decomposer,openapi-contract-reviewer,spec-decider | artifact-handoff | data-model-document |
| `<work>/spec-<slug>.criteria.md` | criteria-document | acceptance-criteria-writer | task-decomposer,openapi-contract-reviewer,spec-decider | artifact-handoff | criteria-document |
| `<work>/spec-<slug>.review.json` | spec-review | openapi-contract-reviewer | api-specification-author,data-model-specification-author,acceptance-criteria-writer,spec-decider | artifact-handoff `schemas/spec-review.schema.json` | spec-review (`spec_review_contract.SpecReview`) |
| `<work>/spec-<slug>.<document>.correction.json`, `spec-<slug>.<document>.revision.json` | spec-correction | api-specification-author,data-model-specification-author,acceptance-criteria-writer | spec-decider | artifact-handoff `schemas/spec-correction.schema.json` | spec-correction (`spec_review_contract.SpecCorrection`) |
| `<work>/spec-<slug>.ruling.json` | spec-ruling | spec-decider | api-specification-author,data-model-specification-author,acceptance-criteria-writer | artifact-handoff `schemas/spec-ruling.schema.json` | spec-ruling (`spec_review_contract.SpecRuling`) |
| `<work>/story-<slug>.json` | story | python | task-decomposer | artifact-handoff | story |
| the filed Spec documents in the vault | filed-documents | python | python | artifact-handoff | filed-documents |
| `<work>/tasks-<slug>.items.json` | task-items | python | python | artifact-handoff | task-items |
| `<work>/tasks-<slug>.context.json` | task-context | python | python | artifact-handoff | task-context |
| `<work>/tasks-<slug>.json` | tasks | task-decomposer | task-dependency-mapper | artifact-handoff | tasks |
| `<work>/tasks-<slug>.correction.json` | tasks-correction | task-decomposer | python | artifact-handoff | tasks-correction |
| `<workDir>/score-plan.json` | out-of-scope | python | python | none | out-of-scope |
| `<workDir>/judge-input-epic.json`, `judge-input-task.json` | out-of-scope | python | python | none | out-of-scope |
| `<workDir>/prd/<epic-id>.md` | out-of-scope | python | python | none | out-of-scope |
| `<workDir>/judgments/epic/<id>.json`, `judgments/task/<key>.json` | out-of-scope | python | python | none | out-of-scope |
| `<workDir>/record.json` | out-of-scope | python | python | none | out-of-scope |
| `<workDir>/score.json` | out-of-scope | python | python | none | out-of-scope |
| `<workDir>/assess-plan.json` | out-of-scope | python | python | none | out-of-scope |
| `<workDir>/context/prd/<id>.md`, `context/task/<id>.md`, `context/index.md` | out-of-scope | python | python | none | out-of-scope |
| `<workDir>/context.json` | out-of-scope | python | python | none | out-of-scope |
| `<workDir>/edges.json` | out-of-scope | python | python | none | out-of-scope |
| `<workDir>/reasoning.md` | out-of-scope | python | python | none | out-of-scope |
| `<workDir>/validation.json` | out-of-scope | python | python | none | out-of-scope |
| `<workDir>/apply-edges.json` (or `apply-edges-dry-run.json`) | out-of-scope | python | python | none | out-of-scope |
| `<workDir>/scoring/` | out-of-scope | python | python | none | out-of-scope |
