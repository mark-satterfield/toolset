export const meta = {
  name: 'repo-scoping',
  description:
    'Leaf mini — rules the repository span of a PRD from its approved architecture delta. One polyrepo-steward session places each delta item (one element the delta shows, as depscore.py arch-delta lists it) in the repository whose code changes for it, or records that the element has no code in this project, and creates each new repository the approved target names, from the name, template and reason the target gives. The span is the distinct repositories the placements name. The run fails when an item is placed twice or not at all, or when no placement names a repository.',
  phases: [
    { title: 'Place and provision', detail: 'the polyrepo-steward places each delta item in a repository and creates the new repositories the approved target names' },
  ],
}
// ===== SHARED BLOCK fable — BEGIN (canonical: scripts/shared-blocks/fable.js; edit there, then: node scripts/shared-blocks.mjs --write) =====
const ownedCoreContracts = "---\nname: subagent-contract\ndescription: Global contract for bounded specialist agents. Use when loading any agent that receives delegated work and must preserve role boundaries, scope discipline, clear DONE/BLOCKED signaling, and verifiable deliverables.\nuser-invocable: false\n---\n\n# Subagent Contract\n\nThis contract governs specialist agents in the agent-teams-workforce plugin. It keeps delegated work bounded, auditable, and easy for leads or orchestrators to compose.\n\n## Role Contract\n\nWhen operating under this contract:\n\n- You are a specialist agent.\n- You perform only the role assigned in your agent file and task prompt.\n- You do not change scope, invent requirements, or choose downstream work.\n- You return `STATUS: BLOCKED` rather than guessing when required context is missing.\n- You return `STATUS: DONE` only after the requested deliverables are complete and verified.\n\n## Work Rules\n\n1. Restate the task and acceptance criteria before starting.\n2. Identify the minimal scope of files, artifacts, or decisions involved.\n3. Stay inside the assigned scope unless the supervisor explicitly expands it. When the caller expressly assigns repair of all baseline failures in an affected repository, that repair is already assigned scope, including pre-existing failures outside the feature. Preserve test-author ownership and required checks; this does not authorize unrelated cleanup, changes to other repositories, or inventing external resources.\n4. Use only tools allowed by your agent frontmatter and task constraints.\n5. Report material commands you ran and their outcomes.\n6. Prefer small, reversible changes unless the task explicitly requires broader change.\n\n## Resource use and incremental review\n\nConsumed by: every roster agent — scopes its work, evaluates findings, and carries valid work forward to the next revision.\n\n- Use tokens conscientiously without compromising required correctness, completeness, safety, or evidence. Before a material expansion (extra agents, another proposal, optional checks, or a broader investigation), briefly state the specific unresolved need and expected benefit in the existing brief or progress update. Routine tool calls need no separate justification; do not add a report, review pass, arbitrary token quota, or automatic human approval step for this rule. If no concrete benefit exists, omit the optional work. Respect existing role boundaries, workflow limits, and approval requirements.\n- Makers and reviewers use the same accepted requirements, constraints, and success criteria. Review succeeds by determining actual correctness, including passing sound work; finding more failures is not a measure of success. Do not manufacture findings, invent requirements, or turn stylistic preferences into blocking defects. Necessary safety and regression checks remain required.\n- For each genuine failure, use the existing finding format to identify the affected artifact/location, the requirement or dependency at risk, the observed evidence, and an actionable correction with a verifiable pass condition. Distinguish a demonstrated defect from missing evidence and from a proposed new requirement. Do not rubber-stamp unresolved defects or claim unperformed checks passed.\n- Revise the original artifacts incrementally using the feedback. Keep valid completed work and still-applicable evidence; do not restart or regenerate everything by default. On rereview, examine the changed scope and affected dependencies. Reopen other work only when new evidence or demonstrated impact explains why its earlier evidence no longer suffices; state that reason. Preserve required independent review and necessary regression coverage.\n\nUse the caller's required output schema for these observations; this contract does not add fields to it. Where the role has an exact machine-consumed response, that format takes precedence over the generic DONE/BLOCKED presentation below.\n\n## DONE Signal\n\nBegin final output with:\n\n```text\nSTATUS: DONE\n```\n\nInclude:\n\n- Summary of what was accomplished.\n- Deliverables created or changed.\n- Verification performed, with evidence.\n- Residual risks or follow-up items.\n\n## BLOCKED Signal\n\nBegin final output with:\n\n```text\nSTATUS: BLOCKED\n```\n\nInclude:\n\n- What is blocking progress.\n- Specific input, permission, dependency, or decision needed.\n- What was already checked.\n- Recommended next action for the supervisor.\n\n## Forbidden Patterns\n\n- Scope creep: \"While I was here, I also...\"\n- Assumption-making: \"I assumed the user meant...\"\n- Silent partial work: completing only the easy portion without declaring the gap.\n- Unbounded exploration: reading broadly without a clear relationship to the task.\n- Requirement invention: adding behavior not requested or derived from accepted criteria.\n\n## Pre-DONE Checklist\n\n- [ ] All acceptance criteria were addressed.\n- [ ] Stated restrictions were respected.\n- [ ] No unrelated files or artifacts were changed.\n- [ ] Verification evidence is included.\n- [ ] Output follows this agent's expected deliverable format.\n\n\n## Delivered skills and authoritative artifacts\n\nBefore acting, read skill content actually supplied in this prompt and load every remaining declared skill through the Skill tool using its exact name. Complete canonical skill text supplied here counts as delivered; a frontmatter name alone does not. Read the content and apply its requirements within your assigned role; record applicability briefly in the existing status/result, without adding a separate approval pass. A missing required skill is an explicit blocked dependency, not permission to substitute memory.\n\nAll shared documents, including Markdown, vault notes, schemas and JSON, remain authoritative at their source reference. Read the actual relevant source and connected contracts; summaries and excerpts guide navigation and never replace that reading. A delegation identifies read inputs, editable existing outputs and new outputs separately. Preserve source content unless the assignment includes changing it. Return output references and compact status instead of copying whole documents into another agent response. If exact copying is needed, use the supplied deterministic file tools/scripts; do not retype it through a model. Use source version/provenance when it matters to the check; do not demand content hashes merely for a semantic edit.\n\nMakers and reviewers receive the same applicable requirements and completion criteria. Review changed work and affected dependencies, keeping accepted evidence unless a specific change invalidates it. For a durable authoring task, use the caller's checkpoint location: after each coherent artifact update, record completed work, remaining work and artifact references. Checkpoints are progress, never accepted results. On resume, read the checkpoint and actual artifacts, verify the saved state, and complete remaining work in the same assigned dispatch; do not regenerate valid completed documents. Read-only reviewers must use caller-supported result/checkpoint mechanisms and never write source artifacts.\n\n## AWS evidence authority\n\nFor AWS architecture choices, the AWS MCP Server and associated AWS skills are the leading source for proper implementation and best practice, evaluated against the applicable AWS Well-Architected principles. Consult the actual documentation/skill guidance and retain source references for the choice and tradeoffs. Existing generated architecture and model recollection do not establish correctness. Makers and reviewers use this same evidence criterion. Apply it to actual stated requirements, deployment, usage and cost constraints rather than hypothetical scale. Surface conflicts with product requirements or owner constraints explicitly; do not silently replace them with a preferred AWS pattern. Missing required MCP/skill access is a named blocker or uncertainty, never evidence that a check passed. Coordinators may research and route AWS questions, but cannot author or approve designs.\n\n\n---\nname: artifact-handoff\ndescription: Share authoritative documents, diagrams and JSON by artifact path, with format-specific validation and resumable checkpoints; never retype full payloads between agents.\n---\n\nShared documents, Markdown, diagrams and other artifacts stay in their authoritative files. Pass paths and brief task context; recipients read the actual files. A summary is navigation, never a substitute source. Edit only explicitly assigned files; preserve accepted work. Do not retype an entire document into another agent's prompt or machine response. Use existing deterministic file operations for exact copies when a copy is explicitly required.\n\nKeep the caller-specified checkpoint current after meaningful work: status, task, completed work, remaining work and artifact paths. On resume read the checkpoint and referenced artifacts, verify current state and complete remaining work. A checkpoint is progress evidence, never acceptance or permission to omit validation.\n\nFor JSON, write the caller's requested JSON object once to its exact candidate path. Use the supplied artifact schema; do not confuse it with the small return schema. Preserve existing completed work and inspect an existing candidate before continuing interrupted work. Return only the candidate path using the caller's structured return schema. Never copy the full artifact into StructuredOutput or prose.\n\nThe workflow's named command runner invokes `scripts/portfolio/jsonartifact.py` with the expected candidate, final path and schema. The script rejects duplicate keys, invalid JSON, schema violations and changes to already accepted results. It writes canonical JSON and an integrity receipt; downstream scripts verify the receipt. Candidates stay outside the accepted result directory. A failed candidate is never treated as a completed step.\n\nThe command runner runs only the exact checked command supplied by the workflow. Validation failure is reported explicitly; it does not authorize rewriting another producer's content or repeating a successful administrative command. Existing legacy artifacts are preserved.\n\nFor Markdown and diagrams, `jsonartifact.py --document PATH` verifies the actual nonempty UTF-8 file and returns its path, raw-byte SHA-256, length and format. It never copies or rewrites the document. This receipt identifies the reviewed version; it is not a semantic quality verdict and does not prohibit later authorized edits. Keep structured metadata separate and refer to the document path instead of embedding its contents.\n\nCandidate completion checkpoints bind the exact candidate path, expected schema hash and caller revision. The workflow derives that revision from actual source-file/corpus byte fingerprints and assignment context; a path alone is not freshness evidence. Changed inputs require a new candidate revision. A saved complete result for the same revision is reused; it is never silently replaced. Fingerprints exclude the producer’s assigned output files to preserve interruption recovery.\n"
const ownedAgentContracts = {"acceptance-criteria-reviewer":{"agentType":"agent-teams-workforce:acceptance-criteria-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"acceptance-criteria-writer":{"agentType":"acceptance-criteria-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"accessibility-validator":{"agentType":"agent-teams-workforce:accessibility-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:a11y-audit","agent-teams-workforce:senior-frontend"]},"advantage-evaluator":{"agentType":"agent-teams-workforce:advantage-evaluator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"adversarial-critique-adjudicator":{"agentType":"agent-teams-workforce:adversarial-critique-adjudicator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-security"]},"adversarial-review-loop-supervisor":{"agentType":"agent-teams-workforce:adversarial-review-loop-supervisor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"ambiguity-detector":{"agentType":"agent-teams-workforce:ambiguity-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"android-compose-implementer":{"agentType":"agent-teams-workforce:android-compose-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"api-contract-designer":{"agentType":"api-contract-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer","agent-teams-workforce:aws-solution-architect"]},"api-documentation-writer":{"agentType":"agent-teams-workforce:api-documentation-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer"]},"api-gateway-cdk-implementer":{"agentType":"api-gateway-cdk-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-gateway","agent-teams-workforce:aws-cdk-development"]},"api-specification-author":{"agentType":"api-specification-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer"]},"appsync-cdk-implementer":{"agentType":"agent-teams-workforce:appsync-cdk-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cdk-development"]},"appsync-client-subscription-implementer":{"agentType":"agent-teams-workforce:appsync-client-subscription-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend"]},"architecture-boundary-guardian":{"agentType":"architecture-boundary-guardian","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect"]},"architecture-conformance-reviewer":{"agentType":"architecture-conformance-reviewer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:arc42","agent-teams-workforce:aws-solution-architect"]},"architecture-decider":{"agentType":"architecture-decider","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect"]},"architecture-decision-workflow-coordinator":{"agentType":"architecture-decision-workflow-coordinator","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-solution-architect"]},"architecture-diagram-author":{"agentType":"agent-teams-workforce:architecture-diagram-author","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:c4-diagramming","agent-teams-workforce:uml-diagramming","agent-teams-workforce:senior-architect"]},"architecture-fitness-function-author":{"agentType":"agent-teams-workforce:architecture-fitness-function-author","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"architecture-impact-analyst":{"agentType":"agent-teams-workforce:architecture-impact-analyst","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:beads-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"architecture-maintainer":{"agentType":"architecture-maintainer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:arc42","agent-teams-workforce:arc42-maintain","agent-teams-workforce:c4-diagramming","agent-teams-workforce:uml-diagramming","agent-teams-workforce:senior-architect"]},"architecture-pattern-challenger":{"agentType":"architecture-pattern-challenger","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect"]},"architecture-tradeoff-skeptic":{"agentType":"architecture-tradeoff-skeptic","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect"]},"athena-redshift-analytics-implementer":{"agentType":"agent-teams-workforce:athena-redshift-analytics-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer"]},"auth-bypass-tester":{"agentType":"agent-teams-workforce:auth-bypass-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops","agent-teams-workforce:cognito"]},"aws-integration-test-runner":{"agentType":"agent-teams-workforce:aws-integration-test-runner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:test-failure-mindset"]},"aws-integration-test-writer":{"agentType":"agent-teams-workforce:aws-integration-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda"]},"beads-format-validator":{"agentType":"agent-teams-workforce:beads-format-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:beads-contract"]},"bedrock-integration-implementer":{"agentType":"agent-teams-workforce:bedrock-integration-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:bedrock","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:senior-prompt-engineer","agent-teams-workforce:aws-agentic-ai"]},"behavioral-signals-implementer":{"agentType":"agent-teams-workforce:behavioral-signals-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:senior-data-scientist","agent-teams-workforce:product-analytics"]},"bounded-context-mapper":{"agentType":"bounded-context-mapper","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect"]},"brd-traceability-auditor":{"agentType":"agent-teams-workforce:brd-traceability-auditor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"c4-diagram-author":{"agentType":"agent-teams-workforce:c4-diagram-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:c4-diagramming","agent-teams-workforce:senior-architect"]},"cdk-infrastructure-designer":{"agentType":"cdk-infrastructure-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:aws-solution-architect"]},"cdk-infrastructure-drift-detector":{"agentType":"agent-teams-workforce:cdk-infrastructure-drift-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:cloudformation"]},"cdk-stack-author":{"agentType":"cdk-stack-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:cloudformation"]},"cds-finding-reviewer":{"agentType":"agent-teams-workforce:cds-finding-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","cds:apply-design-system","cds:audit-against-system"]},"cds-ui-implementer":{"agentType":"agent-teams-workforce:cds-ui-implementer","skills":["agent-teams-workforce:subagent-contract","cds:apply-design-system","cds:audit-against-system","cds:compose-page"]},"changelog-writer":{"agentType":"agent-teams-workforce:changelog-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:changelog-generator"]},"chassis-extension-implementer":{"agentType":"chassis-extension-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:lambda","agent-teams-workforce:aws-serverless-eda"]},"code-correctness-reviewer":{"agentType":"agent-teams-workforce:code-correctness-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:code-reviewer"]},"code-quality-lead":{"agentType":"agent-teams-workforce:code-quality-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"code-refactoring-specialist":{"agentType":"agent-teams-workforce:code-refactoring-specialist","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:code-reviewer"]},"code-style-and-linting-enforcer":{"agentType":"agent-teams-workforce:code-style-and-linting-enforcer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:code-reviewer"]},"cognito-lambda-trigger-implementer":{"agentType":"agent-teams-workforce:cognito-lambda-trigger-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:cognito","agent-teams-workforce:lambda"]},"completeness-checker":{"agentType":"agent-teams-workforce:completeness-checker","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"complexity-analyzer":{"agentType":"agent-teams-workforce:complexity-analyzer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:tech-debt-tracker"]},"constitutional-agent":{"agentType":"agent-teams-workforce:constitutional-agent","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"constraint-extractor":{"agentType":"agent-teams-workforce:constraint-extractor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"consumer-driven-contract-test-writer":{"agentType":"agent-teams-workforce:consumer-driven-contract-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-test-suite-builder"]},"context-curator":{"agentType":"agent-teams-workforce:context-curator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"contract-violation-tester":{"agentType":"agent-teams-workforce:contract-violation-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-test-suite-builder"]},"cost-architecture-reviewer":{"agentType":"cost-architecture-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-cost-operations","agent-teams-workforce:aws-solution-architect"]},"cost-impact-reviewer":{"agentType":"cost-impact-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cost-operations","agent-teams-workforce:aws-solution-architect"]},"cross-repo-integration-test-coordinator":{"agentType":"agent-teams-workforce:cross-repo-integration-test-coordinator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"cross-service-contract-tester":{"agentType":"agent-teams-workforce:cross-service-contract-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-test-suite-builder"]},"data-consistency-checker":{"agentType":"agent-teams-workforce:data-consistency-checker","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb"]},"data-exposure-scanner":{"agentType":"agent-teams-workforce:data-exposure-scanner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"data-model-specification-author":{"agentType":"data-model-specification-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb","agent-teams-workforce:database-schema-designer"]},"data-pipeline-test-writer":{"agentType":"agent-teams-workforce:data-pipeline-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer"]},"definition-of-done-enforcer":{"agentType":"agent-teams-workforce:definition-of-done-enforcer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"dependency-change-detector":{"agentType":"agent-teams-workforce:dependency-change-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dependency-auditor"]},"dependency-cve-auditor":{"agentType":"agent-teams-workforce:dependency-cve-auditor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dependency-auditor"]},"dependency-graph-extractor":{"agentType":"agent-teams-workforce:dependency-graph-extractor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"deployment-lead":{"agentType":"agent-teams-workforce:deployment-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"deployment-strategy-decider":{"agentType":"agent-teams-workforce:deployment-strategy-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:cove-prompt-design"]},"documentation-accuracy-reviewer":{"agentType":"agent-teams-workforce:documentation-accuracy-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"documentation-currency-auditor":{"agentType":"agent-teams-workforce:documentation-currency-auditor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"documentation-lead":{"agentType":"agent-teams-workforce:documentation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"domain-boundary-validator":{"agentType":"agent-teams-workforce:domain-boundary-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"domain-event-modeler":{"agentType":"domain-event-modeler","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:aws-solution-architect"]},"dos-resilience-tester":{"agentType":"agent-teams-workforce:dos-resilience-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"dynamodb-access-layer-implementer":{"agentType":"dynamodb-access-layer-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb"]},"dynamodb-cost-optimizer":{"agentType":"dynamodb-cost-optimizer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb","agent-teams-workforce:aws-cost-operations"]},"dynamodb-schema-access-pattern-reviewer":{"agentType":"dynamodb-schema-access-pattern-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb"]},"dynamodb-streams-cdc-implementer":{"agentType":"dynamodb-streams-cdc-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:dynamodb"]},"email-notification-implementer":{"agentType":"agent-teams-workforce:email-notification-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:email-template-builder","agent-teams-workforce:sns"]},"epic-sequencer":{"agentType":"agent-teams-workforce:epic-sequencer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:epic-sequencing"]},"espresso-test-writer":{"agentType":"agent-teams-workforce:espresso-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:tdd-guide"]},"event-api-client-implementer":{"agentType":"agent-teams-workforce:event-api-client-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda"]},"event-driven-consumer-implementer":{"agentType":"event-driven-consumer-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:sqs","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:sns"]},"event-flow-tester":{"agentType":"agent-teams-workforce:event-flow-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda"]},"event-schema-designer":{"agentType":"event-schema-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:eventbridge","agent-teams-workforce:sns","agent-teams-workforce:aws-solution-architect"]},"event-schema-reviewer":{"agentType":"event-schema-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda"]},"failure-mode-analyst":{"agentType":"failure-mode-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:observability-designer","agent-teams-workforce:aws-solution-architect"]},"filing-clerk":{"agentType":"filing-clerk","skills":["agent-teams-workforce:subagent-contract","obsidian:obsidian-cli","obsidian:obsidian-markdown","agent-teams-workforce:arc42","notebooklm","document-classification"]},"finops-analyst":{"agentType":"finops-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-cost-operations"]},"flaky-test-detector":{"agentType":"agent-teams-workforce:flaky-test-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:test-failure-mindset","agent-teams-workforce:find-cause"]},"frontend-performance-optimizer":{"agentType":"agent-teams-workforce:frontend-performance-optimizer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend"]},"github-actions-pipeline-implementer":{"agentType":"agent-teams-workforce:github-actions-pipeline-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops"]},"glue-etl-implementer":{"agentType":"agent-teams-workforce:glue-etl-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer"]},"graphql-schema-designer":{"agentType":"graphql-schema-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer","agent-teams-workforce:aws-solution-architect"]},"graphql-schema-reviewer":{"agentType":"agent-teams-workforce:graphql-schema-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer"]},"implementation-lead":{"agentType":"agent-teams-workforce:implementation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"incident-responder":{"agentType":"agent-teams-workforce:incident-responder","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:find-cause","agent-teams-workforce:validation-protocol"]},"incident-response-runbook-designer":{"agentType":"agent-teams-workforce:incident-response-runbook-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:observability-designer"]},"infrastructure-security-scanner":{"agentType":"infrastructure-security-scanner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops","agent-teams-workforce:aws-cdk-development"]},"injection-attack-tester":{"agentType":"agent-teams-workforce:injection-attack-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"integration-pattern-architect":{"agentType":"integration-pattern-architect","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:aws-solution-architect"]},"integration-testing-lead":{"agentType":"agent-teams-workforce:integration-testing-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"ios-swiftui-implementer":{"agentType":"agent-teams-workforce:ios-swiftui-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"kinesis-stream-implementer":{"agentType":"agent-teams-workforce:kinesis-stream-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:aws-serverless-eda"]},"lambda-performance-optimizer":{"agentType":"lambda-performance-optimizer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:lambda"]},"llm-observability-implementer":{"agentType":"agent-teams-workforce:llm-observability-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:observability-designer","agent-teams-workforce:senior-prompt-engineer","agent-teams-workforce:aws-agentic-ai"]},"matching-algorithm-implementer":{"agentType":"agent-teams-workforce:matching-algorithm-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer"]},"mcp-server-implementer":{"agentType":"agent-teams-workforce:mcp-server-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:mcp-server-builder","agent-teams-workforce:aws-agentic-ai","agent-teams-workforce:aws-mcp-setup"]},"ml-evaluation-tester":{"agentType":"agent-teams-workforce:ml-evaluation-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:senior-data-scientist"]},"mobile-e2e-test-writer":{"agentType":"agent-teams-workforce:mobile-e2e-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"nextjs-component-implementer":{"agentType":"agent-teams-workforce:nextjs-component-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend","agent-teams-workforce:a11y-audit","agent-teams-workforce:senior-fullstack"]},"nfr-analyst":{"agentType":"agent-teams-workforce:nfr-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:product-discovery"]},"okr-writer":{"agentType":"agent-teams-workforce:okr-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-strategist","agent-teams-workforce:product-analytics"]},"openapi-contract-reviewer":{"agentType":"openapi-contract-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer"]},"operational-readiness-reviewer":{"agentType":"operational-readiness-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:observability-designer","agent-teams-workforce:aws-solution-architect"]},"payments-integration-implementer":{"agentType":"agent-teams-workforce:payments-integration-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:stripe-integration-expert","agent-teams-workforce:secrets-manager"]},"performance-benchmark-writer":{"agentType":"agent-teams-workforce:performance-benchmark-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"permission-escalation-tester":{"agentType":"agent-teams-workforce:permission-escalation-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops","agent-teams-workforce:iam"]},"persistence-architecture-specialist":{"agentType":"persistence-architecture-specialist","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:dynamodb","agent-teams-workforce:database-schema-designer","agent-teams-workforce:rds","agent-teams-workforce:aws-solution-architect"]},"persona-profile-writer":{"agentType":"agent-teams-workforce:persona-profile-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:product-analytics"]},"phase-gate-enforcer":{"agentType":"agent-teams-workforce:phase-gate-enforcer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"playwright-e2e-web-test-writer":{"agentType":"agent-teams-workforce:playwright-e2e-web-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:a11y-audit"]},"polyrepo-steward":{"agentType":"agent-teams-workforce:polyrepo-steward","skills":["agent-teams-workforce:subagent-contract"]},"power-tools-configuration-implementer":{"agentType":"agent-teams-workforce:power-tools-configuration-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:lambda","agent-teams-workforce:secrets-manager"]},"prd-alignment-verifier":{"agentType":"agent-teams-workforce:prd-alignment-verifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"prd-creation-lead":{"agentType":"agent-teams-workforce:prd-creation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"prd-reality-reconciler":{"agentType":"prd-reality-reconciler","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"prd-trd-traceability-verifier":{"agentType":"agent-teams-workforce:prd-trd-traceability-verifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"prd-validation-analyst":{"agentType":"agent-teams-workforce:prd-validation-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"prd-validation-lead":{"agentType":"agent-teams-workforce:prd-validation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"prd-writer":{"agentType":"agent-teams-workforce:prd-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"production-readiness-review-facilitator":{"agentType":"agent-teams-workforce:production-readiness-review-facilitator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"race-condition-tester":{"agentType":"agent-teams-workforce:race-condition-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"react-native-implementer":{"agentType":"agent-teams-workforce:react-native-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend"]},"readme-writer":{"agentType":"agent-teams-workforce:readme-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"recommendation-engine-implementer":{"agentType":"agent-teams-workforce:recommendation-engine-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer"]},"requirements-clarifier":{"agentType":"agent-teams-workforce:requirements-clarifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:product-discovery"]},"requirements-conflict-detector":{"agentType":"agent-teams-workforce:requirements-conflict-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"root-cause-analyst":{"agentType":"agent-teams-workforce:root-cause-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:find-cause","agent-teams-workforce:test-failure-mindset"]},"run-ledger-writer":{"agentType":"agent-teams-workforce:run-ledger-writer","skills":["agent-teams-workforce:subagent-contract"]},"s3-data-lake-implementer":{"agentType":"agent-teams-workforce:s3-data-lake-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:s3"]},"sdlc-pipeline-orchestrator":{"agentType":"agent-teams-workforce:sdlc-pipeline-orchestrator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:beads-contract"]},"security-architecture-designer":{"agentType":"security-architecture-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-security","agent-teams-workforce:iam","agent-teams-workforce:secrets-manager","agent-teams-workforce:aws-solution-architect"]},"security-test-case-designer":{"agentType":"agent-teams-workforce:security-test-case-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-security"]},"slo-error-budget-designer":{"agentType":"slo-error-budget-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:observability-designer","agent-teams-workforce:cloudwatch"]},"smoke-test-author":{"agentType":"agent-teams-workforce:smoke-test-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"spec-authoring-lead":{"agentType":"agent-teams-workforce:spec-authoring-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"spec-currency-validator":{"agentType":"agent-teams-workforce:spec-currency-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"spec-decider":{"agentType":"spec-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:cove-prompt-design"]},"spec-freshness-lead":{"agentType":"agent-teams-workforce:spec-freshness-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"stakeholder-request-intake-writer":{"agentType":"agent-teams-workforce:stakeholder-request-intake-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"task-decomposer":{"agentType":"task-decomposer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:beads-contract"]},"task-decomposition-lead":{"agentType":"agent-teams-workforce:task-decomposition-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:beads-contract"]},"task-dependency-mapper":{"agentType":"task-dependency-mapper","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:beads-contract"]},"task-readiness-runner":{"agentType":"agent-teams-workforce:task-readiness-runner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:beads-contract"]},"tdd-unit-test-generator":{"agentType":"agent-teams-workforce:tdd-unit-test-generator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:tdd-guide"]},"test-command-resolver":{"agentType":"agent-teams-workforce:test-command-resolver","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:test-failure-mindset"]},"test-coverage-gap-reviewer":{"agentType":"agent-teams-workforce:test-coverage-gap-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"test-design-lead":{"agentType":"agent-teams-workforce:test-design-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"test-environment-orchestrator":{"agentType":"test-environment-orchestrator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:aws-mcp-setup"]},"test-failure-parser":{"agentType":"agent-teams-workforce:test-failure-parser","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:test-failure-mindset"]},"test-isolation-specialist":{"agentType":"agent-teams-workforce:test-isolation-specialist","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:tdd-guide","agent-teams-workforce:test-failure-mindset"]},"test-plan-strategy-reviewer":{"agentType":"agent-teams-workforce:test-plan-strategy-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"test-strategy-decider":{"agentType":"agent-teams-workforce:test-strategy-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cove-prompt-design"]},"trd-author":{"agentType":"trd-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"trd-authoring-lead":{"agentType":"agent-teams-workforce:trd-authoring-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"trd-decider":{"agentType":"agent-teams-workforce:trd-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"trd-validator":{"agentType":"agent-teams-workforce:trd-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"ubiquitous-language-writer":{"agentType":"agent-teams-workforce:ubiquitous-language-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"uml-diagram-author":{"agentType":"agent-teams-workforce:uml-diagram-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:uml-diagramming","agent-teams-workforce:senior-architect"]},"user-guide-writer":{"agentType":"agent-teams-workforce:user-guide-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:roadmap-communicator"]},"user-story-reviewer":{"agentType":"agent-teams-workforce:user-story-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:beads-contract"]},"user-story-writer":{"agentType":"agent-teams-workforce:user-story-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"vector-search-embeddings-implementer":{"agentType":"agent-teams-workforce:vector-search-embeddings-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:rag-architect"]},"webauthn-implementer":{"agentType":"agent-teams-workforce:webauthn-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend","agent-teams-workforce:cognito"]},"workflow-command-runner":{"agentType":"agent-teams-workforce:workflow-command-runner","skills":["agent-teams-workforce:artifact-handoff"]},"worktree-independent-verifier":{"agentType":"agent-teams-workforce:worktree-independent-verifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"wsjf-scorer":{"agentType":"agent-teams-workforce:wsjf-scorer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-strategist","agent-teams-workforce:wsjf","agent-teams-workforce:beads-contract"]},"wsjf-scoring-reviewer":{"agentType":"agent-teams-workforce:wsjf-scoring-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-strategist","agent-teams-workforce:wsjf"]},"xcuitest-writer":{"agentType":"agent-teams-workforce:xcuitest-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:tdd-guide"]}}
// Runtime replay identifies calls by their unchanged prompt/options and start order.
// Recovery metadata stays in workflow arguments and never enters those options.
const fableInput = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const fableTypes = new Set((Array.isArray(fableInput.fableAgentTypes) ? fableInput.fableAgentTypes : []).map((name) => String(name).replace(/^agent-teams-workforce:/, '')))
const fablePath = fableInput.fableInvocationPath || 'root'
const fableRecovery = fableInput.fableRecovery && typeof fableInput.fableRecovery === 'object' ? fableInput.fableRecovery : null
let fableAgentOrdinal = 0
let fableChildOrdinal = 0
function fableEvent(event, identity, error = null) {
  log(`FABLE-CALL ${JSON.stringify({ event, ...identity, ...(error === null ? {} : { error }) })}`)
}
async function fableAgent(prompt, options) {
  const suppliedType = String((options && options.agentType) || '')
  const key = suppliedType.replace(/^agent-teams-workforce:/, '')
  const contract = Object.keys(ownedAgentContracts).includes(key) ? ownedAgentContracts[key] : null
  if (!contract) throw new Error(`NAMED_AGENT_REQUIRED: ${suppliedType || '(missing agentType)'} is not a plugin-owned specialist`)
  options = { ...options, agentType: contract.agentType }
  const domainSkills = contract.skills.filter(name => !['agent-teams-workforce:subagent-contract', 'agent-teams-workforce:artifact-handoff'].includes(name))
  const skillBrief = domainSkills.length
    ? `Before doing the assignment, assess which declared domain skills apply and invoke each applicable skill with the Skill tool using its exact name: ${domainSkills.join(', ')}. Read its instructions and apply the parts relevant to your role and task; briefly name any inapplicable skill and why in existing progress, without inventing extra work. Do not assume frontmatter injected the skill. If required skill content cannot be loaded, report that specific missing dependency; do not substitute memory or a generic agent.\n\n`
    : ''
  const sourceBrief = 'Artifact contract: source files and vault notes are authoritative. Read the referenced source sections needed for this assignment; summaries are navigation, not substitutes. Observe the stated read/edit/create ownership. Preserve existing source unless its change is assigned. Return the requested result references and compact status; do not reconstruct or retype shared documents for handoff.\n\n'
  const identity = { invocationPath: fablePath, ordinal: fableAgentOrdinal++, agentType: (options && options.agentType) || null, label: (options && options.label) || null }
  const isFable = fableTypes.has(String(identity.agentType || '').replace(/^agent-teams-workforce:/, ''))
  const cutoffs = (fableRecovery && fableRecovery.cutoffs) || {}
  const cutoff = Number.isInteger(cutoffs[fablePath]) && cutoffs[fablePath] >= 0 ? cutoffs[fablePath] : 0
  const call = isFable && fableRecovery && identity.ordinal >= cutoff ? { ...options, model: 'opus' } : options
  fableEvent('start', identity)
  try {
    const result = await agent(ownedCoreContracts + '\n\n' + skillBrief + sourceBrief + prompt, call)
    if (!result) fableEvent('failed', identity)
    return result
  } catch (error) {
    const message = String((error && error.message) || error)
    fableEvent('failed', identity, message)
    if (isFable && /out of (?:usage )?credits|seven_day_overage_included|fable.{0,40}(?:limit|allowance)/i.test(message)) return null
    throw error
  }
}
async function fableWorkflow(name, input) {
  const invocationPath = `${fablePath}/${fableChildOrdinal++}:${name}`
  return await workflow(name, {
    ...input,
    fableAgentTypes: fableInput.fableAgentTypes || [],
    fableInvocationPath: invocationPath,
    ...(fableRecovery ? { fableRecovery } : {}),
  })
}
// ===== SHARED BLOCK fable — END =====

// BEGIN interruption propagation — no retry or replay of completed dispatches.
let dispatchInterruption = null
function dispatchOutcome(result) {
  if (!dispatchInterruption) return result
  const out = result && typeof result === 'object' ? result : {}
  return { ...out, ok: false, dispatchFailed: true, paused: true, resumable: true,
    stage: dispatchInterruption.stage, reason: dispatchInterruption.message, headline: dispatchInterruption.message,
    ...(typeof out.passed === 'boolean' ? { passed: false } : {}),
    ...(out.ledger ? { ledger: { ...out.ledger, ok: false } } : {}), dispatchInterruption }
}
function dispatchFailureCause(err) {
  const e = err && typeof err === 'object' ? err : {}
  const text = [e.message || err || '', e.type, e.code, e.error && e.error.type].join(' ')
  if (/structured ?output|schema|validation|does not match|required property|additionalproperties|unsatisfiable|invalid argument/i.test(text)) return 'deterministic'
  if (/insufficient_quota|quota|usage[ _-]?limit|spend[ _-]?limit|session[ _-]?limit|credit balance|out of credits|hit your limit|token limit|account.quota.exhausted/i.test(text)) return 'exhausted'
  const status = [e.status, e.statusCode, e.code, e.response && e.response.status]
    .map((value) => Number(value)).find((value) => Number.isFinite(value) && value >= 100 && value < 600)
  return [408, 425, 429, 500, 502, 503, 504, 529].includes(status) || /overload|rate[ _-]?limit|too many requests|capacity|throttl|timed? ?out|timeout|econnreset|econnrefused|etimedout|eai_again|socket hang up|network|temporarily unavailable|service unavailable|upstream connect|bad gateway/i.test(text) ? 'transient' : 'deterministic'
}
function captureDispatchInterruption(err, name) {
  const cause = dispatchFailureCause(err)
  if (cause === 'deterministic') return
  const stage = cause === 'exhausted' ? 'account-quota-exhausted' : 'api-unavailable'
  dispatchInterruption = { stage, message: stage + ': ' + name + ': ' + String((err && err.message) || err) }
}
// END interruption propagation

// ===== SHARED BLOCK relay — BEGIN (canonical: scripts/shared-blocks/relay.js; edit there, then: node scripts/shared-blocks.mjs --write) =====
// ── CHECKED RELAY: deterministic work reaches this script unaltered, or not at all ──
//
// A workflow script cannot run a command or read a file. A command reaches the shell only as
// text a runner session types, and its result reaches the script only as that session's copy.
// Neither copy is trusted:
// - every command line carries --argv-sha256, the SHA-256 of the canonical JSON of its argument
//   list; the program refuses (exit 3, nothing run) a command line typed differently;
// - every result is printed as ONE RELAY64v1: line carrying base64 canonical JSON: a flat object of scalars (the view's leaves keyed by
//   path, plus ~exit, ~checksum and the relay file's ~file, ~sha256, ~bytes), where ~checksum
//   is the SHA-256 of the canonical JSON of { exit, view }. The runner returns that line as a
//   verbatim string; the script parses it, recomputes the checksum and accepts only an exact
//   copy, then rebuilds the view. A damaged copy can retry only reading the exact saved
//   receipt twice; the original command never repeats. Exhaustion pauses this item visibly.
// depscore.py carries the protocol itself; scripts/portfolio/relayrun.py carries it for any
// other program, and checks or writes a saved JSON file against the hash of the value this
// script holds. relayKit.inline runs a Python payload under a self-checking bootstrap, for the
// one step that runs before the plugin root is known. canonicalJson spells the same bytes as
// scripts/portfolio/relay.py canonical().
const relayKit = (() => {
  const SHORT = { '"': '\\"', '\\': '\\\\', '\n': '\\n', '\r': '\\r', '\t': '\\t', '\b': '\\b', '\f': '\\f' }
  /** The canonical JSON of a value: sorted keys, no whitespace, ASCII only. */
  function canonicalJson(v) {
    if (v === null) return 'null'
    if (v === true) return 'true'
    if (v === false) return 'false'
    if (typeof v === 'number') {
      if (!Number.isFinite(v)) throw new Error(`${v} has no JSON spelling`)
      return String(v)
    }
    if (typeof v === 'string') {
      let out = '"'
      for (let i = 0; i < v.length; i++) {
        const unit = v.charCodeAt(i)
        const esc = unit < 0x80 ? SHORT[v[i]] : undefined
        if (esc) out += esc
        else if (unit >= 0x20 && unit <= 0x7e) out += v[i]
        else out += `\\u${unit.toString(16).padStart(4, '0')}`
      }
      return `${out}"`
    }
    if (Array.isArray(v)) return `[${v.map(canonicalJson).join(',')}]`
    if (typeof v === 'object') return `{${Object.keys(v).filter((k) => v[k] !== undefined).sort().map((k) => `${canonicalJson(k)}:${canonicalJson(v[k])}`).join(',')}}`
    throw new Error(`a ${typeof v} has no JSON spelling`)
  }
  const K = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
  ]
  /** The SHA-256, in lower-case hex, of an ASCII text (canonicalJson's output is ASCII only). */
  function sha256Ascii(text) {
    const bytes = []
    for (let i = 0; i < text.length; i++) {
      const c = text.charCodeAt(i)
      if (c > 0x7f) throw new Error('sha256Ascii: the text is not ASCII')
      bytes.push(c)
    }
    const bits = bytes.length * 8
    bytes.push(0x80)
    while (bytes.length % 64 !== 56) bytes.push(0)
    for (const w of [Math.floor(bits / 0x100000000), bits >>> 0]) bytes.push((w >>> 24) & 255, (w >>> 16) & 255, (w >>> 8) & 255, w & 255)
    const H = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]
    const W = new Array(64)
    const rotr = (x, n) => (x >>> n) | (x << (32 - n))
    for (let off = 0; off < bytes.length; off += 64) {
      for (let t = 0; t < 16; t++) W[t] = ((bytes[off + 4 * t] << 24) | (bytes[off + 4 * t + 1] << 16) | (bytes[off + 4 * t + 2] << 8) | bytes[off + 4 * t + 3]) >>> 0
      for (let t = 16; t < 64; t++) {
        const s0 = rotr(W[t - 15], 7) ^ rotr(W[t - 15], 18) ^ (W[t - 15] >>> 3)
        const s1 = rotr(W[t - 2], 17) ^ rotr(W[t - 2], 19) ^ (W[t - 2] >>> 10)
        W[t] = (W[t - 16] + s0 + W[t - 7] + s1) >>> 0
      }
      let [a, b, c, d, e, f, g, h] = H
      for (let t = 0; t < 64; t++) {
        const t1 = (h + (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) + ((e & f) ^ (~e & g)) + K[t] + W[t]) >>> 0
        const t2 = ((rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) + ((a & b) ^ (a & c) ^ (b & c))) >>> 0
        h = g
        g = f
        f = e
        e = (d + t1) >>> 0
        d = c
        c = b
        b = a
        a = (t1 + t2) >>> 0
      }
      ;[a, b, c, d, e, f, g, h].forEach((x, i) => { H[i] = (H[i] + x) >>> 0 })
    }
    return H.map((x) => x.toString(16).padStart(8, '0')).join('')
  }
  /** The SHA-256 of a value's canonical JSON. */
  const sha256Json = (v) => sha256Ascii(canonicalJson(v))
  /** One shell word, single-quoted. */
  const quote = (v) => `'${String(v).replace(/'/g, "'\\''")}'`
  /**
   * The argument list a POSIX shell makes of a command line built from bare words and single
   * quoting. A line using any other shell feature (double quotes, $, backticks, ;, |, &, <, >, a
   * glob) is refused: its argument list is not knowable here, so it cannot be checked.
   */
  function shellWords(line) {
    const words = []
    let word = null
    for (let i = 0; i < line.length; i++) {
      const ch = line[i]
      if (ch === "'") {
        const close = line.indexOf("'", i + 1)
        if (close < 0) throw new Error('shellWords: unterminated quote')
        word = (word || '') + line.slice(i + 1, close)
        i = close
      } else if (ch === '\\') {
        if (i + 1 >= line.length) throw new Error('shellWords: trailing backslash')
        word = (word || '') + line[i + 1]
        i += 1
      } else if (/\s/.test(ch)) {
        if (word !== null) words.push(word)
        word = null
      } else if (/["$`;|&<>*?[\]{}()~#!]/.test(ch)) {
        throw new Error(`shellWords: ${JSON.stringify(ch)} is a shell feature the checksum cannot cover; quote it`)
      } else {
        word = (word || '') + ch
      }
    }
    if (word !== null) words.push(word)
    return words
  }
  /** A runner's return: the exit status and stdout, verbatim, as one string. Nothing is rebuilt. */
  const SCHEMA = {
    type: 'object',
    additionalProperties: false,
    required: ['exitCode', 'stdout'],
    properties: { exitCode: { type: 'integer' }, stdout: { type: 'string', description: 'Copy the complete RELAY64v1: line verbatim. Treat its base64 payload as opaque text; never decode or reconstruct it.' } },
  }
  const HEX = /^[0-9a-f]{64}$/
  /** The relay's own keys in a printed envelope; every other key is a leaf of the flat view. */
  const RELAY_KEYS = ['~file', '~sha256', '~bytes', '~exit', '~checksum']
  /**
   * Rebuilds a view from its flat form (scripts/portfolio/relay.py flatten): leaves keyed by
   * `/`-joined paths (`~0` is `~`, `~1` is `/`), containers and nulls marked by `/~{}`, `/~#`,
   * `/~null`; a list of plain strings is one comma-joined value marked `/~,`.
   */
  function unflatten(flat) {
    const root = {}
    const at = new Map([['', root]])
    const unesc = (seg) => seg.replace(/~1/g, '/').replace(/~0/g, '~')
    const MARK = { '~{}': 1, '~#': 1, '~null': 1, '~,': 1 }
    const entries = Object.keys(flat).map((k) => {
      const segs = k.split('/')
      const mark = MARK[segs[segs.length - 1]] ? segs[segs.length - 1] : null
      return { k, segs: mark ? segs.slice(0, -1) : segs, mark, v: flat[k] }
    })
    entries.sort((x, y) => (x.mark ? x.segs.length - 0.5 : x.segs.length) - (y.mark ? y.segs.length - 0.5 : y.segs.length))
    for (const e of entries) {
      const parentKey = e.segs.slice(0, -1).join('/')
      const parent = at.get(parentKey)
      if (!parent) throw new Error(`unflatten: ${e.k} has no container`)
      const last = e.segs[e.segs.length - 1]
      const slot = Array.isArray(parent) ? Number(last) : unesc(last)
      const value = e.mark === '~{}' ? {} : e.mark === '~#' ? new Array(Number(e.v) || 0) : e.mark === '~null' ? null : e.mark === '~,' ? String(e.v).split(',') : e.v
      parent[slot] = value
      if (e.mark === '~{}' || e.mark === '~#') at.set(e.segs.join('/'), value)
    }
    return root
  }
  function decodeTransport(text) {
    const prefix = 'RELAY64v1:'
    if (!text.startsWith(prefix)) return text
    const encoded = text.slice(prefix.length)
    if (!encoded || !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(encoded)) throw new Error('invalid relay base64 alphabet or padding')
    const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
    let decoded = ''
    for (let i = 0; i < encoded.length; i += 4) {
      const a = alphabet.indexOf(encoded[i])
      const b = alphabet.indexOf(encoded[i + 1])
      const c = encoded[i + 2] === '=' ? 0 : alphabet.indexOf(encoded[i + 2])
      const d = encoded[i + 3] === '=' ? 0 : alphabet.indexOf(encoded[i + 3])
      if ((encoded[i + 2] === '=' && (b & 15)) || (encoded[i + 3] === '=' && encoded[i + 2] !== '=' && (c & 3))) throw new Error('noncanonical relay base64 padding bits')
      const bytes = [(a << 2) | (b >> 4)]
      if (encoded[i + 2] !== '=') bytes.push(((b & 15) << 4) | (c >> 2))
      if (encoded[i + 3] !== '=') bytes.push(((c & 3) << 6) | d)
      for (const byte of bytes) {
        if (byte > 0x7f) throw new Error('relay payload must be canonical ASCII JSON, a strict UTF-8 subset')
        decoded += String.fromCharCode(byte)
      }
    }
    return decoded
  }
  /** Parses a runner's stdout copy and checks it is exactly the envelope the program printed; returns { env, flat } or { why }. */
  function parse(stdout, file) {
    let env
    try {
      const text = String(stdout || '').trim()
      const open = '<exact_text>'
      const close = '</exact_text>'
      const payload = text.startsWith(open) && text.endsWith(close) ? text.slice(open.length, -close.length) : text
      env = JSON.parse(decodeTransport(payload))
    } catch (err) {
      env = null
    }
    if (!env || typeof env !== 'object' || Array.isArray(env)) {
      const text = String(stdout || '')
      const exception = exceptionOf(text)
      return { why: exception ? `the program failed: ${exception}` : `stdout is not one valid relay envelope line: ${JSON.stringify(text.slice(0, 300))}` }
    }
    if (!HEX.test(String(env['~checksum'])) || !Number.isInteger(env['~exit'])) return { why: 'the copy has no relay checksum or exit status' }
    const named = env['~file'] === undefined ? null : env['~file']
    if (named !== file && !(named === null && env['~exit'] === 3)) return { why: `the copy names relay file ${JSON.stringify(named)}, not ${JSON.stringify(file)}` }
    const flat = {}
    for (const k of Object.keys(env)) if (!RELAY_KEYS.includes(k)) flat[k] = env[k]
    let got = ''
    try {
      got = sha256Json({ exit: env['~exit'], view: flat })
    } catch (err) {
      return { why: `the copy cannot be hashed: ${String((err && err.message) || err)}` }
    }
    if (got !== env['~checksum']) return { env, why: `the copy hashes to ${got}, not to the ${env['~checksum']} the program printed` }
    return { env, flat }
  }
  const prompt = (command) => `Run exactly this one shell command, once, in the FOREGROUND (never set run_in_background) with the Bash tool's \`timeout\` parameter set to 600000, and change nothing else. Type the command exactly as written below, character for character: the program checks it against the checksum it carries and refuses any difference.

${command}

It prints exactly one line beginning RELAY64v1: followed by base64 text. Copy that entire line as opaque text, including the prefix and any trailing = characters. Do not decode the base64, interpret its contents, or rebuild the JSON. Return the process exit code as \`exitCode\` and that line, verbatim, as the string \`stdout\`: every character as printed, in order, with nothing added, removed, reordered, reformatted or re-typed. Do not parse it, do not summarize it. If it printed more than one line, return all of stdout verbatim. Do not retry, do not repair, do not run any other command.`
  /** Runs a command once. A damaged copy can only re-read its exact saved receipt. */
  async function exec(dispatch, { label, phase, command, file = null, readRunner = null }) {
    const out = await dispatch(prompt(command), { label, phase, agentType: 'agent-teams-workforce:workflow-command-runner', model: 'sonnet', effort: 'low', schema: SCHEMA })
    if (!out) return { ok: false, noResult: true, error: `the ${label} runner returned no result` }
    let got = parse(out.stdout, file)
    if (got.why) {
      const receipt = got.env
      const bound = out.exitCode === 0 && receipt && receipt['~exit'] === 0 && file && readRunner && HEX.test(String(receipt['~sha256'])) && Number.isInteger(receipt['~bytes']) && receipt['~bytes'] >= 0
      let attempts = 1
      let reason = got.why
      if (bound) {
        const readCommand = pythonLine(readRunner, ['read', '--relay', file, '--sha256', receipt['~sha256'], '--bytes', String(receipt['~bytes'])])
        for (let retry = 1; retry <= 2; retry++) {
          attempts++
          log(`RELAY_COPY_RECOVERY_ATTEMPT ${JSON.stringify({ label, relayFile: file, attempt: retry, reason })}`)
          const copied = await dispatch(`The previous response failed validation: ${reason}. The original command has already completed. Do not execute it again. This corrective attempt only reads the saved result whose bytes must match the original receipt.

${prompt(readCommand)}`, { label: `${label}:copy-recovery${retry}`, phase, agentType: 'agent-teams-workforce:workflow-command-runner', model: 'sonnet', effort: 'low', schema: SCHEMA })
          // The dispatch wrapper owns quota/API interruptions; do not turn one into a copy hold.
          if (!copied) return { ok: false, noResult: true, error: `${label}: the corrective reader returned no result` }
          got = parse(copied.stdout, file)
          if (!got.why && (copied.exitCode !== 0 || got.env['~sha256'] !== receipt['~sha256'] || got.env['~bytes'] !== receipt['~bytes'] || got.env['~exit'] !== 0)) got = { why: 'the corrective read did not return the successful original receipt' }
          if (!got.why) break
          reason = got.why
        }
      }
      if (got.why) {
        const detail = { label, relayFile: file, attempts, reason: `${reason}${bound ? '' : '; no successful saved receipt is available for safe read-only recovery'}` }
        const error = `RELAY_COPY_RECOVERY_EXHAUSTED ${JSON.stringify(detail)}`
        log(error)
        return { ok: false, paused: true, recoveryKind: 'relay-copy-recovery', error }
      }
    }
    const exit = got.env['~exit']
    let view
    try {
      view = unflatten(got.flat)
    } catch (err) {
      return { ok: false, error: `${label}: the printed view could not be rebuilt: ${String((err && err.message) || err)}` }
    }
    if (exit === 3) return { ok: false, error: `${label}: ${String(view.error || 'the runner typed the command line differently from the one built')}; nothing ran` }
    return { ok: true, exit, view }
  }
  /** The exception line a Python traceback in `text` ends with, or ''. */
  function exceptionOf(text) {
    const s = String(text || '')
    if (!/Traceback \(most recent call last\)/.test(s)) return ''
    const lines = s.split('\n').map((l) => l.trim()).filter(Boolean)
    return [...lines].reverse().find((l) => /^[A-Za-z_][\w.]*(Error|Exception|Exit|Interrupt)(:|$)/.test(l)) || lines[lines.length - 1] || ''
  }
  /** The checked command line running python3 `script` with the argument list `rest`. */
  const pythonLine = (script, rest) => ['python3', script, '--argv-sha256', sha256Json(rest), ...rest].map(quote).join(' ')
  /**
   * Runs one depscore.py command. `tail` is its arguments as shell text (single-quoted words only),
   * `repo` the beads repository (-C), `file` the relay file its full result is saved in. Returns
   * what it printed, checked, with relayFile; or { error, exception?, output? }.
   */
  async function depscore(dispatch, { label, phase, script, repo, tail, file }) {
    let rest
    try {
      rest = [...(repo ? ['-C', repo] : []), '--relay', file, ...shellWords(tail)]
    } catch (err) {
      return { error: `${label}: ${String((err && err.message) || err)}` }
    }
    const r = await exec(dispatch, { label, phase, command: pythonLine(script, rest), file, readRunner: script.replace(/[^/]+$/, 'relayrun.py') })
    if (!r.ok) return { error: r.error, noResult: !!r.noResult }
    if (r.exit !== 0 || r.view.error) {
      const raw = String(r.view.error || `depscore.py exited ${r.exit}`)
      const exception = exceptionOf(raw)
      return { error: exception ? `${exception} (depscore.py exited ${r.exit}; full output: ${raw})` : raw, exception, output: r.view, relayFile: file }
    }
    return { ...r.view, relayFile: file }
  }
  /**
   * Runs `argv` (a program and its arguments, no shell) through relayrun.py at `runner`, in `cwd`.
   * Returns { ok: true, exitCode, json, stdoutBytes, stderrBytes, stdoutTail?, stderrTail?, relayFile }
   * — json is stdout parsed when it is one JSON object (reduced to `keys` when given), else null —
   * or { ok: false, error }.
   */
  async function run(dispatch, { label, phase, runner, argv, cwd = null, file, keys = [], tail = 0, timeout = null }) {
    const rest = ['run', '--relay', file, ...(cwd ? ['--cwd', cwd] : []), ...(keys.length ? ['--keys', keys.join(',')] : []), ...(tail ? ['--tail', String(tail)] : []), ...(timeout ? ['--timeout', String(timeout)] : []), '--', ...argv.map(String)]
    const r = await exec(dispatch, { label, phase, command: pythonLine(runner, rest), file, readRunner: runner })
    if (!r.ok) return { ok: false, error: r.error, noResult: !!r.noResult }
    if (r.exit !== 0) return { ok: false, error: String(r.view.error || `relayrun.py exited ${r.exit}`) }
    return { ok: true, ...r.view, relayFile: file }
  }
  /** Whether the JSON file `file` holds exactly `value`. Returns { ok: true, exists, parsed, match } or { ok: false, error }. */
  async function checkFile(dispatch, { label, phase, runner, file, value }) {
    const r = await exec(dispatch, { label, phase, command: pythonLine(runner, ['check-file', '--file', file, '--sha256', sha256Json(value)]) })
    if (!r.ok) return { ok: false, error: r.error, noResult: !!r.noResult }
    return { ok: true, exists: r.view.exists === true, parsed: r.view.parsed === true, match: r.view.match === true }
  }
  /**
   * Makes the JSON file `file` hold exactly `value`, the schema-validated result a session
   * returned: checks the file, and when it differs (or is missing) writes `value` through
   * relayrun.py write-file, which refuses a copy that does not hash as built, then checks again.
   * Returns { ok, rewritten, error? }.
   */
  async function ensureJson(dispatch, { label, phase, runner, file, value }) {
    const first = await checkFile(dispatch, { label: `${label}:check`, phase, runner, file, value })
    if (!first.ok) return { ok: false, rewritten: false, error: first.error }
    if (first.match) return { ok: true, rewritten: false }
    log(`${label}: ${file} ${first.exists ? 'differs from the result the session returned' : 'was not saved'}; writing the returned result`)
    const w = await exec(dispatch, { label: `${label}:write`, phase, command: pythonLine(runner, ['write-file', '--file', file, '--sha256', sha256Json(value), '--json', canonicalJson(value)]) })
    if (!w.ok || w.exit !== 0 || w.view.written !== true) return { ok: false, rewritten: false, error: (w.ok ? String(w.view.error || 'not written') : w.error) }
    const again = await checkFile(dispatch, { label: `${label}:recheck`, phase, runner, file, value })
    return again.ok && again.match ? { ok: true, rewritten: true } : { ok: false, rewritten: true, error: again.error || `${file} still differs after it was written` }
  }
  const BOOT = [
    'import base64, hashlib, json, sys',
    'a = sys.orig_argv',
    'i = a.index("-c")',
    'boot, want, code, args = a[i + 1], a[i + 2], a[i + 3], a[i + 4:]',
    'c = lambda v: json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=True)',
    'h = lambda v: hashlib.sha256(c(v).encode("ascii")).hexdigest()',
    'def flat(v, p="", o=None):',
    '    o = {} if o is None else o',
    '    j = (lambda s: p + "/" + s) if p else (lambda s: s)',
    '    if isinstance(v, dict):',
    '        if p:',
    '            o[j("~{}")] = len(v)',
    '        for k, x in v.items():',
    '            flat(x, j(str(k).replace("~", "~0").replace("/", "~1")), o)',
    '    elif isinstance(v, list):',
    '        o[j("~#")] = len(v)',
    '        for n, x in enumerate(v):',
    '            flat(x, j(str(n)), o)',
    '    elif v is None:',
    '        o[j("~null")] = 1',
    '    else:',
    '        o[p] = v',
    '    return o',
    'def emit(view, ex=0):',
    '    f = flat(view)',
    '    print("RELAY64v1:" + base64.b64encode(c(dict(f, **{"~exit": ex, "~checksum": h({"exit": ex, "view": f})})).encode("ascii")).decode("ascii"))',
    '    sys.exit(ex)',
    'if h([boot, code] + args) != want:',
    '    emit({"argvMismatch": True, "error": "the command line differs from the one the workflow script built"}, 3)',
    'exec(code, {"ARGS": args, "emit": emit, "__name__": "__relay__"})',
  ].join('\n')
  /**
   * Runs the Python `code` (which reads its arguments from ARGS and calls emit(obj) once with a
   * JSON object holding no floats) under a bootstrap that checks the command line, payload included,
   * and seals what it emits. Returns
   * { ok: true, view } or { ok: false, error }.
   */
  async function inline(dispatch, { label, phase, code, args = [] }) {
    const words = args.map(String)
    const command = ['python3', '-c', BOOT, sha256Json([BOOT, code, ...words]), code, ...words].map(quote).join(' ')
    const r = await exec(dispatch, { label, phase, command })
    if (!r.ok) return { ok: false, error: r.error, noResult: !!r.noResult }
    if (r.exit !== 0) return { ok: false, error: String(r.view.error || `exited ${r.exit}`) }
    return { ok: true, view: r.view }
  }
  const ARTIFACT_SCHEMA = { type: 'object', additionalProperties: false, required: ['artifactPath'], properties: { artifactPath: { type: 'string' } } }
  function artifactBrief(candidate, schema, revision = '') {
    return `\n\nAUTHORITATIVE ARTIFACT HANDOFF: Write the complete JSON result ONCE to ${candidate}, with schema ${JSON.stringify(schema)}. Return only {"artifactPath":"${candidate}"} using StructuredOutput, never a second payload copy. Keep ${candidate}.checkpoint current with status, artifactPath, schemaSha256, task, completed, remaining and artifacts (paths). Before returning set status="complete", artifactPath="${candidate}", schemaSha256="${sha256Json(schema)}", revision=${JSON.stringify(revision)}. On resume read the checkpoint and actual artifacts first, preserve completed work and finish only missing work. Shared Markdown, diagrams and other documents remain authoritative at their paths; read them directly, never replace them with summaries. Do not write the final accepted result; the workflow validates and publishes the candidate.`
  }
  async function acceptArtifact(dispatch, { label, phase, runner, candidate, file, schema, relayFile, returned = null, revision = '', keys = [], counts = [], projection = '', probe = false }) {
    if (returned && returned.artifactPath !== candidate) return { ok: false, error: `invalid artifact reference: expected ${candidate}` }
    const args = ['python3', runner.replace(/[^/]+$/, 'jsonartifact.py'), '--candidate', candidate, '--final', file, '--schema-json', canonicalJson(schema), ...(revision ? ['--revision', revision] : []), ...(keys.length ? ['--keys', keys.join(',')] : []), ...(counts.length ? ['--counts', counts.join(',')] : []), ...(projection ? ['--projection', projection] : []), ...(probe ? ['--probe'] : []), ...(!returned ? ['--recover'] : [])]
    const result = await run(dispatch, { label, phase, runner, argv: args, file: relayFile })
    if (!result.ok) return result
    if (result.exitCode !== 0) return { ok: false, error: `artifact validation failed: ${JSON.stringify(result.json)}`, relayFile }
    const receipt = result.json
    if (probe && receipt && receipt.pending === true) return { ok: true, pending: true }
    if (!receipt || receipt.artifactPath !== file || !/^[a-f0-9]{64}$/.test(receipt.sha256 || '') || !Number.isSafeInteger(receipt.bytes) || receipt.bytes < 1 || receipt.schemaSha256 !== sha256Json(schema) || receipt.revision !== revision) return { ok: false, error: 'invalid artifact receipt', relayFile }
    return { ok: true, receipt, facts: receipt.facts || {}, counts: receipt.counts || {} }
  }
  async function authorArtifact(dispatch, options, produce, interrupted = () => false) {
    const paused = () => ({ ok: false, noResult: true, error: 'artifact dispatch interrupted; saved work retained' })
    if (interrupted()) return paused()
    const prior = await acceptArtifact(dispatch, { ...options, label: `${options.label}:probe`, relayFile: `${options.relayFile}.probe`, returned: null, probe: true })
    if (interrupted()) return paused()
    if (!prior.ok || !prior.pending) return prior
    const returned = await produce()
    if (interrupted()) return paused()
    return acceptArtifact(dispatch, { ...options, returned, probe: false })
  }
  async function artifactRevision(dispatch, { label, phase, runner, files = [], relayFile, context = {} }) {
    if (!Array.isArray(files)) return { ok: false, error: 'artifact revision requires explicit source paths' }
    let receipts = []
    if (files.length) {
      const result = await run(dispatch, { label, phase, runner, argv: ['python3', runner.replace(/[^/]+$/, 'jsonartifact.py'), ...files.flatMap(file => ['--source', file])], file: relayFile })
      if (!result.ok) return result
      if (result.exitCode !== 0 || !result.json || !Array.isArray(result.json.receipts)) return { ok: false, error: `source fingerprint failed: ${JSON.stringify(result.json)}` }
      receipts = result.json.receipts
      if (receipts.length !== files.length || receipts.some((r, i) => r.artifactPath !== files[i] || !/^[a-f0-9]{64}$/.test(r.sha256 || '') || !Number.isSafeInteger(r.bytes) || r.bytes < 0 || !['file', 'directory'].includes(r.format))) return { ok: false, error: 'invalid source receipt' }
    }
    return { ok: true, revision: sha256Json({ receipts, context }) }
  }
  async function documentReceipt(dispatch, { label, phase, runner, files, relayFile }) {
    if (!Array.isArray(files) || !files.length) return { ok: false, error: 'document receipt requires explicit file paths' }
    const result = await run(dispatch, { label, phase, runner, argv: ['python3', runner.replace(/[^/]+$/, 'jsonartifact.py'), ...files.flatMap(file => ['--document', file])], file: relayFile })
    if (!result.ok) return result
    if (result.exitCode !== 0 || !result.json || !Array.isArray(result.json.receipts)) return { ok: false, error: `document verification failed: ${JSON.stringify(result.json)}` }
    const receipts = result.json.receipts
    if (receipts.length !== files.length || receipts.some((r, i) => r.artifactPath !== files[i] || !/^[a-f0-9]{64}$/.test(r.sha256 || '') || !Number.isSafeInteger(r.bytes) || r.bytes < 1 || r.format !== 'text')) return { ok: false, error: 'invalid document receipt' }
    return { ok: true, receipts }
  }
  return { ARTIFACT_SCHEMA, artifactBrief, acceptArtifact, authorArtifact, artifactRevision, documentReceipt, canonicalJson, sha256Ascii, sha256Json, quote, shellWords, exec, depscore, run, checkFile, ensureJson, inline, exceptionOf, unflatten, parse, SCHEMA }
})()
// ===== SHARED BLOCK relay — END =====

const dispatchFailures = []

async function run(prompt, opts) {
  if (dispatchInterruption) return null
  let message = 'returned nothing'
  try {
    const out = await fableAgent(prompt, opts)
    if (out) return out
  } catch (err) {
    captureDispatchInterruption(err, (opts && (opts.label || opts.agentType)) || 'agent')
    message = String((err && err.message) || err).slice(0, 300)
  }
  dispatchFailures.push({ label: opts.label, agentType: opts.agentType || null, phase: opts.phase, message })
  log(`${opts.label}: no structured result — ${message}`)
  return null
}

// args: { prd: { id?, title?, path? }, delta: { subject, targetDir, deltaDir, items: [{ id, element, views }] },
//   epic?: { key?, title? }, artifacts?: { dir, relDir?, epicId, script, phase, inputs?, beadId? },
//   pluginRoot? | relay?: { runner, dir? } (the checked relay: relayrun.py, given directly or as
//     <pluginRoot>/scripts/portfolio/relayrun.py; the script then checks and records repo-scoping.json
//     itself; without it the steward session records it, as before) }
// returns: { ok, reason?, repos, placements, noCode, createdRepos, creationFailures, spanRationale, surveySummary, persistErrors?, ledger }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const hasText = (v) => typeof v === 'string' && v.trim().length > 0

const ART = a.artifacts && typeof a.artifacts === 'object' && typeof a.artifacts.dir === 'string' && a.artifacts.dir ? a.artifacts : null
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
const relayArg = a.relay && typeof a.relay === 'object' ? a.relay : {}
const pluginRootArg = hasText(a.pluginRoot) && a.pluginRoot.trim().startsWith('/') ? a.pluginRoot.trim().replace(/\/+$/, '') : ''
const RELAY_RUNNER = hasText(relayArg.runner) && relayArg.runner.trim().startsWith('/')
  ? relayArg.runner.trim()
  : pluginRootArg ? `${pluginRootArg}/scripts/portfolio/relayrun.py` : ''

const prdInput = a.prd && typeof a.prd === 'object' ? a.prd : {}
const prdId = prdInput.id || ''
const prdTitle = prdInput.title || ''
const epic = a.epic || {}
const delta = a.delta && typeof a.delta === 'object' ? a.delta : {}
const items = (Array.isArray(delta.items) ? delta.items : []).filter((i) => i && hasText(i.id) && hasText(i.element))


const fail = (reason, extra) => ({
  ok: false,
  reason,
  repos: [],
  placements: [],
  noCode: [],
  createdRepos: [],
  creationFailures: [],
  ...(extra || {}),
})
const died = (phaseName) => {
  const deaths = dispatchFailures.filter((f) => f.phase === phaseName)
  return deaths.length ? { dispatchFailed: true, dispatchFailures: deaths } : {}
}

if (!hasText(delta.deltaDir) || !hasText(delta.targetDir)) {
  return dispatchOutcome({ ...fail('no approved target and delta were supplied: the span is the repositories the delta changes'), stage: 'input', deterministicFailure: true })
}
if (!items.length) {
  return dispatchOutcome({ ...fail(`the delta at ${delta.deltaDir} lists no item: depscore.py arch-delta found no element in its views' \`shows\``), stage: 'input', deterministicFailure: true })
}

phase('Place and provision')

const itemLines = items
  .map((i) => `- ${i.id}: ${i.element}${Array.isArray(i.views) && i.views.length ? `\n    shown in: ${i.views.join('; ')}` : ''}`)
  .join('\n')

if (!ART || !RELAY_RUNNER) return dispatchOutcome(fail('An artifact directory and relay runner are required to retain the authoritative placement.'))
const placementSchema = {
      type: 'object',
      additionalProperties: false,
      required: ['placements', 'noCode', 'createdRepos', 'creationFailures', 'spanRationale'],
      properties: {
        placements: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['repoPath', 'repoName', 'itemIds', 'frontend', 'rationale'],
            properties: {
              repoPath: { type: 'string' },
              repoName: { type: 'string' },
              itemIds: { type: 'array', items: { type: 'string' } },
              frontend: { type: 'boolean' },
              rationale: { type: 'string' },
              created: { type: 'boolean' },
            },
          },
        },
        noCode: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['itemId', 'reason'],
            properties: { itemId: { type: 'string' }, reason: { type: 'string' } },
          },
        },
        createdRepos: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['name', 'repoPath', 'purpose'],
            properties: {
              name: { type: 'string' },
              repoPath: { type: 'string' },
              template: { type: 'string' },
              purpose: { type: 'string' },
              itemIds: { type: 'array', items: { type: 'string' } },
            },
          },
        },
        creationFailures: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['proposedName', 'error'],
            properties: {
              proposedName: { type: 'string' },
              itemIds: { type: 'array', items: { type: 'string' } },
              error: { type: 'string' },
            },
          },
        },
        surveySummary: { type: 'string' },
        spanRationale: { type: 'string' },
      },
    }
const candidateFile = `${ART.dir}/candidates/repo-scoping.json`
const inputBinding = await relayKit.artifactRevision(run, { label: 'placement:inputs', phase: 'Place and provision', runner: RELAY_RUNNER, files: [...new Set([...(ART.inputs || []), delta.targetDir, delta.deltaDir].filter(hasText))], relayFile: `${ART.dir}/relay/placement-inputs.json`, context: { prd: prdInput, delta, epic } })
if (!inputBinding.ok) return dispatchOutcome(fail(inputBinding.error))
const inputRevision = inputBinding.revision
const place = () => run(
  `Place each item of an approved architecture delta in the repository whose code changes for it, and CREATE each new repository the approved target names. You own the project's repositories and your records of them; repository facts come from your records and the live repositories, as the polyrepo-repo skill describes.

THE APPROVED TARGET for ${prdTitle || prdId || 'this PRD'} is ${delta.targetDir}; the change alone, its delta, is ${delta.deltaDir}. Read the delta views, and the target views where a delta view leaves an element's home unstated. Each item below is one element the delta shows:
${itemLines}

DO THIS, IN ORDER:

1. Take the inventory LIVE, now, with your polyrepo tool: \`inventory --json\` (the polyrepo-repo skill names the tool and its path).
2. For each item, name the repository whose code changes for it: the repository that owns the element, as your records and the code on its \`main\` show. An element that has no code in this project (an external system, or a managed service whose configuration lives in the code of another item's repository) goes in \`noCode\` with the reason; an element whose configuration lives in a repository's code is placed in that repository.
3. Where the approved target names a NEW repository for an element, look first in the live inventory for a repository that already serves it, including one an earlier run of this same PRD created, and place the item there rather than creating a second. Otherwise create it with the polyrepo tool's \`create\` command, locally and on GitHub, as the polyrepo-repo skill describes, with the name, the template and the reason the target gives; where the target names no template, the template whose kind matches the element as the target describes it. If a creation fails, fix what the error names and try it once more; if it still fails, report it in creationFailures with the error text. Create no repository the target does not name.

Return:

- placements — one entry per repository that holds work, including each repository you created. Each: repoPath (the repository's absolute local path, exactly as your polyrepo tool reports it), repoName, itemIds (the ids of the items placed there), frontend (true when the repository serves a user interface, per your records), rationale, and created (true when you created it in this session).
- noCode — one entry per item with no code in this project: itemId and reason.
- createdRepos — one entry per repository you created in this session: name, repoPath, template, purpose, itemIds. Empty when you created none.
- creationFailures — one entry per repository the target names that you could not create: proposedName, itemIds, error. Empty when every creation succeeded.
- surveySummary — how many repositories the inventory holds and how you took it.
- spanRationale — why these are the repositories the delta changes, in a few sentences.

Every item appears exactly once: in one placement or in noCode. Change nothing in any repository beyond creating the ones the target names.${relayKit.artifactBrief(candidateFile, placementSchema, inputRevision)}`,
  {
    label: 'scope:place-delta',
    phase: 'Place and provision',
    effort: 'high',
    agentType: 'agent-teams-workforce:polyrepo-steward',
    schema: relayKit.ARTIFACT_SCHEMA,
  }
)

if (dispatchInterruption) return dispatchOutcome(fail('Placement was interrupted.', died('Place and provision')))
let placed
const persistErrors = []
if (ART && RELAY_RUNNER) {
  const relayDir = hasText(relayArg.dir) && relayArg.dir.trim().startsWith('/') ? relayArg.dir.trim().replace(/\/+$/, '') : `${ART.dir}/relay/repo-scoping`
  let relaySeq = 0
  const relayFile = (label) => {
    relaySeq += 1
    return `${relayDir}/${String(relaySeq).padStart(3, '0')}-${label}.json`
  }
  const file = `${ART.dir}/repo-scoping.json`
  const saved = await relayKit.authorArtifact(run, { label: 'save:repo-scoping', phase: 'Place and provision', runner: RELAY_RUNNER, candidate: candidateFile, file, schema: placementSchema, revision: inputRevision, relayFile: relayFile('accepted-repo-scoping'), keys: ['placements.repoPath', 'placements.repoName', 'placements.itemIds', 'placements.frontend', 'placements.created', 'noCode.itemId', 'createdRepos.name', 'createdRepos.repoPath', 'createdRepos.itemIds', 'creationFailures.proposedName', 'creationFailures.itemIds'] }, place, () => !!dispatchInterruption)
  placed = saved.facts
  if (!saved.ok) {
    return dispatchOutcome(fail(`The authoritative placement was not accepted: ${saved.error || 'not saved'}`))
  } else {
    const inputs = (Array.isArray(ART.inputs) ? ART.inputs : []).filter(hasText)
    const recorded = await relayKit.run(run, {
      label: 'record:repo-scoping',
      phase: 'Place and provision',
      runner: RELAY_RUNNER,
      argv: ['python3', ART.script, 'record', file, '--epic', ART.epicId, '--phase', ART.phase, ...(inputs.length ? ['--inputs', ...inputs] : [])],
      file: relayFile('record-repo-scoping'),
      keys: ['sha256', 'bytes'],
      tail: 20,
    })
    if (!recorded.ok || recorded.exitCode !== 0) persistErrors.push(`repo-scoping.json was not recorded: ${!recorded.ok ? recorded.error : `the record command exited ${recorded.exitCode}: ${String(recorded.stderrTail || recorded.stdoutTail || '').trim().slice(0, 600)}`}`)
  }
  for (const e of persistErrors) log(e)
} else if (ART) {
  log('repo-scoping: no relay runner (pluginRoot or relay.runner) was passed, so the steward session recorded repo-scoping.json itself')
}

const known = new Set(items.map((i) => i.id))
const seen = new Map()
const note = (id, where) => seen.set(id, [...(seen.get(id) || []), where])
const placements = []
const repos = []
for (const p of placed.placements) {
  if (!p || !hasText(p.repoPath)) continue
  const repoPath = p.repoPath.trim()
  const itemIds = (Array.isArray(p.itemIds) ? p.itemIds : []).filter((x) => hasText(x)).map((x) => x.trim())
  if (!itemIds.length) continue
  if (!repos.includes(repoPath)) repos.push(repoPath)
  for (const id of itemIds) note(id, repoPath)
  placements.push({
    repoPath,
    repoName: hasText(p.repoName) ? p.repoName : repoPath,
    itemIds,
    frontend: p.frontend === true,
    rationalePath: `${ART.dir}/repo-scoping.json`,
    created: p.created === true,
  })
}
const noCode = (Array.isArray(placed.noCode) ? placed.noCode : []).filter((n) => n && hasText(n.itemId)).map((n) => ({ itemId: n.itemId.trim(), reasonPath: `${ART.dir}/repo-scoping.json` }))
for (const n of noCode) note(n.itemId, 'noCode')
const createdRepos = placed.createdRepos.filter((c) => c && hasText(c.name))
const creationFailures = placed.creationFailures.filter((f) => f && hasText(f.proposedName))

const unknown = [...seen.keys()].filter((id) => !known.has(id))
const twice = [...seen.entries()].filter(([id, where]) => known.has(id) && where.length > 1).map(([id, where]) => `${id} (${where.join(', ')})`)
const unplaced = items.filter((i) => !seen.has(i.id)).map((i) => `${i.id} ${i.element}`)
const faults = [
  unplaced.length ? `not placed: ${unplaced.join('; ')}` : '',
  twice.length ? `placed more than once: ${twice.join('; ')}` : '',
  unknown.length ? `not items of the delta: ${unknown.join(', ')}` : '',
  creationFailures.length ? `not created: ${creationFailures.map((f) => `${f.proposedName} (details in ${ART.dir}/repo-scoping.json)`).join('; ')}` : '',
].filter(Boolean)
if (faults.length) {
  return dispatchOutcome(fail(`the placement of the delta items is incomplete — ${faults.join('; ')}`, { placements, noCode, createdRepos, creationFailures, ...(persistErrors.length ? { persistErrors } : {}) }))
}
if (!repos.length) {
  return dispatchOutcome(fail('the polyrepo-steward placed the delta in no repository: every item was recorded as having no code in this project.', { noCode, createdRepos, creationFailures, ...(persistErrors.length ? { persistErrors } : {}) }))
}

log(
  `Span placed: ${repos.length} repositor(ies) — ${repos.join(', ')}` +
    `${createdRepos.length ? `; ${createdRepos.length} created (${createdRepos.map((c) => c.name).join(', ')})` : ''}` +
    `${noCode.length ? `; ${noCode.length} item(s) with no code here` : ''}.`
)

return dispatchOutcome({
  ok: true,
  repos,
  placements,
  noCode,
  createdRepos,
  creationFailures,
  artifactPath: `${ART.dir}/repo-scoping.json`,
  ...(persistErrors.length ? { persistErrors } : {}),
  ledger: {
    phase: 'repo-scoping',
    beadId: (epic && epic.key) || null,
    subject: prdId || prdTitle || null,
    chosen: ['polyrepo-steward'],
    mode: 'fixed',
    repoCount: repos.length,
    itemCount: items.length,
    createdRepoCount: createdRepos.length,
    ok: true,
  },
})
