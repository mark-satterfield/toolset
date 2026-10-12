export const meta = {
  name: 'prd-reconciliation',
  description:
    'Leaf mini — per-repository detailing of an approved architecture delta. One read-only session compares each delta item placed in one repository (one element the delta shows) with the code on that repository\'s main, gives it one status, each citing file:line (an item another Epic\'s open bead plans also names that bead), gives each ui item its design source (the newest single-artifact cds bundle the owner supplied for a kind and slug is the supplied one) and the artifact it builds, so a mockup supplied later is found when the Task is built — and reports upstream dependency changes; the statuses, design sources and every field are those the artifact-handoff skill\'s recon.schema.json defines. depscore.py recon-facts normalizes the file rather than refusing it: a missing item is taken as new work, a duplicate keeps its first entry, an unknown status or design source takes a default, and each is a warning. The session saves the detailing in the file that schema names and returns no item content; depscore.py recon-facts checks the saved file on disk and returns only the facts the callers branch on (the ids that make work, the ids that do not, each ui work item\'s design source with the bundle and build spec of a bundle item, whether dependencies are current), and the callers hand the file path to the sessions that read it. A saved result is replayed through the same check instead of dispatching the session; a saved file that cannot be replayed is detailed again.',
  phases: [{ title: 'Detailing', detail: 'one read-only session compares each delta item placed in the repository with the code on its main, and checks upstream dependencies' }],
}
// ===== SHARED BLOCK fable — BEGIN (canonical: scripts/shared-blocks/fable.js; filled from skills/pipeline-contracts/schemas/driver-surface.schema.json; edit there, then: node scripts/shared-blocks.mjs --write) =====
const ownedCoreContracts = "---\nname: subagent-contract\ndescription: Bounded specialist work in direct sessions, with file outputs and independent validation.\nuser-invocable: false\n---\n\n# Direct specialist session\n\nPerform the role in your definition. The brief gives a bead, input paths, output path and outcome;\nit supplies no procedures or schema. Load the skills in your frontmatter and read the applicable\ncontract before writing. The artifact-handoff skill is the shared producer/reviewer authority.\nWrite the result file; Python handles validation, acceptance, fingerprints and pipeline state.\nDo not invoke a Workflow, another agent, a command runner or StructuredOutput. Do not create\nreceipts or revision bindings. When the brief carries ARTIFACT CONTRACT DATA, write the progress\nfile it names and record a checkpoint or the submission only by running the artifactcontract.py\ncommands it gives; never write a checkpoint sidecar any other way. The progress file's fields are\ndefined by the artifact-handoff skill (schemas/checkpoint.schema.json, $defs/Progress). If resumed,\ninspect and continue the existing result and input files; retain completed valid work.\n\nOnly assigned files are writable. Reviewers may write their result, never the reviewed source.\nNever write arc42 section 2, expose secrets or touch apps/marketing repositories. Never run keeper\nor supervisor. Agents do not write pipeline beads; Python owns those writes. If reading beads is\nneeded, use the central atw-bd wrapper from beads-contract. No agent creates a bug or loose Task.\nRead repository AGENTS.md before an authorized repository edit; input-only reads do not require\nloading every repository's instruction tree.\n\nMissing inputs are named dependencies, not permission to invent facts. Distinguish observed\nfacts, assumptions and unresolved questions in the artifact's supported fields. Do not mark your\nown work approved. In elaboration, repository code is evidence of current design detail only;\nthe matrix is the sole built-state record, and Python derives implementation work from it.\n\n## Resource use and incremental review\n\n- Use tokens conscientiously without compromising required correctness, completeness, safety or evidence. Before a material optional expansion, identify its unresolved need and expected benefit in existing progress. Routine tools need no justification. Do not add a report, review pass, token quota or human approval gate for this rule; omit optional work with no concrete benefit.\n- Makers and reviewers use the same applicable requirements, constraints and completion criteria. Review determines actual correctness, including passing sound work; finding more failures is not success. Do not invent requirements or turn stylistic preferences into blocking defects. Preserve necessary safety and regression checks.\n- Use the caller's finding format to identify the affected location, requirement/dependency at risk, observed evidence and actionable correction with a verifiable pass condition. Distinguish defects, missing evidence and proposed new requirements. Never claim unperformed checks passed.\n- Revise original artifacts incrementally. Retain valid work and applicable evidence. Rereview changed scope and affected dependencies; reopen accepted work only when new evidence or demonstrated impact invalidates its earlier evidence, and state why. Preserve required independent review.\n\n## Technical gaps are decided, not escalated\n\nWhere the approved or effective architecture, a requirement or an owner answer is silent, unclear or self-contradictory on a technical matter, decide it by best practice, with AWS Well-Architected guidance and AWS documentation as the evidence (see AWS evidence authority below). Record the decision, the gap it closes and its cited evidence in your result, and continue. A technical matter is any question of how the system works: services, patterns, interfaces, data, values and limits, security and privacy controls, cost and operations. A recorded decision is a claim reviewers check like any other; it is not an open item.\n\nOwner-only facts (credentials, money and destructive actions outside AWS dev), irreconcilable business requirements and section 2 conflicts go through the caller's owner channel. Technical choices remain with the specialists. Never put a technical question to the owner or any person, and never hold work waiting for a technical answer.\n\n## The approved architecture is authoritative\n\nThe approved (effective) architecture and the owner's answers are authoritative. Older documents, repository READMEs and existing code are evidence of the current state: they show what exists and what still has to change, never that the approved architecture or an owner answer is wrong. Where they disagree with the approved architecture, the approved architecture holds and the difference is work to plan, not a conflict to raise. The approved architecture changes only through a reviewed target backed by requirements and evidence, or a reviewed correction from what a Story built.\n\n## AWS evidence authority\n\nBefore any AWS claim, design choice or question, check the AWS MCP Server documentation tools (`search_documentation`, `read_documentation`, `retrieve_skill`) and the relevant AWS plugin skills (`aws-core:*`, for example `aws-core:aws-cdk`, `aws-core:aws-serverless`, `aws-core:aws-iam`, `aws-core:aws-networking`, `aws-core:aws-well-architected-review`), including the applicable Well-Architected principles. A question AWS documentation can answer is answered from it and never reaches the owner. Retain source references and the concrete tradeoffs. Existing generated architecture and model recollection do not establish correctness. Makers and reviewers use this same evidence criterion.\n\nApply guidance to stated requirements, deployment, usage and cost constraints rather than hypothetical scale. Where AWS guidance conflicts with a business requirement or a section 2 constraint, the requirement or constraint holds: record the conflict and the design that honours it, and do not silently substitute a preferred AWS pattern. Missing required MCP/skill access is a named blocker or uncertainty, never a passed check. Coordinators may research and route AWS questions, but cannot author or approve designs.\n"
const ownedArtifactContract = "---\nname: artifact-handoff\ndescription: Shared file contracts for direct specialist sessions; producers and consumers read the same schemas and completion rules.\n---\n\n# Direct artifact handoff\n\nRead [Epic contracts](epic-contracts.md) for the artifact assigned to this session, including its\nfields, interpretation and completion criteria. JSON schemas are in [schemas/](schemas/).\nProducers and reviewers use this same contract; a reviewer cannot add unstated requirements.\n\nThe brief contains only a bead id, labeled absolute input paths, an absolute output path, and a\none-line outcome. Read the named files yourself. Write the complete result to the exact output\npath. Write only assigned outputs and, for architecture writers, the assigned draft views.\nFor a JSON output write one strict JSON value with unique keys; for a document write nonempty\nUTF-8 Markdown. Do not paste file contents into a response. A final reply may name the result path.\n\nPython validates the file against the schema, checks declared document citations, publishes the\ncanonical JSON, and records input/output fingerprints. The agent does not accept its own result,\nwrite receipts, compute revision bindings, submit StructuredOutput, or run artifact checkpoint or\nsubmission helpers. There is no machine mode or command-runner handoff in direct sessions.\nA structurally valid artifact is not automatically a semantically correct one.\n\nOn a corrective pass, read the labeled validation-errors input and the existing output, repair the\nspecific findings and affected references, and preserve valid work. On interruption retain the\nactual files; resumption continues those files. Do not fabricate completion for missing reasoning.\nNamed missing inputs or remaining uncertainties belong in the contract's existing evidence fields;\nnever add fields to a closed schema or return a success reference for absent work.\n\n## Generated contract types\n\nEach schema in [schemas/](schemas/) is the one definition of its contract. Python code never\nrestates a key, type or allowed value: it imports the module that\n`scripts/generate_contract_types.py` generates from the schema, and\n`scripts/check_contract_types.py` fails when a generated module is stale. Run\n`python3 scripts/generate_contract_types.py` after changing a schema.\n\n| Schema | Generated module |\n|---|---|\n| `schemas/task-deps.schema.json` (Cross-Story Task dependencies) | `scripts/task_deps_contract.py` |\n"
const ownedBaselineContract = "---\nname: architecture-baseline\ndescription: Assess and evolve effective architecture using one shared author, reviewer and decider standard.\n---\n\n# Architecture baseline\n\nRead [the review standard](review-standard.md) before surveying, coordinating, authoring,\nreviewing, deciding or integrating architecture. That is the common completion basis.\nRead artifact-handoff's [Epic contracts](../artifact-handoff/epic-contracts.md) and the relevant\nschema there for input and output fields. Contract correctness and architecture correctness are\nseparate: Python validates structure; independent reviewers judge claims and coverage.\n\nAn effective view is reviewed design, not evidence of implementation and not a permanent\nconstraint on future PRDs. Preserve valid design and evidence, revise what current requirements\nchange, and fill the implementation-detail gaps in the affected views. Do not redesign unrelated\nhistorical debt. No fixed specialist quota applies; the coordinator selects bounded specialties.\n\nThe survey judges design and documentation, never built-ness. Python computes implementationWork\nfrom the matrix snapshot and cited view elements. A fresh survey baseline entry follows the\nsurvey.schema.json `$defs/FreshBaselineEntry` rule; legacy values are compatibility context only.\nThe Closure agent walks views, never repository code or deployments; Python classifies its\nreached elements using the matrix. A missing or unknown matrix row creates implementation work.\nOpen Tasks elsewhere add blockers; they do not remove this Epic's work.\n"
const ownedAgentContracts = {"acceptance-criteria-reviewer":{"artifactCapable":false,"agentType":"agent-teams-workforce:acceptance-criteria-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"acceptance-criteria-writer":{"artifactCapable":true,"agentType":"acceptance-criteria-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:artifact-handoff"]},"accessibility-validator":{"artifactCapable":true,"agentType":"agent-teams-workforce:accessibility-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:a11y-audit","agent-teams-workforce:senior-frontend"]},"advantage-evaluator":{"artifactCapable":false,"agentType":"agent-teams-workforce:advantage-evaluator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"adversarial-critique-adjudicator":{"artifactCapable":false,"agentType":"agent-teams-workforce:adversarial-critique-adjudicator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-security"]},"adversarial-review-loop-supervisor":{"artifactCapable":false,"agentType":"agent-teams-workforce:adversarial-review-loop-supervisor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"ambiguity-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:ambiguity-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"android-compose-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:android-compose-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:graphrag-lookup"]},"api-contract-designer":{"artifactCapable":true,"agentType":"api-contract-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:architecture-baseline"]},"api-documentation-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:api-documentation-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer"]},"api-gateway-cdk-implementer":{"artifactCapable":true,"agentType":"api-gateway-cdk-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-gateway","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"api-specification-author":{"artifactCapable":true,"agentType":"api-specification-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer","agent-teams-workforce:artifact-handoff","agent-teams-workforce:skillspoke-standard-event"]},"appsync-cdk-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:appsync-cdk-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"appsync-client-subscription-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:appsync-client-subscription-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend","agent-teams-workforce:graphrag-lookup"]},"architecture-boundary-guardian":{"artifactCapable":true,"agentType":"architecture-boundary-guardian","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:architecture-baseline"]},"architecture-conformance-reviewer":{"artifactCapable":true,"agentType":"architecture-conformance-reviewer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:arc42","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:architecture-baseline"]},"architecture-decider":{"artifactCapable":true,"agentType":"architecture-decider","skills":["agent-teams-workforce:architecture-baseline","agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect"]},"architecture-decision-workflow-coordinator":{"artifactCapable":true,"agentType":"architecture-decision-workflow-coordinator","skills":["agent-teams-workforce:architecture-baseline","agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"architecture-diagram-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:architecture-diagram-author","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:architecture-diagramming","agent-teams-workforce:c4-diagramming","agent-teams-workforce:uml-diagramming","agent-teams-workforce:senior-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:architecture-baseline"]},"architecture-fitness-function-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:architecture-fitness-function-author","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"architecture-impact-analyst":{"artifactCapable":false,"agentType":"agent-teams-workforce:architecture-impact-analyst","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:beads-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:graphrag-lookup"]},"architecture-maintainer":{"artifactCapable":true,"agentType":"architecture-maintainer","skills":["agent-teams-workforce:architecture-baseline","agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:arc42","agent-teams-workforce:arc42-maintain","agent-teams-workforce:c4-diagramming","agent-teams-workforce:uml-diagramming","agent-teams-workforce:senior-architect","agent-teams-workforce:graphrag-lookup"]},"architecture-pattern-challenger":{"artifactCapable":true,"agentType":"architecture-pattern-challenger","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:architecture-baseline"]},"architecture-tradeoff-skeptic":{"artifactCapable":true,"agentType":"architecture-tradeoff-skeptic","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:architecture-baseline"]},"athena-redshift-analytics-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:athena-redshift-analytics-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:graphrag-lookup"]},"auth-bypass-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:auth-bypass-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops","agent-teams-workforce:cognito"]},"aws-integration-test-runner":{"artifactCapable":true,"agentType":"agent-teams-workforce:aws-integration-test-runner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:test-failure-mindset","agent-teams-workforce:cumulative-regression"]},"aws-integration-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:aws-integration-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:cumulative-regression"]},"beads-format-validator":{"artifactCapable":true,"agentType":"agent-teams-workforce:beads-format-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:beads-contract"]},"bedrock-integration-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:bedrock-integration-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:bedrock","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:senior-prompt-engineer","agent-teams-workforce:aws-agentic-ai","agent-teams-workforce:graphrag-lookup"]},"behavioral-signals-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:behavioral-signals-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:senior-data-scientist","agent-teams-workforce:product-analytics","agent-teams-workforce:graphrag-lookup"]},"bounded-context-mapper":{"artifactCapable":true,"agentType":"bounded-context-mapper","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:architecture-baseline"]},"brd-traceability-auditor":{"artifactCapable":true,"agentType":"agent-teams-workforce:brd-traceability-auditor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"c4-diagram-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:c4-diagram-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:architecture-diagramming","agent-teams-workforce:c4-diagramming","agent-teams-workforce:senior-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:artifact-handoff","agent-teams-workforce:architecture-baseline"]},"cdk-infrastructure-designer":{"artifactCapable":true,"agentType":"cdk-infrastructure-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming","agent-teams-workforce:architecture-baseline"]},"cdk-infrastructure-drift-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:cdk-infrastructure-drift-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:cloudformation"]},"cdk-stack-author":{"artifactCapable":true,"agentType":"cdk-stack-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:cloudformation","agent-teams-workforce:resource-naming"]},"cds-finding-reviewer":{"artifactCapable":false,"agentType":"agent-teams-workforce:cds-finding-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","cds:apply-design-system","cds:audit-against-system"]},"cds-ui-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:cds-ui-implementer","skills":["agent-teams-workforce:subagent-contract","cds:apply-design-system","cds:audit-against-system","cds:compose-page","agent-teams-workforce:graphrag-lookup"]},"changelog-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:changelog-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:changelog-generator"]},"chassis-extension-implementer":{"artifactCapable":true,"agentType":"chassis-extension-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:lambda","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"code-correctness-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:code-correctness-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:code-reviewer"]},"code-quality-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:code-quality-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"code-refactoring-specialist":{"artifactCapable":true,"agentType":"agent-teams-workforce:code-refactoring-specialist","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:code-reviewer","agent-teams-workforce:graphrag-lookup"]},"code-style-and-linting-enforcer":{"artifactCapable":true,"agentType":"agent-teams-workforce:code-style-and-linting-enforcer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:code-reviewer"]},"cognito-lambda-trigger-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:cognito-lambda-trigger-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:cognito","agent-teams-workforce:lambda","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"completeness-checker":{"artifactCapable":false,"agentType":"agent-teams-workforce:completeness-checker","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"complexity-analyzer":{"artifactCapable":false,"agentType":"agent-teams-workforce:complexity-analyzer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:tech-debt-tracker"]},"constitutional-agent":{"artifactCapable":false,"agentType":"agent-teams-workforce:constitutional-agent","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"constraint-extractor":{"artifactCapable":true,"agentType":"agent-teams-workforce:constraint-extractor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"consumer-driven-contract-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:consumer-driven-contract-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-test-suite-builder","agent-teams-workforce:cumulative-regression"]},"context-curator":{"artifactCapable":false,"agentType":"agent-teams-workforce:context-curator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"contract-violation-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:contract-violation-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-test-suite-builder"]},"cost-architecture-reviewer":{"artifactCapable":true,"agentType":"cost-architecture-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-cost-operations","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:artifact-handoff","agent-teams-workforce:architecture-baseline"]},"cost-impact-reviewer":{"artifactCapable":true,"agentType":"cost-impact-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cost-operations","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:artifact-handoff","agent-teams-workforce:architecture-baseline"]},"cross-repo-integration-test-coordinator":{"artifactCapable":false,"agentType":"agent-teams-workforce:cross-repo-integration-test-coordinator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"cross-service-contract-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:cross-service-contract-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-test-suite-builder"]},"data-consistency-checker":{"artifactCapable":true,"agentType":"agent-teams-workforce:data-consistency-checker","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb"]},"data-exposure-scanner":{"artifactCapable":true,"agentType":"agent-teams-workforce:data-exposure-scanner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"data-model-specification-author":{"artifactCapable":true,"agentType":"data-model-specification-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb","agent-teams-workforce:database-schema-designer","agent-teams-workforce:artifact-handoff"]},"data-pipeline-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:data-pipeline-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:cumulative-regression"]},"definition-of-done-enforcer":{"artifactCapable":true,"agentType":"agent-teams-workforce:definition-of-done-enforcer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"dependency-change-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:dependency-change-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dependency-auditor"]},"dependency-cve-auditor":{"artifactCapable":true,"agentType":"agent-teams-workforce:dependency-cve-auditor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dependency-auditor"]},"dependency-graph-extractor":{"artifactCapable":true,"agentType":"agent-teams-workforce:dependency-graph-extractor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"deployment-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:deployment-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"deployment-strategy-decider":{"artifactCapable":false,"agentType":"agent-teams-workforce:deployment-strategy-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:cove-prompt-design"]},"documentation-accuracy-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:documentation-accuracy-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"documentation-currency-auditor":{"artifactCapable":true,"agentType":"agent-teams-workforce:documentation-currency-auditor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"documentation-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:documentation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"domain-boundary-validator":{"artifactCapable":true,"agentType":"agent-teams-workforce:domain-boundary-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"domain-event-modeler":{"artifactCapable":true,"agentType":"domain-event-modeler","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:architecture-baseline","agent-teams-workforce:skillspoke-standard-event"]},"dos-resilience-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:dos-resilience-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"dynamodb-access-layer-implementer":{"artifactCapable":true,"agentType":"dynamodb-access-layer-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"dynamodb-cost-optimizer":{"artifactCapable":true,"agentType":"dynamodb-cost-optimizer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb","agent-teams-workforce:aws-cost-operations"]},"dynamodb-schema-access-pattern-reviewer":{"artifactCapable":true,"agentType":"dynamodb-schema-access-pattern-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb"]},"dynamodb-streams-cdc-implementer":{"artifactCapable":true,"agentType":"dynamodb-streams-cdc-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:dynamodb","agent-teams-workforce:graphrag-lookup"]},"email-notification-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:email-notification-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:email-template-builder","agent-teams-workforce:sns","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:skillspoke-standard-event"]},"epic-sequencer":{"artifactCapable":true,"agentType":"agent-teams-workforce:epic-sequencer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:epic-sequencing"]},"espresso-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:espresso-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:tdd-guide","agent-teams-workforce:cumulative-regression"]},"event-api-client-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:event-api-client-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming","agent-teams-workforce:skillspoke-standard-event"]},"event-driven-consumer-implementer":{"artifactCapable":true,"agentType":"event-driven-consumer-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:sqs","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:sns","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming","agent-teams-workforce:skillspoke-standard-event"]},"event-flow-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:event-flow-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda"]},"event-schema-designer":{"artifactCapable":true,"agentType":"event-schema-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:eventbridge","agent-teams-workforce:sns","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:architecture-baseline","agent-teams-workforce:skillspoke-standard-event"]},"event-schema-reviewer":{"artifactCapable":true,"agentType":"event-schema-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:skillspoke-standard-event"]},"failure-mode-analyst":{"artifactCapable":true,"agentType":"failure-mode-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:observability-designer","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:artifact-handoff","agent-teams-workforce:architecture-baseline"]},"filing-clerk":{"artifactCapable":true,"agentType":"filing-clerk","skills":["agent-teams-workforce:subagent-contract","obsidian:obsidian-cli","obsidian:obsidian-markdown","agent-teams-workforce:arc42","notebooklm","document-classification"]},"finops-analyst":{"artifactCapable":false,"agentType":"finops-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-cost-operations"]},"flaky-test-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:flaky-test-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:test-failure-mindset","agent-teams-workforce:find-cause"]},"frontend-performance-optimizer":{"artifactCapable":true,"agentType":"agent-teams-workforce:frontend-performance-optimizer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend"]},"github-actions-pipeline-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:github-actions-pipeline-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"glue-etl-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:glue-etl-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:graphrag-lookup"]},"graphql-schema-designer":{"artifactCapable":true,"agentType":"graphql-schema-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:architecture-baseline"]},"graphql-schema-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:graphql-schema-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer"]},"implementation-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:implementation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:graphrag-lookup"]},"incident-response-runbook-designer":{"artifactCapable":true,"agentType":"agent-teams-workforce:incident-response-runbook-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:observability-designer"]},"infrastructure-security-scanner":{"artifactCapable":true,"agentType":"infrastructure-security-scanner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops","agent-teams-workforce:aws-cdk-development"]},"injection-attack-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:injection-attack-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"integration-pattern-architect":{"artifactCapable":true,"agentType":"integration-pattern-architect","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:architecture-baseline"]},"integration-testing-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:integration-testing-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"ios-swiftui-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:ios-swiftui-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:graphrag-lookup"]},"kinesis-stream-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:kinesis-stream-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"lambda-performance-optimizer":{"artifactCapable":true,"agentType":"lambda-performance-optimizer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:lambda"]},"llm-observability-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:llm-observability-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:observability-designer","agent-teams-workforce:senior-prompt-engineer","agent-teams-workforce:aws-agentic-ai","agent-teams-workforce:graphrag-lookup"]},"matching-algorithm-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:matching-algorithm-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:graphrag-lookup"]},"mcp-server-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:mcp-server-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:mcp-server-builder","agent-teams-workforce:aws-agentic-ai","agent-teams-workforce:aws-mcp-setup","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"ml-evaluation-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:ml-evaluation-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:senior-data-scientist","agent-teams-workforce:cumulative-regression"]},"mobile-e2e-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:mobile-e2e-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"nextjs-component-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:nextjs-component-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend","agent-teams-workforce:a11y-audit","agent-teams-workforce:senior-fullstack","agent-teams-workforce:graphrag-lookup"]},"nfr-analyst":{"artifactCapable":false,"agentType":"agent-teams-workforce:nfr-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:product-discovery"]},"okr-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:okr-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-strategist","agent-teams-workforce:product-analytics"]},"openapi-contract-reviewer":{"artifactCapable":false,"agentType":"openapi-contract-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer","agent-teams-workforce:skillspoke-standard-event"]},"operational-readiness-reviewer":{"artifactCapable":true,"agentType":"operational-readiness-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:observability-designer","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:artifact-handoff","agent-teams-workforce:architecture-baseline"]},"payments-integration-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:payments-integration-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:stripe-integration-expert","agent-teams-workforce:secrets-manager","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:skillspoke-standard-event"]},"performance-benchmark-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:performance-benchmark-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"permission-escalation-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:permission-escalation-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops","agent-teams-workforce:iam"]},"persistence-architecture-specialist":{"artifactCapable":true,"agentType":"persistence-architecture-specialist","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:dynamodb","agent-teams-workforce:database-schema-designer","agent-teams-workforce:rds","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:architecture-baseline"]},"persona-profile-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:persona-profile-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:product-analytics"]},"phase-gate-enforcer":{"artifactCapable":false,"agentType":"agent-teams-workforce:phase-gate-enforcer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:cumulative-regression"]},"playwright-e2e-web-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:playwright-e2e-web-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:a11y-audit","agent-teams-workforce:cumulative-regression"]},"polyrepo-steward":{"artifactCapable":true,"agentType":"agent-teams-workforce:polyrepo-steward","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:graphrag-lookup","polyrepo-repo","polyrepo-info","polyrepo-governance","polyrepo-setup","polyrepo-tribal-knowledge","polyrepo-doctor","polyrepo-beads","gitnexus-exploring","agent-teams-workforce:artifact-handoff"]},"power-tools-configuration-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:power-tools-configuration-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:lambda","agent-teams-workforce:secrets-manager","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"prd-alignment-verifier":{"artifactCapable":true,"agentType":"agent-teams-workforce:prd-alignment-verifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"prd-creation-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:prd-creation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"prd-reality-reconciler":{"artifactCapable":true,"agentType":"prd-reality-reconciler","skills":["agent-teams-workforce:architecture-baseline","agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:graphrag-lookup"]},"prd-trd-traceability-verifier":{"artifactCapable":true,"agentType":"agent-teams-workforce:prd-trd-traceability-verifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"prd-validation-analyst":{"artifactCapable":true,"agentType":"agent-teams-workforce:prd-validation-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"prd-validation-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:prd-validation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"prd-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:prd-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"production-readiness-review-facilitator":{"artifactCapable":false,"agentType":"agent-teams-workforce:production-readiness-review-facilitator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"race-condition-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:race-condition-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"react-native-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:react-native-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend","agent-teams-workforce:graphrag-lookup"]},"readme-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:readme-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"recommendation-engine-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:recommendation-engine-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:graphrag-lookup"]},"regression-coverage-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:regression-coverage-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:artifact-handoff","agent-teams-workforce:cumulative-regression"]},"regression-impact-assessor":{"artifactCapable":true,"agentType":"agent-teams-workforce:regression-impact-assessor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:artifact-handoff","agent-teams-workforce:cumulative-regression"]},"requirements-clarifier":{"artifactCapable":false,"agentType":"agent-teams-workforce:requirements-clarifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:product-discovery"]},"requirements-conflict-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:requirements-conflict-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"root-cause-analyst":{"artifactCapable":false,"agentType":"agent-teams-workforce:root-cause-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:find-cause","agent-teams-workforce:test-failure-mindset","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:artifact-handoff"]},"run-ledger-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:run-ledger-writer","skills":["agent-teams-workforce:subagent-contract"]},"s3-data-lake-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:s3-data-lake-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:s3","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"sdlc-pipeline-orchestrator":{"artifactCapable":false,"agentType":"agent-teams-workforce:sdlc-pipeline-orchestrator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:beads-contract"]},"security-architecture-designer":{"artifactCapable":true,"agentType":"security-architecture-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-security","agent-teams-workforce:iam","agent-teams-workforce:secrets-manager","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:architecture-baseline"]},"security-test-case-designer":{"artifactCapable":true,"agentType":"agent-teams-workforce:security-test-case-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-security","agent-teams-workforce:cumulative-regression"]},"slo-error-budget-designer":{"artifactCapable":false,"agentType":"slo-error-budget-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:observability-designer","agent-teams-workforce:cloudwatch"]},"smoke-test-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:smoke-test-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"spec-authoring-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:spec-authoring-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"spec-currency-validator":{"artifactCapable":true,"agentType":"agent-teams-workforce:spec-currency-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"spec-decider":{"artifactCapable":false,"agentType":"spec-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:cove-prompt-design"]},"spec-freshness-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:spec-freshness-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"stakeholder-request-intake-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:stakeholder-request-intake-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"task-decomposer":{"artifactCapable":true,"agentType":"task-decomposer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:beads-contract","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:artifact-handoff","agent-teams-workforce:wsjf"]},"task-decomposition-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:task-decomposition-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:beads-contract","agent-teams-workforce:graphrag-lookup"]},"task-dependency-mapper":{"artifactCapable":true,"agentType":"task-dependency-mapper","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:beads-contract","agent-teams-workforce:artifact-handoff"]},"task-readiness-runner":{"artifactCapable":false,"agentType":"agent-teams-workforce:task-readiness-runner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:beads-contract"]},"tdd-unit-test-generator":{"artifactCapable":true,"agentType":"agent-teams-workforce:tdd-unit-test-generator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:tdd-guide","agent-teams-workforce:cumulative-regression"]},"test-command-resolver":{"artifactCapable":false,"agentType":"agent-teams-workforce:test-command-resolver","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:test-failure-mindset"]},"test-coverage-gap-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:test-coverage-gap-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"test-design-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:test-design-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"test-environment-orchestrator":{"artifactCapable":true,"agentType":"test-environment-orchestrator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:aws-mcp-setup"]},"test-failure-parser":{"artifactCapable":false,"agentType":"agent-teams-workforce:test-failure-parser","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:test-failure-mindset"]},"test-isolation-specialist":{"artifactCapable":true,"agentType":"agent-teams-workforce:test-isolation-specialist","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:tdd-guide","agent-teams-workforce:test-failure-mindset"]},"test-plan-strategy-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:test-plan-strategy-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"test-strategy-decider":{"artifactCapable":false,"agentType":"agent-teams-workforce:test-strategy-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cove-prompt-design"]},"trd-author":{"artifactCapable":true,"agentType":"trd-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:artifact-handoff"]},"trd-authoring-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:trd-authoring-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"trd-decider":{"artifactCapable":false,"agentType":"agent-teams-workforce:trd-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"trd-validator":{"artifactCapable":false,"agentType":"agent-teams-workforce:trd-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"ubiquitous-language-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:ubiquitous-language-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"uml-diagram-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:uml-diagram-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:architecture-diagramming","agent-teams-workforce:uml-diagramming","agent-teams-workforce:senior-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:artifact-handoff","agent-teams-workforce:architecture-baseline"]},"user-guide-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:user-guide-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:roadmap-communicator"]},"user-story-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:user-story-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:beads-contract"]},"user-story-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:user-story-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"vector-search-embeddings-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:vector-search-embeddings-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:rag-architect","agent-teams-workforce:graphrag-lookup"]},"webauthn-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:webauthn-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend","agent-teams-workforce:cognito","agent-teams-workforce:graphrag-lookup"]},"workflow-command-runner":{"artifactCapable":false,"agentType":"agent-teams-workforce:workflow-command-runner","skills":["artifact-handoff"]},"worktree-independent-verifier":{"artifactCapable":false,"agentType":"agent-teams-workforce:worktree-independent-verifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"wsjf-scorer":{"artifactCapable":true,"agentType":"agent-teams-workforce:wsjf-scorer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-strategist","agent-teams-workforce:wsjf","agent-teams-workforce:beads-contract"]},"wsjf-scoring-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:wsjf-scoring-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-strategist","agent-teams-workforce:wsjf"]},"xcuitest-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:xcuitest-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:tdd-guide","agent-teams-workforce:cumulative-regression"]}}
// skills/pipeline-contracts/schemas/driver-surface.schema.json, inlined by shared-blocks.mjs. DRIVER_SURFACE maps
// each x-constant of $defs.DriverEnvironment to its environment variable name and each x-values entry of
// $defs.RateLimitInfo to its wire value, so no workflow names a driver environment variable or a rate-limit value itself.
const DRIVER_SURFACE_SCHEMA = {"$schema":"https://json-schema.org/draft/2020-12/schema","$id":"agent-teams-workforce/skills/pipeline-contracts/schemas/driver-surface.schema.json","title":"Driver module surface","description":"The one definition of the driver (ops/sdlc-automation in the control repository) surface the plugin orchestrator imports, the ATW_* environment the driver hands every child and orchestrator process, and the Claude CLI rate-limit event the driver's quota readers take. scripts/generate_types.py renders scripts/driver_surface_types.py from this file; scripts/check_generated.py fails when that module is stale.","x-driver":{"dirParts":["ops","sdlc-automation"],"dirDoc":"Path parts of the driver directory under ATW_CONTROL_REPO.","modules":[{"module":"headlessenv","constant":"HEADLESSENV_MODULE","protocol":"HeadlessEnvironment","doc":"Driver headlessenv module surface consumed by session setup.","members":[{"name":"DENIED_TOOLS","kind":"attribute","python":"tuple[str, ...]","doc":"Tools every headless and orchestrator agent session is denied, in order."},{"name":"child_env","kind":"method","params":[["scratch","Path"]],"returns":"dict[str, str]","doc":"Build the subprocess environment: DriverEnvironment over the inherited one."}]},{"module":"fablewall","constant":"FABLEWALL_MODULE","protocol":"FableWall","doc":"Driver fablewall module surface consumed by model fallback.","members":[{"name":"is_refusal","kind":"method","params":[["info","object"]],"returns":"bool","doc":"Return whether a RateLimitInfo is a model-specific refusal."},{"name":"reset_of","kind":"method","params":[["info","object"]],"returns":"float | None","doc":"Return the model-specific reset of a RateLimitInfo, in epoch seconds."}]},{"module":"breaker","constant":"BREAKER_MODULE","protocol":"Breaker","doc":"Driver breaker module surface consumed by quota handling.","members":[{"name":"exhausted_reset","kind":"method","params":[["info","object"]],"returns":"float | None","doc":"Return the latest reset among the exhausted windows, in epoch seconds."}]},{"module":"childproc","constant":"CHILDPROC_MODULE","protocol":"ChildProcess","doc":"Driver childproc module termination policy.","members":[{"name":"TERMINATE_GRACE","kind":"attribute","python":"float","doc":"Seconds a terminated child is given before it is killed."}]}]},"$defs":{"DriverEnvironment":{"description":"The ATW_* and process environment the driver hands child and orchestrator processes.","x-details":"headlessenv.child_env(scratch) returns these keys over the inherited os.environ (atw.environment fills only absent or blank values); the keeper, supervisor and orchestrator dispatch add ATW_STOP_FILE, ATW_EXECUTION_ID and ATW_ORCH_IDLE.","type":"object","x-python":{"typeddict":"DriverEnvironment"},"properties":{"ATW_PROJECT_ROOT":{"type":"string","minLength":1,"description":"Absolute path of the project root.","x-constant":"PROJECT_ROOT_ENV"},"ATW_ARTIFACT_SCRIPT":{"type":"string","minLength":1,"description":"Absolute path of the phase-artifact recorder (artifactio.recorder_path()).","x-constant":"ARTIFACT_SCRIPT_ENV"},"ATW_PRD_EPIC_SYNC":{"type":"string","minLength":1,"description":"Path of the PRD-to-Epic sync script.","x-constant":"PRD_EPIC_SYNC_ENV"},"ATW_PRD_EPIC_VERIFY":{"type":"string","minLength":1,"description":"Path of the PRD-to-Epic verify script.","x-constant":"PRD_EPIC_VERIFY_ENV"},"ATW_FLEET_DIR":{"type":"string","minLength":1,"description":"The fleet directory: SKILLSPOKE_APP_ROOT, else the control repository's parent.","x-constant":"FLEET_DIR_ENV"},"ATW_CONTROL_REPO":{"type":"string","minLength":1,"description":"Absolute path of the control repository (SKILLSPOKE_CC, else the driver's repository root). The driver modules live under it at DRIVER_DIR_PARTS.","x-constant":"CONTROL_REPO_ENV"},"ATW_ARCH_PATH":{"type":"string","minLength":1,"description":"The architecture root; set only when the driver knows one. Readers use args.archPath first and fall back to it.","x-constant":"ARCH_PATH_ENV"},"ATW_DESIGN_PACKAGES_DIR":{"type":"string","minLength":1,"description":"The owner's cds design packages directory; optional.","x-constant":"DESIGN_PACKAGES_ENV"},"ATW_PRD_DIR":{"type":"string","minLength":1,"description":"The first PRD root; optional.","x-constant":"PRD_DIR_ENV"},"PATH":{"type":"string","minLength":1,"description":"The controller runtime's bin directory first, de-duplicated.","x-constant":"PATH_ENV"},"TMPDIR":{"type":"string","minLength":1,"description":"The dispatch scratch directory.","x-constant":"TMPDIR_ENV","x-group":"SCRATCH_ENV_KEYS"},"TMP":{"type":"string","minLength":1,"description":"The dispatch scratch directory.","x-constant":"TMP_ENV","x-group":"SCRATCH_ENV_KEYS"},"TEMP":{"type":"string","minLength":1,"description":"The dispatch scratch directory.","x-constant":"TEMP_ENV","x-group":"SCRATCH_ENV_KEYS"},"CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS":{"type":"string","const":"0","description":"Disables the Claude CLI print-mode background wait.","x-constant":"BACKGROUND_WAIT_KEY","x-const-mapping":"BACKGROUND_WAIT_ENV"},"ATW_STOP_FILE":{"type":"string","minLength":1,"description":"Path of the stop marker file; absent means no stop marker. A consumer touches the file (mode 0o600) to request a drain, or tests whether it exists. It only requests a stop: how a stop is classified belongs to the handback contract.","x-constant":"STOP_FILE_ENV","x-file-mode":"STOP_FILE_MODE"},"ATW_EXECUTION_ID":{"type":"string","minLength":1,"description":"The driver execution id. Required for an orchestrator dispatch; set for a headless workflow session only when its arguments carry an executionId.","x-constant":"EXECUTION_ID_ENV"},"ATW_ORCH_IDLE":{"type":"string","pattern":"^[0-9]+(\\.[0-9]+)?$","default":"3600","description":"Orchestrator idle limit in seconds: a positive finite float. A non-finite or non-positive value is a ValueError.","x-constant":"ORCH_IDLE_ENV","x-default-constant":"ORCH_IDLE_DEFAULT"}},"required":["ATW_PROJECT_ROOT","ATW_ARTIFACT_SCRIPT","ATW_PRD_EPIC_SYNC","ATW_PRD_EPIC_VERIFY","ATW_FLEET_DIR","ATW_CONTROL_REPO","PATH","TMPDIR","TMP","TEMP","CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS"],"additionalProperties":{"type":"string"}},"StopFileMode":{"description":"Permission bits a consumer creates the stop marker file with.","type":"integer","const":384,"x-python":{"constant":"STOP_FILE_MODE","type":"int","render":"0o600"}},"DeniedTool":{"description":"A tool every headless and orchestrator agent session is denied. DENIED_TOOLS keeps this order.","type":"string","enum":["WebFetch","WebSearch","Artifact","SendMessage","EndConversation","CronCreate","CronDelete","CronList","mcp__claude_ai_Gmail__send_message","mcp__claude_ai_Gmail__reply","mcp__claude_ai_Gmail__forward","mcp__claude_ai_Gmail__create_draft","mcp__claude_ai_Google_Drive__share_file","mcp__claude_ai_Google_Drive__create_file","mcp__plugin_slack_slack__slack_send_message","mcp__plugin_slack_slack__slack_send_message_draft","mcp__plugin_slack_slack__slack_schedule_message"],"x-python":{"literal":"DeniedTool","tuple":"DENIED_TOOLS"}},"TerminateGrace":{"description":"Seconds a terminated child process is given before it is killed.","type":"number","const":10,"x-python":{"constant":"TERMINATE_GRACE","type":"float"}},"ExhaustedUtilization":{"description":"A usage window whose utilization is at or above this value is exhausted.","type":"number","const":1,"x-python":{"constant":"EXHAUSTED_UTILIZATION","type":"float"}},"RateLimitStatus":{"description":"RateLimitInfo.status; only rejected is acted on.","type":"string","enum":["allowed","allowed_warning","rejected"],"x-python":{"literal":"RateLimitStatus","tuple":"RATE_LIMIT_STATUSES","constants":{"rejected":"REJECTED_STATUS"}}},"UsageWindowName":{"description":"The account-wide usage windows. Any other window name is model-specific.","type":"string","enum":["five_hour","seven_day"],"x-python":{"literal":"UsageWindowName","frozenset":"ACCOUNT_WINDOWS"}},"UsageWindow":{"description":"One usage window of a RateLimitInfo.","type":"object","x-python":{"typeddict":"UsageWindow"},"properties":{"utilization":{"type":"number","description":"Exhausted when at or above EXHAUSTED_UTILIZATION."},"resetsAt":{"type":"number","description":"Reset time in epoch seconds."}},"required":["utilization"]},"RateLimitInfo":{"description":"The rate_limit_info of a rate_limit_event: the info argument of the quota readers.","type":"object","x-python":{"typeddict":"RateLimitInfo"},"properties":{"status":{"$ref":"#/$defs/RateLimitStatus"},"unifiedWindows":{"type":"object","additionalProperties":{"$ref":"#/$defs/UsageWindow"},"description":"Window name -> usage window."},"resetsAt":{"type":"number","description":"Top-level reset time in epoch seconds."},"rateLimitType":{"type":"string","description":"The value with meaning here is MODEL_OVERAGE_TYPE.","x-values":{"MODEL_OVERAGE_TYPE":"seven_day_overage_included"}},"overageDisabledReason":{"type":"string","description":"The value with meaning here is OUT_OF_CREDITS_REASON.","x-values":{"OUT_OF_CREDITS_REASON":"out_of_credits"}}},"required":["status"]},"RateLimitEvent":{"description":"One Claude CLI stream-json rate-limit event.","type":"object","x-python":{"typeddict":"RateLimitEvent"},"properties":{"type":{"type":"string","const":"rate_limit_event","x-value-constant":"RATE_LIMIT_EVENT_TYPE"},"rate_limit_info":{"$ref":"#/$defs/RateLimitInfo","x-key-constant":"RATE_LIMIT_INFO_KEY"}},"required":["type","rate_limit_info"]}}}
const DRIVER_SURFACE = (() => {
  const defs = (DRIVER_SURFACE_SCHEMA && DRIVER_SURFACE_SCHEMA.$defs) || {}
  const env = defs.DriverEnvironment && defs.DriverEnvironment.properties
  const info = defs.RateLimitInfo && defs.RateLimitInfo.properties
  if (!env || !info) throw new Error('shared block fable: DRIVER_SURFACE_SCHEMA was not filled from skills/pipeline-contracts/schemas/driver-surface.schema.json (run node scripts/shared-blocks.mjs --write)')
  const named = {}
  for (const [key, spec] of Object.entries(env)) if (spec && typeof spec['x-constant'] === 'string') named[spec['x-constant']] = key
  for (const spec of Object.values(info)) if (spec && spec['x-values'] && typeof spec['x-values'] === 'object') Object.assign(named, spec['x-values'])
  return Object.freeze(named)
})()
const driverSurfaceRe = (value) => String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const FABLE_EXHAUSTED = new RegExp(`out of (?:usage )?credits|${driverSurfaceRe(DRIVER_SURFACE.MODEL_OVERAGE_TYPE)}|${driverSurfaceRe(DRIVER_SURFACE.OUT_OF_CREDITS_REASON)}|fable.{0,40}(?:limit|allowance)`, 'i')
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
  const schema = options && options.schema
  const artifactSchema = schema && schema.type === 'object' && Array.isArray(schema.required) && schema.required.length === 1 && schema.required[0] === 'artifactPath' && schema.properties && schema.properties.artifactPath && schema.properties.artifactPath.type === 'string'
  const outputMode = ['artifact', 'inline', 'machine'].includes(options && options.outputMode) ? options.outputMode : artifactSchema ? 'artifact' : 'inline'
  const { outputMode: _mode, architectureBaseline = false, ...runtimeOptions } = options || {}
  options = { ...runtimeOptions, agentType: contract ? contract.agentType : suppliedType }
  const domainSkills = (contract ? contract.skills : []).filter(name => !['agent-teams-workforce:subagent-contract', 'agent-teams-workforce:artifact-handoff'].includes(name))
  const contracts = outputMode === 'machine' ? '' : ownedCoreContracts + (outputMode === 'artifact' ? '\n\n' + ownedArtifactContract : '')
  const baselineContract = outputMode !== 'machine' && (architectureBaseline === true || domainSkills.includes('agent-teams-workforce:architecture-baseline')) ? ownedBaselineContract + '\n\n' : ''
  const skillData = outputMode !== 'machine' && domainSkills.length ? `Declared domain skills: ${domainSkills.join(', ')}\n\n` : ''
  const identity = { invocationPath: fablePath, ordinal: fableAgentOrdinal++, agentType: (options && options.agentType) || null, label: (options && options.label) || null }
  const isFable = fableTypes.has(String(identity.agentType || '').replace(/^agent-teams-workforce:/, ''))
  const cutoffs = (fableRecovery && fableRecovery.cutoffs) || {}
  const cutoff = Number.isInteger(cutoffs[fablePath]) && cutoffs[fablePath] >= 0 ? cutoffs[fablePath] : 0
  const call = isFable && fableRecovery && identity.ordinal >= cutoff ? { ...options, model: 'opus' } : options
  fableEvent('start', identity)
  try {
    const result = await agent(`OUTPUT_MODE: ${outputMode}\n\n${contracts}\n\n${baselineContract}${skillData}${prompt}`, call)
    if (!result) fableEvent('failed', identity)
    return result
  } catch (error) {
    const message = String((error && error.message) || error)
    fableEvent('failed', identity, message)
    if (isFable && FABLE_EXHAUSTED.test(message)) return null
    throw error
  }
}
async function fableWorkflow(name, input) {
  const invocationPath = `${fablePath}/${fableChildOrdinal++}:${name}`
  return await workflow(name, {
    ...input,
    fableAgentTypes: fableInput.fableAgentTypes || [],
    fableInvocationPath: invocationPath,
    ...(fableInput.relayExecutionId ? { relayExecutionId: fableInput.relayExecutionId } : {}),
    ...(fableInput.relayRequestDir ? { relayRequestDir: fableInput.relayRequestDir } : {}),
    ...(fableInput.relayCaptureScript ? { relayCaptureScript: fableInput.relayCaptureScript } : {}),
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

// ===== SHARED BLOCK relay — BEGIN (canonical: scripts/shared-blocks/relay.js; filled from skills/artifact-handoff/schemas/checkpoint.schema.json; edit there, then: node scripts/shared-blocks.mjs --write) =====
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
//   copy, then rebuilds the view. A copy that fails (damaged, missing, or handed back without
//   the hook) is recovered by reading the relay file the command wrote, bound to the command
//   line that wrote it; the original command never repeats.
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
  let captureOrdinal = 0
  const RECEIPT_SCHEMA = { type: 'object', additionalProperties: false, required: ['request', 'commandSha256', 'sha256', 'bytes', 'exitCode'], properties: { request: { type: 'string' }, commandSha256: { type: 'string' }, sha256: { type: 'string' }, bytes: { type: 'integer' }, exitCode: { type: 'integer' } } }
  const CAPTURE_SCHEMA = { type: 'object', additionalProperties: false, required: ['exitCode', 'stdout', 'receipt'], properties: { ...SCHEMA.properties, receipt: RECEIPT_SCHEMA } }
  const capturePrompt = command => `Execute this exact checksum-guarded command once in the foreground with Bash timeout 600000. Return its JSON stdout object through the required response schema unchanged. The exitCode inside that object belongs to the captured original command, not the capture helper. Do not execute another command, reconstruct missing output, or replace receipt fields. If the tool fails, report the actual failure; never invent a receipt.\n\n${command}`
  const REGISTERED_SCHEMA = { type: 'object', additionalProperties: false, required: ['state', 'exitCode', 'stdout', 'receipt', 'bridge', 'error'], properties: { state: { type: 'string', enum: ['completed', 'not-started', 'unknown'] }, exitCode: { type: 'integer' }, stdout: { type: 'string' }, receipt: { anyOf: [RECEIPT_SCHEMA, { type: 'null' }] }, bridge: { type: 'boolean' }, error: { type: 'string' } } }
  async function registeredCommand(dispatch, { label, phase, command }, ordinal) {
    const argv = shellWords(command)
    const commandSha256 = sha256Json(argv)
    const executionId = fableInput.relayExecutionId
    const request = sha256Json({ execution: executionId, invocation: fablePath, ordinal, commandSha256 })
    const document = canonicalJson({ version: 1, executionId, invocation: fablePath, ordinal, request, commandSha256, argv })
    if (document.length > 2097152) return { captureError: 'registered command exceeds the 2 MiB request bound' }
    let operation = 'registered'
    const recovered = new Set()
    for (let attempt = 0; attempt < 3; attempt++) {
      const callLabel = attempt ? `${label}:machine-recovery${attempt}` : label
      const before = new Set(typeof dispatchFailures === 'undefined' ? [] : dispatchFailures)
      const binding = canonicalJson({ executionId, request, directory: fableInput.relayRequestDir, operation })
      const out = await dispatch(`WORKFORCE_RELAY_BINDING_V1 ${binding}\nWORKFORCE_RELAY_REQUEST_V1 ${document}`, { label: callLabel, phase, agentType: 'agent-teams-workforce:workflow-command-runner', model: 'sonnet', effort: 'low', schema: REGISTERED_SCHEMA, outputMode: 'machine' })
      if (typeof dispatchFailures !== 'undefined') for (const entry of dispatchFailures) if (!before.has(entry) && entry.label === callLabel && entry.phase === phase) recovered.add(entry)
      if (!out) {
        if (typeof dispatchInterruption !== 'undefined' && dispatchInterruption) return null
        operation = 'registered-result'
        continue
      }
      const settle = (result) => {
        if (typeof dispatchFailures !== 'undefined') for (const entry of recovered) { const at = dispatchFailures.indexOf(entry); if (at >= 0) dispatchFailures.splice(at, 1) }
        return result
      }
      if (out.state === 'not-started') { operation = 'registered'; continue }
      // Without the hand-off hook the result is the runner's own copy: exec checks it, and reads the relay file when it fails.
      if (out.bridge !== true) return settle({ exitCode: out.exitCode, stdout: String(out.stdout || '') })
      if (out.state !== 'completed') return settle({ captureError: out.error || 'registered command outcome unknown' })
      const receipt = out.receipt
      let exact = false
      try { exact = receipt && receipt.request === request && receipt.commandSha256 === commandSha256 && receipt.exitCode === out.exitCode && Number.isInteger(out.exitCode) && Number.isSafeInteger(receipt.bytes) && receipt.bytes >= 0 && receipt.bytes <= 1048576 && typeof out.stdout === 'string' && out.stdout.length === receipt.bytes && HEX.test(String(receipt.sha256)) && sha256Ascii(out.stdout) === receipt.sha256 } catch (_) { exact = false }
      if (!exact) return settle({ captureError: 'machine handoff failed request/command/exit/byte verification' })
      return settle({ exitCode: out.exitCode, stdout: out.stdout, receipt, machine: true })
    }
    return { captureError: 'registered command could not hand back its result after three bounded machine attempts' }
  }
  async function captureCommand(dispatch, { label, phase, command, file, readRunner }, ordinal) {
    const argv = shellWords(command)
    const commandSha256 = sha256Json(argv)
    const request = sha256Json({ execution: fableInput.relayExecutionId, invocation: fablePath, ordinal, commandSha256 })
    const runner = readRunner.replace(/[^/]+$/, 'relaycapture.py')
    const common = ['--directory', `${file}.captures`, '--request', request, '--command-sha256', commandSha256]
    const out = await dispatch(capturePrompt(pythonLine(runner, ['capture', ...common, '--argv-json', canonicalJson(argv)])), { label, phase, agentType: 'agent-teams-workforce:workflow-command-runner', model: 'sonnet', effort: 'low', schema: CAPTURE_SCHEMA })
    if (!out && typeof dispatchInterruption !== 'undefined' && dispatchInterruption) return null
    const receipt = out && out.receipt
    let exact = false
    try { exact = receipt && receipt.request === request && receipt.commandSha256 === commandSha256 && HEX.test(String(receipt.sha256)) && Number.isInteger(receipt.exitCode) && out.exitCode === receipt.exitCode && typeof out.stdout === 'string' && out.stdout.length === receipt.bytes && sha256Ascii(out.stdout) === receipt.sha256 } catch (_) { exact = false }
    return exact ? out : { captureError: 'the capture copy failed byte or invocation validation' }
  }
  /** The `--argv-sha256` value a checked command line carries, or ''. */
  function argvShaOf(command) {
    try {
      const words = shellWords(command)
      const at = words.indexOf('--argv-sha256')
      return at >= 0 && HEX.test(String(words[at + 1])) ? words[at + 1] : ''
    } catch (_) {
      return ''
    }
  }
  /**
   * Runs a command once. When its result does not come back as an exact copy (a damaged copy, a
   * hand-back without the hook, an unknown outcome), the relay file the command wrote is read
   * instead, bound to the command line that wrote it; the command itself never runs twice. A
   * command line the runner typed differently ran nothing and is sent once more.
   */
  async function exec(dispatch, { label, phase, command, file = null, readRunner = null }, typedAgain = false) {
    const ordinal = captureOrdinal++
    const runner = { agentType: 'agent-teams-workforce:workflow-command-runner', model: 'sonnet', effort: 'low' }
    const registered = fableInput.relayExecutionId && fableInput.relayRequestDir && fableInput.relayCaptureScript
    const out = registered
      ? await registeredCommand(dispatch, { label, phase, command }, ordinal)
      : fableRecovery && file && readRunner && fableInput.relayExecutionId
        ? await captureCommand(dispatch, { label, phase, command, file, readRunner }, ordinal)
        : await dispatch(prompt(command), { label, phase, ...runner, schema: SCHEMA })
    if (!out) return { ok: false, noResult: true, error: `the ${label} runner returned no result` }
    let got = out.captureError ? { why: out.captureError } : parse(out.stdout, file)
    if (got.why) {
      if (!file || !readRunner) {
        const error = `RELAY_COPY_RECOVERY_EXHAUSTED ${JSON.stringify({ label, relayFile: file, attempts: 1, reason: `${got.why}; the command saves no relay file to read` })}`
        log(error)
        return { ok: false, paused: true, recoveryKind: 'relay-copy-recovery', error }
      }
      const sha = got.env && HEX.test(String(got.env['~sha256'])) ? got.env['~sha256'] : ''
      const argvSha = argvShaOf(command)
      let reason = got.why
      for (let attempt = 1; attempt <= 3; attempt++) {
        log(`RELAY_COPY_RECOVERY_ATTEMPT ${JSON.stringify({ label, relayFile: file, attempt, reason })}`)
        const readCommand = pythonLine(readRunner, ['read', '--relay', file, ...(attempt === 1 && sha ? ['--sha256', sha] : []), ...(argvSha ? ['--for-argv', argvSha] : [])])
        const copied = registered
          ? await registeredCommand(dispatch, { label: `${label}:read${attempt}`, phase, command: readCommand }, captureOrdinal++)
          : await dispatch(`The command below only reads the result an earlier command already saved; it runs nothing else.\n\n${prompt(readCommand)}`, { label: `${label}:read${attempt}`, phase, ...runner, schema: SCHEMA })
        if (!copied) return { ok: false, noResult: true, error: `${label}: the relay file reader returned no result` }
        const read = copied.captureError ? { why: copied.captureError } : parse(copied.stdout, file)
        if (!read.why && read.env['~exit'] === 4) return { ok: false, error: `${label}: the command saved no result in ${file}` }
        if (!read.why) { got = read; break }
        reason = read.why
      }
      if (got.why) {
        const error = `RELAY_COPY_RECOVERY_EXHAUSTED ${JSON.stringify({ label, relayFile: file, attempts: 3, reason })}`
        log(error)
        return { ok: false, paused: true, recoveryKind: 'relay-copy-recovery', error }
      }
      log(`RELAY_COPY_RECOVERED ${JSON.stringify({ label, relayFile: file })}`)
    }
    const exit = got.env['~exit']
    let view
    try {
      view = unflatten(got.flat)
    } catch (err) {
      return { ok: false, error: `${label}: the printed view could not be rebuilt: ${String((err && err.message) || err)}` }
    }
    if (exit === 3) {
      if (!typedAgain) {
        log(`${label}: the runner typed the command line differently and nothing ran; sending it once more`)
        return exec(dispatch, { label, phase, command, file, readRunner }, true)
      }
      return { ok: false, error: `${label}: ${String(view.error || 'the runner typed the command line differently from the one built')}; nothing ran` }
    }
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
   * what it printed, checked, with relayFile; or { error, cause, exception?, output? }: cause is
   * 'relay' when the result did not come back through the relay, else the `cause` depscore.py
   * printed ('contention' when bd reported another writer's lock, 'bd-timeout' when it reported
   * the beads server failed), else 'other'.
   */
  async function depscore(dispatch, { label, phase, script, repo, tail, file }) {
    let rest
    try {
      rest = [...(repo ? ['-C', repo] : []), '--relay', file, ...shellWords(tail)]
    } catch (err) {
      return { error: `${label}: ${String((err && err.message) || err)}`, cause: 'other' }
    }
    const r = await exec(dispatch, { label, phase, command: pythonLine(script, rest), file, readRunner: script.replace(/[^/]+$/, 'relayrun.py') })
    if (!r.ok) return { error: r.error, noResult: !!r.noResult, cause: 'relay' }
    if (r.exit !== 0 || r.view.error) {
      const raw = String(r.view.error || `depscore.py exited ${r.exit}`)
      const exception = exceptionOf(raw)
      const cause = ['bd-timeout', 'contention'].includes(r.view.cause) ? r.view.cause : 'other'
      return { error: exception ? `${exception} (depscore.py exited ${r.exit}; full output: ${raw})` : raw, cause, exception, output: r.view, relayFile: file }
    }
    return { ...r.view, relayFile: file }
  }
  /**
   * Runs `argv` (a program and its arguments, no shell) through relayrun.py at `runner`, in `cwd`.
   * Returns { ok: true, exitCode, json, stdoutBytes, stderrBytes, stdoutTail?, stderrTail?, relayFile }
   * — json is stdout parsed when it is one JSON object (reduced to `keys` when given), else null —
   * or { ok: false, error, cause }: cause 'relay' when the result did not come back through the relay.
   */
  async function run(dispatch, { label, phase, runner, argv, cwd = null, file, keys = [], tail = 0, timeout = null }) {
    const rest = ['run', '--relay', file, ...(cwd ? ['--cwd', cwd] : []), ...(keys.length ? ['--keys', keys.join(',')] : []), ...(tail ? ['--tail', String(tail)] : []), ...(timeout ? ['--timeout', String(timeout)] : []), '--', ...argv.map(String)]
    const r = await exec(dispatch, { label, phase, command: pythonLine(runner, rest), file, readRunner: runner })
    if (!r.ok) return { ok: false, error: r.error, noResult: !!r.noResult, cause: 'relay' }
    if (r.exit !== 0) return { ok: false, error: String(r.view.error || `relayrun.py exited ${r.exit}`), cause: 'other' }
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
  // The artifact checkpoint contract, inlined by scripts/shared-blocks.mjs from its one place,
  // skills/artifact-handoff/schemas/checkpoint.schema.json. Never restate any part of it here.
  const CHECKPOINT_SCHEMA = {"$schema":"https://json-schema.org/draft/2020-12/schema","title":"Artifact checkpoint","description":"The sidecar <candidate><x-sidecarSuffix> that artifactcontract.py checkpoint|complete|submit writes and artifactcontract.py status and jsonartifact.py read. It is built from the agent-authored progress file <candidate><x-progressSuffix> ($defs/Progress) plus the binding keys. The Python types are generated from this file by scripts/generate_checkpoint_contract.py.","x-sidecarSuffix":".checkpoint","x-progressSuffix":".progress.json","x-bindingKeys":["artifactPath","schemaSha256","revision"],"x-authoredStatuses":["in-progress","blocked"],"x-operations":["validate","checkpoint","complete","submit","status"],"type":"object","additionalProperties":false,"required":["status","artifactPath","schemaSha256","revision","task","completed","remaining","artifacts"],"properties":{"status":{"enum":["in-progress","blocked","complete"]},"artifactPath":{"$ref":"#/$defs/ArtifactPath"},"schemaSha256":{"$ref":"#/$defs/Sha256"},"candidateSha256":{"$ref":"#/$defs/Sha256"},"revision":{"$ref":"#/$defs/Revision"},"task":{"$ref":"#/$defs/Progress/properties/task"},"completed":{"$ref":"#/$defs/Progress/properties/completed"},"remaining":{"$ref":"#/$defs/Progress/properties/remaining"},"artifacts":{"$ref":"#/$defs/Progress/properties/artifacts"},"reason":{"$ref":"#/$defs/Progress/properties/reason"}},"allOf":[{"if":{"properties":{"status":{"const":"complete"}}},"then":{"required":["candidateSha256"],"properties":{"remaining":{"maxItems":0}}}},{"if":{"properties":{"status":{"const":"blocked"}}},"then":{"required":["reason"],"properties":{"remaining":{"minItems":1}}}}],"$defs":{"ArtifactPath":{"description":"The absolute candidate path; a binding key.","type":"string","minLength":1},"Revision":{"description":"The input revision; a binding key.","type":"string","minLength":1},"Sha256":{"description":"Lowercase hex SHA-256 of a canonical JSON value.","type":"string","pattern":"^[a-f0-9]{64}$"},"Progress":{"description":"The agent-authored progress file <candidate><x-progressSuffix>; its keys are copied into the checkpoint.","type":"object","additionalProperties":false,"required":["task","completed","remaining","artifacts"],"properties":{"task":{"type":"string","minLength":1},"completed":{"type":"array","items":{"type":"string","minLength":1}},"remaining":{"type":"array","items":{"type":"string","minLength":1}},"artifacts":{"type":"array","items":{"type":"string","minLength":1}},"reason":{"type":"string","minLength":1}}},"StatusReport":{"description":"What the status operation reports for a candidate.","type":"object","additionalProperties":false,"required":["status"],"properties":{"status":{"enum":["incomplete","in-progress","blocked","complete-unaccepted"]},"reason":{"type":"string"},"remaining":{"$ref":"#/$defs/Progress/properties/remaining"},"artifactPath":{"$ref":"#/$defs/ArtifactPath"},"schemaSha256":{"$ref":"#/$defs/Sha256"},"revision":{"$ref":"#/$defs/Revision"},"candidateSha256":{"$ref":"#/$defs/Sha256"}}},"CommandResult":{"description":"What the validate, checkpoint, complete and submit operations print; status is absent only for submit.","type":"object","additionalProperties":false,"required":[],"properties":{"status":{"enum":["schema-valid","complete-unaccepted","in-progress","blocked","invalid"]},"artifactPath":{"$ref":"#/$defs/ArtifactPath"},"error":{"type":"string","minLength":1}}}}}
  function artifactBrief(candidate, schema, revision = '', helper) {
    if (typeof helper !== 'string' || !helper) throw new Error('artifactBrief requires the artifactcontract.py helper path')
    const suffix = CHECKPOINT_SCHEMA['x-progressSuffix']
    const operations = CHECKPOINT_SCHEMA['x-operations']
    if (typeof suffix !== 'string' || !suffix || !Array.isArray(operations) || !operations.length) throw new Error('artifactBrief: the checkpoint contract was not inlined from checkpoint.schema.json')
    const progress = `${candidate}${suffix}`
    const binding = ['--candidate', candidate, '--schema-json', canonicalJson(schema), '--revision', revision, '--progress-file', progress]
    const command = operation => ['python3', helper, operation, ...binding].map(quote).join(' ')
    return `\n\nARTIFACT CONTRACT DATA:
Candidate: ${candidate}
Progress: ${progress}
Input revision: ${revision}
${operations.map(operation => `Command ${operation}: ${command(operation)}`).join('\n')}`
  }
  async function acceptArtifact(dispatch, { label, phase, runner, candidate, file, schema, relayFile, returned = null, revision = '', keys = [], counts = [], projection = '', probe = false, recordArgv = [], researchAgent = '', researchRepo = '' }) {
    const args = ['python3', runner.replace(/[^/]+$/, 'jsonartifact.py'), '--candidate', candidate, '--final', file, '--schema-json', canonicalJson(schema), ...(revision ? ['--revision', revision] : []), ...(keys.length ? ['--keys', keys.join(',')] : []), ...(counts.length ? ['--counts', counts.join(',')] : []), ...(projection ? ['--projection', projection] : []), ...(probe ? ['--probe'] : []), ...(probe && researchAgent && researchRepo ? ['--research-agent', researchAgent, '--research-repo', researchRepo] : []), ...(!returned ? ['--recover'] : [])]
    if (!Array.isArray(recordArgv) || recordArgv.some(word => typeof word !== 'string' || !word)) return { ok: false, error: 'invalid artifact recorder argv' }
    const argv = recordArgv.length ? ['python3', runner.replace(/[^/]+$/, 'artifactpublish.py'), '--record-argv-json', canonicalJson(recordArgv), '--', ...args.slice(2)] : args
    const result = await run(dispatch, { label, phase, runner, argv, file: relayFile })
    if (!result.ok) return result
    if (result.exitCode !== 0) return { ok: false, error: `artifact validation failed: ${JSON.stringify(result.json)}`, relayFile }
    const receipt = result.json
    if (probe && receipt && receipt.blocked === true) {
      const detail = { candidate, revision, reason: String(receipt.reason || 'producer blocked'), remaining: receipt.remaining || [] }
      return { ok: false, blocked: true, resumable: true, error: `ARTIFACT_BLOCKED ${JSON.stringify(detail)}`, ...detail }
    }
    if (probe && receipt && receipt.pending === true) return { ok: true, pending: true, ...(receipt.research ? { research: receipt.research } : {}) }
    if (!receipt || typeof receipt !== 'object') return { ok: false, error: 'artifact validation printed no receipt', relayFile }
    if (recordArgv.length && receipt.recorded !== true) log(`${label}: provenance of ${file} was not recorded (${receipt.recordError || 'no reason given'}); the accepted result is used`)
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
      if (!result.ok && (result.noResult || result.paused)) return result
      if (result.ok && result.exitCode === 0 && result.json && Array.isArray(result.json.receipts)) {
        receipts = result.json.receipts
        if (Array.isArray(result.json.skipped) && result.json.skipped.length) log(`${label}: ${result.json.skipped.length} symlink(s) or special file(s) left out of the source fingerprint (listed in ${relayFile})`)
      } else {
        // The fingerprint only decides whether saved work is reused: without it, the paths alone bind the revision.
        log(`${label}: the source fingerprint failed (${result.error || JSON.stringify(result.json)}); the revision binds the paths alone`)
        receipts = files.map((artifactPath) => ({ artifactPath, format: 'unfingerprinted' }))
      }
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
// ===== SHARED BLOCK recon-contract — BEGIN (canonical: skills/artifact-handoff/schemas/recon.schema.json; edit there, then: python3 skills/artifact-handoff/scripts/gen_recon_contract.py --write and node scripts/shared-blocks.mjs --write) =====
// GENERATED by skills/artifact-handoff/scripts/gen_recon_contract.py from
// skills/artifact-handoff/schemas/recon.schema.json, the one definition of recon-<slug>.json and of the
// detailing session's reply. Never edit: change the schema, then run
// python3 skills/artifact-handoff/scripts/gen_recon_contract.py --write and node scripts/shared-blocks.mjs --write.
const RECON_SCHEMA = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "recon.schema.json", "title": "Per-repository detailing", "description": "The detailing of one repository against the approved architecture delta, saved as recon-<slug>.json in the Epic's working directory. Every delta item placed in the repository gets one status with file:line evidence, its surface, the design source of each ui item, and the upstream dependency changes.", "x-fileTemplate": "recon-{slug}.json", "x-producerRequired": ["items", "dependencyChanges"], "$ref": "#/$defs/ReconDetailing", "$defs": {"ReconStatus": {"description": "How the code on main relates to the delta item.", "enum": ["add", "modify", "remove", "done", "planned-elsewhere"]}, "WorkStatus": {"description": "The statuses that make work.", "enum": ["add", "modify", "remove"]}, "IdleStatus": {"description": "The statuses that make no work.", "enum": ["done", "planned-elsewhere"]}, "Surface": {"description": "The surface the item lives on.", "enum": ["ui", "service", "infra", "data", "unknown"], "default": "unknown"}, "DesignSource": {"description": "Where a ui item's design comes from: bundle (a single-artifact cds bundle the owner supplied packages it), cds (it changes design and no bundle packages it, so it is designed with the CDS design system) or none (it changes no design).", "enum": ["bundle", "cds", "none"], "default": "cds"}, "ArtifactKind": {"description": "The kind of cds artifact, as a bundle.json names it.", "enum": ["page", "shell", "view"], "default": "page"}, "FromAbsent": {"description": "The `from` value of an add item.", "const": "absent"}, "ToRemoved": {"description": "The `to` value of a remove item.", "const": "removed"}, "ReconDetailing": {"description": "The saved detailing of one repository.", "type": "object", "additionalProperties": false, "required": ["items"], "properties": {"items": {"description": "One entry per delta item placed in this repository.", "type": "array", "items": {"$ref": "#/$defs/ReconItem"}}, "evidenceSummary": {"description": "A short summary of the evidence read.", "type": "string"}, "uiAuthority": {"description": "The design source of each ui item; empty values when the repository holds no UI.", "$ref": "#/$defs/UiAuthority"}, "dependencyChanges": {"description": "Whether an upstream contract, shared schema, event, library version or interface the delta assumes has changed in a way that invalidates it.", "$ref": "#/$defs/DependencyChanges"}}}, "ReconItem": {"description": "The detailing of one placed delta item.", "type": "object", "additionalProperties": false, "required": ["id", "element", "status", "evidence", "surface"], "properties": {"id": {"description": "The placed delta item id.", "type": "string", "minLength": 1}, "element": {"description": "The element the delta shows.", "type": "string", "minLength": 1}, "status": {"description": "How the code on main relates to the item.", "$ref": "#/$defs/ReconStatus"}, "from": {"description": "What the code holds now; the literal value absent for an add item.", "type": "string"}, "to": {"description": "What the code must hold; the literal value removed for a remove item.", "type": "string"}, "evidence": {"description": "Each entry a file:line on main you read, followed by what it shows; required for every status.", "type": "array", "minItems": 1, "items": {"type": "string", "pattern": "[^\\s:]+:\\d+"}}, "plannedBy": {"description": "The id of the open bead that plans the change; for planned-elsewhere only, null otherwise.", "type": ["string", "null"]}, "surface": {"description": "The surface the item lives on.", "$ref": "#/$defs/Surface"}}, "allOf": [{"if": {"required": ["status"], "properties": {"status": {"const": "add"}}}, "then": {"properties": {"from": {"$ref": "#/$defs/FromAbsent"}}}}, {"if": {"required": ["status"], "properties": {"status": {"const": "remove"}}}, "then": {"properties": {"to": {"$ref": "#/$defs/ToRemoved"}}}}, {"if": {"required": ["status"], "properties": {"status": {"const": "planned-elsewhere"}}}, "then": {"required": ["plannedBy"], "properties": {"plannedBy": {"type": "string", "minLength": 1}}}, "else": {"properties": {"plannedBy": {"type": "null"}}}}]}, "UiAuthority": {"description": "The design source of each ui item.", "type": "object", "additionalProperties": false, "required": ["uiItems"], "properties": {"uiItems": {"description": "One entry per ui item.", "type": "array", "items": {"$ref": "#/$defs/UiItem"}}, "mocksDir": {"description": "The mocks directory consulted, or null.", "type": ["string", "null"]}, "artifactsConsulted": {"description": "Every design artifact path opened.", "type": "array", "items": {"type": "string"}}}}, "UiItem": {"description": "The design source of one ui item.", "type": "object", "additionalProperties": false, "required": ["item", "designSource"], "properties": {"item": {"description": "The placed item id.", "type": "string", "minLength": 1}, "designSource": {"description": "Where the item's design comes from.", "$ref": "#/$defs/DesignSource"}, "reason": {"description": "One sentence: which bundle packages it, or why it is designed with CDS or changes no design.", "type": "string"}, "artifact": {"description": "The artifact the item builds; required for bundle and cds, null for none.", "anyOf": [{"type": "null"}, {"$ref": "#/$defs/UiArtifact"}]}, "bundle": {"description": "Bundle only: the bundle directory exactly as depscore.py cds-bundles lists it.", "type": ["string", "null"]}, "buildSpec": {"description": "Bundle only: the build-spec.md path exactly as depscore.py cds-bundles lists it.", "type": ["string", "null"]}, "sections": {"description": "Bundle only: Section IDs (S1, S2, ...) from the build spec's Sections table; empty means the whole artifact.", "type": "array", "items": {"type": "string"}}}, "allOf": [{"if": {"required": ["designSource"], "properties": {"designSource": {"const": "none"}}}, "then": {"properties": {"artifact": {"type": "null"}}}, "else": {"required": ["artifact"], "properties": {"artifact": {"$ref": "#/$defs/UiArtifact"}}}}, {"if": {"required": ["designSource"], "properties": {"designSource": {"const": "bundle"}}}, "then": {"required": ["bundle", "buildSpec"], "properties": {"bundle": {"type": "string", "minLength": 1}, "buildSpec": {"type": "string", "minLength": 1}}}, "else": {"properties": {"bundle": {"type": "null"}, "buildSpec": {"type": "null"}, "sections": {"maxItems": 0}}}}]}, "UiArtifact": {"description": "A cds artifact, as a bundle.json names it.", "type": "object", "additionalProperties": false, "required": ["kind", "slug"], "properties": {"kind": {"description": "The artifact kind.", "$ref": "#/$defs/ArtifactKind"}, "slug": {"description": "Lower-case words joined by hyphens.", "type": "string", "pattern": "^[a-z0-9]+(-[a-z0-9]+)*$"}}}, "DependencyChanges": {"description": "The upstream dependency changes that bear on the delta.", "type": "object", "additionalProperties": false, "required": ["current"], "properties": {"current": {"description": "True when no upstream change invalidates the delta.", "type": "boolean"}, "changeFindings": {"description": "One entry per upstream change that invalidates the delta.", "type": "array", "items": {"$ref": "#/$defs/ChangeFinding"}}, "evidence": {"description": "Under 60 words: what was checked.", "type": "string"}}}, "ChangeFinding": {"description": "One upstream change that invalidates the delta.", "type": "object", "additionalProperties": false, "required": ["dependency", "change", "invalidates"], "properties": {"dependency": {"description": "The dependency that changed.", "type": "string"}, "change": {"description": "What changed.", "type": "string"}, "invalidates": {"description": "What in the delta it invalidates.", "type": "string"}}}, "ReconReply": {"description": "What the detailing session returns: no item content.", "type": "object", "additionalProperties": false, "required": ["itemCount"], "properties": {"itemCount": {"description": "The number of entries in items.", "type": "integer"}, "error": {"description": "What failed, when anything failed.", "type": "string"}}}}}
const RECON_REPLY_SCHEMA = {"description": "What the detailing session returns: no item content.", "type": "object", "additionalProperties": false, "required": ["itemCount"], "properties": {"itemCount": {"description": "The number of entries in items.", "type": "integer"}, "error": {"description": "What failed, when anything failed.", "type": "string"}}}
const reconEnum = (name) => Object.freeze([...RECON_SCHEMA.$defs[name].enum])
const RECON_STATUSES = reconEnum('ReconStatus')
const RECON_WORK_STATUSES = reconEnum('WorkStatus')
const RECON_IDLE_STATUSES = reconEnum('IdleStatus')
const RECON_SURFACES = reconEnum('Surface')
const DESIGN_SOURCES = reconEnum('DesignSource')
const reconConstName = (v) => v.toUpperCase().replace(/[^A-Z0-9]+/g, '_')
const DESIGN_SOURCE = Object.freeze(Object.fromEntries(DESIGN_SOURCES.map((v) => [reconConstName(v), v])))
const ARTIFACT_KINDS = reconEnum('ArtifactKind')
const RECON_FROM_ABSENT = RECON_SCHEMA.$defs.FromAbsent.const
const RECON_TO_REMOVED = RECON_SCHEMA.$defs.ToRemoved.const
/** The detailing file name of one repository, from the schema's file template. */
const reconFileName = (slug) => {
  if (typeof slug !== 'string' || !slug || slug !== slug.trim() || slug.includes('/')) {
    const got = JSON.stringify(slug)
    throw new Error(`recon slug must be a non-empty name with no path separator, got ${got}`)
  }
  return RECON_SCHEMA['x-fileTemplate'].replace('{slug}', slug)
}
/** The detailing's fields as prompt text, rendered from RECON_SCHEMA so no prompt restates them. */
const reconFieldList = () => {
  const defs = RECON_SCHEMA.$defs
  const refName = (node) => (node && typeof node.$ref === 'string' ? node.$ref.split('/').pop() : null)
  const resolve = (node) => (refName(node) ? resolve(defs[refName(node)]) : node)
  const describe = (node) => {
    const name = refName(node)
    const n = resolve(node)
    if (n.anyOf) return n.anyOf.map(describe).join(' or ')
    if (n.enum) return n.enum.join(' | ')
    if (n.const !== undefined) return JSON.stringify(n.const)
    if (n.type === 'object') return name ? `${name} object` : 'object'
    if (n.type === 'array') return `list of ${describe(n.items)}`
    const t = Array.isArray(n.type) ? n.type.join(' or ') : n.type
    return n.pattern ? `${t} matching ${n.pattern}` : t
  }
  const objectOf = (node) => {
    const n = resolve(node)
    if (n.type === 'object') return n
    if (n.type === 'array') return objectOf(n.items)
    if (n.anyOf) return n.anyOf.map(objectOf).find(Boolean) || null
    return null
  }
  const lines = []
  const walk = (obj, depth, required) => {
    for (const [key, raw] of Object.entries(obj.properties || {})) {
      const description = raw.description || resolve(raw).description || ''
      const need = required.includes(key) ? 'required' : 'optional'
      lines.push(`${'  '.repeat(depth)}- \`${key}\` (${describe(raw)}, ${need}): ${description}`)
      const child = objectOf(raw)
      if (child) walk(child, depth + 1, child.required || [])
    }
  }
  const root = defs.ReconDetailing
  walk(root, 0, [...new Set([...(root.required || []), ...(RECON_SCHEMA['x-producerRequired'] || [])])])
  return lines.join('\n')
}
// ===== SHARED BLOCK recon-contract — END =====

const dispatchFailures = []
function dispatchDeaths(...phases) {
  const named = phases.filter(Boolean)
  return named.length ? dispatchFailures.filter((f) => named.includes(f.phase)) : dispatchFailures.slice()
}
// Runs agent(); returns its result, or null after recording the failure in dispatchFailures.
async function settleAgent(prompt, opts) {
  if (dispatchInterruption) return null
  const o = opts || {}
  const who = { agentType: o.agentType || null, label: o.label || null, phase: o.phase || null }
  const name = who.label || who.agentType || 'agent'
  try {
    const out = await fableAgent(prompt, o)
    if (out) return out
    dispatchFailures.push({ ...who, outcome: 'skipped', note: `${name} returned nothing` })
    log(`${name}: returned nothing`)
  } catch (err) {
    captureDispatchInterruption(err, (opts && (opts.label || opts.agentType)) || 'agent')
    const message = String((err && err.message) || err).slice(0, 300)
    dispatchFailures.push({ ...who, outcome: 'threw', message, note: `${name} ended without a structured result: ${message}` })
    log(`${name}: ended without a structured result — ${message}`)
  }
  return null
}

// args: {
//   prd: { id?, title?, path?, repoPath? }, repos: [<the one repository>],
//   items: [{ id, element, views? }] (the delta items placed in this repository),
//   delta: { targetDir, deltaDir },
//   mocksDir?, packagesDir?, shellsDir? (packagesDir holds zero or more single-artifact cds bundles; absent or empty supplies none), dependencies?: string[], uiRepo?: boolean (false skips the cds UI resolution),
//   artifacts: { dir, relDir?, epicId, script, phase, inputs?, slug } (required: the detailing lives only in the file reconFileName(slug) names),
//   depscore: <absolute path of depscore.py> (required: recon-facts reads the saved detailing),
//   replay?: { files: { recon: <absolute path of a saved result> } }
// }
// returns { ok, resumed?, reconPath, itemCount, counts, work, idle, uiWork, bundles, mocksDir,
//           dependenciesCurrent, dependencyFindings, ledger } — facts only; the items are in reconPath
//   or { ok: false, stage, headline, reason, reconPath?, failedItems?, dispatchFailed? }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const prdInput = a.prd && typeof a.prd === 'object' ? a.prd : {}
const prdId = prdInput.id || ''
const prdTitle = prdInput.title || ''
const hasText = (v) => typeof v === 'string' && v.trim().length > 0
const repoPath = prdInput.repoPath || a.repoPath || ''
const repos = (Array.isArray(a.repos) && a.repos.length ? a.repos : [repoPath]).filter((r) => hasText(r))
const dependencies = Array.isArray(a.dependencies) ? a.dependencies : []
const repoRoot = hasText(repoPath) ? repoPath.replace(/\/+$/, '') : ''
const uiCheck = a.uiRepo !== false
const mocksDir = uiCheck && hasText(a.mocksDir) ? a.mocksDir.trim() : ''
const packagesDir = uiCheck && hasText(a.packagesDir) ? a.packagesDir.trim() : ''
const shellsDir = uiCheck && hasText(a.shellsDir) ? a.shellsDir.trim() : ''
const delta = a.delta && typeof a.delta === 'object' ? a.delta : {}
const placed = (Array.isArray(a.items) ? a.items : []).filter((i) => i && hasText(i.id) && hasText(i.element))

function artifactsFrom(x) {
  if (!x || typeof x !== 'object') return null
  return ['dir', 'script', 'epicId', 'phase'].every((k) => typeof x[k] === 'string' && x[k]) ? x : null
}
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
const ART = artifactsFrom(a.artifacts)
const artSlug = ART && hasText(ART.slug) ? ART.slug : null
const reconPath = ART && artSlug ? `${ART.dir}/${reconFileName(artSlug)}` : null
const depscorePath = hasText(a.depscore) && a.depscore.trim().startsWith('/') ? a.depscore.trim() : null
const replayFile = a.replay && a.replay.files && a.replay.files.recon
const replayPath = typeof replayFile === 'string' && replayFile.startsWith('/') ? replayFile : null

/**
 * The approved target's documents as a prompt sentence. The documents are deduplicated: a partial
 * change has target views and a delta folder of the change alone; an entirely new architecture has
 * target views that are also its delta; no architecture change has one set, the effective views the
 * target's baseline.json cites, and no delta. Build items then come from the future set's gaps
 * against the code on main, never from an architecture delta.
 */
const targetDocs = (t) => {
  const change = t && hasText(t.architectureChange) ? t.architectureChange : hasText(t && t.deltaDir) ? 'partial' : 'none'
  if (change === 'partial' && hasText(t.deltaDir)) return `THIS PRD'S APPROVED TARGET is ${t.targetDir}, and the change alone, its delta, is ${t.deltaDir}.`
  if (change === 'new') return `THIS PRD'S APPROVED TARGET is ${t.targetDir}: an entirely new architecture, with no current set, so its target views are both the future and the delta (there is no delta folder). Its baseline.json lists the implementation gaps against the code on \`main\`.`
  return `THIS PRD'S APPROVED TARGET is ${t.targetDir}: no architecture change, so current and future are the same and there is no delta. The future set is the effective views its baseline.json cites (\`entries[].documents\`); the build work is the gaps between those views and the code on \`main\` (\`implementationWork\` in baseline.json, and the prerequisites in the architecture closure beside it, the file the artifact-handoff skill's epic-contracts.md#closure defines).`
}
const refuse = (why) => ({ ok: false, stage: 'input', deterministicFailure: true, headline: `Detailing refused its input: ${why}`, reason: why, error: why })
if (!repos.length) return dispatchOutcome(refuse('no repository was supplied to detail'))
if (repos.length > 1) log(`detailing is scoped to one repository; ${repos[0]} is detailed and ${repos.slice(1).join(', ')} ignored`)
if (!hasText(delta.targetDir) && !hasText(delta.deltaDir)) return dispatchOutcome(refuse('no approved target supplied: delta.targetDir names the documents the items come from'))
if (!placed.length) return dispatchOutcome(refuse(`no delta item is placed in ${repos[0]}`))
if (!reconPath) return dispatchOutcome(refuse(`no artifact directory and slug were supplied for ${repos[0]}: the detailing exists only as ${reconFileName('<slug>')} in the Epic's artifact directory, which the sessions downstream read by path`))
if (!depscorePath) return dispatchOutcome(refuse('no absolute depscore.py path was supplied in `depscore`: depscore.py recon-facts reads the saved detailing'))

phase('Detailing')

/** The relay runner for any program other than depscore.py: relayrun.py beside depscore.py. */
const RELAY_RUNNER = depscorePath.replace(/[^/]+$/, 'relayrun.py')
/** This repository's relay files, under the Epic's artifact directory, numbered so a run's names are deterministic. */
const RELAY_DIR = `${ART.dir}/relay/detailing-${artSlug}`
let relaySeq = 0
function relayFile(label) {
  relaySeq += 1
  return `${RELAY_DIR}/${String(relaySeq).padStart(3, '0')}-${String(label).replace(/[^A-Za-z0-9._-]+/g, '-')}.json`
}
/** Runs depscore.py recon-facts on a saved detailing through the checked relay; returns { facts } or { error } naming the file. */
async function readFacts(file, label) {
  const out = await relayKit.depscore(settleAgent, {
    label,
    phase: 'Detailing',
    script: depscorePath,
    repo: null,
    tail: `recon-facts --file ${shq(file)} --items ${shq(placed.map((i) => i.id).join(','))}`,
    file: relayFile(label),
  })
  if (out.error) return { error: String(out.error).trim().slice(0, 600), ...(out.noResult ? { dispatchFailed: true } : {}) }
  if (typeof out.ok !== 'boolean') return { error: `depscore.py recon-facts printed no verdict for ${file}` }
  const { relayFile: _relay, ...facts } = out
  return { facts }
}
/** Returns the failure a step stopped on, with the stage and a headline naming the file. */
function stopped(stage, headline, extra) {
  log(headline)
  return { ok: false, stage, headline, reason: headline, error: headline, reconPath: (extra && extra.file) || reconPath, ...(extra || {}) }
}
/** Returns the failure for a detailing that was read but is not usable. */
function unusable(f, file, stage, after) {
  const what = hasText(f.problem) ? f.problem : 'it is not a detailing'
  return stopped(stage, `The detailing of ${repos[0]} in ${file} is not usable — ${what}${after || ''}`, {
    file,
    deterministicFailure: true,
  })
}

let facts = null
let resumed = false
if (replayPath) {
  const read = await readFacts(replayPath, 'replay:recon-facts')
  if (read.error || read.facts.ok !== true) {
    log(`The saved detailing ${replayPath} of ${repos[0]} could not be replayed (${read.error || read.facts.problem || 'not usable'}); ${repos[0]} is detailed again`)
  } else {
    facts = read.facts
    resumed = true
    log(`Detailing replayed from ${replayPath} (${facts.itemCount} item(s), ${facts.bytes} bytes on disk)`)
  }
}

/** Lists the cds bundles packagesDir supplies with depscore.py cds-bundles; returns { bundles } or { error }. */
async function listBundles() {
  if (!uiCheck || !packagesDir) return { bundles: [] }
  const out = await relayKit.depscore(settleAgent, {
    label: 'detail:cds-bundles',
    phase: 'Detailing',
    script: depscorePath,
    repo: null,
    tail: `cds-bundles --packages-dir ${shq(packagesDir)}`,
    file: relayFile('detail:cds-bundles'),
  })
  if (out.error) return { error: String(out.error).trim().slice(0, 600), ...(out.noResult ? { dispatchFailed: true } : {}) }
  if (!Array.isArray(out.bundles)) return { error: 'depscore.py cds-bundles printed no bundle list' }
  return { bundles: out.bundles.filter((b) => b && hasText(b.path) && hasText(b.buildSpec)) }
}
let bundles = []
if (!facts && uiCheck) {
  const listed = await listBundles()
  if (listed.error) log(`The cds bundles in ${packagesDir} could not be listed for ${repos[0]} (${listed.error}); no bundle is supplied, so UI items are designed with CDS`)
  bundles = listed.error ? [] : listed.bundles
  log(`Detailing of ${repos[0]}: ${bundles.length} supplied cds bundle(s)${packagesDir ? ` in ${packagesDir}` : ' (no packages directory)'}`)
}
const bundleLines = bundles
  .map((b) => `  - ${b.kind} \`${b.slug}\`${b.shell && b.shell.name ? ` (in shell ${b.shell.name})` : ''}, created ${b.createdAt}\n      bundle: ${b.path}\n      build spec: ${b.buildSpec}${b.buildSpecExists === false ? ' (MISSING on disk)' : ''}\n      design: ${b.design}\n      styles: ${b.styles}`)
  .join('\n')

const itemLines = placed
  .map((i) => i.kind === 'prerequisite'
    ? `- ${i.id}: ${i.element} — a prerequisite the delta's work rests on (${i.state}); the delta does not change it, so these effective views say what it must be: ${(Array.isArray(i.views) ? i.views : []).join('; ')}${hasText(i.closure) ? `\n    closure entry and its evidence: ${i.closure}` : ''}`
    : `- ${i.id}: ${i.element}${Array.isArray(i.views) && i.views.length ? `\n    delta views: ${i.views.join('; ')}` : ''}`)
  .join('\n')
const prdLine = `PRD ${prdId}${prdTitle ? `: ${prdTitle}` : ''}`.trim()

const inputs = (Array.isArray(ART.inputs) ? ART.inputs : []).filter(hasText)
/** Records the saved detailing with the artifact script's `record` through the checked relay; returns { ok } or { error }. */
async function recordDetailing() {
  const argv = ['python3', ART.script, 'record', reconPath, '--epic', ART.epicId, '--phase', ART.phase, ...(inputs.length ? ['--inputs', ...inputs] : [])]
  const r = await relayKit.run(settleAgent, { label: 'detail:record', phase: 'Detailing', runner: RELAY_RUNNER, argv, file: relayFile('detail:record'), keys: ['sha256', 'bytes'], tail: 20 })
  if (!r.ok) return { error: r.error, ...(r.noResult ? { dispatchFailed: true } : {}) }
  if (r.exitCode !== 0) return { error: `the record command exited ${r.exitCode}: ${String(r.stderrTail || r.stdoutTail || '').trim().slice(0, 600)}` }
  return { ok: true }
}
const session = facts ? null : await settleAgent(
  `DETAIL an approved architecture delta for ONE repository: for each delta item placed in it, compare what the delta says the element becomes with what the code on the repository's \`main\` holds today, and give the item one status. You are READ-ONLY: read and search, change nothing anywhere, and write no document other than the one result file named at the end of this brief. Two checks, one pass — both go in that file.

═══ CHECK 1 — the detailing ═══

${prdLine}

THE REPOSITORY — this run is scoped to it, and only it:
  ${repos[0]}
Read its code as committed on \`main\` (\`git -C <repo> grep -n <term> main\`, \`git -C <repo> show main:<path>\`). Do not survey other repositories.

${targetDocs({ ...delta, targetDir: delta.targetDir || '(the folder above the delta)' })} What the delta views (or the views an item cites) say about an element is what it becomes; read the target views where a delta view needs their context.

THE ITEMS PLACED IN THIS REPOSITORY (each one element the delta shows):
${itemLines}

Give every item above exactly one entry, with one status from the detailing schema (${RECON_STATUSES.join(' | ')}); the schema's field descriptions, listed at the end of this brief, say what each field holds. Choose a status that makes work (${RECON_WORK_STATUSES.join(' | ')}) when the code on \`main\` must change: the element is missing (its \`from\` is ${JSON.stringify(RECON_FROM_ABSENT)}), it is held and the delta changes it, or the delta removes it (its \`to\` is ${JSON.stringify(RECON_TO_REMOVED)}). Choose a status that makes no work (${RECON_IDLE_STATUSES.join(' | ')}) when the code on \`main\` already holds the element as the delta shows it (\`from\` and \`to\` are both that state), or when an open bead of another Epic (a Story or Task planned and not built) already plans this change: name that bead in \`plannedBy\` (read beads with \`atw-bd list\`, \`atw-bd show\`, \`atw-bd search\` only).

SOURCE EVIDENCE HANDOFF. ${hasText(a.surveyPath) ? `Use relevant entries from the existing survey ${a.surveyPath}, including its evidenceRefs (path, heading, repo, revision, url; unused fields empty).` : 'No survey path was supplied; use the target/delta and bounded source evidence, identifying any unknowns.'} Resolve the exact main commit in this repository once and retain it with the repository path and file:line in each item's existing evidence strings, linked to that item's id and the originating claim/coverage or TRD requirement IDs when supplied. Keep cited document headings or URL/retrieval revision when relevant. Reuse unchanged evidence sufficient for the status; before another read, name the changed revision, unsupported claim or unanswered question in that item's from/evidence. When main changed, check the cited files/integration dependencies that can affect that item; do not resurvey unrelated source. Legacy citations without a revision require a targeted freshness check, not a fabricated commit. Preserve existing working/stub/absent/unknown distinctions and historical evidence.

Cite evidence for every status in \`evidence\`: a \`file:line\` on \`main\` you read. For a missing element, cite the file and line where it attaches (the route table, the stack, the module that will hold it). An item another bead plans carries that bead's id in \`plannedBy\` and, like every status, a \`file:line\`: where the planned change attaches in the code on \`main\`. An item with no citation fails the run.

EXISTING CODE IS EVIDENCE TO INSPECT, NOT AN ASSUMPTION OF CORRECTNESS. In this same read-only pass, follow the relevant entrypoint into the implementation, its consumed/published contracts, configuration and focused tests. Reuse supplied survey citations to narrow the reading; do not resurvey the fleet. In each item's existing \`from\` and \`evidence\`, distinguish behavior supported by the inspected path from incomplete wiring, stubs, absence and unresolved behavior. Name what the tests assert and their limits: reading a mocked test is not a passing test or live-runtime proof. A matching name, import, class, file or mock is not enough for \`done\`. Use \`modify\` for an existing element with an evidenced gap, and \`add\` for a missing element at its cited attachment point. If a material unknown prevents choosing a status, report that uncertainty as an error rather than inventing completeness or replacement work. Preserve verified parts and compatible published contracts; justify any necessary replacement from requirements and concrete evidence. An existing repository is the implementation home unless the approved architecture explicitly establishes a different owner; the presence of a PRD or missing implementation alone does not require a new repository, service or product feature.

Also classify the SURFACE each item lives on, in \`surface\`: ${RECON_SURFACES.join(' | ')}.

${uiCheck ? `═══ EVERY UI ITEM TAKES ONE DESIGN SOURCE ═══

For every item on the user-interface surface, decide its design source (${DESIGN_SOURCES.join(' | ')}) from the delta and the code. ${RECON_SCHEMA.$defs.DesignSource.description} A supplied bundle is the target state: its \`spec/build-spec.md\` together with its composed \`design/<kind>.html\` and its own \`styles/\`. A design change is layout, components, styles, visual states, or a new screen; copy or label text, or data wired into an existing element without changing how it looks, changes no design and is built like any other code change.

THE SUPPLIED cds BUNDLES — each packages exactly one artifact; the newest of a kind and slug is
listed, older ones are not supplied:
${bundleLines || `  (none: no bundle is supplied, so no item takes ${DESIGN_SOURCE.BUNDLE})`}

Match an item to a bundle only when the bundle packages the artifact that item builds: read the
bundle's build spec and design, and the approved target/delta views with their scoped design
references (linked source views included). The PRD (${hasText(prdInput.path) ? prdInput.path : 'no PRD path supplied'})
may name a visual reference that helps identify the artifact; it carries no package paths.
Use only the bundles listed above, at the paths listed. Do not package, copy or regenerate a
bundle, and do not cite a directory that is not listed. When no listed bundle packages the
item, it takes ${DESIGN_SOURCE.CDS} or ${DESIGN_SOURCE.NONE}, decided by whether it changes design.

The loose composed artifacts may help you understand the existing design; they are not
supplied mockups and never make an item take ${DESIGN_SOURCE.BUNDLE}:
${mocksDir ? `  composed pages and views: ${mocksDir}` : '  composed pages and views: (no directory supplied)'}
${shellsDir ? `  composed shells: ${shellsDir}` : '  composed shells: (no directory supplied)'}

Record each user-interface item's design source in the detailing's ui authority, with the
fields the detailing schema lists at the end of this brief. The artifact an item builds is the
Page, Shell or View named as a cds bundle's \`bundle.json\` names it (kind ${ARTIFACT_KINDS.join(' | ')}): for an item a
listed bundle packages, that bundle's kind and slug; for an item designed with CDS, the slug a
bundle of that artifact would carry: the artifact's name in lower-case words joined by hyphens,
matching an existing composed artifact's slug where one exists. A mockup can arrive any time
before the Task is built: the build looks for a bundle of this artifact then. Copy a bundle's
directory and build spec exactly as listed; its Section IDs are those in the build spec's
Sections table that the item builds. The Spec cites these and every Task that builds the item
carries them in its build contract.` : `═══ THIS REPOSITORY HOLDS NO UI ═══

Its items take no design source and the ui authority stays empty.`}

═══ SEARCH BUDGET ═══

Work item by item and stop searching for each the moment its status is settled. Cover every
item once before you deepen any of them, and when the budget is spent, stop and return your
structured output with what you have.

═══ CHECK 2 — upstream dependency changes ═══

Upstream dependencies the work relies on:
${dependencies.length ? dependencies.map((d, i) => `${i + 1}. ${d}`).join('\n') : '(none declared in args — discover them from the repository\'s manifests, lockfiles and imports)'}

Determine whether any upstream contract, shared schema, event, library version, or interface the delta assumes has changed in a way that invalidates it. Check the dependencies THIS repository consumes, as its manifests, lockfiles and imports on \`main\` show them, and record what you find in the detailing's dependency changes.

═══ THE RESULT IS A FILE, NOT YOUR REPLY ═══

1. Write your whole detailing, as ONE JSON object that validates against the artifact-handoff skill's \`schemas/recon.schema.json\`, to ${reconPath} with the Write tool, replacing the file if it exists (Read it first if the Write tool asks you to). Write no other file. Its fields, rendered from that schema:
${reconFieldList()}
2. Return ONLY the reply the detailing schema defines (its \`ReconReply\`). Do NOT return the detailing itself: the workflow records and checks the file on disk, and every session after you reads it by its path.`,
  {
    label: 'detail:delta-and-dependencies',
    phase: 'Detailing',
    effort: 'medium',
    agentType: 'prd-reality-reconciler',
    schema: RECON_REPLY_SCHEMA,
  }
)

if (!facts) {
  if (!session) {
    const deaths = dispatchDeaths('Detailing')
    return dispatchOutcome(stopped('detailing', `The detailing session for ${repos[0]} returned nothing, so the repository was not detailed (${deaths.map((f) => f.note).join('; ') || 'no dispatch was recorded'}).`, {
      dispatchFailed: true,
      dispatchFailures: deaths,
    }))
  }
  const recorded = await recordDetailing()
  if (recorded.error) log(`The detailing of ${repos[0]} in ${reconPath} was not recorded: ${recorded.error}`)
  const read = await readFacts(reconPath, 'detail:recon-facts')
  if (read.error) {
    return dispatchOutcome(stopped('detailing-read', `The detailing of ${repos[0]} was saved to ${reconPath} but could not be read back: ${read.error}.`, {
      ...(read.dispatchFailed ? { dispatchFailed: true, dispatchFailures: dispatchDeaths('Detailing') } : {}),
    }))
  }
  if (read.facts.ok !== true) return dispatchOutcome(unusable(read.facts, reconPath, 'detailing'))
  facts = read.facts
  if (Number(session.itemCount) !== Number(facts.itemCount)) log(`Detailing of ${repos[0]}: the session reported ${session.itemCount} item(s) and ${reconPath} holds ${facts.itemCount}; the file governs.`)
}

const ids = (v) => (Array.isArray(v) ? v.filter(hasText).map((x) => x.trim()) : [])
const counts = Object.fromEntries(RECON_STATUSES.map((s) => [s, Number((facts.counts || {})[s]) || 0]))
const work = ids(facts.work)
const idle = (Array.isArray(facts.idle) ? facts.idle : [])
  .filter((x) => x && hasText(x.id))
  .map((x) => ({ id: x.id.trim(), status: hasText(x.status) ? x.status.trim() : '', plannedBy: hasText(x.plannedBy) ? x.plannedBy.trim() : null }))
const uiWork = (Array.isArray(facts.uiWork) ? facts.uiWork : [])
  .filter((u) => u && hasText(u.id))
  .map((u) => ({
    id: u.id.trim(),
    designSource: hasText(u.designSource) ? u.designSource.trim() : null,
    artifact: u.artifact && hasText(u.artifact.kind) && hasText(u.artifact.slug) ? { kind: u.artifact.kind.trim(), slug: u.artifact.slug.trim() } : null,
    bundle: hasText(u.bundle) ? u.bundle.trim() : null,
    buildSpec: hasText(u.buildSpec) ? u.buildSpec.trim() : null,
    sections: ids(u.sections),
  }))
const detailingFile = resumed ? replayPath : reconPath

log(`Detailing of ${repos[0]} (${detailingFile}): ${facts.itemCount} item(s) — ${RECON_STATUSES.map((s) => `${counts[s]} ${s}`).join(', ')}.`)

return dispatchOutcome({
  ok: true,
  ...(resumed ? { resumed: true } : {}),
  reconPath: detailingFile,
  itemCount: Number(facts.itemCount) || 0,
  counts,
  work,
  idle,
  uiWork,
  bundles: [...new Set(uiWork.map((u) => u.bundle).filter(Boolean))],
  mocksDir: hasText(facts.mocksDir) ? facts.mocksDir.trim() : mocksDir || null,
  dependenciesCurrent: typeof facts.dependenciesCurrent === 'boolean' ? facts.dependenciesCurrent : null,
  dependencyFindings: Number(facts.dependencyFindings) || 0,
  ledger: {
    phase: 'prd-reconciliation',
    beadId: null,
    subject: prdId || prdTitle || null,
    chosen: ['prd-reality-reconciler'],
    mode: 'combined',
    uiCheck,
    resumed,
    reconPath: detailingFile,
    itemCount: Number(facts.itemCount) || 0,
    ...counts,
    ok: true,
  },
})
