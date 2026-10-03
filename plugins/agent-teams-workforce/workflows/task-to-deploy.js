export const meta = {
  name: 'task-to-deploy',
  description:
    "Builds a Task from its build contract on its Story's branch and commits it only when the repository's whole test suite passes. Establishes (or reuses) the Story's worktree, stashing a reused tree's uncommitted changes; for an infrastructure Task authors the provisioning intent; runs the suite command the repository declares once as a baseline; loops Red until a new test fails with no new collection error and no regression; loops Green until the whole suite exits 0, routing tests the implementer names to Red in update mode; refactors, restoring the pre-refactor snapshot when the suite goes red; for a web-ui Task first selects the design source it builds with from the bundles supplied now (depscore.py cds-bundles on designSystem.packagesDir): a cds Task whose artifact has a supplied bundle builds from that bundle, a bundle Task builds from the newest bundle of its artifact and stops blocked-upstream when none remains, a none Task is unchanged; then audits the files it changed by that design source — against the cds bundle the owner supplied (bundle) with the cds plugin's tools/audit-app.py, cds:audit-against-system ruling the findings the script cannot rule on; against the live CDS design system with cds:audit-against-system (cds); not at all for a change with no design impact (none) — sends violations back through the Green loop once and stops with cds-audit when they remain (blocked-upstream when required cds configuration, design artifacts or capabilities remain unresolved), returning the verdict, with the design source and bundle used, as cdsAudit and the design source as designSource; updates the documentation; then commits to the Story branch after a final green run. Stops with red-unsatisfied, blocked-upstream or no-progress when the contract cannot be built. Every deterministic step — the cds bundle selection (depscore.py cds-bundles), the cds audit script, the fingerprint of Red's test files and of the work tree around each Green round, and the git and suite steps of its minis — runs through relayrun.py, whose result reaches the workflow checked; the relay runner is pluginRoot's (else the plugin registry's) and the relay files go in relay.dir (else a mkdtemp directory), and each mini gets a numbered directory of its own. It deploys nothing and opens no pull request: the Story deploys and opens one pull request once its last Task is done. Returns { ok, stage, beadId, storyId, headline, detailPath, branch, worktree, commit }.",
  phases: [
    { title: 'Workspace', detail: "establishes or reuses the Story's worktree every writing phase operates in" },
    { title: 'Infra Intent', detail: 'authors the provisioning intent for an infrastructure Task' },
    { title: 'Baseline', detail: "resolves the repository's suite command and runs it before any change" },
    { title: 'Red' },
    { title: 'Green' },
    { title: 'Refactor' },
    { title: 'CDS Audit', detail: "audits a web-ui Task's changed files against its supplied cds bundle or the live CDS design system, by its design source, and sends violations back through the Green loop once" },
    { title: 'Documentation' },
    { title: 'Commit', detail: 'runs the suite a final time and commits the Task to the Story branch' },
    { title: 'Run Ledger', detail: 'writes the run journal on every exit path' },
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

// BEGIN bounded dispatch policy — identical in workflow consumers (no runtime imports).
let dispatchInterruption = null
function dispatchOutcome(result) {
  if (!dispatchInterruption) return result
  const out = result && typeof result === 'object' ? result : {}
  return { ...out, ok: false, dispatchFailed: true, paused: true, resumable: true,
    stage: dispatchInterruption.stage, reason: dispatchInterruption.message, headline: dispatchInterruption.message,
    ...(typeof out.passed === 'boolean' ? { passed: false } : {}),
    ...(out.ledger ? { ledger: { ...out.ledger, ok: false } } : {}), dispatchInterruption }
}
function dispatchPolicy(options) {
  const input = (typeof args === 'string' ? JSON.parse(args) : args) || {}
  const policy = (options && options.retryPolicy) || input.retryPolicy || {}
  return { maxAttempts: Number.isInteger(policy.maxAttempts) && policy.maxAttempts > 0 ? policy.maxAttempts : 3,
    maxWaitMs: Number.isFinite(policy.maxWaitMs) && policy.maxWaitMs >= 0 ? policy.maxWaitMs : 300000 }
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
function dispatchRetry(err, name, attempt, waitedMs, policy, canWait) {
  const cause = dispatchFailureCause(err)
  if (cause === 'deterministic') return { retry: false, cause }
  const e = err && typeof err === 'object' ? err : {}
  const headers = e.headers || (e.response && e.response.headers) || {}
  const rawRetryAfter = e.retryAfter !== undefined ? e.retryAfter : headers['retry-after']
  const retryAfter = e.retryAfterMs !== undefined ? Number(e.retryAfterMs) : Number(rawRetryAfter) * 1000
  // An HTTP-date without a supplied clock cannot be safely shortened to our backoff.
  const unknownRetryDate = rawRetryAfter !== undefined && !Number.isFinite(retryAfter)
  let hash = 2166136261
  for (const ch of `${name}#${attempt}`) hash = Math.imul(hash ^ ch.charCodeAt(0), 16777619)
  const scheduled = Math.round(Math.min(300000, 5000 * Math.pow(3, attempt - 1)) * (0.5 + 0.5 * ((hash >>> 0) / 4294967296)))
  const wait = Math.max(scheduled, Number.isFinite(retryAfter) && retryAfter >= 0 ? retryAfter : 0)
  if (cause === 'transient' && !unknownRetryDate && canWait && attempt < policy.maxAttempts && waitedMs + wait <= policy.maxWaitMs) return { retry: true, cause, wait }
  const stage = cause === 'exhausted' ? 'account-quota-exhausted' : 'api-unavailable'
  return { retry: false, cause, interruption: { stage, message: `${stage}: ${name}: ${String(e.message || err || cause)}`, attempt,
    retryAfterMs: Number.isFinite(retryAfter) && retryAfter >= 0 ? retryAfter : null, retryAfter: rawRetryAfter || null } }
}
async function settleWorkflow(name, input) {
  if (dispatchInterruption) return dispatchOutcome({})
  const source = (typeof args === 'string' ? JSON.parse(args) : args) || {}
  try {
    const out = await fableWorkflow(name, { ...input, ...(source.retryPolicy && !(input && input.retryPolicy) ? { retryPolicy: source.retryPolicy } : {}) })
    if (out && out.paused && out.resumable && out.dispatchInterruption) dispatchInterruption = out.dispatchInterruption
    return out
  } catch (err) {
    const plan = dispatchRetry(err, name, 1, 0, dispatchPolicy(null), false)
    if (!plan.interruption) throw err
    dispatchInterruption = plan.interruption
    return dispatchOutcome({})
  }
}
// END bounded dispatch policy
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


// args: {
//   bead: { id, repoPath, story: { id, title? }, type?, labels?, title?, description?, specPath?, specPaths?, specSections?,
//           requirementIds?, definitionOfDone?, decisionIds?, acceptanceCriteria?, surfaces?, apiSpec?, eventContracts?, testStrategy?,
//           cdsDesignSource?: 'bundle' | 'cds' | 'none', cdsArtifact?: { kind, slug }, cdsBundlePath?, cdsBuildSpecs? },
//   designSystem?: { packagesDir? } (the folder of single-artifact cds bundles the owner supplied; read at build time),
//   pluginRoot?: string (the agent-teams-workforce install; else the install $CLAUDE_CONFIG_DIR/plugins/installed_plugins.json records),
//   infraVocabulary: { types, labels } (the plugin's scripts/infra-vocabulary.json),
//   spec?: object (defaults to bead), implementer?: string, worktreeRoot?: string,
//   cdsRoot?: string (the cds plugin install; else the cds install $CLAUDE_CONFIG_DIR/plugins/installed_plugins.json records),
//   maxRedRounds?: number (default 4), maxGreenRounds?: number (default 8),
//   relay?: { runner?, dir? } (relayrun.py and a directory for this run's relay files; the runner defaults to pluginRoot's,
//           else the registry's, and the directory to mkdtemp)
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const bead = a.bead || {}
const spec = a.spec || bead
const story = bead.story && typeof bead.story === 'object' ? bead.story : {}
const MAX_RED_ROUNDS = a.maxRedRounds || 4
const MAX_GREEN_ROUNDS = a.maxGreenRounds || 8
const DISPATCH_FAILED_STAGE = 'agent-dispatch-failed'
const TAIL_CHARS = 4000

// An infrastructure Task, by the same type and label test route-build applies.
const norm = (v) => String(v || '').trim().toLowerCase()
const vocabulary = a.infraVocabulary || {}
const INFRA_TYPES = (Array.isArray(vocabulary.types) ? vocabulary.types : []).map(norm).filter(Boolean)
const INFRA_LABELS = (Array.isArray(vocabulary.labels) ? vocabulary.labels : []).map(norm).filter(Boolean)
const beadLabels = (Array.isArray(bead.labels) ? bead.labels : []).map(norm)
const isInfra = INFRA_TYPES.includes(norm(bead.type)) || beadLabels.some((l) => INFRA_LABELS.includes(l))

// A Task whose surfaces include web-ui takes one design source: bundle (built from the cds bundle the owner
// supplied and audited against it), cds (designed with the CDS design system and audited against the live
// design system) or none (no design impact: no cds design step and no cds audit). A contract that records
// no design source takes bundle when it names a bundle, else cds. Before the build, the bundles supplied now
// decide the source actually used: a mockup can arrive any time before its Task is built.
const UI_SURFACE = 'web-ui'
const isUiTask = (Array.isArray(bead.surfaces) ? bead.surfaces : []).map(norm).includes(UI_SURFACE)
const DESIGN_SOURCES = ['bundle', 'cds', 'none']
let designSource = !isUiTask
  ? null
  : DESIGN_SOURCES.includes(norm(bead.cdsDesignSource))
    ? norm(bead.cdsDesignSource)
    : String(bead.cdsBundlePath || '').trim()
      ? 'bundle'
      : 'cds'

if (!bead.id) return dispatchOutcome({ ok: false, stage: 'input', error: 'no bead.id supplied' })
if (!INFRA_TYPES.length || !INFRA_LABELS.length) {
  return dispatchOutcome({ ok: false, stage: 'input', error: 'no infraVocabulary supplied: pass the types and labels from scripts/infra-vocabulary.json' })
}

const runLedger = []
let runDetail = null
let workspaceOut = null
// The cds audit verdict, { verdict: pass | fail | blocked | error, findings, scriptVersion }, once the audit ran.
let cdsVerdict = null
// The bundle the build uses, once the design source is selected.
let usedBundle = null

// Logs the journal payload as `RUN-JOURNAL {json}`, or as `RUN-JOURNAL-PART i/n <chunk>` lines when
// it exceeds JOURNAL_CHUNK characters; the host concatenates the parts and writes the journal file.
const JOURNAL_CHUNK = 4000
function emitRunJournal(payload) {
  const body = JSON.stringify(payload)
  if (body.length <= JOURNAL_CHUNK) {
    log(`RUN-JOURNAL ${body}`)
    return
  }
  const parts = []
  for (let i = 0; i < body.length; ) {
    let end = Math.min(i + JOURNAL_CHUNK, body.length)
    const last = body.charCodeAt(end - 1)
    if (end < body.length && last >= 0xd800 && last <= 0xdbff) end -= 1
    parts.push(body.slice(i, end))
    i = end
  }
  parts.forEach((part, i) => log(`RUN-JOURNAL-PART ${i + 1}/${parts.length} ${part}`))
}
function persistRun(outcome) {
  if (!runLedger.length && !runDetail) return null
  try {
    emitRunJournal({ composite: 'task-to-deploy', bead: null, subject: bead.id || null, outcome, runLedger, detail: runDetail })
  } catch (e) {
    log(`run journal could not be serialized: ${e && e.message ? e.message : e}`)
  }
  return null
}

let currentPhase = null
function enterPhase(title) {
  currentPhase = title
  phase(title)
}

// Returns the caller-facing result; `detail` goes to the run journal only.
function handback(ok, stage, headline, detail) {
  runDetail = detail === undefined ? null : detail
  return {
    ok,
    stage,
    beadId: bead.id || null,
    storyId: story.id || null,
    headline: String(headline || ''),
    branch: (workspaceOut && workspaceOut.branch) || null,
    worktree: (workspaceOut && workspaceOut.repoPath) || null,
    ...(designSource ? { designSource } : {}),
    ...(cdsVerdict ? { cdsAudit: { ...cdsVerdict, designSource, bundle: usedBundle } } : {}),
  }
}

// Returns the stage for a failed phase result: dispatch failure, or `stage`.
const stageOf = (stage, r) => (!r || r.dispatchFailed ? DISPATCH_FAILED_STAGE : stage)

function implementersOf(artifact) {
  const l = artifact && artifact.ledger
  return l && (l.mode === 'selected' || l.mode === 'reused') && Array.isArray(l.chosen) && l.chosen.length ? l.chosen : undefined
}

const list = (v) => (Array.isArray(v) ? v.filter(Boolean) : [])

// Consumed by greenLoop: a Red update must disposition every requested test before Green retries.
function checkTestDecisions(issues, decisions) {
  const requested = [...new Set((Array.isArray(issues) ? issues : []).map((x) => String((x && x.testId) || '').trim()).filter(Boolean))]
  const returned = Array.isArray(decisions) ? decisions : []
  const problems = []
  const accepted = []
  for (const id of requested) {
    const matches = returned.filter((x) => x && String(x.testId || '').trim() === id)
    if (matches.length !== 1) {
      problems.push(`${id}: expected one disposition, received ${matches.length}`)
      continue
    }
    const decision = matches[0]
    if (!['update', 'delete', 'keep'].includes(decision.action) || typeof decision.reason !== 'string' || !decision.reason.trim()) {
      problems.push(`${id}: disposition needs a valid action and a nonempty reason`)
      continue
    }
    accepted.push({ testId: id, action: decision.action, reason: decision.reason })
  }
  return { problems, decisions: accepted }
}

// A suite-run failure, { kind: test | load, file, test, line }, keyed the same way in every run.
const entryOf = (f) =>
  f && typeof f === 'object'
    ? { kind: f.kind === 'load' ? 'load' : 'test', file: String(f.file || '').trim().replace(/^\.\//, ''), test: String(f.test || '').trim(), line: String(f.line || '').trim() }
    : null
const idOf = (e) => `${e.kind}|${e.file}|${e.test}`
const describe = (e) => (e.kind === 'load' ? `${e.file || e.line} could not be loaded` : `${e.file}${e.test ? ` ${e.test}` : ''}`)
const failures = (run) => {
  const byId = new Map()
  for (const e of list(run && run.failing).map(entryOf)) if (e && (e.file || e.test)) byId.set(idOf(e), e)
  return byId
}
const failingIds = (run) => new Set(failures(run).keys())
const sameFile = (p, f) => {
  const x = String(p || '').replace(/^\.\//, '')
  const y = String(f || '').replace(/^\.\//, '')
  return !!x && !!y && (x === y || x.endsWith(`/${y}`) || y.endsWith(`/${x}`))
}

// The runner's report as feedback text for the next session.
const runText = (run) =>
  [
    `The suite runner ran \`${(run && run.command) || '(no command)'}\` and it exited ${run ? run.exitCode : 'with no result'}.`,
    run && run.summary ? `Summary: ${run.summary}` : '',
    failures(run).size ? `Failing:\n${[...failures(run).values()].map((e) => e.line || describe(e)).join('\n')}` : '',
    run && run.tail ? `Output (last part):\n${String(run.tail).slice(-TAIL_CHARS)}` : '',
  ]
    .filter(Boolean)
    .join('\n')

const validRun = (r) => !!r && !r.dispatchFailed && Number.isInteger(r.exitCode) && r.exitCode >= 0

const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
// ── Relay setup: relayrun.py (the plugin's scripts/portfolio/) runs every deterministic step, and
// each result is saved as NNN-<label>.json in a directory of this run's own. A caller passes
// relay: { runner, dir }; whatever it leaves out is resolved once, by a self-checking inline step:
// the runner from the agent-teams-workforce install $CLAUDE_CONFIG_DIR/plugins/installed_plugins.json
// records (the install for $ATW_CONTROL_REPO first, else the user-scope one), the directory from mkdtemp.
const RELAY_RESOLVE_PY = `import json, os, tempfile
from pathlib import Path
root, base, name = ARGS
marker = ("scripts", "portfolio", "relayrun.py")
problem = ""
if root and not Path(root, *marker).is_file():
    problem = f"{root} has no scripts/portfolio/relayrun.py"
if not root:
    config = os.environ.get("CLAUDE_CONFIG_DIR", "").strip() or str(Path.home() / ".claude")
    reg = Path(config) / "plugins" / "installed_plugins.json"
    control = os.environ.get("ATW_CONTROL_REPO", "").strip()
    control = os.path.normpath(control) if control else ""
    try:
        plugins = json.loads(reg.read_text(encoding="utf-8")).get("plugins", {})
    except (OSError, ValueError) as exc:
        plugins, problem = {}, f"{reg} is unreadable: {exc}"
    ranked = []
    for key, entries in plugins.items():
        if not key.startswith("agent-teams-workforce@") or not isinstance(entries, list):
            continue
        for e in entries:
            path = str(e.get("installPath") or "") if isinstance(e, dict) else ""
            if not path or not Path(path, *marker).is_file():
                continue
            if control and e.get("scope") in ("local", "project") and os.path.normpath(str(e.get("projectPath") or "")) == control:
                ranked.append((0, path))
            elif e.get("scope") == "user":
                ranked.append((1, path))
    if ranked:
        root = sorted(ranked)[0][1]
    elif not problem:
        problem = f"{reg} lists no agent-teams-workforce install shipping scripts/portfolio/relayrun.py"
if problem:
    emit({"error": problem}, 2)
if base:
    Path(base).mkdir(parents=True, exist_ok=True)
    folder = os.path.realpath(base)
else:
    folder = os.path.realpath(tempfile.mkdtemp(prefix=f"{name}-relay-"))
emit({"runner": os.path.join(os.path.normpath(root), *marker), "dir": folder})`
const RUNNER_TAIL = '/scripts/portfolio/relayrun.py'
let relaySeq = 0
/** Returns { runner, dir, gitfacts } for this run, or { error }. */
async function relaySetup(name, given, phaseTitle) {
  const g = given && typeof given === 'object' ? given : {}
  const runner = String(g.runner || '').trim()
  const dir = String(g.dir || '').trim().replace(/\/+$/, '')
  const usable = runner.startsWith('/') && runner.endsWith(RUNNER_TAIL)
  let found = { runner, dir }
  if (!usable || !dir.startsWith('/')) {
    const r = await relayKit.inline(guardedAgent, {
      label: `${name}:relay-setup`,
      phase: phaseTitle,
      code: RELAY_RESOLVE_PY,
      args: [usable ? runner.slice(0, -RUNNER_TAIL.length) : '', dir.startsWith('/') ? dir : '', name],
    })
    if (!r.ok) return { error: `the relay runner could not be resolved: ${r.error}`, noResult: !!r.noResult }
    found = { runner: String(r.view.runner || ''), dir: String(r.view.dir || '').replace(/\/+$/, '') }
  }
  if (!found.runner.startsWith('/') || !found.dir.startsWith('/')) return { error: 'the relay runner or its directory is not an absolute path' }
  return { ...found, gitfacts: `${found.runner.slice(0, -'relayrun.py'.length)}gitfacts.py` }
}
/** The next relay file in `dir`, numbered by this run's counter. */
const relayFileIn = (dir, label) => `${dir}/${String(++relaySeq).padStart(3, '0')}-${String(label).replace(/[^A-Za-z0-9._-]+/g, '-')}.json`
// Set once the relay runner is resolved, before the first deterministic step.
let RELAY = null
/** The relay arg a child workflow gets: this run's runner and a numbered directory of its own. */
const childRelay = (name) => ({ runner: RELAY.runner, dir: `${RELAY.dir}/${String(++relaySeq).padStart(3, '0')}-${name}` })
/** Runs one gitfacts.py command through relayrun.py; returns { facts } or { error }. */
async function gitfacts(label, argv) {
  const r = await relayKit.run(guardedAgent, { label, phase: currentPhase || 'Green', runner: RELAY.runner, argv: ['python3', RELAY.gitfacts, ...argv], file: relayFileIn(RELAY.dir, label) })
  if (!r.ok) return { error: r.error }
  if (r.exitCode !== 0 || !r.json || r.json.error) return { error: String((r.json && r.json.error) || `gitfacts.py ${argv[0]} exited ${r.exitCode}`) }
  return { facts: r.json }
}
/**
 * Returns { files: { <path>: <git blob hash or "missing"> }, treeDigest } for the given test files in the
 * tree (treeDigest changes exactly when the work tree changes), or { error }.
 */
async function fingerprint(tree, files, label) {
  let r
  try {
    r = await gitfacts(label, ['hash-files', '--tree', tree, ...files])
  } catch (err) {
    return { error: String((err && err.message) || err).slice(0, 300) }
  }
  if (r.error) return { error: `the fingerprint of the test files did not run: ${r.error}`.slice(0, 500) }
  const got = r.facts.files && typeof r.facts.files === 'object' ? r.facts.files : {}
  const missing = files.filter((f) => !(f in got))
  return missing.length ? { error: `the fingerprint names no hash for ${missing.join(', ')}` } : { files: got, treeDigest: String(r.facts.treeDigest || '') }
}

// ── cds audit: the cds plugin's tools/audit-app.py over the files the Task changed (uncommitted
// against HEAD, untracked included: the Task commits only at the end), then a judgment session on
// the findings the script cannot rule on ──
const CDS_AUDIT_MAX_FINDINGS = 60
const CDS_JUDGMENT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['rulings'],
  properties: {
    rulings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['file', 'line', 'value', 'ruling', 'reason'],
        properties: {
          file: { type: 'string' },
          line: { type: 'integer' },
          value: { type: 'string' },
          ruling: { type: 'string', enum: ['violation', 'allowed', 'cds-gap'] },
          reason: { type: 'string' },
        },
      },
    },
  },
}
// Resolves tools/audit-app.py (cdsRoot, else the cds install the plugin registry records for
// $ATW_CONTROL_REPO, else the user-scope one) and runs it; its exit status is the script's.
const RUN_CDS_AUDIT_PY = `import json, os, subprocess, sys
from pathlib import Path
repo, bundle, override, cap = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
script = Path(override, "tools", "audit-app.py") if override else None
problem = f"{script} does not exist" if script and not script.is_file() else ""
if script is None:
    control = os.environ.get("ATW_CONTROL_REPO", "").strip()
    config = os.environ.get("CLAUDE_CONFIG_DIR", "").strip() or str(Path.home() / ".claude")
    reg = Path(config) / "plugins" / "installed_plugins.json"
    try:
        plugins = json.loads(reg.read_text(encoding="utf-8")).get("plugins", {})
    except (OSError, ValueError) as exc:
        plugins, problem = {}, f"{reg} is unreadable: {exc}"
    ranked = []
    for key, entries in plugins.items():
        if not key.startswith("cds@") or not isinstance(entries, list):
            continue
        for e in entries:
            path = Path(str(e.get("installPath") or ""), "tools", "audit-app.py") if isinstance(e, dict) else None
            if not path or not path.is_file():
                continue
            if e.get("scope") in ("local", "project") and control and os.path.normpath(str(e.get("projectPath") or "")) == os.path.normpath(control):
                ranked.append((0, str(path)))
            elif e.get("scope") == "user":
                ranked.append((1, str(path)))
    if ranked:
        script = Path(sorted(ranked)[0][1])
    elif not problem:
        problem = f"{reg} lists no cds install shipping tools/audit-app.py at user scope or for $ATW_CONTROL_REPO"
if problem:
    print(json.dumps({"error": problem}))
    sys.exit(2)
done = subprocess.run([sys.executable, str(script), "--repo", repo, "--bundle", bundle], capture_output=True, text=True)
try:
    report = json.loads(done.stdout)
except ValueError:
    print(json.dumps({"error": (done.stdout + done.stderr).strip()[-2000:] or f"audit-app.py exited {done.returncode} and printed nothing"}))
    sys.exit(2)
findings = report.get("findings") or []
if len(findings) > int(cap):
    report["findings"], report["truncated"] = findings[: int(cap)], len(findings)
def cell(v):
    return "" if v is None else str(v)
canon = "\\n".join("\\t".join(cell(f.get(k)) for k in ("file", "line", "rule", "value", "ruling")) for f in report.get("findings") or [] if isinstance(f, dict))
h = 0x811C9DC5
for ch in f"{cell(report.get('scriptVersion'))}\\n{done.returncode}\\n{cell(report.get('truncated'))}\\n{canon}":
    h = ((h ^ ord(ch)) * 0x01000193) & 0xFFFFFFFF
report["digest"] = format(h, "08x")
print(json.dumps(report))
sys.exit(done.returncode)`

// The digest RUN_CDS_AUDIT_PY prints: FNV-1a (32-bit) over the script version, the exit status, the
// truncated count and each finding's file, line, rule, value and ruling, by code point. The verdict is
// computed from the relayed report only when this recomputes to the digest the script printed, so a
// relay that drops, adds or alters a finding is refused instead of acted on.
const cell = (v) => (v === null || v === undefined ? '' : String(v))
function auditDigest(report, exitCode) {
  const canon = list(report.findings)
    .filter((f) => f && typeof f === 'object')
    .map((f) => ['file', 'line', 'rule', 'value', 'ruling'].map((k) => cell(f[k])).join('\t'))
    .join('\n')
  let h = 0x811c9dc5
  for (const ch of `${cell(report.scriptVersion)}\n${exitCode}\n${cell(report.truncated)}\n${canon}`) {
    h = Math.imul(h ^ ch.codePointAt(0), 0x01000193) >>> 0
  }
  return h.toString(16).padStart(8, '0')
}

const findingText = (f) => `${f.file}:${f.line} ${f.rule} ${f.value}${f.reason ? ` (${f.reason})` : ''}`

/** Runs the audit script over the Task's changes and rules its judgment findings; returns { error } or { report, violations, gaps, allowed, scriptVersion }. */
async function auditCds(tree, bundle, label) {
  // relayrun.py runs the audit script; its exit status and report reach the workflow checked.
  let out = null
  try {
    const r = await relayKit.run(guardedAgent, {
      label,
      phase: currentPhase || 'CDS Audit',
      runner: RELAY.runner,
      argv: ['python3', '-c', RUN_CDS_AUDIT_PY, tree, bundle, String(a.cdsRoot || '').trim(), String(CDS_AUDIT_MAX_FINDINGS)],
      file: relayFileIn(RELAY.dir, label),
    })
    if (!r.ok) return { error: String(r.error).slice(0, 500) }
    out = { exitCode: r.exitCode, output: r.json || { error: `the cds audit printed no JSON (exit ${r.exitCode}); its output is in ${r.relayFile}` } }
  } catch (err) {
    return { error: String((err && err.message) || err).slice(0, 300) }
  }
  const report = (out && out.output) || {}
  if (!out || ![0, 1].includes(out.exitCode) || report.error || !Array.isArray(report.findings)) {
    return { error: String(report.error || `the cds audit did not run${out ? `: exit ${out.exitCode}` : ''}`).slice(0, 500), scriptVersion: report.scriptVersion || null }
  }
  if (String(report.digest || '') !== auditDigest(report, out.exitCode)) {
    return { error: 'the relayed cds audit report does not match the digest the audit script printed, so its findings are not the script\'s own', scriptVersion: report.scriptVersion || null }
  }
  if ((out.exitCode === 0) !== (report.findings.length === 0 && !report.truncated)) {
    return { error: `the cds audit exited ${out.exitCode} with ${report.truncated || report.findings.length} finding(s)`, scriptVersion: report.scriptVersion || null }
  }
  const scriptVersion = String(report.scriptVersion || 'unknown')
  const findings = report.findings.filter((f) => f && typeof f === 'object')
  const violations = findings.filter((f) => f.ruling !== 'judgment')
  const gaps = []
  const allowed = []
  const toJudge = findings.filter((f) => f.ruling === 'judgment')
  const sameFinding = (x, f) => x && x.file === f.file && Number(x.line) === Number(f.line) && x.value === f.value
  let unruled = toJudge
  if (unruled.length) {
    let judged = null
    try {
      judged = await guardedAgent(
        `Use the Skill tool to load cds:audit-against-system, then rule on findings a deterministic cds audit could not rule on. They come from the files this Task changed in the work tree at ${tree}, audited against the cds bundle at ${bundle} (its stylesheet set is the only design system the app may use).

Each finding is a class name the bundle's stylesheets do not name. Read the line in the file, the applicable bundle design artifacts and stylesheets, and the audit-against-system skill. Use supplied applicable mock/build-spec choices, graphics and stylesheets as design inputs. A static mock communicates design intent without specifying every detail; preserve its established intent and any explicit precision requirements, and use judgment with the Task requirements, configured cds and approved application standards for unspecified interactions, states and responsive behavior. When no mock is supplied and the Task delegates UI design, judge that design against configured cds and the approved application standards; absence of a pre-existing Page or Section preset is not itself a missing capability.

Consider supported configuration/composition and generated-stylesheet freshness when identifying the remedy. Missing output in this bundle does not by itself prove that the cds plugin needs an extension. Distinguish a configuration or artifact correction from a genuinely missing capability; do not invent off-system styling or treat unverified output as allowed. Rule each finding:
- violation: the class styles the UI outside cds (a utility class, a component class of the app's own, a value cds tokens cover) and the code must use the cds classes and tokens instead;
- allowed: the class carries no styling (a behaviour or test hook, a third-party library's own class the cds bundle does not style);
- cds-gap: required system-provided UI remains unavailable in the applicable bundle; name the unresolved configuration, generated artifact or actual missing capability and the evidence. A plugin extension is required only when the evidence establishes a capability the configured system cannot supply.

Findings, one per line (file:line rule value):
${unruled.map(findingText).join('\n')}

Return one ruling per finding, with its file, line and value exactly as given, the ruling, and a one-sentence reason. Change no file.`,
        { agentType: 'agent-teams-workforce:cds-finding-reviewer', label: `${label}:judgment`, phase: currentPhase || 'CDS Audit', schema: CDS_JUDGMENT_SCHEMA }
      )
    } catch (err) {
      return { error: `the judgment on ${unruled.length} cds finding(s) threw: ${String((err && err.message) || err).slice(0, 300)}`, scriptVersion }
    }
    const rulings = list(judged && judged.rulings)
    const still = []
    for (const f of unruled) {
      const r = rulings.find((x) => sameFinding(x, f))
      if (!r) {
        still.push(f)
        continue
      }
      const ruled = { ...f, ruling: r.ruling, reason: r.reason }
      if (ruled.ruling === 'allowed') allowed.push(ruled)
      else if (ruled.ruling === 'cds-gap') gaps.push(ruled)
      else violations.push(ruled)
    }
    unruled = still
  }
  if (unruled.length) {
    return { error: `cds:audit-against-system returned no ruling on ${unruled.length} finding(s): ${unruled.slice(0, 5).map(findingText).join('; ')}`, scriptVersion }
  }
  if (report.truncated) log(`cds audit: ${report.truncated} finding(s); the first ${CDS_AUDIT_MAX_FINDINGS} are ruled on`)
  return { report, violations, gaps, allowed, scriptVersion }
}

const packagesDir = String((a.designSystem && a.designSystem.packagesDir) || a.packagesDir || '').trim()
/** Selects the design source a bundle or cds Task builds with now; returns { selection } or { error }. */
async function selectDesign() {
  const art = bead.cdsArtifact && typeof bead.cdsArtifact === 'object' ? bead.cdsArtifact : {}
  const recorded = String(bead.cdsBundlePath || '').trim()
  if (!packagesDir && !recorded) return { selection: null }
  const argv = [
    '--packages-dir', packagesDir,
    '--design-source', designSource,
    '--kind', String(art.kind || '').trim(),
    '--slug', String(art.slug || '').trim(),
    '--recorded-bundle', recorded,
  ]
  let o = null
  try {
    o = await relayKit.depscore(guardedAgent, {
      label: 'cds-select',
      phase: currentPhase || 'Workspace',
      script: RELAY.depscore,
      repo: null,
      tail: ['cds-bundles', ...argv].map(relayKit.quote).join(' '),
      file: relayFileIn(RELAY.dir, 'cds-select'),
    })
  } catch (err) {
    return { error: String((err && err.message) || err).slice(0, 300) }
  }
  if (o.error || !o.selection || typeof o.selection !== 'object') {
    return { error: String(o.error || 'depscore.py cds-bundles returned no selection').slice(0, 500) }
  }
  return { selection: o.selection }
}

const LIVE_AUDIT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['audited', 'findings'],
  properties: {
    audited: { type: 'boolean' },
    error: { type: 'string' },
    files: { type: 'array', items: { type: 'string' } },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['file', 'line', 'rule', 'value', 'ruling', 'reason'],
        properties: {
          file: { type: 'string' },
          line: { type: 'integer' },
          rule: { type: 'string' },
          value: { type: 'string' },
          ruling: { type: 'string', enum: ['violation', 'allowed', 'cds-gap'] },
          reason: { type: 'string' },
        },
      },
    },
  },
}
/** Audits the Task's changes against the live CDS design system with cds:audit-against-system; returns { error } or { report, violations, gaps, allowed, scriptVersion }. */
async function auditCdsLive(tree, label) {
  let out = null
  try {
    out = await guardedAgent(
      `Use the Skill tool to load cds:audit-against-system, then audit the UI files this Task changed against the live Configurable Design System (cds) — the project's design system config and the stylesheets, tokens and components it defines. No mockup was supplied for this Task: its UI was designed with cds, so the live design system is the only standard it is held to.

The files: those the work tree at ${tree} changed against HEAD, untracked included (\`git -C ${shq(tree)} status --porcelain\`), restricted to markup, component, script and stylesheet files. Change no file.

Report every finding as { file (relative to the tree), line, rule (the compliance rule the skill names), value (the offending class, property or literal), ruling, reason (one sentence) }, ruling each:
- violation: the code styles the UI outside cds (a raw color or length, an inline style, a stylesheet or token of its own, a class cds does not define that carries styling) and must use the cds classes and tokens instead;
- allowed: it carries no styling (a behaviour or test hook, a third-party library's own class);
- cds-gap: the UI needs something the configured design system does not supply; name the missing configuration or capability and the evidence.

Return \`audited\` true with the files you audited and the findings (an empty list when there are none), or \`audited\` false with \`error\` naming what stopped the audit.`,
      { label, phase: currentPhase || 'CDS Audit', schema: LIVE_AUDIT_SCHEMA }
    )
  } catch (err) {
    return { error: String((err && err.message) || err).slice(0, 300), scriptVersion: 'audit-against-system' }
  }
  if (!out || out.audited !== true || !Array.isArray(out.findings)) {
    return { error: String((out && out.error) || 'cds:audit-against-system returned no audit').slice(0, 500), scriptVersion: 'audit-against-system' }
  }
  const findings = out.findings.filter((f) => f && typeof f === 'object')
  return {
    report: { findings, files: list(out.files) },
    violations: findings.filter((f) => f.ruling === 'violation'),
    gaps: findings.filter((f) => f.ruling === 'cds-gap'),
    allowed: findings.filter((f) => f.ruling === 'allowed'),
    scriptVersion: 'audit-against-system',
  }
}

let result
try {
  result = await (async () => {
    if (!String(bead.repoPath || '').trim()) {
      return {
        ...handback(false, 'input', `${bead.id} carries no repoPath, so its build contract is incomplete. The repository is ruled during elaboration: re-elaborate the Task's Story, or record the repository on the Task as its repoPath.`),
        incompleteContract: ['repoPath'],
        requiredHumanActions: [`re-elaborate the Story of ${bead.id}, or record the ruled repository on it as its repoPath`],
      }
    }
    if (!String(story.id || '').trim()) {
      return {
        ...handback(false, 'input', `${bead.id} names no Story. A Task is built on its Story's branch and deploys with its Story, so it needs one: parent it to the Story of its repository.`),
        incompleteContract: ['story'],
        requiredHumanActions: [`parent ${bead.id} to the Story of its repository`],
      }
    }
    // ── Relay: every deterministic step below runs through relayrun.py and reaches this script checked ──
    const pluginRoot = String(a.pluginRoot || '').trim().replace(/\/+$/, '')
    const givenRelay = a.relay && typeof a.relay === 'object' ? a.relay : {}
    const setup = await relaySetup('task-to-deploy', { runner: givenRelay.runner || (pluginRoot ? `${pluginRoot}${RUNNER_TAIL}` : ''), dir: givenRelay.dir }, 'Workspace')
    if (setup.error) return handback(false, setup.noResult ? DISPATCH_FAILED_STAGE : 'relay-setup', `relay-setup: ${setup.error}`)
    RELAY = { ...setup, depscore: `${setup.runner.slice(0, -'relayrun.py'.length)}depscore.py` }
    log(`Relay: ${RELAY.runner}; relay files in ${RELAY.dir}`)

    // ── Design source: the bundles supplied now decide what a bundle or cds Task builds from ──
    let buildSpecs = list(bead.cdsBuildSpecs).map((x) => String(x).trim()).filter(Boolean)
    usedBundle = designSource === 'bundle' ? String(bead.cdsBundlePath || '').trim() || null : null
    if (designSource === 'bundle' || designSource === 'cds') {
      const picked = await selectDesign()
      if (picked.error) {
        return handback(false, 'cds-select', `cds-select: the design source of ${bead.id} could not be selected: ${picked.error}`)
      }
      if (picked.selection) {
        const sel = picked.selection
        if (sel.blocked) {
          cdsVerdict = { verdict: 'blocked', findings: 0, scriptVersion: null }
          const upstream = [{ what: `cds bundle: ${sel.blocked}` }]
          return {
            ...handback(false, 'blocked-upstream', `blocked-upstream: ${bead.id} builds from a supplied cds bundle and ${sel.blocked}`, { selection: sel, upstreamMissing: upstream }),
            upstreamMissing: upstream,
          }
        }
        if (sel.designSource === 'bundle' && sel.bundle) {
          const sameBundle = usedBundle && sel.bundle.replace(/\/+$/, '') === usedBundle.replace(/\/+$/, '')
          if (!sameBundle) buildSpecs = [sel.buildSpec]
          if (designSource !== 'bundle' || !sameBundle) log(`Design source: ${designSource} -> bundle ${sel.bundle}`)
          designSource = 'bundle'
          usedBundle = sel.bundle
        }
      }
      if (designSource === 'bundle' && !usedBundle) {
        cdsVerdict = { verdict: 'blocked', findings: 0, scriptVersion: null }
        const upstream = [{ what: `cds bundle: ${bead.id} records design source bundle but names neither a bundle nor a packages directory holding one` }]
        return { ...handback(false, 'blocked-upstream', `blocked-upstream: ${upstream[0].what}`, { upstreamMissing: upstream }), upstreamMissing: upstream }
      }
    }

    enterPhase('Workspace')
    const workspace = await settleWorkflow('agent-teams-workforce:workspace', {
      repoPath: bead.repoPath,
      beadId: story.id,
      branchPrefix: 'story',
      purpose: story.title || `Story ${story.id}`,
      worktreeRoot: a.worktreeRoot,
      stashUncommitted: true,
      stashLabel: bead.id,
      relay: childRelay('workspace'),
    })
    if (!workspace || workspace.ok !== true || !workspace.repoPath) {
      const why = (workspace && Array.isArray(workspace.blocked) && workspace.blocked[0]) || 'the workspace step returned nothing'
      return handback(false, stageOf('workspace', workspace), `no worktree was established: ${why}`, { workspace: workspace || null })
    }
    workspaceOut = workspace
    const workRepoPath = workspace.repoPath
    if (workspace.ledger) runLedger.push(workspace.ledger)

    const declaredSurfaces = Array.isArray(bead.surfaces) ? bead.surfaces : null
    const structuralSurfaces = [
      bead.apiSpec ? 'api-contract' : null,
      Array.isArray(bead.eventContracts) && bead.eventContracts.length ? 'event-chain' : null,
    ].filter(Boolean)
    const contractSurfaces = declaredSurfaces
      ? [...new Set([...declaredSurfaces, ...structuralSurfaces])]
      : structuralSurfaces.length
        ? structuralSurfaces
        : null
    const contract = {
      spec,
      bead: { id: bead.id, title: bead.title || null, description: bead.description || null, repoPath: workRepoPath },
      repoPath: workRepoPath,
      acceptanceCriteria: Array.isArray(bead.acceptanceCriteria) ? bead.acceptanceCriteria : [],
      decisionIds: [
        ...new Set(
          [...(Array.isArray(spec && spec.decisionIds) ? spec.decisionIds : []), ...(Array.isArray(bead.decisionIds) ? bead.decisionIds : [])]
            .map((x) => String(x || '').trim())
            .filter(Boolean)
        ),
      ],
      surfaces: contractSurfaces,
      testStrategy: bead.testStrategy && typeof bead.testStrategy === 'object' ? bead.testStrategy : null,
      cdsDesignSource: designSource,
      cdsBundlePath: designSource === 'bundle' ? usedBundle : null,
      cdsBuildSpecs: designSource === 'bundle' ? buildSpecs : [],
    }

    let intent = null
    if (isInfra) {
      enterPhase('Infra Intent')
      intent = await settleWorkflow('agent-teams-workforce:infra-intent', {
        change: { id: bead.id, title: bead.title, description: bead.description, repoPath: workRepoPath },
      })
      if (!intent || !intent.provisioningIntent) {
        return handback(false, stageOf('infra-intent', intent), `infra-intent: ${(intent && intent.reason) || 'no provisioning intent was produced'}`, { intent: intent || null })
      }
      const stacks = Array.isArray(intent.affectedStacks) ? intent.affectedStacks : []
      contract.affectedStacks = stacks
      contract.provisioningIntent = intent.provisioningIntent
      contract.acceptanceCriteria = [
        ...contract.acceptanceCriteria.filter(Boolean),
        {
          given: `the provisioning intent for ${bead.title || 'this infrastructure change'} on stacks ${stacks.join(', ') || '(affected stacks)'}`,
          when: 'cdk synth runs against the changed stacks',
          then: 'the synthesized template asserts the intended resources and their properties, the cross-stack references the stacks write and read, and the IAM permissions the intent names',
        },
      ]
    }
    const implementer = a.implementer || (isInfra ? 'cdk-stack-author' : undefined)

    // ── Baseline: the suite command the repository declares, resolved once and reused ──
    enterPhase('Baseline')
    const baseline = await settleWorkflow('agent-teams-workforce:suite-run', { repoPath: workRepoPath, label: 'baseline', relay: childRelay('suite-baseline') })
    if (baseline && baseline.resolveError) {
      return {
        ...handback(false, 'baseline', `baseline: ${workRepoPath} declares no test command (${baseline.resolveError}). A Task is committed only when the repository's whole suite passes, so the repository must say how its suite runs.`, { baseline }),
        requiredHumanActions: [`declare the command that runs the whole test suite in the AGENTS.md or CLAUDE.md of the repository at ${bead.repoPath}, or as the \`test\` task in its Taskfile`],
      }
    }
    if (!validRun(baseline) || !String(baseline.command || '').trim()) {
      return handback(false, stageOf('baseline', baseline), `baseline: the suite runner returned no exit code: ${(baseline && baseline.reason) || 'no result'}`, { baseline: baseline || null })
    }
    const suiteCommand = String(baseline.command).trim()
    contract.suiteCommand = suiteCommand
    // Consumed by tdd-green selection and implementation briefs: explicit runtime repair authority.
    contract.baselineRepairScope = 'affected-repository'
    const baselineIds = failingIds(baseline)
    const runSuite = async (label) => {
      const r = await settleWorkflow('agent-teams-workforce:suite-run', { repoPath: workRepoPath, command: suiteCommand, label, relay: childRelay(`suite-${label}`) })
      return r || null
    }
    log(`Baseline: \`${suiteCommand}\` exited ${baseline.exitCode}; ${baselineIds.size} failing before any change`)

    // ── Red: loops until a new test fails, with no new collection error and no regression ──
    const redFiles = []
    const addRedFiles = (r) => {
      for (const f of list(r && r.testFiles).map(String)) if (!redFiles.includes(f)) redFiles.push(f)
    }
    const judgeRed = (run) => {
      const inRedFile = (e) => redFiles.some((f) => sameFile(e.file, f))
      const fresh = [...failures(run).entries()].filter(([id]) => !baselineIds.has(id)).map(([, e]) => e)
      const collection = fresh.filter((e) => e.kind === 'load').map(describe)
      const redFails = fresh.filter((e) => e.kind === 'test' && inRedFile(e)).map(describe)
      const regressions = fresh.filter((e) => e.kind === 'test' && !inRedFile(e)).map(describe)
      const reasons = [
        redFails.length ? '' : 'no test in a file Red wrote or edited fails',
        collection.length ? `test files that no longer load: ${collection.join('; ')}` : '',
        regressions.length ? `tests outside Red's files that did not fail at baseline now fail: ${regressions.join('; ')}` : '',
      ].filter(Boolean)
      return { ok: run.exitCode !== 0 && !reasons.length, reasons, redFails, collection, regressions }
    }

    let red = null
    let redRun = null
    let redFeedback = ''
    let previousRedKey = null
    for (let round = 1; ; round++) {
      enterPhase('Red')
      red = await settleWorkflow('agent-teams-workforce:tdd-red', {
        contract,
        feedback: redFeedback,
        ...(redFiles.length ? { red: { testFiles: [...redFiles] } } : {}),
      })
      if (red && red.ledger) runLedger.push(red.ledger)
      if (!red || red.dispatchFailed) {
        return handback(false, stageOf('red', red), `red: ${(red && red.reason) || 'the Red phase returned nothing'}`, { red })
      }
      addRedFiles(red)
      redRun = await runSuite(`red-${round}`)
      if (!validRun(redRun)) {
        return handback(false, stageOf('red', redRun), `red: the suite runner returned no exit code: ${(redRun && redRun.reason) || 'no result'}`, { red, run: redRun })
      }
      const verdict = judgeRed(redRun)
      if (verdict.ok) {
        log(`Red: round ${round} satisfied — ${verdict.redFails.length} new failing test(s) in Red's files`)
        break
      }
      log(`Red: round ${round} not satisfied — ${verdict.reasons.join('; ')}`)
      if (round >= MAX_RED_ROUNDS) {
        return {
          ...handback(
            false,
            'red-unsatisfied',
            `red-unsatisfied: after ${round} Red round(s) the suite does not show the Task's new tests failing cleanly: ${verdict.reasons.join('; ')}`,
            { red, run: redRun, verdict, baseline }
          ),
          evidence: runText(redRun).slice(0, TAIL_CHARS),
        }
      }
      // A round whose suite fails exactly as the round before gives Red the same input again.
      const redKey = JSON.stringify([redRun.exitCode, ...[...failingIds(redRun)].sort(), ...verdict.reasons])
      if (redKey === previousRedKey) {
        return {
          ...handback(false, 'no-progress', `no-progress: Red round ${round} left the suite exactly as the round before: ${verdict.reasons.join('; ')}`, { red, run: redRun, verdict }),
          evidence: runText(redRun).slice(0, TAIL_CHARS),
        }
      }
      previousRedKey = redKey
      redFeedback = `The suite does not show Red yet: ${verdict.reasons.join('; ')}.\n${runText(redRun)}`
      runLedger.push({ phase: 'retry:red', round: round + 1, whatChanged: `Red round ${round + 1} is given round ${round}'s suite result: ${verdict.reasons.join('; ')}` })
    }

    // ── Green: loops until the whole suite exits 0. The CDS Audit sends its violations back through
    // this same loop, with tag 'cds-green' and the findings as the first round's feedback. ──
    const baselineNote = baseline.exitCode !== 0
      ? `\nBASELINE REPAIR IS ASSIGNED: fix ALL pre-existing suite failures in ${workRepoPath}, including failures outside the Task's feature. ${baselineIds.size ? [...failures(baseline).values()].map(describe).join('; ') : 'No individual failing test IDs were parsed; diagnose the baseline output.'} Green still requires the whole suite to exit 0.\nBaseline evidence:\n${runText(baseline)}`
      : ''
    let green = null
    let finalRun = null
    const acceptedTestDecisions = new Map()
    /** Runs Green rounds until the suite exits 0; returns { run } when green, or { stop } (a handback) when the loop ends without it. */
    const greenLoop = async (firstFeedback, tag, what) => {
      let greenFeedback = firstFeedback
      let previousKey = null
      for (let round = 1; ; round++) {
        enterPhase('Green')
        const testPrint = await fingerprint(workRepoPath, [...redFiles], `${tag}-${round}:tests-before`)
        if (testPrint.error) return { stop: handback(false, 'green', `${what}: Red's test files could not be fingerprinted before Green round ${round}: ${testPrint.error}`, {}) }
        const g = await settleWorkflow('agent-teams-workforce:tdd-green', {
          contract,
          red: { ...red, testFiles: [...redFiles], evidence: runText(redRun) },
          implementer,
          implementers: implementersOf(green),
          feedback: `${greenFeedback}${acceptedTestDecisions.size ? `\n\nAccepted test-author rulings (retain these unless new evidence warrants reopening):\n${JSON.stringify([...acceptedTestDecisions.values()])}` : ''}`,
        })
        if (g && g.ledger) runLedger.push(g.ledger)
        if (!g || g.dispatchFailed) {
          return { stop: handback(false, stageOf('green', g), `${what}: ${(g && g.reason) || 'the Green phase returned nothing'}`, { green: g }) }
        }
        green = g
        const testsAfter = await fingerprint(workRepoPath, Object.keys(testPrint.files), `${tag}-${round}:tests-after`)
        if (testsAfter.error) return { stop: handback(false, 'green', `${what}: Red's test files could not be fingerprinted after Green round ${round}: ${testsAfter.error}`, { green: g }) }
        const touchedTests = Object.keys(testPrint.files).filter((f) => testPrint.files[f] !== testsAfter.files[f])
        if (touchedTests.length) {
          return {
            stop: handback(
              false,
              'green-modified-tests',
              `green-modified-tests: ${what} round ${round} changed test files Red wrote, which Green leaves to Red (a test Green believes is wrong goes in testIssues): ${touchedTests.join(', ')}`,
              { green: g, touchedTests }
            ),
          }
        }
        let run = await runSuite(`${tag}-${round}`)
        if (!validRun(run)) {
          return { stop: handback(false, stageOf('green', run), `${what}: the suite runner returned no exit code: ${(run && run.reason) || 'no result'}`, { green: g, run }) }
        }
        if (run.exitCode === 0) return { run }

        const upstream = list(g.upstreamMissing)
        if (upstream.length) {
          return {
            stop: {
              ...handback(
                false,
                'blocked-upstream',
                `blocked-upstream: the suite cannot pass until something outside this Task exists: ${upstream.map((u) => u.what).join('; ')}`,
                { green: g, run, upstreamMissing: upstream }
              ),
              upstreamMissing: upstream,
              evidence: runText(run).slice(0, TAIL_CHARS),
            },
          }
        }

        let redUpdated = false
        const issues = list(g.testIssues)
        if (issues.length) {
          enterPhase('Red')
          const updated = await settleWorkflow('agent-teams-workforce:tdd-red', {
            contract,
            testIssues: issues,
            red: { testFiles: [...redFiles] },
            feedback: runText(run),
          })
          if (updated && updated.ledger) runLedger.push(updated.ledger)
          if (!updated || updated.dispatchFailed) {
            return { stop: handback(false, stageOf('red', updated), `red (update): ${(updated && updated.reason) || 'the Red update returned nothing'}`, { green: g, red: updated, issues }) }
          }
          const rulingCheck = checkTestDecisions(issues, updated.decisions)
          if (rulingCheck.problems.length) {
            return { stop: handback(false, 'red-decisions-incomplete', `red (update): ${rulingCheck.problems.join('; ')}; return one justified disposition for each requested test ID before Green continues`, { green: g, red: updated, issues, acceptedTestDecisions: [...acceptedTestDecisions.values()] }) }
          }
          for (const decision of rulingCheck.decisions) acceptedTestDecisions.set(decision.testId, decision)
          runLedger.push({ phase: 'red:test-rulings', round: `${tag}-${round}`, decisions: rulingCheck.decisions })
          addRedFiles(updated)
          redUpdated = true
          run = await runSuite(`${tag === 'green' ? '' : `${tag}-`}red-update-${round}`)
          if (!validRun(run)) {
            return { stop: handback(false, stageOf('red', run), `red (update): the suite runner returned no exit code: ${(run && run.reason) || 'no result'}`, { red: updated, run }) }
          }
          if (run.exitCode === 0) return { run }
        }

        const key = JSON.stringify([run.exitCode, ...[...failingIds(run)].sort()])
        // Whether Green changed any file is read from the work tree (its digest before and after Green), not from Green's report.
        const changedNothing = !!testPrint.treeDigest && testPrint.treeDigest === testsAfter.treeDigest && !redUpdated
        if (changedNothing && key === previousKey) {
          return {
            stop: {
              ...handback(false, 'no-progress', `no-progress: ${what} round ${round} changed no file and the suite fails exactly as it did the round before`, { green: g, run }),
              evidence: runText(run).slice(0, TAIL_CHARS),
            },
          }
        }
        previousKey = key
        if (round >= MAX_GREEN_ROUNDS) {
          return { stop: handback(false, 'green', `${what}: the suite is not green after ${round} Green round(s): ${run.summary || `exit ${run.exitCode}`}`, { green: g, run }) }
        }
        greenFeedback = `The suite is not green yet.${redUpdated ? ' The test author ruled on the named tests; the exact accepted decisions are attached below.' : ''}\n${runText(run)}${baselineNote}`
        runLedger.push({
          phase: 'retry:green',
          round: `${tag}-${round + 1}`,
          whatChanged: `Green round ${round + 1} is given round ${round}'s suite result${list(g.changedFiles).length ? ` after round ${round} changed ${list(g.changedFiles).join(', ')}` : ''}${redUpdated ? ', and the tests the test author updated' : ''}`,
        })
      }
    }
    const built = await greenLoop(`${runText(redRun)}${baselineNote}`, 'green', 'green')
    if (built.stop) return built.stop
    finalRun = built.run

    // ── Refactor: ends green, refactored or restored to its snapshot ──
    enterPhase('Refactor')
    const refactor = await settleWorkflow('agent-teams-workforce:tdd-refactor', { contract, green, relay: childRelay('refactor') })
    if (refactor && refactor.ledger) runLedger.push(refactor.ledger)
    if (!refactor || refactor.dispatchFailed) {
      return handback(false, stageOf('refactor', refactor), `refactor: ${(refactor && refactor.reason) || 'the Refactor phase returned nothing'}`, { refactor })
    }
    let refactorRun = await runSuite('refactor')
    if (!validRun(refactorRun)) {
      return handback(false, stageOf('refactor', refactorRun), `refactor: the suite runner returned no exit code: ${(refactorRun && refactorRun.reason) || 'no result'}`, { refactor, run: refactorRun })
    }
    let restored = null
    if (refactorRun.exitCode !== 0) {
      const snapshot = String(refactor.snapshotTree || '').trim()
      if (!snapshot) {
        return handback(false, 'refactor', `refactor: the suite is red after the refactor and the refactor recorded no snapshot to restore: ${refactorRun.summary || `exit ${refactorRun.exitCode}`}`, { refactor, run: refactorRun })
      }
      restored = await settleWorkflow('agent-teams-workforce:tdd-refactor', { contract, restoreTo: snapshot, relay: childRelay('refactor-restore') })
      if (!restored || restored.dispatchFailed || restored.restored !== true) {
        return handback(false, stageOf('refactor', restored), `refactor: the suite is red after the refactor and the tree could not be restored to ${snapshot}`, { refactor, restored, run: refactorRun })
      }
      refactorRun = await runSuite('refactor-restored')
      if (!validRun(refactorRun) || refactorRun.exitCode !== 0) {
        return handback(false, stageOf('refactor', refactorRun), `refactor: the suite is red after restoring the pre-refactor snapshot ${snapshot}: ${(refactorRun && refactorRun.summary) || 'no result'}`, { refactor, restored, run: refactorRun })
      }
      log(`Refactor: the suite went red, so the tree was restored to ${snapshot}`)
    }

    // ── CDS Audit: a web-ui Task's changes against its supplied cds bundle (bundle) or the live CDS design
    // system (cds); a change with no design impact (none) is not audited. Violations go back through the Green loop once ──
    if (isUiTask && designSource !== 'none') {
      enterPhase('CDS Audit')
      const bundle = designSource === 'bundle' ? contract.cdsBundlePath : null
      const runAudit = (label) => (bundle ? auditCds(workRepoPath, bundle, label) : auditCdsLive(workRepoPath, label))
      const standard = bundle
        ? `The cds bundle at ${bundle} (its styles/ stylesheet set) is the only source of visual design: replace each finding with the classes and custom properties the bundle ships`
        : 'No mockup was supplied: the live CDS design system (the project\'s design system config and the stylesheets, tokens and components it defines) is the only source of visual design: replace each finding with the cds classes and custom properties'
      const verdictOf = (audit) => ({
        verdict: audit.violations.length ? 'fail' : audit.gaps.length ? 'blocked' : 'pass',
        findings: audit.violations.length + audit.gaps.length,
        scriptVersion: audit.scriptVersion,
      })
      const auditFailed = (audit, when) => {
        cdsVerdict = { verdict: 'error', findings: 0, scriptVersion: audit.scriptVersion || null }
        return handback(false, 'cds-audit', `cds-audit: the cds audit ${when} could not rule: ${audit.error}`, { cdsAudit: audit })
      }
      let audit = await runAudit('cds-audit-1')
      if (audit.error) return auditFailed(audit, 'after Refactor')
      log(`CDS Audit: ${audit.violations.length} violation(s), ${audit.gaps.length} cds gap(s), ${audit.allowed.length} allowed`)
      if (audit.violations.length) {
        const brief = `The cds audit found UI code that styles outside the cds design system. ${standard}, and add no stylesheet, inline style, color or length of your own. Use supplied applicable mock/build-spec choices, graphics and stylesheets as design inputs that need not specify every detail. Preserve their established intent and any explicit precision requirements; use judgment with the Task requirements and configured cds for unspecified interactions, states and responsive behavior; when this Task instead owns UI design without a mock, use configured cds and the approved application standards. Resolve findings through supported configuration/composition or generated-artifact correction where applicable. If an input or capability outside this Task remains necessary, name it with evidence in upstreamMissing; do not assume a cds plugin extension is required merely because the current bundle lacks the output. The whole suite has to stay green.
Findings (file:line rule value):
${audit.violations.map(findingText).join('\n')}${baselineNote}`
        runLedger.push({ phase: 'retry:green', round: 'cds-audit', whatChanged: `Green is given the ${audit.violations.length} cds audit violation(s) as its brief` })
        const fixed = await greenLoop(brief, 'cds-green', 'green (cds audit)')
        if (fixed.stop) {
          cdsVerdict = { verdict: fixed.stop.stage === 'blocked-upstream' ? 'blocked' : 'fail', findings: audit.violations.length, scriptVersion: audit.scriptVersion }
          return { ...fixed.stop, cdsAudit: cdsVerdict }
        }
        const upstream = list(green && green.upstreamMissing)
        if (upstream.length) {
          cdsVerdict = { verdict: 'blocked', findings: audit.violations.length, scriptVersion: audit.scriptVersion }
          return {
            ...handback(false, 'blocked-upstream', `blocked-upstream: the cds audit violations cannot be fixed until something outside this Task exists: ${upstream.map((u) => u.what).join('; ')}`, { green, cdsAudit: audit, upstreamMissing: upstream }),
            upstreamMissing: upstream,
            evidence: audit.violations.map(findingText).join('\n').slice(0, TAIL_CHARS),
          }
        }
        enterPhase('CDS Audit')
        audit = await runAudit('cds-audit-2')
        if (audit.error) return auditFailed(audit, 'after the Green round')
        log(`CDS Audit (after Green): ${audit.violations.length} violation(s), ${audit.gaps.length} cds gap(s), ${audit.allowed.length} allowed`)
      }
      cdsVerdict = verdictOf(audit)
      if (audit.violations.length) {
        return {
          ...handback(false, 'cds-audit', `cds-audit: ${audit.violations.length} cds violation(s) remain after one Green round: ${audit.violations.slice(0, 5).map(findingText).join('; ')}`, { cdsAudit: audit }),
          evidence: audit.violations.map(findingText).join('\n').slice(0, TAIL_CHARS),
        }
      }
      if (audit.gaps.length) {
        const upstream = audit.gaps.map((f) => ({ what: `cds: ${f.reason || f.value} (${f.file}:${f.line})` }))
        return {
          ...handback(false, 'blocked-upstream', `blocked-upstream: required cds configuration, design artifacts or capabilities remain unresolved: ${audit.gaps.map(findingText).join('; ')}`, { cdsAudit: audit, upstreamMissing: upstream }),
          upstreamMissing: upstream,
          evidence: audit.gaps.map(findingText).join('\n').slice(0, TAIL_CHARS),
        }
      }
    }

    enterPhase('Documentation')
    const docs = await settleWorkflow('agent-teams-workforce:documentation', { contract, green })
    if (docs && docs.ledger) runLedger.push(docs.ledger)

    enterPhase('Commit')
    finalRun = await runSuite('final')
    if (!validRun(finalRun) || finalRun.exitCode !== 0) {
      return handback(false, stageOf('commit', finalRun), `commit: the final suite run did not exit 0 (${(finalRun && (finalRun.summary || `exit ${finalRun.exitCode}`)) || 'no result'}), so nothing was committed`, { run: finalRun })
    }
    const committed = await settleWorkflow('agent-teams-workforce:settle', {
      repoPath: workRepoPath,
      commitOnly: true,
      branch: workspace.branch || null,
      defaultBranch: workspace.defaultBranch || null,
      message: `${bead.id} ${bead.title || ''}`.trim(),
      relay: childRelay('settle'),
    })
    if (!committed || committed.status !== 'reported' || (Array.isArray(committed.blocked) && committed.blocked.length)) {
      const why =
        (committed && (committed.error || committed.reason || (Array.isArray(committed.blocked) && committed.blocked.join('; ')))) ||
        'the commit step returned nothing'
      return handback(false, !committed || committed.status === 'error' ? DISPATCH_FAILED_STAGE : 'commit', `commit: ${why}`, { commit: committed || null })
    }

    return {
      ...handback(
        true,
        'committed',
        `${bead.id} built on ${workspace.branch}: \`${suiteCommand}\` exits 0${finalRun.summary ? ` (${finalRun.summary})` : ''} and the work is committed to the branch of Story ${story.id} (${committed.commit || 'no new commit'}).`,
        {
          contract,
          stashed: workspace.stashed || null,
          results: { intent, baseline, red, green, refactor, restored, documentation: docs, final: finalRun, commit: committed },
        }
      ),
      commit: committed.commit || null,
      suite: { command: suiteCommand, summary: finalRun.summary || '' },
    }
  })()
} catch (err) {
  const message = String((err && err.message) || err)
  const environmental = /overload|rate[ _-]?limit|too many requests|quota|capacity|session limit|usage limit|spend limit|credit balance|out of credits|timed? ?out|network/i.test(message)
  const where = currentPhase || 'unknown'
  const slug = String(where).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'unknown'
  log(`RUN ABORTED in ${where}: ${message.slice(0, 300)}`)
  result = handback(false, environmental ? DISPATCH_FAILED_STAGE : slug, `${where}: the run threw — ${message.slice(0, 300)}`, {
    reason: message.slice(0, 400),
    dispatchFailed: environmental,
  })
} finally {
  enterPhase('Run Ledger')
  const detailPath = persistRun(result && result.ok ? 'ok' : `failed:${(result && result.stage) || 'unknown'}`)
  if (result) result.detailPath = detailPath || null
}
return dispatchOutcome(result)

async function guardedAgent(prompt, options) {
  if (dispatchInterruption) return null
  try { return await fableAgent(prompt, options) } catch (err) {
    const plan = dispatchRetry(err, (options && options.label) || 'agent', 1, 0, dispatchPolicy(options), false)
    if (plan.interruption) dispatchInterruption = plan.interruption
    throw err
  }
}
