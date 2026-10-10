export const meta = {
  name: 'prd-to-spec',
  description:
    'Composite: elaborates an existing, scored Epic and its PRD into Stories and Tasks written to beads. It starts the Epic lifecycle with depscore.py elaboration-start, runs the architecture mini for every PRD (it is never skipped: a PRD the effective version already serves gets a delta that says so), which writes the Epic\'s target and delta under target/<subject>/ and integrates the approved target into the effective version, and holds the Epic for the owner on two business requirements no design can satisfy together, or section 2 constraints the owner wrote that contradict each other or that no design can meet together with the PRD, before any Story or Task exists — lists the delta items with depscore.py arch-delta (one per element the delta shows, then one prerequisite item per element the delta\'s work rests on that the architecture step\'s Closure found absent, stale or planned by an open bead, every item with the items it requires), rules the repo span as the repositories the delta changes (the polyrepo-steward places each item, a prerequisite in the repository that deploys it, and creates the new repositories the target or a prerequisite names; a prerequisite an open bead plans is placed nowhere; a placement in the control repository or the repository holding the architecture goes back to the steward once, and is then left unplaced; a span with no repository is no implementation work), authors the TRD from the target and delta views, details per repo each placed item against the code on main (add, modify, remove, done, planned-elsewhere; a failed detailing blocks that repo\'s Spec) and authors one Spec and Story per repo for its add, modify and remove items (the session that authors the Story writes its bead with depscore.py write-story), decomposes each Story into Tasks for those items only, with a blocks edge onto an open Task of another Epic instead of a duplicate, and with the edges the items\' requires relations make written by depscore.py plan-tasks and depscore.py closure-edges, which warn about a required item with no Task, no open bead and not done (the session that decomposes it writes each Task bead with one depscore.py write-task command, in build order), derives the Task edges between Stories (the session that derives them writes every Task\'s edges with one depscore.py write-all-task-edges command), then scores the Epic and its Tasks and sets it done with depscore.py elaboration-finish once every span repository has its Story and Tasks, or nothing to build; when a repository failed the run returns ok:false at stage repositories-incomplete. Every failure carries failure: { stage, cause, repositories: [{ repository, stage, cause, headline }] }, cause one of api, quota, bd-timeout, relay, contention or other, set where the failure happens from structured fields (a dispatch interruption, the cause a depscore.py or relay result carries, a child workflow\'s failure.cause), never from a reason\'s text; the run\'s cause is transient (any but other) only when every failed repository\'s is. A transient cause releases the Epic so the next dispatch reruns only the failed steps after the supervisor\'s backoff; ordinary item failures are recorded while other eligible work continues; fatal defects stop new dispatch. Genuine owner-fact holds remain; once it is done, depscore.py arch-target-remove deletes target/<subject>/ and commits the removal. Every bead write is keyed by elab_key, so a rerun updates what exists. A Story whose saved Tasks\' inputs are unchanged keeps every Task as it is and gets only the ones not yet written; one whose inputs changed has its unstarted Task beads deleted and the full set decomposed again around the started or closed ones; the case and why are in the run ledger (event task-rerun). Returns { ok, stage, beadId, headline, detailPath } plus hierarchy, repoSpan, targetRemoval, beadsEmitted and lifecycle.',
  phases: [
    { title: 'Epic Lifecycle', detail: 'depscore.py elaboration-start: refuse with a named reason, or mark the Epic in_progress' },
    { title: 'PRD', detail: 'resolve the PRD text or path supplied by the caller' },
    { title: 'Epic', detail: "adopt the caller's Epic" },
    { title: 'Architecture', detail: 'the architecture mini writes the target and delta for the Epic and integrates the approved target into the effective version; only two business requirements no design can satisfy together, or section 2 constraints the owner wrote that contradict each other or that no design can meet together with the PRD, hold the Epic for the owner' },
    { title: 'Repo Scoping', detail: 'the polyrepo-steward places each delta item; the span is the repositories the delta changes; a placement in the control repository or the architecture repository goes back to the steward once' },
    { title: 'TRD Authoring', detail: 'author the TRD once per PRD from the target and delta views' },
    { title: 'Spec Authoring', detail: 'per repo: detail each placed delta item against the code on main, then author the Spec for its add, modify and remove items and write its Story bead' },
    { title: 'Task Decomposition', detail: 'per Story: decompose its add, modify and remove items into Tasks, each Task bead written with its edges as it is saved; then derive the Task edges between Stories and write them with one command' },
    { title: 'Finish', detail: 'depscore.py elaboration-finish: score the Epic and its Tasks; set done once every span repository has its Story and Tasks, or nothing to build, else return ok:false at stage repositories-incomplete with failure.cause (a transient cause released for a backoff retry, any other cause held for diagnosis); then depscore.py arch-target-remove deletes target/<subject>/ and commits the removal' },
    { title: 'Run Ledger', detail: 'log the run journal on every exit path' },
  ],
}
// ===== SHARED BLOCK fable — BEGIN (canonical: scripts/shared-blocks/fable.js; edit there, then: node scripts/shared-blocks.mjs --write) =====
const ownedCoreContracts = "---\nname: subagent-contract\ndescription: Bounded specialist work in direct sessions, with file outputs and independent validation.\nuser-invocable: false\n---\n\n# Direct specialist session\n\nPerform the role in your definition. The brief gives a bead, input paths, output path and outcome;\nit supplies no procedures or schema. Load the skills in your frontmatter and read the applicable\ncontract before writing. The artifact-handoff skill is the shared producer/reviewer authority.\nWrite the result file; Python handles validation, acceptance, fingerprints and pipeline state.\nDo not invoke a Workflow, another agent, a command runner, a submission helper or StructuredOutput.\nDo not create receipts, revision bindings or checkpoint sidecars. If resumed, inspect and continue\nthe existing result and input files; retain completed valid work.\n\nOnly assigned files are writable. Reviewers may write their result, never the reviewed source.\nNever write arc42 section 2, expose secrets or touch apps/marketing repositories. Never run keeper\nor supervisor. Agents do not write pipeline beads; Python owns those writes. If reading beads is\nneeded, use the central atw-bd wrapper from beads-contract. No agent creates a bug or loose Task.\nRead repository AGENTS.md before an authorized repository edit; input-only reads do not require\nloading every repository's instruction tree.\n\nMissing inputs are named dependencies, not permission to invent facts. Distinguish observed\nfacts, assumptions and unresolved questions in the artifact's supported fields. Do not mark your\nown work approved. In elaboration, repository code is evidence of current design detail only;\nthe matrix is the sole built-state record, and Python derives implementation work from it.\n\n## Resource use and incremental review\n\n- Use tokens conscientiously without compromising required correctness, completeness, safety or evidence. Before a material optional expansion, identify its unresolved need and expected benefit in existing progress. Routine tools need no justification. Do not add a report, review pass, token quota or human approval gate for this rule; omit optional work with no concrete benefit.\n- Makers and reviewers use the same applicable requirements, constraints and completion criteria. Review determines actual correctness, including passing sound work; finding more failures is not success. Do not invent requirements or turn stylistic preferences into blocking defects. Preserve necessary safety and regression checks.\n- Use the caller's finding format to identify the affected location, requirement/dependency at risk, observed evidence and actionable correction with a verifiable pass condition. Distinguish defects, missing evidence and proposed new requirements. Never claim unperformed checks passed.\n- Revise original artifacts incrementally. Retain valid work and applicable evidence. Rereview changed scope and affected dependencies; reopen accepted work only when new evidence or demonstrated impact invalidates its earlier evidence, and state why. Preserve required independent review.\n\n## Technical gaps are decided, not escalated\n\nWhere the approved or effective architecture, a requirement or an owner answer is silent, unclear or self-contradictory on a technical matter, decide it by best practice, with AWS Well-Architected guidance and AWS documentation as the evidence (see AWS evidence authority below). Record the decision, the gap it closes and its cited evidence in your result, and continue. A technical matter is any question of how the system works: services, patterns, interfaces, data, values and limits, security and privacy controls, cost and operations. A recorded decision is a claim reviewers check like any other; it is not an open item.\n\nOwner-only facts (credentials, money and destructive actions outside AWS dev), irreconcilable business requirements and section 2 conflicts go through the caller's owner channel. Technical choices remain with the specialists. Never put a technical question to the owner or any person, and never hold work waiting for a technical answer.\n\n## The approved architecture is authoritative\n\nThe approved (effective) architecture and the owner's answers are authoritative. Older documents, repository READMEs and existing code are evidence of the current state: they show what exists and what still has to change, never that the approved architecture or an owner answer is wrong. Where they disagree with the approved architecture, the approved architecture holds and the difference is work to plan, not a conflict to raise. The approved architecture changes only through a reviewed target backed by requirements and evidence, or a reviewed correction from what a Story built.\n\n## AWS evidence authority\n\nBefore any AWS claim, design choice or question, check the AWS MCP Server documentation tools (`search_documentation`, `read_documentation`, `retrieve_skill`) and the relevant AWS plugin skills (`aws-core:*`, for example `aws-core:aws-cdk`, `aws-core:aws-serverless`, `aws-core:aws-iam`, `aws-core:aws-networking`, `aws-core:aws-well-architected-review`), including the applicable Well-Architected principles. A question AWS documentation can answer is answered from it and never reaches the owner. Retain source references and the concrete tradeoffs. Existing generated architecture and model recollection do not establish correctness. Makers and reviewers use this same evidence criterion.\n\nApply guidance to stated requirements, deployment, usage and cost constraints rather than hypothetical scale. Where AWS guidance conflicts with a business requirement or a section 2 constraint, the requirement or constraint holds: record the conflict and the design that honours it, and do not silently substitute a preferred AWS pattern. Missing required MCP/skill access is a named blocker or uncertainty, never a passed check. Coordinators may research and route AWS questions, but cannot author or approve designs.\n"
const ownedArtifactContract = "---\nname: artifact-handoff\ndescription: Shared file contracts for direct specialist sessions; producers and consumers read the same schemas and completion rules.\n---\n\n# Direct artifact handoff\n\nRead [Epic contracts](epic-contracts.md) for the artifact assigned to this session, including its\nfields, interpretation and completion criteria. JSON schemas are in [schemas/](schemas/).\nProducers and reviewers use this same contract; a reviewer cannot add unstated requirements.\n\nThe brief contains only a bead id, labeled absolute input paths, an absolute output path, and a\none-line outcome. Read the named files yourself. Write the complete result to the exact output\npath. Write only assigned outputs and, for architecture writers, the assigned draft views.\nFor a JSON output write one strict JSON value with unique keys; for a document write nonempty\nUTF-8 Markdown. Do not paste file contents into a response. A final reply may name the result path.\n\nPython validates the file against the schema, checks declared document citations, publishes the\ncanonical JSON, and records input/output fingerprints. The agent does not accept its own result,\nwrite receipts, compute revision bindings, submit StructuredOutput, or run artifact checkpoint or\nsubmission helpers. There is no machine mode or command-runner handoff in direct sessions.\nA structurally valid artifact is not automatically a semantically correct one.\n\nOn a corrective pass, read the labeled validation-errors input and the existing output, repair the\nspecific findings and affected references, and preserve valid work. On interruption retain the\nactual files; resumption continues those files. Do not fabricate completion for missing reasoning.\nNamed missing inputs or remaining uncertainties belong in the contract's existing evidence fields;\nnever add fields to a closed schema or return a success reference for absent work.\n"
const ownedBaselineContract = "---\nname: architecture-baseline\ndescription: Assess and evolve effective architecture using one shared author, reviewer and decider standard.\n---\n\n# Architecture baseline\n\nRead [the review standard](review-standard.md) before surveying, coordinating, authoring,\nreviewing, deciding or integrating architecture. That is the common completion basis.\nRead artifact-handoff's [Epic contracts](../artifact-handoff/epic-contracts.md) and the relevant\nschema there for input and output fields. Contract correctness and architecture correctness are\nseparate: Python validates structure; independent reviewers judge claims and coverage.\n\nAn effective view is reviewed design, not evidence of implementation and not a permanent\nconstraint on future PRDs. Preserve valid design and evidence, revise what current requirements\nchange, and fill the implementation-detail gaps in the affected views. Do not redesign unrelated\nhistorical debt. No fixed specialist quota applies; the coordinator selects bounded specialties.\n\nThe survey judges design and documentation, never built-ness. Python computes implementationWork\nfrom the matrix snapshot and cited view elements. Fresh survey code.state, implementationAction\nand disposition are unknown/unknown/undetermined; legacy values are compatibility context only.\nThe Closure agent walks views, never repository code or deployments; Python classifies its\nreached elements using the matrix. A missing or unknown matrix row creates implementation work.\nOpen Tasks elsewhere add blockers; they do not remove this Epic's work.\n"
const ownedAgentContracts = {"acceptance-criteria-reviewer":{"artifactCapable":false,"agentType":"agent-teams-workforce:acceptance-criteria-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"acceptance-criteria-writer":{"artifactCapable":true,"agentType":"acceptance-criteria-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:artifact-handoff"]},"accessibility-validator":{"artifactCapable":true,"agentType":"agent-teams-workforce:accessibility-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:a11y-audit","agent-teams-workforce:senior-frontend"]},"advantage-evaluator":{"artifactCapable":false,"agentType":"agent-teams-workforce:advantage-evaluator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"adversarial-critique-adjudicator":{"artifactCapable":false,"agentType":"agent-teams-workforce:adversarial-critique-adjudicator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-security"]},"adversarial-review-loop-supervisor":{"artifactCapable":false,"agentType":"agent-teams-workforce:adversarial-review-loop-supervisor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"ambiguity-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:ambiguity-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"android-compose-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:android-compose-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:graphrag-lookup"]},"api-contract-designer":{"artifactCapable":true,"agentType":"api-contract-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:architecture-baseline"]},"api-documentation-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:api-documentation-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer"]},"api-gateway-cdk-implementer":{"artifactCapable":true,"agentType":"api-gateway-cdk-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-gateway","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"api-specification-author":{"artifactCapable":true,"agentType":"api-specification-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer","agent-teams-workforce:artifact-handoff"]},"appsync-cdk-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:appsync-cdk-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"appsync-client-subscription-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:appsync-client-subscription-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend","agent-teams-workforce:graphrag-lookup"]},"architecture-boundary-guardian":{"artifactCapable":true,"agentType":"architecture-boundary-guardian","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:architecture-baseline"]},"architecture-conformance-reviewer":{"artifactCapable":true,"agentType":"architecture-conformance-reviewer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:arc42","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:architecture-baseline"]},"architecture-decider":{"artifactCapable":true,"agentType":"architecture-decider","skills":["agent-teams-workforce:architecture-baseline","agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect"]},"architecture-decision-workflow-coordinator":{"artifactCapable":true,"agentType":"architecture-decision-workflow-coordinator","skills":["agent-teams-workforce:architecture-baseline","agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"architecture-diagram-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:architecture-diagram-author","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:architecture-diagramming","agent-teams-workforce:c4-diagramming","agent-teams-workforce:uml-diagramming","agent-teams-workforce:senior-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:architecture-baseline"]},"architecture-fitness-function-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:architecture-fitness-function-author","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"architecture-impact-analyst":{"artifactCapable":false,"agentType":"agent-teams-workforce:architecture-impact-analyst","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:beads-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:graphrag-lookup"]},"architecture-maintainer":{"artifactCapable":true,"agentType":"architecture-maintainer","skills":["agent-teams-workforce:architecture-baseline","agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:arc42","agent-teams-workforce:arc42-maintain","agent-teams-workforce:c4-diagramming","agent-teams-workforce:uml-diagramming","agent-teams-workforce:senior-architect","agent-teams-workforce:graphrag-lookup"]},"architecture-pattern-challenger":{"artifactCapable":true,"agentType":"architecture-pattern-challenger","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:architecture-baseline"]},"architecture-tradeoff-skeptic":{"artifactCapable":true,"agentType":"architecture-tradeoff-skeptic","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:architecture-baseline"]},"athena-redshift-analytics-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:athena-redshift-analytics-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:graphrag-lookup"]},"auth-bypass-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:auth-bypass-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops","agent-teams-workforce:cognito"]},"aws-integration-test-runner":{"artifactCapable":true,"agentType":"agent-teams-workforce:aws-integration-test-runner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:test-failure-mindset","agent-teams-workforce:cumulative-regression"]},"aws-integration-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:aws-integration-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:cumulative-regression"]},"beads-format-validator":{"artifactCapable":true,"agentType":"agent-teams-workforce:beads-format-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:beads-contract"]},"bedrock-integration-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:bedrock-integration-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:bedrock","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:senior-prompt-engineer","agent-teams-workforce:aws-agentic-ai","agent-teams-workforce:graphrag-lookup"]},"behavioral-signals-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:behavioral-signals-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:senior-data-scientist","agent-teams-workforce:product-analytics","agent-teams-workforce:graphrag-lookup"]},"bounded-context-mapper":{"artifactCapable":true,"agentType":"bounded-context-mapper","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:architecture-baseline"]},"brd-traceability-auditor":{"artifactCapable":true,"agentType":"agent-teams-workforce:brd-traceability-auditor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"c4-diagram-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:c4-diagram-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:architecture-diagramming","agent-teams-workforce:c4-diagramming","agent-teams-workforce:senior-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:artifact-handoff","agent-teams-workforce:architecture-baseline"]},"cdk-infrastructure-designer":{"artifactCapable":true,"agentType":"cdk-infrastructure-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming","agent-teams-workforce:architecture-baseline"]},"cdk-infrastructure-drift-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:cdk-infrastructure-drift-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:cloudformation"]},"cdk-stack-author":{"artifactCapable":true,"agentType":"cdk-stack-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:cloudformation","agent-teams-workforce:resource-naming"]},"cds-finding-reviewer":{"artifactCapable":false,"agentType":"agent-teams-workforce:cds-finding-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","cds:apply-design-system","cds:audit-against-system"]},"cds-ui-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:cds-ui-implementer","skills":["agent-teams-workforce:subagent-contract","cds:apply-design-system","cds:audit-against-system","cds:compose-page","agent-teams-workforce:graphrag-lookup"]},"changelog-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:changelog-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:changelog-generator"]},"chassis-extension-implementer":{"artifactCapable":true,"agentType":"chassis-extension-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:lambda","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"code-correctness-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:code-correctness-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:code-reviewer"]},"code-quality-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:code-quality-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"code-refactoring-specialist":{"artifactCapable":true,"agentType":"agent-teams-workforce:code-refactoring-specialist","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:code-reviewer","agent-teams-workforce:graphrag-lookup"]},"code-style-and-linting-enforcer":{"artifactCapable":true,"agentType":"agent-teams-workforce:code-style-and-linting-enforcer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:code-reviewer"]},"cognito-lambda-trigger-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:cognito-lambda-trigger-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:cognito","agent-teams-workforce:lambda","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"completeness-checker":{"artifactCapable":false,"agentType":"agent-teams-workforce:completeness-checker","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"complexity-analyzer":{"artifactCapable":false,"agentType":"agent-teams-workforce:complexity-analyzer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:tech-debt-tracker"]},"constitutional-agent":{"artifactCapable":false,"agentType":"agent-teams-workforce:constitutional-agent","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"constraint-extractor":{"artifactCapable":true,"agentType":"agent-teams-workforce:constraint-extractor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"consumer-driven-contract-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:consumer-driven-contract-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-test-suite-builder","agent-teams-workforce:cumulative-regression"]},"context-curator":{"artifactCapable":false,"agentType":"agent-teams-workforce:context-curator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"contract-violation-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:contract-violation-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-test-suite-builder"]},"cost-architecture-reviewer":{"artifactCapable":true,"agentType":"cost-architecture-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-cost-operations","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:artifact-handoff","agent-teams-workforce:architecture-baseline"]},"cost-impact-reviewer":{"artifactCapable":true,"agentType":"cost-impact-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cost-operations","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:artifact-handoff","agent-teams-workforce:architecture-baseline"]},"cross-repo-integration-test-coordinator":{"artifactCapable":false,"agentType":"agent-teams-workforce:cross-repo-integration-test-coordinator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"cross-service-contract-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:cross-service-contract-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-test-suite-builder"]},"data-consistency-checker":{"artifactCapable":true,"agentType":"agent-teams-workforce:data-consistency-checker","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb"]},"data-exposure-scanner":{"artifactCapable":true,"agentType":"agent-teams-workforce:data-exposure-scanner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"data-model-specification-author":{"artifactCapable":true,"agentType":"data-model-specification-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb","agent-teams-workforce:database-schema-designer","agent-teams-workforce:artifact-handoff"]},"data-pipeline-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:data-pipeline-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:cumulative-regression"]},"definition-of-done-enforcer":{"artifactCapable":true,"agentType":"agent-teams-workforce:definition-of-done-enforcer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"dependency-change-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:dependency-change-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dependency-auditor"]},"dependency-cve-auditor":{"artifactCapable":true,"agentType":"agent-teams-workforce:dependency-cve-auditor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dependency-auditor"]},"dependency-graph-extractor":{"artifactCapable":true,"agentType":"agent-teams-workforce:dependency-graph-extractor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"deployment-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:deployment-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"deployment-strategy-decider":{"artifactCapable":false,"agentType":"agent-teams-workforce:deployment-strategy-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:cove-prompt-design"]},"documentation-accuracy-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:documentation-accuracy-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"documentation-currency-auditor":{"artifactCapable":true,"agentType":"agent-teams-workforce:documentation-currency-auditor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"documentation-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:documentation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"domain-boundary-validator":{"artifactCapable":true,"agentType":"agent-teams-workforce:domain-boundary-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"domain-event-modeler":{"artifactCapable":true,"agentType":"domain-event-modeler","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:architecture-baseline"]},"dos-resilience-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:dos-resilience-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"dynamodb-access-layer-implementer":{"artifactCapable":true,"agentType":"dynamodb-access-layer-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"dynamodb-cost-optimizer":{"artifactCapable":true,"agentType":"dynamodb-cost-optimizer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb","agent-teams-workforce:aws-cost-operations"]},"dynamodb-schema-access-pattern-reviewer":{"artifactCapable":true,"agentType":"dynamodb-schema-access-pattern-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb"]},"dynamodb-streams-cdc-implementer":{"artifactCapable":true,"agentType":"dynamodb-streams-cdc-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:dynamodb","agent-teams-workforce:graphrag-lookup"]},"email-notification-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:email-notification-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:email-template-builder","agent-teams-workforce:sns","agent-teams-workforce:graphrag-lookup"]},"epic-sequencer":{"artifactCapable":true,"agentType":"agent-teams-workforce:epic-sequencer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:epic-sequencing"]},"espresso-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:espresso-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:tdd-guide","agent-teams-workforce:cumulative-regression"]},"event-api-client-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:event-api-client-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"event-driven-consumer-implementer":{"artifactCapable":true,"agentType":"event-driven-consumer-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:sqs","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:sns","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"event-flow-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:event-flow-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda"]},"event-schema-designer":{"artifactCapable":true,"agentType":"event-schema-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:eventbridge","agent-teams-workforce:sns","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:architecture-baseline"]},"event-schema-reviewer":{"artifactCapable":true,"agentType":"event-schema-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda"]},"failure-mode-analyst":{"artifactCapable":true,"agentType":"failure-mode-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:observability-designer","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:artifact-handoff","agent-teams-workforce:architecture-baseline"]},"filing-clerk":{"artifactCapable":true,"agentType":"filing-clerk","skills":["agent-teams-workforce:subagent-contract","obsidian:obsidian-cli","obsidian:obsidian-markdown","agent-teams-workforce:arc42","notebooklm","document-classification"]},"finops-analyst":{"artifactCapable":false,"agentType":"finops-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-cost-operations"]},"flaky-test-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:flaky-test-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:test-failure-mindset","agent-teams-workforce:find-cause"]},"frontend-performance-optimizer":{"artifactCapable":true,"agentType":"agent-teams-workforce:frontend-performance-optimizer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend"]},"github-actions-pipeline-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:github-actions-pipeline-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"glue-etl-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:glue-etl-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:graphrag-lookup"]},"graphql-schema-designer":{"artifactCapable":true,"agentType":"graphql-schema-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:architecture-baseline"]},"graphql-schema-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:graphql-schema-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer"]},"implementation-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:implementation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:graphrag-lookup"]},"incident-response-runbook-designer":{"artifactCapable":true,"agentType":"agent-teams-workforce:incident-response-runbook-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:observability-designer"]},"infrastructure-security-scanner":{"artifactCapable":true,"agentType":"infrastructure-security-scanner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops","agent-teams-workforce:aws-cdk-development"]},"injection-attack-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:injection-attack-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"integration-pattern-architect":{"artifactCapable":true,"agentType":"integration-pattern-architect","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:architecture-baseline"]},"integration-testing-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:integration-testing-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"ios-swiftui-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:ios-swiftui-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:graphrag-lookup"]},"kinesis-stream-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:kinesis-stream-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"lambda-performance-optimizer":{"artifactCapable":true,"agentType":"lambda-performance-optimizer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:lambda"]},"llm-observability-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:llm-observability-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:observability-designer","agent-teams-workforce:senior-prompt-engineer","agent-teams-workforce:aws-agentic-ai","agent-teams-workforce:graphrag-lookup"]},"matching-algorithm-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:matching-algorithm-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:graphrag-lookup"]},"mcp-server-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:mcp-server-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:mcp-server-builder","agent-teams-workforce:aws-agentic-ai","agent-teams-workforce:aws-mcp-setup","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"ml-evaluation-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:ml-evaluation-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:senior-data-scientist","agent-teams-workforce:cumulative-regression"]},"mobile-e2e-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:mobile-e2e-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"nextjs-component-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:nextjs-component-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend","agent-teams-workforce:a11y-audit","agent-teams-workforce:senior-fullstack","agent-teams-workforce:graphrag-lookup"]},"nfr-analyst":{"artifactCapable":false,"agentType":"agent-teams-workforce:nfr-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:product-discovery"]},"okr-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:okr-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-strategist","agent-teams-workforce:product-analytics"]},"openapi-contract-reviewer":{"artifactCapable":false,"agentType":"openapi-contract-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer"]},"operational-readiness-reviewer":{"artifactCapable":true,"agentType":"operational-readiness-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:observability-designer","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:artifact-handoff","agent-teams-workforce:architecture-baseline"]},"payments-integration-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:payments-integration-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:stripe-integration-expert","agent-teams-workforce:secrets-manager","agent-teams-workforce:graphrag-lookup"]},"performance-benchmark-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:performance-benchmark-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"permission-escalation-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:permission-escalation-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops","agent-teams-workforce:iam"]},"persistence-architecture-specialist":{"artifactCapable":true,"agentType":"persistence-architecture-specialist","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:dynamodb","agent-teams-workforce:database-schema-designer","agent-teams-workforce:rds","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:architecture-baseline"]},"persona-profile-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:persona-profile-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:product-analytics"]},"phase-gate-enforcer":{"artifactCapable":false,"agentType":"agent-teams-workforce:phase-gate-enforcer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:cumulative-regression"]},"playwright-e2e-web-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:playwright-e2e-web-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:a11y-audit","agent-teams-workforce:cumulative-regression"]},"polyrepo-steward":{"artifactCapable":true,"agentType":"agent-teams-workforce:polyrepo-steward","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:graphrag-lookup","polyrepo-repo","polyrepo-info","polyrepo-governance","polyrepo-setup","polyrepo-tribal-knowledge","polyrepo-doctor","polyrepo-beads","gitnexus-exploring","agent-teams-workforce:artifact-handoff"]},"power-tools-configuration-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:power-tools-configuration-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:lambda","agent-teams-workforce:secrets-manager","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"prd-alignment-verifier":{"artifactCapable":true,"agentType":"agent-teams-workforce:prd-alignment-verifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"prd-creation-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:prd-creation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"prd-reality-reconciler":{"artifactCapable":true,"agentType":"prd-reality-reconciler","skills":["agent-teams-workforce:architecture-baseline","agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:graphrag-lookup"]},"prd-trd-traceability-verifier":{"artifactCapable":true,"agentType":"agent-teams-workforce:prd-trd-traceability-verifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"prd-validation-analyst":{"artifactCapable":true,"agentType":"agent-teams-workforce:prd-validation-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"prd-validation-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:prd-validation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"prd-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:prd-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"production-readiness-review-facilitator":{"artifactCapable":false,"agentType":"agent-teams-workforce:production-readiness-review-facilitator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"race-condition-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:race-condition-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"react-native-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:react-native-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend","agent-teams-workforce:graphrag-lookup"]},"readme-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:readme-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"recommendation-engine-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:recommendation-engine-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:graphrag-lookup"]},"regression-coverage-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:regression-coverage-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:artifact-handoff","agent-teams-workforce:cumulative-regression"]},"regression-impact-assessor":{"artifactCapable":true,"agentType":"agent-teams-workforce:regression-impact-assessor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:artifact-handoff","agent-teams-workforce:cumulative-regression"]},"requirements-clarifier":{"artifactCapable":false,"agentType":"agent-teams-workforce:requirements-clarifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:product-discovery"]},"requirements-conflict-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:requirements-conflict-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"root-cause-analyst":{"artifactCapable":false,"agentType":"agent-teams-workforce:root-cause-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:find-cause","agent-teams-workforce:test-failure-mindset","agent-teams-workforce:graphrag-lookup"]},"run-ledger-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:run-ledger-writer","skills":["agent-teams-workforce:subagent-contract"]},"s3-data-lake-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:s3-data-lake-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:s3","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"sdlc-pipeline-orchestrator":{"artifactCapable":false,"agentType":"agent-teams-workforce:sdlc-pipeline-orchestrator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:beads-contract"]},"security-architecture-designer":{"artifactCapable":true,"agentType":"security-architecture-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-security","agent-teams-workforce:iam","agent-teams-workforce:secrets-manager","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:architecture-baseline"]},"security-test-case-designer":{"artifactCapable":true,"agentType":"agent-teams-workforce:security-test-case-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-security","agent-teams-workforce:cumulative-regression"]},"slo-error-budget-designer":{"artifactCapable":false,"agentType":"slo-error-budget-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:observability-designer","agent-teams-workforce:cloudwatch"]},"smoke-test-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:smoke-test-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"spec-authoring-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:spec-authoring-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"spec-currency-validator":{"artifactCapable":true,"agentType":"agent-teams-workforce:spec-currency-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"spec-decider":{"artifactCapable":false,"agentType":"spec-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:cove-prompt-design"]},"spec-freshness-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:spec-freshness-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"stakeholder-request-intake-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:stakeholder-request-intake-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"task-decomposer":{"artifactCapable":true,"agentType":"task-decomposer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:beads-contract","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:artifact-handoff","agent-teams-workforce:wsjf"]},"task-decomposition-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:task-decomposition-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:beads-contract","agent-teams-workforce:graphrag-lookup"]},"task-dependency-mapper":{"artifactCapable":true,"agentType":"task-dependency-mapper","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:beads-contract","agent-teams-workforce:artifact-handoff"]},"task-readiness-runner":{"artifactCapable":false,"agentType":"agent-teams-workforce:task-readiness-runner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:beads-contract"]},"tdd-unit-test-generator":{"artifactCapable":true,"agentType":"agent-teams-workforce:tdd-unit-test-generator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:tdd-guide","agent-teams-workforce:cumulative-regression"]},"test-command-resolver":{"artifactCapable":false,"agentType":"agent-teams-workforce:test-command-resolver","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:test-failure-mindset"]},"test-coverage-gap-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:test-coverage-gap-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"test-design-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:test-design-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"test-environment-orchestrator":{"artifactCapable":true,"agentType":"test-environment-orchestrator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:aws-mcp-setup"]},"test-failure-parser":{"artifactCapable":false,"agentType":"agent-teams-workforce:test-failure-parser","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:test-failure-mindset"]},"test-isolation-specialist":{"artifactCapable":true,"agentType":"agent-teams-workforce:test-isolation-specialist","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:tdd-guide","agent-teams-workforce:test-failure-mindset"]},"test-plan-strategy-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:test-plan-strategy-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"test-strategy-decider":{"artifactCapable":false,"agentType":"agent-teams-workforce:test-strategy-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cove-prompt-design"]},"trd-author":{"artifactCapable":true,"agentType":"trd-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:artifact-handoff"]},"trd-authoring-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:trd-authoring-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"trd-decider":{"artifactCapable":false,"agentType":"agent-teams-workforce:trd-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"trd-validator":{"artifactCapable":false,"agentType":"agent-teams-workforce:trd-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"ubiquitous-language-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:ubiquitous-language-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"uml-diagram-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:uml-diagram-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:architecture-diagramming","agent-teams-workforce:uml-diagramming","agent-teams-workforce:senior-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:artifact-handoff","agent-teams-workforce:architecture-baseline"]},"user-guide-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:user-guide-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:roadmap-communicator"]},"user-story-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:user-story-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:beads-contract"]},"user-story-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:user-story-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"vector-search-embeddings-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:vector-search-embeddings-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:rag-architect","agent-teams-workforce:graphrag-lookup"]},"webauthn-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:webauthn-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend","agent-teams-workforce:cognito","agent-teams-workforce:graphrag-lookup"]},"workflow-command-runner":{"artifactCapable":false,"agentType":"agent-teams-workforce:workflow-command-runner","skills":[]},"worktree-independent-verifier":{"artifactCapable":false,"agentType":"agent-teams-workforce:worktree-independent-verifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"wsjf-scorer":{"artifactCapable":true,"agentType":"agent-teams-workforce:wsjf-scorer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-strategist","agent-teams-workforce:wsjf","agent-teams-workforce:beads-contract"]},"wsjf-scoring-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:wsjf-scoring-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-strategist","agent-teams-workforce:wsjf"]},"xcuitest-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:xcuitest-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:tdd-guide","agent-teams-workforce:cumulative-regression"]}}
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
    ...(fableInput.relayExecutionId ? { relayExecutionId: fableInput.relayExecutionId } : {}),
    ...(fableInput.relayRequestDir ? { relayRequestDir: fableInput.relayRequestDir } : {}),
    ...(fableInput.relayCaptureScript ? { relayCaptureScript: fableInput.relayCaptureScript } : {}),
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
/**
 * Classifies a thrown error as exhausted (quota), transient (api) or deterministic. Its structured
 * fields decide first: the HTTP status and the API's error type or code. Its message is read only
 * when `ownMessage` is true, for the error a session's own API call threw; an error a child
 * workflow threw carries text a workflow composed (a Task title can say "rate limit"), so only
 * its structured fields count.
 */
function dispatchFailureCause(err, ownMessage = true) {
  const e = err && typeof err === 'object' ? err : {}
  const kinds = [e.type, e.error && e.error.type, typeof e.code === 'string' ? e.code : ''].filter(Boolean).join(' ')
  const known = [e.status, e.statusCode, e.code, e.response && e.response.status]
    .map((value) => Number(value)).find((value) => Number.isFinite(value) && value >= 100 && value < 600)
  if (/insufficient_quota|billing_error|quota|usage_limit/i.test(kinds)) return 'exhausted'
  if ([408, 425, 429, 500, 502, 503, 504, 529].includes(known) || /rate_limit|overloaded|api_error|timeout|econnreset|econnrefused|etimedout|eai_again/i.test(kinds)) return 'transient'
  if (!ownMessage) return 'deterministic'
  const text = [e.message || err || '', kinds].join(' ')
  if (/structured ?output|schema|validation|does not match|required property|additionalproperties|unsatisfiable|invalid argument/i.test(text)) return 'deterministic'
  if (/insufficient_quota|quota|usage[ _-]?limit|spend[ _-]?limit|session[ _-]?limit|credit balance|out of credits|hit your limit|token limit|account.quota.exhausted/i.test(text)) return 'exhausted'
  return /overload|rate[ _-]?limit|too many requests|capacity|throttl|timed? ?out|timeout|econnreset|econnrefused|etimedout|eai_again|socket hang up|network|temporarily unavailable|service unavailable|upstream connect|bad gateway/i.test(text) ? 'transient' : 'deterministic'
}
function dispatchRetry(err, name, attempt, waitedMs, policy, canWait, ownMessage = true) {
  const cause = dispatchFailureCause(err, ownMessage)
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
    // A child workflow's error message is text a workflow composed: only its structured fields count.
    const plan = dispatchRetry(err, name, 1, 0, dispatchPolicy(null), false, false)
    if (!plan.interruption) throw err
    dispatchInterruption = plan.interruption
    return dispatchOutcome({})
  }
}
// END bounded dispatch policy

const dispatchFailures = []
function dispatchDeaths(...phases) {
  const named = phases.filter(Boolean)
  if (!named.length) return dispatchFailures.slice()
  return dispatchFailures.filter((f) => named.includes(f.phase))
}
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
    const plan = dispatchRetry(err, name, 1, 0, dispatchPolicy(o), false)
    if (plan.interruption) dispatchInterruption = plan.interruption
    const message = String((err && err.message) || err).slice(0, 300)
    const cause = plan.cause === 'exhausted' ? 'quota' : plan.cause === 'transient' ? 'api' : 'other'
    dispatchFailures.push({ ...who, outcome: 'threw', cause, message, note: `${name} ended without a structured result: ${message}` })
    log(`${name}: ended without a structured result — ${message}`)
  }
  return null
}

const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
if (!a.prd) return dispatchOutcome({ ok: false, stage: 'input', error: 'no prd supplied', failure: { stage: 'input', cause: 'other', repositories: [] } })
const hasText = (v) => typeof v === 'string' && v.trim().length > 0
const shellq = (v) => `'${String(v).replace(/'/g, "'\\''")}'`
const repoPath = a.repoPath || a.prd.repoPath || null
let repos = []
const epicRef = a.epic && typeof a.epic === 'object' ? a.epic : {}
const epicBeadId = String(epicRef.id || epicRef.beadId || '').trim()
const subjectId = a.prd.id || a.prd.path || epicRef.key || epicBeadId || null
const emitTarget = a.beadsRepoPath || repoPath
const normRepo = (p) => String(p || '').trim().replace(/\/+$/, '')
/** The control repository: the one beads runs in. It is never a placement target. */
const CONTROL_REPO = normRepo(emitTarget)

const DISPATCH_FAILED_STAGE = 'agent-dispatch-failed'
const HUMAN_ACTION_STAGE = 'requires-human-action'

/**
 * The cause every failure carries in failure: { stage, cause, repositories }. It is set where the
 * failure happens, from structured fields (a dispatch interruption's stage, the cause a depscore.py
 * or relay result carries, a child workflow's failure.cause), never from a reason's text. Every
 * cause but 'other' is transient: a later dispatch, after backoff, can be expected to get past it.
 */
const CAUSES = ['api', 'quota', 'bd-timeout', 'relay', 'contention', 'other']
const TRANSIENT_CAUSES = ['api', 'quota', 'bd-timeout', 'relay', 'contention']
const causeOrOther = (c) => (CAUSES.includes(c) ? c : 'other')
/** The cause of a dispatch interruption: 'quota' or 'api', from the stage it was set with. */
const interruptionCause = (i) => (i && i.stage === 'account-quota-exhausted' ? 'quota' : i && i.stage === 'api-unavailable' ? 'api' : 'other')
/** One cause for several failures: the first one's when every one is transient, else 'other'. */
const combinedCause = (causes) => (causes.length && causes.every((c) => TRANSIENT_CAUSES.includes(c)) ? causes[0] : 'other')
/**
 * The cause a step's result carries: its failure.cause, else its own cause, else the dispatch
 * interruption it stopped on, else the combined cause of the sessions that died in it, else 'other'.
 */
function causeOf(r) {
  if (!r || typeof r !== 'object') return 'other'
  if (r.failure && CAUSES.includes(r.failure.cause)) return r.failure.cause
  if (CAUSES.includes(r.cause)) return r.cause
  if (r.dispatchInterruption) return interruptionCause(r.dispatchInterruption)
  const deaths = Array.isArray(r.dispatchFailures) ? r.dispatchFailures : []
  return deaths.length ? combinedCause(deaths.map((d) => causeOrOther(d && d.cause))) : 'other'
}
/**
 * Returns the failed result `out` with failure: { stage, cause, repositories }: the failure it
 * already carries, else one at its stage with cause 'other'; a dispatch interruption makes the
 * cause the interruption's.
 */
function withFailure(out) {
  const o = out && typeof out === 'object' ? out : { ok: false, stage: 'unknown' }
  const prior = o.failure && typeof o.failure === 'object' ? o.failure : {}
  const cause = dispatchInterruption ? interruptionCause(dispatchInterruption) : causeOrOther(prior.cause)
  return { ...o, failure: { stage: prior.stage || o.stage || 'unknown', cause, repositories: Array.isArray(prior.repositories) ? prior.repositories : [] } }
}

const produced = {}
const runLedger = []
let runDetail = null

const EXPECTED_PHASES = [
  'Epic Lifecycle',
  'PRD',
  'Epic',
  'PRD Parse',
  'Architecture',
  'Repo Scoping',
  'TRD Authoring',
  'Spec Authoring',
  'Task Decomposition',
  'Finish',
  'Run Ledger',
]
const runRecord = { expectedPhases: EXPECTED_PHASES.slice(), phases: [] }
let currentPhase = null
const recCurrent = () => (runRecord.phases.length ? runRecord.phases[runRecord.phases.length - 1] : null)
function enterPhase(title) {
  currentPhase = title
  runRecord.phases.push({ seq: runRecord.phases.length + 1, name: title, status: 'running', decision: null, artifacts: [], failure: null, skipReason: null })
  phase(title)
}
function recRuled(decision, extra) {
  const entry = recCurrent()
  if (!entry) return
  if (hasText(decision)) {
    const one = decision.trim()
    entry.decision = (entry.decision ? `${entry.decision}; ${one}` : one).slice(0, 1200)
  }
  if (extra && typeof extra.status === 'string') entry.status = extra.status
  if (extra && extra.failure) entry.failure = extra.failure
  if (extra && typeof extra.skipReason === 'string') entry.skipReason = extra.skipReason
}

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
  try {
    emitRunJournal({
      composite: 'prd-to-spec',
      bead: { id: epicBeadId || subjectId, title: epicRef.title || null },
      subject: a.prd.id || null,
      outcome,
      carriedFlags: [],
      run: runRecord,
      runLedger,
      detail: runDetail,
    })
  } catch (e) {
    log(`run journal could not be serialized: ${(e && e.message) || e}`)
  }
  return null
}

const reasonOf = (stage, detail) =>
  String((detail && (detail.reason || detail.error || detail.headline)) || `the ${stage} phase failed`)
const partial = (stage, detail, extra) => {
  const salvage = { ...produced, ...(extra || {}) }
  const why = reasonOf(stage, detail)
  recRuled(null, { status: 'failed', failure: { stage, reason: why } })
  runDetail = { stage, detail, partial: salvage }
  const keys = Object.keys(salvage)
  return {
    ok: false,
    stage: detail && detail.dispatchFailed ? DISPATCH_FAILED_STAGE : stage,
    beadId: subjectId,
    headline: `${stage}: ${why}. ${keys.length ? `Produced before it stopped, in the run journal under \`partial\`: ${keys.join(', ')}.` : 'Nothing had been produced.'}`,
    partialProduced: keys,
    failure: { stage, cause: causeOf(detail), repositories: [] },
  }
}
function handback(ok, stage, headline, detail) {
  runDetail = detail === undefined ? null : detail
  if (!ok) {
    const entry = recCurrent()
    if (entry && entry.status === 'running') {
      entry.status = 'failed'
      entry.failure = { stage, reason: String(headline || `the ${stage} phase failed`) }
    }
  }
  return { ok, stage, beadId: subjectId, headline: String(headline || '') }
}

const artPhases = {}
const artReport = { dir: null, epicId: null, filing: {} }

const lifecycle = { started: false, owner: null, pluginRoot: null, start: null, finish: null, release: null, held: false, holdAttempted: false, holdWrite: null }
const RESOLVE_PLUGIN_ROOT_PY = `import json, os, sys
from pathlib import Path
repo = os.path.normpath(ARGS[0]) if ARGS and ARGS[0] else ""
control = os.environ.get("ATW_CONTROL_REPO", "").strip()
projects = {p for p in (repo, os.path.normpath(control) if control else "") if p}
config = os.environ.get("CLAUDE_CONFIG_DIR", "").strip() or str(Path.home() / ".claude")
reg = Path(config) / "plugins" / "installed_plugins.json"
try:
    plugins = json.loads(reg.read_text(encoding="utf-8")).get("plugins", {})
except (OSError, ValueError) as exc:
    emit({"pluginRoot": None, "problem": f"{reg} is unreadable: {exc}"})
ranked = []
for key, entries in plugins.items():
    if not key.startswith("agent-teams-workforce@") or not isinstance(entries, list):
        continue
    for e in entries:
        path = e.get("installPath") if isinstance(e, dict) else None
        if not isinstance(path, str) or not Path(path, "scripts", "portfolio", "depscore.py").is_file():
            continue
        if e.get("scope") in ("local", "project") and e.get("projectPath") in projects:
            ranked.append((0, path))
        elif e.get("scope") == "user":
            ranked.append((1, path))
if ranked:
    emit({"pluginRoot": os.path.normpath(sorted(ranked)[0][1]), "problem": None})
emit({"pluginRoot": None, "problem": f"{reg} lists no agent-teams-workforce install shipping scripts/portfolio/depscore.py at user scope or for {sorted(projects)}"})`
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
  function artifactBrief(candidate, schema, revision = '', helper) {
    if (typeof helper !== 'string' || !helper) throw new Error('artifactBrief requires the artifactcontract.py helper path')
    const binding = ['--candidate', candidate, '--schema-json', canonicalJson(schema), '--revision', revision]
    const command = (operation, extra = []) => ['python3', helper, operation, ...binding, ...extra].map(quote).join(' ')
    const progress = `${candidate}.progress.json`
    const submit = command('submit', ['--progress-file', progress])
    return `\n\nARTIFACT CONTRACT DATA:
Candidate: ${candidate}
Progress: ${progress}
Input revision: ${revision}
Submission command: ${submit}
Checkpoint command: ${command('checkpoint', ['--progress-file', progress])}
Status command: ${command('status')}`
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

/** Where the full results relayed to this script are saved: the Epic's artifacts directory once known (set below), else the beads repository's run folder. */
let relayDir = null
let relaySeq = 0
/** The next relay file, named for its label. */
function nextRelayFile(label) {
  const dir = relayDir || `${emitTarget}/.claude/workflow-runs/relay/${String(epicBeadId || 'run').replace(/[^A-Za-z0-9._-]+/g, '_')}`
  relaySeq += 1
  return `${dir}/${String(relaySeq).padStart(3, '0')}-${String(label).replace(/[^A-Za-z0-9._-]+/g, '-')}.json`
}
/** scripts/portfolio/relayrun.py of the plugin: runs any other program through the checked relay. */
const relayRunner = () => `${lifecycle.pluginRoot}/scripts/portfolio/relayrun.py`
/** Runs one depscore.py command through the checked relay; returns the facts it printed with `relayFile`, or { error }. */
function runScript(label, phaseName, commandArgs) {
  return relayKit.depscore(settleAgent, { label, phase: phaseName, script: `${lifecycle.pluginRoot}/scripts/portfolio/depscore.py`, repo: emitTarget, tail: commandArgs, file: nextRelayFile(label) })
}
/** Runs any other program (argv, no shell) through the checked relay; returns relayKit.run's result. */
function runProgram(label, phaseName, argv, opts = {}) {
  return relayKit.run(settleAgent, { label, phase: phaseName, runner: relayRunner(), argv, file: nextRelayFile(label), ...opts })
}
const HOLD_CAUSE = 'awaiting-human-action'
/** Returns the instruction that hands a held Epic back to elaboration. */
function restoreStep(epicId, after = 'what it names has been settled') {
  const elabmark = typeof a.artifactScript === 'string' && /\/artifactio\.py$/.test(a.artifactScript)
    ? `python3 ${a.artifactScript.replace(/artifactio\.py$/, 'elabmark.py')}`
    : 'elabmark.py (in the SDLC automation directory)'
  return `After ${after}, set ${epicId} to elaboration_state=in_progress: ${elabmark} --set=in_progress --bead=${epicId} --apply — the next elaboration sweep resumes it from its last persisted step. Never set a partly-elaborated Epic to ready.`
}
/** The pauses, in ms, before the hold write is made again after it failed. */
const HOLD_BACKOFF_MS = [10000, 30000, 90000]
const pause = (ms) => (typeof setTimeout === 'function' ? new Promise((resolve) => setTimeout(resolve, ms)) : Promise.resolve())
/**
 * Clears the Epic's elaboration_state with cause awaiting-human-action; returns whether the write
 * succeeded. A failed hold write carries the cause beads-contract.py printed ('bd-timeout' or
 * 'contention', from bd's own error) or 'relay' when its result did not come back. Only a
 * bd-timeout or contention is retried, after each pause in HOLD_BACKOFF_MS: setting the same
 * metadata twice changes nothing, so the write is safe to repeat. Any other cause is recorded
 * and not retried. Once a hold is attempted the Epic is never
 * released (lifecycle.holdAttempted): when every attempt fails it is left in_progress under this
 * run's owner, and lifecycle.holdWrite says why.
 */
async function holdForPerson(epicId) {
  lifecycle.holdAttempted = true
  const argv = ['python3', `${lifecycle.pluginRoot}/skills/beads-contract/scripts/beads-contract.py`, '-C', emitTarget, 'metadata', 'set', epicId, 'elaboration_state=', `elaboration_state_cause=${HOLD_CAUSE}`, 'elaboration_state_owner=']
  for (let attempt = 1; ; attempt += 1) {
    const out = await runProgram('epic:hold', currentPhase || 'Architecture', argv)
    lifecycle.held = !!(out && out.ok && out.exitCode === 0 && out.json && !out.json.error)
    if (lifecycle.held) {
      lifecycle.holdWrite = { written: true, attempts: attempt }
      break
    }
    const cause = out && out.ok === false ? causeOrOther(out.cause) : causeOrOther(out && out.json && out.json.cause)
    const error = String((out && (out.error || (out.json && out.json.error) || out.stderrTail)) || `exit ${out && out.exitCode}`).slice(0, 600)
    lifecycle.holdWrite = { written: false, attempts: attempt, cause, error }
    if (!['bd-timeout', 'contention'].includes(cause) || attempt > HOLD_BACKOFF_MS.length || dispatchInterruption) break
    log(`Epic ${epicId}: the hold write failed (${cause}: ${error}); writing it again in ${HOLD_BACKOFF_MS[attempt - 1] / 1000}s`)
    await pause(HOLD_BACKOFF_MS[attempt - 1])
  }
  log(lifecycle.held
    ? `Epic ${epicId}: elaboration_state cleared (cause ${HOLD_CAUSE})`
    : `Epic ${epicId}: could NOT be held for a person after ${lifecycle.holdWrite.attempts} attempt(s) — it stays in_progress under owner ${lifecycle.owner} and is NOT released`)
  return lifecycle.held
}
/** The required action naming a hold write that never landed. */
const holdNotWritten = (epicId) =>
  `The hold write on ${epicId} failed ${lifecycle.holdWrite.attempts} time(s) (${lifecycle.holdWrite.cause}: ${lifecycle.holdWrite.error}); the Epic was NOT released and stays elaboration_state=in_progress under owner ${lifecycle.owner}. Clear it for diagnosis: elaboration_state= elaboration_state_cause=${HOLD_CAUSE} elaboration_state_owner=`
/** Holds the Epic for a person and returns the requires-human-action handback. */
async function holdForHuman(stage, detail, actions, after) {
  await holdForPerson(epicBeadId)
  return {
    ...partial(stage, detail),
    stage: HUMAN_ACTION_STAGE,
    requiredHumanActions: lifecycle.held ? [...actions, restoreStep(epicBeadId, after)] : [...actions, holdNotWritten(epicBeadId)],
  }
}

/** The stage of a run that left the Epic not done because span repositories failed. */
const REPOS_INCOMPLETE_STAGE = 'repositories-incomplete'
/**
 * The outcome of a run whose span repositories did not all get their Story and Tasks: ok:false at
 * stage repositories-incomplete, with failure: { stage, cause, repositories: [{ repository, stage,
 * cause, headline }] }. Each repository's cause is the one its failed step carried; the run's cause
 * is transient only when every repository's is (combinedCause). A transient cause releases the Epic
 * so the next dispatch reruns only the failed steps after backoff. Other failed items are recorded
 * without a diagnosis agent or synthetic owner action.
 */
function repositoriesIncomplete(specFails, decompFails, detail) {
  const failures = [
    ...specFails.map((f) => ({ ...f, step: 'spec', stage: f.stage || 'spec-authoring' })),
    ...decompFails.map((f) => ({ ...f, step: 'tasks', stage: f.stage || 'task-decomposition' })),
  ]
  const repositories = failures.map((f) => ({
    repository: f.repoPath,
    stage: f.stage,
    cause: causeOrOther(f.cause),
    headline: `${f.step === 'spec' ? 'Spec and Story' : 'Tasks'} not written: ${String(f.reason || 'no reason recorded').slice(0, 600)}`,
  }))
  const cause = combinedCause(repositories.map((r) => r.cause))
  const named = failures
    .map((f, i) => `${f.repoPath} (${f.step} at ${f.stage}, cause ${repositories[i].cause}${Array.isArray(f.uncitedItems) && f.uncitedItems.length ? `: no Task cites ${f.uncitedItems.join(', ')}` : ''})`)
    .join('; ')
  repositories.forEach((r) => log(`Repository not finished — ${r.repository} at ${r.stage} (${r.cause}): ${r.headline}`))
  runDetail = detail
  const transient = TRANSIENT_CAUSES.includes(cause)
  return {
    ...handback(
      false,
      REPOS_INCOMPLETE_STAGE,
      transient
        ? `transient (${cause}): ${named} — the next dispatch reruns only these failed steps after backoff`
        : `not retried: ${named} — not every repository failed for a transient cause; the failed item is recorded`,
      detail
    ),
    failure: { stage: REPOS_INCOMPLETE_STAGE, cause, repositories },

  }
}

let result
try {
  result = await (async () => {
enterPhase('Epic Lifecycle')
if (!epicBeadId) {
  return handback(false, 'epic-lifecycle', 'refused: no-epic — args.epic.id names no Epic. Create the Epic, assess its dependencies and score it first')
}
if (!hasText(emitTarget)) {
  return handback(false, 'epic-lifecycle', 'refused: no-tracker — no repository path was supplied, and beads cannot be written without one')
}
// designSystem is optional: packagesDir holds the single-artifact cds bundles the owner supplied (absent or
// empty supplies none), mocksDir and shellsDir the loose composed artifacts.
const designSystemArg = a.designSystem && typeof a.designSystem === 'object' ? a.designSystem : {}
const startArgs = `elaboration-start --epic ${shellq(epicBeadId)}${hasText(a.owner) ? ` --owner ${shellq(a.owner)}` : ''}${a.reclaim === true ? ' --reclaim' : ''}`
// pluginRoot comes from the Workflow args, else from the agent-teams-workforce install that
// $CLAUDE_CONFIG_DIR/plugins/installed_plugins.json records (the install for the beads repository or
// $ATW_CONTROL_REPO first, else the user-scope one); with neither, the run refuses before any other agent.
let pluginRootProblem = ''
const captureScript = String(fableInput.relayCaptureScript || '')
if (hasText(a.pluginRoot) && a.pluginRoot.trim().startsWith('/')) {
  lifecycle.pluginRoot = a.pluginRoot.trim().replace(/\/+$/, '')
} else if (/^\/.+\/scripts\/portfolio\/relaycapture\.py$/.test(captureScript)) {
  lifecycle.pluginRoot = captureScript.replace(/\/scripts\/portfolio\/relaycapture\.py$/, '')
  log(`pluginRoot was not passed; the relay capture script gives ${lifecycle.pluginRoot}`)
} else {
  for (let attempt = 1; attempt <= 3 && !lifecycle.pluginRoot; attempt++) {
    const found = await relayKit.inline(settleAgent, { label: `resolve-plugin-root-${attempt}`, phase: 'Epic Lifecycle', code: RESOLVE_PLUGIN_ROOT_PY, args: [emitTarget] })
    const o = found.ok ? found.view : { error: found.error }
    if (hasText(o.pluginRoot) && o.pluginRoot.trim().startsWith('/')) {
      lifecycle.pluginRoot = o.pluginRoot.trim().replace(/\/+$/, '')
      log(`pluginRoot was not passed; the plugin registry gives ${lifecycle.pluginRoot}`)
    } else {
      pluginRootProblem = String(o.problem || o.error || 'the resolver printed no pluginRoot').slice(0, 500)
      if (dispatchInterruption) break
      log(`resolve-plugin-root attempt ${attempt}: ${pluginRootProblem}`)
    }
  }
}
if (!lifecycle.pluginRoot) {
  return handback(false, 'epic-lifecycle', `refused: no-plugin-root — pluginRoot has no value (${pluginRootProblem}): pass pluginRoot in the Workflow args or install agent-teams-workforce so $CLAUDE_CONFIG_DIR/plugins/installed_plugins.json (default ~/.claude) records it`)
}
const started = await runScript('epic:start', 'Epic Lifecycle', startArgs)
if (started.noResult) {
  return {
    ...handback(false, 'epic-lifecycle', `the Epic lifecycle runner for ${epicBeadId} returned no result`),
    stage: DISPATCH_FAILED_STAGE,
    dispatchFailed: true,
    dispatchFailures: dispatchDeaths('Epic Lifecycle'),
    failure: { stage: 'epic-lifecycle', cause: causeOrOther(started.cause), repositories: [] },
  }
}
lifecycle.start = started.error ? started.output || null : started
const startOut = started.error ? { error: started.error } : started
if (startOut.error) {
  return {
    ...handback(false, 'epic-lifecycle', `the Epic lifecycle check for ${epicBeadId} failed: ${startOut.error}`),
    failure: { stage: 'epic-lifecycle', cause: causeOrOther(started.cause), repositories: [] },
  }
}
if (startOut.ok !== true) {
  const refusal = startOut.refusal || {}
  return {
    ...handback(false, 'epic-lifecycle', `refused: ${refusal.code || 'unknown'} — ${refusal.reason || 'the Epic may not be elaborated now'}`),
    refusal,
  }
}
lifecycle.owner = hasText(startOut.owner) ? startOut.owner : null
lifecycle.started = !!lifecycle.owner
recRuled(`Epic ${epicBeadId} marked in_progress (was ${startOut.previousState}) under owner ${lifecycle.owner}.`, { status: 'done' })
log(`Epic ${epicBeadId}: elaboration started (was ${startOut.previousState}); plugin root ${lifecycle.pluginRoot}`)

enterPhase('PRD')
let prd = a.prd
if (!hasText(prd.body) && hasText(prd.content)) prd = { ...prd, body: prd.content }
const prdByPath = !hasText(prd.body) && hasText(prd.path)
if (!hasText(prd.body) && !prdByPath) {
  const msg = 'the supplied PRD carries no text: none of prd.body, prd.content or prd.path is set'
  return { ...handback(false, 'input', msg), error: msg }
}
recRuled(prdByPath ? `PRD read from its file by each session: ${prd.path}` : 'PRD text supplied inline.', { status: 'done' })
produced.prd = prd

const ARCHITECTURE_DELIVERABLES = ['architecture/survey.md', 'architecture/survey.json', 'architecture/decision.md', 'architecture/decision.json', 'architecture/target.json', 'architecture/architecture-update.json']
function derivedNames(id) {
  if (id === 'architecture') return ARCHITECTURE_DELIVERABLES.slice()
  if (id === 'trd') return ['trd.md']
  if (id === 'repo-scoping') return ['repo-scoping.json']
  if (id === 'task-deps') return ['task-deps.json']
  const m = /^(recon|spec|tasks):([A-Za-z0-9._-]+)$/.exec(id)
  if (!m) return []
  const slug = m[2]
  if (m[1] === 'recon') return [`recon-${slug}.json`]
  if (m[1] === 'tasks') return [`tasks-${slug}.json`]
  return [`spec-${slug}.md`, `spec-${slug}.data-model.md`, `spec-${slug}.criteria.md`, `story-${slug}.json`]
}
function normalizeResume(r) {
  if (!r || typeof r !== 'object' || !Array.isArray(r.completed)) return null
  const names = r.names && typeof r.names === 'object' ? r.names : {}
  const phases = {}
  for (const id of r.completed) {
    if (!hasText(id)) continue
    phases[id] = { names: Array.isArray(names[id]) ? names[id].filter(hasText) : derivedNames(id) }
  }
  const stale = (Array.isArray(r.stale) ? r.stale : []).filter((e) => e && hasText(e.reason))
  return { root: r.root, dir: r.dir, epicId: r.epicId, phases, stale }
}
const RESUME = normalizeResume(a.resume)
for (const e of (RESUME && RESUME.stale) || []) {
  log(`STALE ${e.step || 'saved file'}${hasText(e.what) ? ` (${e.what})` : ''}: ${e.reason} — recreated, not reused`)
  runLedger.push({ phase: 'artifacts', event: 'stale', phaseId: e.step || null, artifacts: hasText(e.what) ? [e.what] : [], reason: e.reason })
}

const ARTIFACT_ROOT = repoPath || a.beadsRepoPath || null
const SS_ROOT = [RESUME && RESUME.root, a.projectRoot].filter(hasText).map((r) => r.replace(/\/+$/, ''))[0] || null
const ART_EPIC = String((RESUME && RESUME.epicId) || epicBeadId || subjectId || '')
  .replace(/[^A-Za-z0-9._-]+/g, '_')
  .replace(/^_+|_+$/g, '')
  .slice(0, 120) || null
const ART_DIR = SS_ROOT && RESUME && hasText(RESUME.dir)
  ? `${SS_ROOT}/${RESUME.dir.replace(/^\/+|\/+$/g, '')}`
  : ARTIFACT_ROOT && ART_EPIC
    ? `${ARTIFACT_ROOT}/.claude/workflow-runs/artifacts/${ART_EPIC}`
    : null
const ART_SCRIPT = hasText(a.artifactScript) ? a.artifactScript : null
const ART_ON = !!(ART_EPIC && ART_DIR && ART_SCRIPT)
const ART_REL = ART_ON && SS_ROOT && ART_DIR.startsWith(`${SS_ROOT}/`) ? ART_DIR.slice(SS_ROOT.length + 1) : null
const artPath = (name) => (ART_ON ? `${ART_DIR}/${name}` : null)
const PRD_INPUTS = hasText(prd.path) ? [prd.path] : []
/** The arc42 revision the architecture step's saved work was produced against: the recorder binds every saved architecture file to it, through the step's revision record, so work made against another arc42 is stale. */
const ARC42_REVISION_INPUTS = ART_ON && hasText(a.archPath)
  ? [`arc42-revision:${JSON.stringify({ dir: `${a.archPath.replace(/\/+$/, '')}/arc42`, record: artPath('architecture/arc42-revision.json') })}`]
  : []
const specFiles = (slug) => [`spec-${slug}.md`, `spec-${slug}.data-model.md`, `spec-${slug}.criteria.md`]
const TASK_DEPS_PHASE = 'task-deps'
const beadsArgs = { script: `${lifecycle.pluginRoot}/scripts/portfolio/depscore.py`, repo: emitTarget, epicId: epicBeadId, ...(SS_ROOT ? { projectRoot: SS_ROOT } : {}) }
artReport.dir = ART_ON ? ART_REL || ART_DIR : null
if (ART_ON) relayDir = `${ART_DIR}/relay`
artReport.epicId = ART_EPIC
log(ART_ON ? `Artifacts: ${ART_DIR}` : `ARTIFACTS DISABLED — no working directory or recorder (artifactScript=${JSON.stringify(ART_SCRIPT)})`)

/** Records a step as passed or reused; a passed step is appended to STEPS.md with artifactio.py step. */
async function acceptPhase(phaseId, status) {
  artPhases[phaseId] = status
  log(`ACCEPTED ${JSON.stringify({ phase: phaseId, status })}`)
  if (status !== 'passed' || !ART_ON) return
  const wrote = await runProgram(`steps:record:${phaseId}`, currentPhase || 'PRD', ['python3', ART_SCRIPT, 'step', ART_EPIC, phaseId], { tail: 5 })
  if (!wrote.ok || wrote.exitCode !== 0) log(`Step '${phaseId}' was NOT written to STEPS.md (${wrote.ok ? wrote.stderrTail || wrote.stdoutTail || `exit ${wrote.exitCode}` : wrote.error})`)
}
/** Returns the artifact descriptor a mini saves into, or undefined when artifacts are off. */
function artFor(phaseId, inputs, extra) {
  if (!ART_ON) return undefined
  return { dir: ART_DIR, relDir: ART_REL, epicId: ART_EPIC, script: ART_SCRIPT, phase: phaseId, inputs: (inputs || []).filter(hasText), ...(extra || {}) }
}
const slugCache = new Map()
/** Returns the stable artifact slug of a repository, suffixed when two repositories share a basename. */
function repoSlug(repo) {
  if (slugCache.has(repo)) return slugCache.get(repo)
  const base = String(repo || '').replace(/\/+$/, '').split('/').pop().replace(/[^A-Za-z0-9._-]+/g, '_') || 'repo'
  const taken = new Set(slugCache.values())
  let slug = base
  for (let n = 2; taken.has(slug); n++) slug = `${base}-${n}`
  slugCache.set(repo, slug)
  return slug
}
/** The steps whose saved files a step's saved files were built from. */
function stepUpstream(phaseId) {
  if (phaseId === 'repo-scoping' || phaseId === 'trd') return ['architecture']
  if (phaseId === TASK_DEPS_PHASE) return Object.keys(artPhases).filter((k) => k.startsWith('tasks:'))
  const m = /^(recon|spec|tasks):(.+)$/.exec(phaseId)
  if (!m) return []
  if (m[1] === 'recon') return ['architecture', 'repo-scoping']
  if (m[1] === 'spec') return ['trd', 'repo-scoping', `recon:${m[2]}`]
  return [`spec:${m[2]}`]
}
/**
 * Returns the saved step to reuse, or null. A step the resume ruled fresh is reused while every
 * step it was built from was reused in this run; when one of them ran again, the step is reused only
 * while the inputs recorded for its files still match (artifactio.py plan, read now), so an
 * upstream rerun that produced the same files costs no rework downstream.
 */
/** Why each step's saved files were found stale: the driver's resume ruling, then resumeFresh. */
const staleWhy = new Map(((RESUME && RESUME.stale) || []).filter((e) => hasText(e.step)).map((e) => [e.step, e.reason]))
async function resumeFresh(phaseId) {
  const hit = (RESUME && RESUME.phases[phaseId]) || null
  if (!hit) return null
  const redone = stepUpstream(phaseId).filter((up) => artPhases[up] !== 'reused')
  if (!redone.length) return hit
  if (ART_ON) {
    const plan = await runProgram(`resume:recheck-${phaseId}`, currentPhase || 'PRD', ['python3', ART_SCRIPT, 'plan', ART_EPIC], { keys: ['phases'] })
    const status = plan && plan.ok && plan.json && plan.json.phases && plan.json.phases[phaseId] ? plan.json.phases[phaseId].status : null
    if (status === 'fresh') {
      log(`Phase '${phaseId}': ${redone.join(', ')} ran again, and the inputs recorded for its saved files still match; reused`)
      return hit
    }
  }
  const reason = `built from ${redone.map((up) => `${up} (${artPhases[up] || 'not reached'})`).join(', ')}, which this run did not reuse, and its recorded inputs changed`
  staleWhy.set(phaseId, reason)
  log(`STALE ${phaseId} (${hit.names.join(', ') || 'no file named'}): ${reason} — recreated, not reused`)
  runLedger.push({ phase: 'artifacts', event: 'stale', phaseId, artifacts: hit.names, reason })
  return null
}
function reuseFrom(phaseId, hit) {
  runLedger.push({ phase: 'artifacts', event: 'reused', phaseId, artifacts: hit.names })
  log(`Phase '${phaseId}' reused from saved artifacts (${hit.names.join(', ') || 'none named'})`)
}

/** Returns the saved target's facts a resume needs ({ ok, subject, targetDir, deltaDir, deltaFiles, integratedFiles }) from depscore.py saved-target, or null when they cannot be read. */
async function readSavedTarget() {
  if (!RESUME || !ART_ON) return null
  const r = await runScript('replay:read-saved-target', 'Architecture', `saved-target --art-dir ${shellq(ART_DIR)}`)
  if (!r || r.error || r.found !== true) return null
  return r
}

/** Returns the saved span ruling a resumed run replays, from depscore.py saved-span, or null when it cannot be read. */
async function readSavedSpan() {
  const r = await runScript('replay:read-saved-span', 'Repo Scoping', `saved-span --art-dir ${shellq(ART_DIR)}`)
  if (!r || r.error || r.found !== true || !Array.isArray(r.placements) || !r.placements.some((p) => p && hasText(p.repoPath))) return null
  const placed = new Set([...r.placements.flatMap((p) => (p && Array.isArray(p.itemIds) ? p.itemIds : [])), ...(Array.isArray(r.noCode) ? r.noCode : []).map((n) => n && n.itemId)])
  const unplaced = deltaItems.filter((i) => !placed.has(i.id)).map((i) => i.id)
  if (unplaced.length) {
    log(`Repo Scoping: the saved placement does not place ${unplaced.join(', ')} of the delta; they are recorded as no code here`)
    r.noCode = [...(Array.isArray(r.noCode) ? r.noCode : []), ...unplaced.map((itemId) => ({ itemId, reason: 'the saved placement does not place it' }))]
  }
  if (CONTROL_REPO && r.placements.some((p) => p && normRepo(p.repoPath) === CONTROL_REPO)) {
    log(`Repo Scoping: the saved placement places delta items in the control repository ${CONTROL_REPO}; the span is ruled again`)
    return null
  }
  return r
}

/**
 * The placements in a repository that never holds placed work: the control repository, which holds
 * the pipeline and its tracker, and the repository holding the architecture documentation.
 */
function misplaced(placements) {
  const archRoot = normRepo(a.archPath)
  const out = []
  for (const p of Array.isArray(placements) ? placements : []) {
    const repo = normRepo(p && p.repoPath)
    if (!repo) continue
    const ids = Array.isArray(p.itemIds) ? p.itemIds.filter(hasText) : []
    if (CONTROL_REPO && repo === CONTROL_REPO) out.push({ repoPath: repo, itemIds: ids, reason: 'it is the control repository, which holds the pipeline and its tracker and is never a placement target' })
    else if (archRoot && (archRoot === repo || archRoot.startsWith(`${repo}/`))) out.push({ repoPath: repo, itemIds: ids, reason: `it holds the architecture documentation (${archRoot}), which the pipeline never builds or deploys` })
  }
  return out
}

enterPhase('Epic')
const epic = { key: epicRef.key || epicBeadId, ...epicRef, id: epicBeadId, type: 'epic' }
produced.epic = epic
recRuled(`Epic ${epicBeadId} adopted.`, { status: 'done' })

enterPhase('Architecture')
let architecture = null
const archHit = await resumeFresh('architecture')
const savedTargetSummary = archHit && archHit.names.includes('architecture/target.json') ? await readSavedTarget() : null
if (archHit && savedTargetSummary && savedTargetSummary.found === true && hasText(savedTargetSummary.targetDir)) {
  if (savedTargetSummary.ok !== true || savedTargetSummary.closureSaved !== true) log(`Architecture: the saved target ${savedTargetSummary.targetDir} is reused${hasText(savedTargetSummary.revisionProblem) ? `; ${savedTargetSummary.revisionProblem}` : ''}${savedTargetSummary.closureSaved !== true ? '; it holds no prerequisite closure' : ''}`)
  reuseFrom('architecture', archHit)
  await acceptPhase('architecture', 'reused')
  architecture = {
    ok: true,
    resumed: true,
    artifact: {
      subject: savedTargetSummary.subject,
      targetDir: savedTargetSummary.targetDir,
      deltaDir: savedTargetSummary.deltaDir,
      deltaFileCount: Number(savedTargetSummary.deltaFiles) || 0,
      integratedFileCount: Number(savedTargetSummary.integratedFiles) || 0,
      targetPath: artPath('architecture/target.json'),
      decisionPath: artPath('architecture/decision.md'),
      architectureUpdatePath: artPath('architecture/architecture-update.json'),
    },
  }
  recRuled(`Architecture reused from saved artifacts: target ${savedTargetSummary.targetDir}.`, { status: 'done' })
} else if (archHit) {
  log(`Architecture: the saved target in ${ART_DIR} was not read back${savedTargetSummary && savedTargetSummary.ok === true && savedTargetSummary.closureSaved !== true ? ', or its delta holds no prerequisite closure' : ''}${savedTargetSummary && hasText(savedTargetSummary.revisionProblem) ? ` (${savedTargetSummary.revisionProblem})` : ''}; the architecture mini resumes from its saved work, or sets it aside when arc42 is not the revision it was produced against`)
}
if (!architecture) {
  const r = await settleWorkflow('agent-teams-workforce:architecture', {
    prd: { id: prd.id, title: prd.title, path: prd.path, body: prdByPath ? undefined : prd.body },
    epic: { id: epicBeadId },
    archPath: a.archPath,
    subject: hasText(a.architectureSubject) ? a.architectureSubject : undefined,
    repoPath,
    maxRounds: Number.isInteger(a.maxArchitectureRounds) ? a.maxArchitectureRounds : undefined,
    depscore: { script: `${lifecycle.pluginRoot}/scripts/portfolio/depscore.py`, repo: emitTarget },
    artifacts: artFor('architecture', [...PRD_INPUTS, ...ARC42_REVISION_INPUTS], { beadId: epicBeadId }),
  })
  architecture = r && r.ok === true
    ? { ok: true, artifact: r }
    : {
        ok: false,
        artifact: r || null,
        reason: (r && (r.reason || r.error)) || 'the architecture mini returned nothing',
        ...(!r || r.dispatchFailed === true ? { dispatchFailed: true, dispatchFailures: (r && r.dispatchFailures) || dispatchDeaths('Architecture') } : {}),
      }
  if (architecture.ok) {
    const changed = r.architectureUpdate ? Number(r.architectureUpdate.touched) || 0 : 0
    recRuled(`Architecture approved for ${r.subject}: target ${r.targetDir}; ${changed} effective file(s) integrated.`, { status: 'done' })
    await acceptPhase('architecture', 'passed')
  }
}
produced.architecture = (architecture.artifact || null)
if (!architecture.ok) {
  const art = architecture.artifact || {}
  if (art.stage === 'input' && /archPath|ATW_ARCH_PATH/.test(architecture.reason)) {
    // Where the architecture lives is the owner's configuration: only the owner can supply it.
    return await holdForHuman(
      'architecture',
      architecture,
      [`architecture refused its input: ${architecture.reason} Set ATW_ARCH_PATH to the architecture directory (the folder holding arc42/, target/ and built/) for the pipeline host.`],
      'the architecture path is configured'
    )
  }
  if (art.stage === 'owner-concern') {
    const actions = Array.isArray(art.requiredHumanActions) && art.requiredHumanActions.length
      ? art.requiredHumanActions.slice()
      : [`The architecture of ${epicBeadId} found business requirements no design can satisfy together, or conflicting section 2 constraints: ${architecture.reason}`]
    return await holdForHuman('architecture', architecture, actions, 'the PRD or section 2 says which side holds')
  }
  // Any other architecture stop is the pipeline's to fix: it is reported, never held for a person.
  return partial('architecture', { ...architecture, ...(art.headline ? { headline: art.headline } : {}) })
}
const archArt = architecture.artifact || {}
if (!hasText(archArt.targetDir)) {
  return partial('architecture', { reason: 'the architecture result names no target directory, which every later phase reads' })
}
if (!hasText(archArt.deltaDir)) archArt.deltaDir = `${archArt.targetDir.replace(/\/+$/, '')}/delta`
const deltaList = await runScript('arch:delta', 'Architecture', `arch-delta --delta-dir ${shellq(archArt.deltaDir)}${ART_ON ? ` --save ${shellq(artPath('delta-items.json'))}` : ''}`)
if (!deltaList || deltaList.error) {
  return partial('architecture', { reason: `depscore.py arch-delta did not list the delta at ${archArt.deltaDir}: ${(deltaList && deltaList.error) || 'no result'}`, cause: causeOf(deltaList) })
}
if (deltaList.ok !== true) log(`Architecture: depscore.py arch-delta lists the delta at ${archArt.deltaDir} with refusals, carried on with the items it lists: ${(deltaList.refusals || []).join('; ') || 'none named'}`)
const deltaItems = (Array.isArray(deltaList.items) ? deltaList.items : [])
  .filter((i) => i && hasText(i.id) && hasText(i.element))
  .map((i) => ({ ...i, id: i.id, element: i.element, views: Array.isArray(i.views) ? i.views.filter(hasText) : [] }))
// Only the validated assessment helper (archbaseline.py) can establish that no implementation is
// needed, and a prerequisite the delta's work rests on is always implementation work.
const prerequisiteItems = deltaItems.filter((i) => i.kind === 'prerequisite')
const noImplementationWork = deltaList.baselineValidated === true &&
  deltaList.implementationComplete === true && deltaList.implementationWork === 0 && !prerequisiteItems.length
/**
 * The approved target, its delta and the build items, as every later phase reads them. deltaDir is
 * the delta folder only when the target has one (a partial change); with no architecture change, or
 * an entirely new one, there is no delta folder and the items come from the future set and its gaps
 * against the code on main.
 */
const architectureChange = hasText(deltaList.architectureChange) ? deltaList.architectureChange : 'partial'
const delta = {
  subject: archArt.subject || null,
  targetDir: archArt.targetDir,
  deltaDir: deltaList.deltaExists === false ? '' : archArt.deltaDir,
  architectureChange,
  note: hasText(deltaList.note) ? deltaList.note : '',
  decisionPath: archArt.decisionPath || artPath('architecture/decision.md'),
  items: deltaItems,
  noImplementationWork,
}
produced.delta = delta
log(`Build items: ${deltaItems.length} item(s) from ${delta.targetDir} (architecture change ${architectureChange}${delta.deltaDir ? `, delta ${delta.deltaDir}` : ', no delta'})${prerequisiteItems.length ? `, ${prerequisiteItems.length} of them prerequisites the delta's work rests on (${prerequisiteItems.map((i) => `${i.id} ${i.element} [${i.state}]`).join('; ')})` : ''}`)

let scoping = null
/** Returns { scoping, scopeHit }: the saved placement on a resume, else a fresh one. */
async function runRepoScoping(avoid = []) {
  if (noImplementationWork) {
    return { scopeHit: null, scoping: {
      ok: true, repos: [], placements: [], createdRepos: [],
      noCode: deltaItems.map((item) => ({ itemId: item.id, reason: 'The validated architecture assessment requires no implementation work.' })),
      spanRationale: 'The approved, validated architecture assessment requires no implementation work; no repository placement is needed.',
      baselineValidated: true,
    } }
  }
  const scopeHit = avoid.length ? null : await resumeFresh('repo-scoping')
  const saved = scopeHit && ART_ON ? await readSavedSpan() : null
  if (scopeHit && !saved) log(`Repo Scoping: the saved ruling in ${ART_DIR} was not read back; the span is ruled again`)
  if (saved) {
    const placements = saved.placements
      .filter((p) => p && hasText(p.repoPath))
      .map((p) => ({ ...p, repoPath: p.repoPath.trim(), itemIds: Array.isArray(p.itemIds) ? p.itemIds : [], frontend: p.frontend === true }))
    const spanRepos = []
    for (const p of placements) if (!spanRepos.includes(p.repoPath)) spanRepos.push(p.repoPath)
    return {
      scopeHit,
      scoping: {
        ok: true,
        resumed: true,
        repos: spanRepos,
        placements,
        noCode: Array.isArray(saved.noCode) ? saved.noCode : [],
        createdRepos: [],
        spanRationale: saved.spanRationale || null,
      },
    }
  }
  const ruled = await settleWorkflow('agent-teams-workforce:repo-scoping', {
    pluginRoot: lifecycle.pluginRoot,
    artifacts: artFor('repo-scoping', [...PRD_INPUTS, artPath('architecture/decision.md'), artPath('architecture/target.json')]),
    prd: { id: prd.id, title: prd.title, path: prd.path },
    delta,
    epic: { key: epic.key, title: epic.title },
    ...(avoid.length ? { avoidRepos: avoid } : {}),
  })
  return { scoping: ruled, scopeHit: null }
}

/** The architecture the TRD is built from, as trd-authoring hands it to its author: this Epic's target and delta, section 2, and the effective views (subject or shows) of the elements the delta changes. */
const ARC42_DIR = hasText(a.archPath) ? `${a.archPath.replace(/\/+$/, '')}/arc42` : null
const deltaElements = [...new Set(deltaItems.map((i) => i.element.trim()))].sort()
const TRD_INPUTS = [
  ...PRD_INPUTS,
  artPath('architecture/decision.md'),
  artPath('architecture/target.json'),
  artPath('architecture/architecture-update.json'),
  artPath('architecture/survey.json'),
  delta.targetDir,
  ARC42_DIR ? `${ARC42_DIR}/02-architecture-constraints` : null,
  ARC42_DIR && deltaElements.length ? `arch-views:${JSON.stringify({ dir: ARC42_DIR, elements: deltaElements })}` : null,
].filter(hasText)
/** Returns { mode: 'resumed' | 'ran', trdAuthoring: { ok, artifact } }. */
async function runTrdAuthoring() {
  const trdHit = await resumeFresh('trd')
  if (trdHit && trdHit.names.includes('trd.md')) {
    reuseFrom('trd', trdHit)
    return {
      mode: 'resumed',
      trdAuthoring: {
        ok: true,
        artifact: {
          trdPath: artPath('trd.md'),
          filingPath: hasText(a.trdPath) && a.trdPath.startsWith('/') ? a.trdPath : null,
          trd: { trdPath: artPath('trd.md'), summary: '' },
        },
      },
    }
  }
  const r = await settleWorkflow('agent-teams-workforce:trd-authoring', {
    pluginRoot: lifecycle.pluginRoot,
    prd: { id: prd.id, title: prd.title, content: prd.body, path: prd.path, acceptanceCriteria: prd.acceptanceCriteria },
    architecture: delta,
    surveyPath: artPath('architecture/survey.json'),
    archPath: a.archPath,
    trdPath: a.trdPath,
    artifacts: artFor('trd', TRD_INPUTS, { beadId: epicBeadId }),
    repoPath,
  })
  return {
    mode: 'ran',
    trdAuthoring: r && r.ok === true
      ? { ok: true, artifact: r }
      : {
          ok: false,
          artifact: r || null,
          reason: (r && (r.reason || r.error)) || 'trd-authoring returned nothing',
          ...(!r || r.dispatchFailed === true ? { dispatchFailed: true, dispatchFailures: (r && r.dispatchFailures) || dispatchDeaths('TRD Authoring') } : {}),
        },
  }
}

const [scopeSettled, trdSettled] = await parallel([() => runRepoScoping(), () => runTrdAuthoring()])
const trdAuthoring = (trdSettled && trdSettled.trdAuthoring) || { ok: false, artifact: null, reason: 'TRD authoring threw' }
if (trdAuthoring.ok) await acceptPhase('trd', trdSettled.mode === 'resumed' ? 'reused' : 'passed')

enterPhase('Repo Scoping')
if (!scopeSettled) return partial('repo-scoping', { reason: 'repo scoping threw' })
scoping = scopeSettled.scoping
if (scoping && scoping.ledger) runLedger.push(scoping.ledger)
produced.repoScoping = scoping || null
if (!scoping || scoping.ok === false) {
  return partial('repo-scoping', {
    reason: (scoping && scoping.reason) || 'repo scoping returned nothing',
    ...(!scoping || scoping.dispatchFailed === true ? { dispatchFailed: true, dispatchFailures: (scoping && scoping.dispatchFailures) || [] } : {}),
  })
}
let wrongPlace = misplaced(scoping.placements)
if (wrongPlace.length) {
  const named = wrongPlace.map((r) => `${r.repoPath} (${r.itemIds.join(', ') || 'no item named'}): ${r.reason}`)
  log(`Repo Scoping: placements in a repository that never holds placed work go back to the polyrepo-steward once — ${named.join(' | ')}`)
  const again = await runRepoScoping(wrongPlace)
  if (again && again.scoping && again.scoping.ok !== false) {
    scoping = again.scoping
    if (scoping.ledger) runLedger.push(scoping.ledger)
    produced.repoScoping = scoping
    wrongPlace = misplaced(scoping.placements)
  }
  if (wrongPlace.length) {
    return partial('repo-scoping', { reason: `the polyrepo-steward placed delta items in a repository that never holds placed work, twice — ${wrongPlace.map((r) => `${r.repoPath} (${r.itemIds.join(', ')}): ${r.reason}`).join(' | ')}`, misplaced: wrongPlace })
  }
}
if (scoping.resumed === true) reuseFrom('repo-scoping', scopeSettled.scopeHit)
if (noImplementationWork) {
  artPhases['repo-scoping'] = 'skipped'
  log('Repo Scoping skipped: the verified architecture assessment requires no implementation; its baseline handoff (baseline.json in the target) is the durable record.')
} else {
  await acceptPhase('repo-scoping', scoping.resumed === true ? 'reused' : 'passed')
}
repos = Array.isArray(scoping.repos) ? scoping.repos : []
recRuled(`Repo span: ${repos.join(', ') || 'no repository'}, the repositories the delta changes.`, { status: 'done' })
if (!repos.length && !noImplementationWork) log('Repo Scoping: the span names no repository: every delta item has no code here, so there is no implementation work')
/** True when there is nothing to build: the assessment needs no implementation, or no delta item has code here. */
const nothingToBuild = noImplementationWork || !repos.length
const createdRepos = (Array.isArray(scoping.createdRepos) && scoping.createdRepos) || []
log(`Span: ${repos.join(', ') || 'no repository'}${createdRepos.length ? `; created by the polyrepo-steward: ${createdRepos.map((c) => (c && c.name) || String(c)).join(', ')}` : ''}`)

enterPhase('TRD Authoring')
if (trdAuthoring.ok && trdAuthoring.artifact && hasText(trdAuthoring.artifact.filingPath)) artReport.filing['trd.md'] = trdAuthoring.artifact.filingPath
produced.trdAuthoring = (trdAuthoring.artifact || null)
if (!trdAuthoring.ok) {
  return partial('trd-authoring', trdAuthoring)
}
recRuled(`TRD ${trdSettled.mode === 'resumed' ? 'reused' : 'authored'}${hasText(trdAuthoring.artifact.trdPath) ? ` at ${trdAuthoring.artifact.trdPath}` : ''}.`, { status: 'done' })
const trd = trdAuthoring.artifact.trd
const prdSummaryFallback = () => (hasText(prd.path) ? `The PRD is the document at ${prd.path}.` : prd.body || '')

enterPhase('Spec Authoring')
const idleText = (recon) => (Array.isArray(recon && recon.idle) ? recon.idle : []).map((r) => `${r.id} [${r.status}${r.plannedBy ? ` by ${r.plannedBy}` : ''}]`).join('; ')
const workIds = (recon) => (Array.isArray(recon && recon.work) ? recon.work : [])
/** The delta detailing as a pointer: its file, and the ids of the items that make work and that do not. The items stay in the file. */
const renderInventory = (recon, repo) => {
  const work = workIds(recon)
  const idle = idleText(recon)
  const idleLine = idle ? `\n\nNo specification for these items: ${idle}.` : ''
  const file = `THE DELTA DETAILING for ${repo} is the file ${recon.reconPath}. Read it: its \`items\` give each delta item placed here its status, the \`from\` state the code on main holds, the \`to\` state the approved target makes it, its surface and its file:line evidence.`
  if (!work.length) return `${file}\n\nNo item placed here is marked add, modify or remove, so there is no change to specify.${idleLine}`
  return (
    `${file}\n\nSpecify the change for these items, and only these: ${work.join(', ')}.\n` +
    '  add    — the element is new here: specify it.\n' +
    '  modify — the element exists: specify the change from what it is to what the target makes it.\n' +
    '  remove — the element is removed: specify its removal.' +
    idleLine
  )
}
const renderDependencies = (recon) => {
  if (!recon || recon.dependenciesCurrent !== false) return ''
  return `UPSTREAM DEPENDENCY CHANGES since the delta was designed: ${recon.dependencyFindings} finding(s) in \`dependencyChanges.changeFindings\` of ${recon.reconPath}. Read them and specify against what is true now.`
}
const renderUiAuthority = (recon) => {
  const ui = uiItemsOf(recon)
  if (!ui.length) return ''
  const of = (source) => ui.filter((u) => u.designSource === source)
  const bundled = of('bundle')
  const cds = of('cds')
  const none = of('none')
  return [
    `UI ITEMS — each \`ui\` item takes one design source, recorded in \`uiAuthority.uiItems\` of ${recon.reconPath}.`,
    bundled.length
      ? `bundle — a cds bundle the owner supplied packages the item. Specify it by reference to that bundle's \`spec/build-spec.md\`; styling is that bundle's own stylesheet set (its styles/), and the spec adds no new CSS, tokens or component stylesheet:\n${bundled.map((u) => `  - ${u.id}: ${u.buildSpec}${u.sections.length ? ` (Sections ${u.sections.join(', ')})` : ''}`).join('\n')}`
      : '',
    cds.length
      ? `cds — the item changes design and no bundle packages it. The implementing agent designs it with the CDS design system; specify its behaviour and content, and state that its design comes from the CDS design system: ${cds.map((u) => u.id).join(', ')}`
      : '',
    none.length
      ? `none — the item changes no design (copy, or data wired into an existing element). Specify the change; it needs no design work: ${none.map((u) => u.id).join(', ')}`
      : '',
  ].filter(hasText).join('\n\n')
}
/** Returns each `ui` work item of a detailing with its design source, and the bundle and build spec of a bundle item. */
function uiItemsOf(recon) {
  return (Array.isArray(recon && recon.uiWork) ? recon.uiWork : []).map((u) => ({
    id: u.id,
    element: null,
    designSource: hasText(u.designSource) ? u.designSource : u.buildSpec ? 'bundle' : 'cds',
    bundle: u.bundle || null,
    buildSpec: u.buildSpec || null,
    sections: Array.isArray(u.sections) ? u.sections.filter(hasText) : [],
  }))
}
const specConstraints = (recon, repo) => {
  const c = [renderInventory(recon, repo), renderDependencies(recon), renderUiAuthority(recon)].filter(hasText)
  return c.length ? c : undefined
}
const placementOf = (repo) => (Array.isArray(scoping.placements) ? scoping.placements : []).filter((p) => p && hasText(p.repoPath) && p.repoPath.trim() === String(repo).trim())
/** Returns the delta items repo scoping placed in one repository. */
function itemsPlacedIn(repo) {
  const ids = new Set(placementOf(repo).flatMap((p) => (Array.isArray(p.itemIds) ? p.itemIds : [])))
  return deltaItems.filter((i) => ids.has(i.id))
}
/** Returns the prd-reconciliation arguments for one repository. */
const DESIGN_SYSTEM = designSystemArg
function reconArgs(repo, slug, reconReplay) {
  return {
    items: itemsPlacedIn(repo),
    delta: { targetDir: delta.targetDir, deltaDir: delta.deltaDir, architectureChange: delta.architectureChange, note: delta.note },
    artifacts: artFor(`recon:${slug}`, [...PRD_INPUTS, artPath('architecture/target.json'), artPath('repo-scoping.json'), artPath('architecture/survey.json'), `git-main:${repo}`], { slug }),
    depscore: beadsArgs.script,
    ...(reconReplay ? { replay: reconReplay } : {}),
    prd: { id: prd.id, title: prd.title, path: prd.path, repoPath: repo },
    repos: [repo],
    surveyPath: artPath('architecture/survey.json'),
    dependencies: a.dependencies,
    uiRepo: placementOf(repo).some((p) => p.frontend === true),
    ...(DESIGN_SYSTEM.mocksDir ? { mocksDir: DESIGN_SYSTEM.mocksDir } : {}),
    ...(DESIGN_SYSTEM.packagesDir ? { packagesDir: DESIGN_SYSTEM.packagesDir } : {}),
    ...(DESIGN_SYSTEM.shellsDir ? { shellsDir: DESIGN_SYSTEM.shellsDir } : {}),
  }
}
/** Returns the spec-authoring arguments for one repository. */
function specArgs(repo, storyKey, slug, recon) {
  return {
    spec: a.spec || {
      id: prd.id,
      title: prd.title,
      summary: (trd && trd.summary) || prdSummaryFallback(),
      repoPath: repo,
    },
    trd,
    architecture: { targetDir: delta.targetDir, deltaDir: delta.deltaDir, architectureChange: delta.architectureChange, note: delta.note },
    accessPatterns: a.accessPatterns,
    repoPath: repo,
    storyKey,
    epic,
    artifacts: artFor(`spec:${slug}`, [artPath('trd.md'), artPath('repo-scoping.json'), artPath(`recon-${slug}.json`), ...PRD_INPUTS], { slug }),
    beads: beadsArgs,
    detailingPath: recon.reconPath,
    constraints: specConstraints(recon, repo),
    ...(uiItemsOf(recon).length ? { uiItems: uiItemsOf(recon) } : {}),
  }
}
/** Details one repository's delta items, then authors its Spec and Story, or replays the saved Story; returns { repo, recon, specAuthoring }. */
async function authorSpecForRepo(repo, repoIndex) {
  const storyKey = `S${repoIndex + 1}`
  const slug = repoSlug(repo)
  const specPhase = `spec:${slug}`
  const reconPhase = `recon:${slug}`
  const reconHit = await resumeFresh(reconPhase)
  const reconReplay = reconHit && ART_ON && reconHit.names.includes(`recon-${slug}.json`) ? { files: { recon: artPath(`recon-${slug}.json`) } } : null
  const recon = await settleWorkflow('agent-teams-workforce:prd-reconciliation', reconArgs(repo, slug, reconReplay))
  if (recon && recon.ledger) runLedger.push(recon.ledger)
  if (!recon || recon.ok !== true) {
    const why = `the detailing of ${repo} failed, so its Spec is not authored: ${(recon && recon.reason) || 'prd-reconciliation returned nothing'}`
    log(`Spec Authoring for ${repo}: ${why}`)
    return {
      repo,
      recon: null,
      specAuthoring: {
        ok: false,
        stage: (recon && hasText(recon.stage) && recon.stage !== 'input' ? recon.stage : 'detailing'),
        reason: why,
        cause: causeOf(recon),
        ...(!recon || recon.dispatchFailed === true ? { dispatchFailed: true, dispatchFailures: (recon && recon.dispatchFailures) || [] } : {}),
      },
    }
  }
  await acceptPhase(reconPhase, reconReplay && recon.resumed === true ? 'reused' : 'passed')
  const specHit = await resumeFresh(specPhase)
  const args = specArgs(repo, storyKey, slug, recon)
  const r = await settleWorkflow('agent-teams-workforce:spec-authoring', specHit ? { ...args, replay: true } : args)
  const specAuthoring = r && r.ok === true && r.story
    ? { ok: true, artifact: r }
    : {
        ok: false,
        stage: (r && r.stage) || null,
        reason: (r && (r.reason || r.error)) || (r ? 'spec-authoring returned no story' : 'spec-authoring returned nothing'),
        cause: causeOf(r),
        ...(!r || r.dispatchFailed === true ? { dispatchFailed: true, dispatchFailures: (r && r.dispatchFailures) || [] } : {}),
      }
  if (specAuthoring.ok && specHit) reuseFrom(specPhase, specHit)
  if (specAuthoring.ok) await acceptPhase(specPhase, specHit ? 'reused' : 'passed')
  return { repo, recon, specAuthoring }
}
for (const r of repos) repoSlug(r)
const specResults = await parallel(repos.map((repo, repoIndex) => () => authorSpecForRepo(repo, repoIndex)))
const reconByRepo = new Map()
const specPairs = []
const specFailures = []
for (const [repoIndex, repo] of repos.entries()) {
  const settled = specResults[repoIndex]
  if (settled && settled.recon) reconByRepo.set(repo, settled.recon)
  const specAuthoring = settled && settled.specAuthoring
  if (!specAuthoring || !specAuthoring.ok) {
    specFailures.push({
      repoPath: repo,
      stage: (specAuthoring && specAuthoring.stage) || null,
      reason: (specAuthoring && specAuthoring.reason) || 'the spec-authoring phase threw',
      cause: causeOrOther(specAuthoring && specAuthoring.cause),
      dispatchFailed: !!(specAuthoring && specAuthoring.dispatchFailed),
      dispatchFailures: (specAuthoring && specAuthoring.dispatchFailures) || [],
    })
    log(`Spec Authoring FAILED for ${repo}: ${(specAuthoring && specAuthoring.reason) || 'threw'}`)
    continue
  }
  const art = specAuthoring.artifact
  specPairs.push({
    repoPath: repo,
    spec: art,
    story: { ...art.story, decisionIds: Array.isArray(art.decisionIds) ? art.decisionIds : [] },
  })
  recRuled(`Spec and Story ${art.story.key || art.story.title} for ${repo}.`)
}
produced.reconciliationByRepo = Array.from(reconByRepo, ([rp, recon]) => ({ repoPath: rp, recon }))
produced.specPairs = specPairs
produced.specFailures = specFailures
if (!specPairs.length && !nothingToBuild) {
  recRuled(null, { status: 'failed', failure: { stage: 'spec-authoring', reason: 'no repo produced a spec' } })
  return repositoriesIncomplete(specFailures, [], { stage: 'spec-authoring', partial: { ...produced } })
}
recRuled(`${specPairs.length} of ${repos.length} repo(s) specified.`, { status: 'done' })

enterPhase('Task Decomposition')
const inventoryBrief = (repo) => {
  const recon = reconByRepo.get(repo)
  if (!recon || !hasText(recon.reconPath)) return ''
  return (
    '\n\n=== DELTA DETAILING — what needs a Task ===\n' +
    `The detailing is the file ${recon.reconPath}: read it for each item's element, its from and to state, its surface and its evidence.\n` +
    `Needs a Task (add, modify, remove): ${workIds(recon).join(', ') || 'none'}\n` +
    `No Task (done, or planned by another Epic's bead): ${idleText(recon) || 'none'}`
  )
}
const stories = specPairs.map((p) => p.story)
const decompositions = []
const decompositionFailures = []
const tasks = []
/** Returns the spec documents of one Story as { path, ref }. */
function specDocsFor(pair) {
  const slug = repoSlug(pair.repoPath)
  const out = []
  const seen = new Set()
  const add = (path, ref) => {
    if (!hasText(path) || seen.has(path)) return
    seen.add(path)
    out.push({ path, ref: ref || null })
  }
  if (ART_ON) for (const name of specFiles(slug)) add(artPath(name), ART_REL ? `${ART_REL}/${name}` : null)
  const sp = pair.spec || {}
  for (const part of [sp.apiSpec, sp.dataModelSpec, sp.eventContracts, sp.errorSpec]) {
    for (const p of part && Array.isArray(part.artifactPaths) ? part.artifactPaths : []) {
      if (hasText(p)) add(p, SS_ROOT && p.startsWith(`${SS_ROOT}/`) ? p.slice(SS_ROOT.length + 1) : null)
    }
  }
  return out
}
/** Returns the task-decomposition arguments for one Story. */
function decompArgs(pair) {
  const slug = repoSlug(pair.repoPath)
  const docs = specDocsFor(pair)
  const summary = (pair.spec && pair.spec.apiSpec && pair.spec.apiSpec.summary) || (trd && trd.summary) || prdSummaryFallback()
  return {
    spec: {
      id: prd.id,
      title: prd.title,
      description: `SUMMARY (navigation aid only — the contract is in the spec documents):\n${summary}` + inventoryBrief(pair.repoPath),
      source: 'spec-authoring output',
      repoPath: pair.repoPath,
    },
    specDocs: docs,
    ...(reconByRepo.get(pair.repoPath) && hasText(reconByRepo.get(pair.repoPath).reconPath) ? { detailingPath: reconByRepo.get(pair.repoPath).reconPath } : {}),
    story: { id: pair.story.id, key: pair.story.key, title: pair.story.title },
    pluginRoot: lifecycle.pluginRoot,
    artifacts: artFor(`tasks:${slug}`, [...docs.map((d) => d.path), artPath(`story-${slug}.json`)], { slug }),
    beads: beadsArgs,
    ...(DESIGN_SYSTEM.packagesDir ? { packagesDir: DESIGN_SYSTEM.packagesDir } : {}),
    ...(staleWhy.has(`tasks:${slug}`) ? { upstreamChange: staleWhy.get(`tasks:${slug}`) } : {}),
  }
}
/** Decomposes one Story and writes its Tasks, or writes the saved task set when the step is complete; returns { ok, artifact } or { ok: false, stage, reason }. */
async function decomposeStory(pair) {
  const slug = repoSlug(pair.repoPath)
  const tasksPhase = `tasks:${slug}`
  const tasksHit = await resumeFresh(tasksPhase)
  const replay = !!(tasksHit && ART_ON && tasksHit.names.includes(`tasks-${slug}.json`))
  const r = await settleWorkflow('agent-teams-workforce:task-decomposition', replay ? { ...decompArgs(pair), replay: true } : decompArgs(pair))
  if (r && r.rerun && hasText(r.rerun.case)) {
    // The rerun case is in the run ledger, so the dashboard shows which applied and why.
    runLedger.push({ phase: 'tasks', event: 'task-rerun', phaseId: tasksPhase, repoPath: pair.repoPath, ...r.rerun })
    log(`Tasks for ${pair.repoPath}: rerun case ${r.rerun.case} — ${r.rerun.reason}`)
  }
  if (r && r.ok === true) {
    if (replay) reuseFrom(tasksPhase, tasksHit)
    await acceptPhase(tasksPhase, replay ? 'reused' : 'passed')
    return { ok: true, artifact: r }
  }
  return {
    ok: false,
    stage: (r && r.stage) || null,
    reason: (r && (r.reason || r.error)) || (r ? 'the decomposition produced no Task' : 'task-decomposition returned nothing'),
    cause: causeOf(r),
    ...(r && Array.isArray(r.uncitedItems) ? { uncitedItems: r.uncitedItems } : {}),
    ...(!r || r.dispatchFailed === true ? { dispatchFailed: true, dispatchFailures: (r && r.dispatchFailures) || [] } : {}),
  }
}
const decompResults = await parallel(specPairs.map((pair) => () => decomposeStory(pair)))
for (const [pairIndex, pair] of specPairs.entries()) {
  const decomposition = decompResults[pairIndex]
  if (!decomposition || !decomposition.ok) {
    decompositionFailures.push({
      repoPath: pair.repoPath,
      storyKey: pair.story.key || null,
      stage: (decomposition && decomposition.stage) || null,
      reason: (decomposition && decomposition.reason) || 'the task-decomposition phase threw',
      cause: causeOrOther(decomposition && decomposition.cause),
      dispatchFailed: !!(decomposition && decomposition.dispatchFailed),
      dispatchFailures: (decomposition && decomposition.dispatchFailures) || [],
      ...(decomposition && Array.isArray(decomposition.uncitedItems) ? { uncitedItems: decomposition.uncitedItems } : {}),
    })
    log(`Task Decomposition FAILED for ${pair.story.key || pair.repoPath}: ${(decomposition && decomposition.reason) || 'threw'}`)
    continue
  }
  decompositions.push({ repoPath: pair.repoPath, storyKey: pair.story.key || null, artifact: decomposition.artifact })
  const storyKeyForTasks = pair.story.key
  const storyTasks = decomposition.artifact.tasks
  for (const t of storyTasks) {
    tasks.push({
      key: `${storyKeyForTasks}-${t.key}`,
      id: t.id,
      elabKey: t.elabKey,
      action: t.action,
      title: t.title,
      parentStoryId: pair.story.id,
      storyKey: storyKeyForTasks,
      dependsOn: (Array.isArray(t.dependsOn) ? t.dependsOn : []).map((d) => `${storyKeyForTasks}-${d}`),
    })
  }
  recRuled(`Story ${storyKeyForTasks} (${pair.repoPath}) decomposed into ${storyTasks.length} Task(s).`)
}
produced.stories = stories
produced.decompositions = decompositions
produced.decompositionFailures = decompositionFailures
produced.tasks = tasks
if (!decompositions.length && !nothingToBuild) {
  recRuled(null, { status: 'failed', failure: { stage: 'task-decomposition', reason: 'no Story produced tasks' } })
  return repositoriesIncomplete(specFailures, decompositionFailures, { stage: 'task-decomposition', partial: { ...produced } })
}

const crossStory = { ran: false, reason: null, note: null, edges: [], rejected: 0, written: null }
/** The Task edges between Stories that the delta's requires relations make, from depscore.py closure-edges; its warnings are reported. */
const closureEdges = { edges: [], warnings: 0 }
if (ART_ON && repos.length) {
  const out = await runScript('beads:closure-edges', 'Task Decomposition', `closure-edges --dir ${shellq(ART_DIR)} --repos ${shellq(repos.join(','))}`)
  if (!out || out.error) log(`Prerequisites: depscore.py closure-edges did not run: ${(out && out.error) || 'no result'}`)
  else {
    closureEdges.edges = Array.isArray(out.edges) ? out.edges : []
    closureEdges.warnings = Number(out.summary && out.summary.warnings) || 0
  }
  if (closureEdges.warnings) log(`Prerequisites: ${closureEdges.warnings} required item(s) with no Task, no open bead and not done (listed under warnings in ${out.relayFile})`)
  if (closureEdges.edges.length) log(`Prerequisites: ${closureEdges.edges.length} Task edge(s) between Stories from the delta's requires relations`)
}
produced.closureEdges = closureEdges
if (decompositions.filter((d) => Array.isArray(d.artifact.tasks) && d.artifact.tasks.length).length < 2) {
  crossStory.note = 'the Tasks sit in one Story or none'
} else {
  crossStory.ran = true
  const depsHit = await resumeFresh(TASK_DEPS_PHASE)
  const spanArgs = `--dir ${shellq(ART_DIR)} --repos ${shellq(repos.join(','))}`
  const edgeOut = (name) => `--out ${shellq(`${ART_DIR}/task-edges/${name}.json`)}`
  /** Writes the saved Task edges between Stories to beads with depscore.py write-all-task-edges; returns its checked summary or null. */
  const writeEdges = async () => {
    const out = await runScript('beads:write-all-task-edges', 'Task Decomposition', `write-all-task-edges --epic ${shellq(epicBeadId)} ${spanArgs} ${edgeOut('all')}`)
    if (out.error) {
      crossStory.reason = `depscore.py write-all-task-edges did not write the Task edges between Stories: ${out.error}`
      return null
    }
    return out.summary && out.summary.blockers ? out.summary : null
  }
  let ran = null
  if (!ART_ON) {
    crossStory.reason = 'no artifact working directory is configured, so there is no saved task-deps.json to write'
  } else if (depsHit && depsHit.names.includes('task-deps.json')) {
    reuseFrom(TASK_DEPS_PHASE, depsHit)
    await acceptPhase(TASK_DEPS_PHASE, 'reused')
    ran = await writeEdges()
  } else {
    const byStory = new Map()
    for (const t of tasks) {
      if (!byStory.has(t.storyKey)) byStory.set(t.storyKey, [])
      byStory.get(t.storyKey).push(t)
    }
    const pairOf = new Map(specPairs.map((p) => [p.story.key, p]))
    const listing = Array.from(byStory, ([storyKey, list]) => {
      const pair = pairOf.get(storyKey)
      const repo = (pair && pair.repoPath) || 'repository not recorded'
      const file = pair ? artPath(`tasks-${repoSlug(pair.repoPath)}.json`) : null
      return (
        `Story ${storyKey} [${repo}]${file ? ` — descriptions, spec sections, requirements and surfaces: ${file} (Task ${storyKey}-<key> is the task with that key there)` : ''}\n` +
        list
          .map((t) => `- ${t.key}: ${t.title}${t.dependsOn.length ? `\n    already depends on (same Story): ${t.dependsOn.join(', ')}` : ''}`)
          .join('\n')
      )
    }).join('\n\n') + (closureEdges.edges.length
      ? `\n\nTHESE EDGES BETWEEN STORIES STAND: the architecture states them (an item requires another), and the workflow writes them. Do not return them again; add only the edges the architecture does not state:\n${closureEdges.edges.map((e) => `- ${e.from} -> ${e.to}: ${e.reason}`).join('\n')}`
      : '')
    const depsInputs = specPairs.map((p) => artPath(`tasks-${repoSlug(p.repoPath)}.json`)).filter(Boolean)
    const mappingSchema = {
          type: 'object',
          additionalProperties: false,
          required: ['edges', 'acyclic'],
          properties: {
            edges: {
              type: 'array',
              items: {
                type: 'object',
                additionalProperties: false,
                required: ['from', 'to', 'kind', 'reason'],
                properties: {
                  from: { type: 'string' },
                  to: { type: 'string' },
                  kind: { type: 'string', enum: ['data', 'contract', 'infrastructure', 'event-flow'] },
                  reason: { type: 'string' },
                },
              },
            },
            acyclic: { type: 'boolean' },
            cycle: { type: 'array', items: { type: 'string' } },
          },
        }
    const mappingCandidate = artPath('candidates/task-deps.json')
    const inputBinding = await relayKit.artifactRevision(settleAgent, { label: 'sequence:inputs', phase: 'Task Decomposition', runner: relayRunner(), files: depsInputs, relayFile: nextRelayFile('task-deps-inputs'), context: { epic: epic.id, listing } })
    if (!inputBinding.ok) log(`Cross-Story Task dependencies: the inputs could not be fingerprinted (${inputBinding.error}); the mapping is bound to no revision`)
    const inputRevision = inputBinding.ok ? inputBinding.revision : ''
    const mapDependencies = () => settleAgent(
      `Derive the Task-to-Task build dependencies whose two ends are Tasks in different Stories of Epic ${epic.id} — ${epic.title || ''}. Each Story is one repository's slice; the edges inside each Story are already drawn and listed. Read each Story's saved task file named below for what each Task builds. Return ONLY edges whose two ends are Tasks in DIFFERENT Stories, referencing Tasks by their key exactly as given. An edge "from -> to" means "from must be built before to".

Add an edge ONLY where a Task cannot be built until a Task in another Story is built: an API it consumes that the other Task provides, an event contract whose producer must publish first, a table, bucket or IAM grant the other repository provisions. Sharing a domain or this Epic is not a dependency. Type each edge as data, contract, infrastructure or event-flow and justify it in one line.

The whole Task graph — the edges already drawn plus yours — must be acyclic. If the only honest reading implies a cycle, set acyclic=false and name the cycle as Task keys; return the edges you found, and the workflow drops each edge that closes a cycle.

Do NOT add, remove, split or rescope Tasks. Do NOT write code.

${listing}${relayKit.artifactBrief(mappingCandidate, mappingSchema, inputRevision, relayRunner().replace(/[^/]+$/, 'artifactcontract.py'))}

Write nothing to beads: the workflow writes the edges from that file.`,
      {
        label: 'sequence:cross-story-tasks',
        effort: 'medium',
        phase: 'Task Decomposition',
        agentType: 'task-dependency-mapper',
        schema: relayKit.ARTIFACT_SCHEMA,
      }
    )
    const accepted = dispatchInterruption ? null : await relayKit.authorArtifact(settleAgent, {
      label: 'sequence:accept-cross-story', phase: 'Task Decomposition', runner: relayRunner(),
      candidate: mappingCandidate, file: artPath('task-deps.json'), schema: mappingSchema, revision: inputRevision,
      relayFile: nextRelayFile('accepted-task-deps'), keys: ['acyclic', 'cycle'],
    }, mapDependencies, () => !!dispatchInterruption)
    const mapped = accepted && accepted.facts
    if (!accepted || !accepted.ok) {
      crossStory.reason = `The authoritative cross-Story dependency artifact was not accepted: ${accepted && accepted.error || 'dispatch interrupted'}`
    } else {
      if (mapped.acyclic === false) log(`Cross-Story Task dependencies: the mapper reported a cycle (${(mapped.cycle || []).join(' -> ') || 'not named'}); the edges that close it are dropped when they are written`)
      const art = artFor(TASK_DEPS_PHASE, depsInputs)
      const rec = await runProgram('sequence:record', 'Task Decomposition', ['python3', art.script, 'record', artPath('task-deps.json'), '--epic', art.epicId, '--phase', art.phase, ...(depsInputs.length ? ['--inputs', ...depsInputs] : [])], { tail: 5 })
      if (!rec.ok || rec.exitCode !== 0) log(`Cross-Story Task dependencies: the accepted mapping was not recorded (${rec.error || rec.stderrTail || rec.exitCode}); its edges are written`)
      else await acceptPhase(TASK_DEPS_PHASE, 'passed')
      ran = await writeEdges()
    }
  }
  if (ran) {
    const plan = ran
    if (plan) {
      crossStory.edges = Object.entries(plan.blockers).flatMap(([to, froms]) => (Array.isArray(froms) ? froms : []).map((from) => ({ from, to })))
      crossStory.rejected = Number(plan.rejected) || 0
      crossStory.written = { added: Number(plan.added) || 0, removed: Number(plan.removed) || 0, standing: Number(plan.standing) || 0 }
      const byKey = new Map(tasks.map((t) => [t.key, t]))
      for (const e of crossStory.edges) {
        const to = byKey.get(e.to)
        if (to) to.dependsOn = [...to.dependsOn, e.from]
      }
    } else {
      log('Cross-Story Task dependencies: the write-all-task-edges summary was not relayed; beads is read at finish')
    }
  }
  if (crossStory.reason) log(`Cross-Story Task dependencies: ${crossStory.reason}`)
}
produced.crossStoryDependencies = crossStory
recRuled(`${tasks.length} Task(s) across ${decompositions.length} Story/Stories; ${crossStory.edges.length} edge(s) across Stories.`, { status: 'done' })

enterPhase('Finish')
// Done once every span repository has its outcome: a Story decomposed into its Tasks, or none
// to build. A failed repository makes the run return ok:false (repositoriesIncomplete).
const done = nothingToBuild || (!specFailures.length && !decompositionFailures.length)
const finishArgs = [
  `elaboration-finish --epic ${shellq(epicBeadId)}`,
  lifecycle.owner ? `--owner ${shellq(lifecycle.owner)}` : '',
  done ? '--done' : '',
].filter(Boolean).join(' ')
const finishOut = await runScript('epic:finish', 'Finish', finishArgs)
lifecycle.finish = finishOut
const finishOk = !!(finishOut && !finishOut.error && finishOut.ok === true)
const epicMarkedDone = finishOk && !!finishOut.lifecycle
const scoringLine = finishOk
  ? `Epic ${epicBeadId} and ${(finishOut.summary && finishOut.summary.tasksScored) || 0} Task(s) scored; Epic ${epicMarkedDone ? 'is elaboration_state=done' : 'stays in_progress'}. `
  : `Scoring did not run for Epic ${epicBeadId}: ${(finishOut && finishOut.error) || 'no result'}. `
log(scoringLine)
const storyEdges = (finishOut && finishOut.storyEdges) || null
const named = (list) => (Array.isArray(list) ? list : []).map((x) => `${(x.stories || []).join(' / ')}${(x.tasks || []).length ? ` (Tasks ${x.tasks.join(', ')})` : ''}`).join('; ')
const storyEdgeLine = !storyEdges
  ? ''
  : storyEdges.error
    ? `Story edges NOT written — ${storyEdges.error}. `
    : `Story edges: ${(storyEdges.added || []).length} added, ${(storyEdges.removed || []).length} removed, ${storyEdges.unchanged || 0} unchanged. ` +
      (storyEdges.ok ? '' : `Not written for ${(storyEdges.refusedStories || []).join(', ')} — ${storyEdges.reason}${named(storyEdges.conflicts) ? `; the sources disagree on ${named(storyEdges.conflicts)}` : ''}${named(storyEdges.cycles) ? `; a cycle runs through ${named(storyEdges.cycles)}` : ''}. `)
if (storyEdgeLine) log(storyEdgeLine)
const targetRemoval = { removed: false, commit: null, reason: null }
if (epicMarkedDone) {
  if (!hasText(a.archPath)) {
    targetRemoval.reason = 'no archPath was passed, so the target folder was not removed'
  } else {
    const message = `docs(architecture): remove the ${delta.subject || 'approved'} target once the Specs and Tasks made from its delta are written`
    const removed = await runScript('arch:target-remove', 'Finish', `arch-target-remove --arch-root ${shellq(a.archPath)} --target-dir ${shellq(delta.targetDir)} --message ${shellq(message)}`)
    if (removed && !removed.error && removed.ok === true) {
      targetRemoval.removed = removed.removed === true
      targetRemoval.commit = removed.commit || null
    } else {
      targetRemoval.reason = removed && !removed.error ? (removed.refusals || []).join('; ') || 'refused' : (removed && removed.error) || 'no result'
    }
  }
} else {
  targetRemoval.reason = 'the Epic is not done, so its Specs and Tasks are not all written'
}
const targetLine = targetRemoval.removed
  ? `Target ${delta.targetDir} removed${targetRemoval.commit ? ` (commit ${targetRemoval.commit})` : ''}. `
  : `Target ${delta.targetDir} kept: ${targetRemoval.reason || 'it was already gone'}. `
log(targetLine)
const counted = (x) => (x && typeof x === 'object' ? (Number(x.created) || 0) + (Number(x.updated) || 0) : 0)
const beadsEmitted =
  specPairs.reduce((n, p) => n + counted(p.spec && p.spec.summary), 0) +
  decompositions.reduce((n, d) => n + counted(d.artifact && d.artifact.summary), 0)
const writeLine = `Written to beads: ${specPairs.length} Story/Stories and ${tasks.length} Task(s); ${beadsEmitted} bead(s) created or updated. `
log(writeLine)
const degraded = !finishOk || !done
const hierarchy = {
  epic,
  stories: specPairs.map((p) => ({ key: p.story.key, id: p.story.id, elabKey: p.story.elabKey, repoPath: p.repoPath, title: p.story.title })),
  tasks: tasks.map((t) => ({ key: t.key, id: t.id, elabKey: t.elabKey, parentStoryId: t.parentStoryId, title: t.title, dependsOn: t.dependsOn })),
}
const runJournal = {
  prd,
  specFailures,
  decompositionFailures,
  delta,
  results: {
    reconciliationByRepo: produced.reconciliationByRepo,
    architecture: (architecture.artifact || null),
    repoScoping: scoping,
    trdAuthoring: (trdAuthoring.artifact || null),
    specAuthoring: specPairs.map((p) => ({ repoPath: p.repoPath, artifact: p.spec })),
    decomposition: decompositions,
  },
}
recRuled(writeLine + scoringLine, { status: 'done' })
const common = {
  degraded,
  beadsEmitted,
  lifecycle: { owner: lifecycle.owner, start: lifecycle.start, finish: lifecycle.finish, done: epicMarkedDone },
  ...(storyEdges ? { storyEdges } : {}),
  crossStoryDependencies: crossStory,
  closureEdges,
  hierarchy,
  repoSpan: repos,
  targetRemoval,
  ...(createdRepos.length ? { createdRepos } : {}),
}
if (!nothingToBuild && (specFailures.length || decompositionFailures.length)) {
  return { ...(await repositoriesIncomplete(specFailures, decompositionFailures, runJournal)), ...common }
}
return {
  ...handback(
    true,
    'finish',
    `1 epic, ${specPairs.length} story/stories, ${tasks.length} task(s) for the PRD at ${prd.path || prd.id || prd.title || '(unpathed)'}. ` +
      `Span: ${repos.join(', ')}. ` +
      `Architecture approved for ${(architecture.artifact && architecture.artifact.subject) || 'the Epic'}; its target is integrated into the effective version. ` +
      writeLine +
      scoringLine +
      storyEdgeLine +
      targetLine +
      (specFailures.length || decompositionFailures.length || crossStory.reason || closureEdges.warnings
        ? `DEGRADED: ${specFailures.length} repo(s) produced no spec, ${decompositionFailures.length} Story/Stories produced no tasks${crossStory.reason ? `, ${crossStory.reason}` : ''}${closureEdges.warnings ? `, ${closureEdges.warnings} prerequisite(s) with no Task, no open bead and not done` : ''}.` +
          (specFailures.length ? ` No spec: ${specFailures.map((x) => `${x.repoPath} at ${x.stage || 'spec-authoring'}: ${x.reason}`).join('; ')}`.slice(0, 1500) : '')
        : ''),
    runJournal
  ),
  ...common,
}
  })()
} catch (err) {
  const message = String((err && err.message) || err)
  const deaths = dispatchDeaths()
  const where = currentPhase || 'unknown'
  const stage = String(where).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'unknown'
  log(`RUN ABORTED in ${where}: ${message.slice(0, 300)}`)
  result = partial(stage, { reason: `the run threw in ${where}: ${message.slice(0, 300)}`, dispatchFailed: deaths.length > 0, dispatchFailures: deaths })
} finally {
  // Preserve every failure and release the lifecycle claim unless a genuine owner-fact hold
  // was requested. Failed-run diagnosis does not create a human action or a repair dispatch.
  const failed = !!dispatchInterruption || !result || result.ok === false
  if (failed) result = withFailure(result)
  const finishedDone = !!(lifecycle.finish && !lifecycle.finish.error && lifecycle.finish.lifecycle)
  if (lifecycle.started && !finishedDone && !lifecycle.held && !lifecycle.holdAttempted) {
    lifecycle.release = await runScript(
      'epic:release',
      currentPhase || 'Epic Lifecycle',
      `elaboration-release --epic ${shellq(epicBeadId)} --owner ${shellq(lifecycle.owner)}`
    )
    if (result) result.lifecycle = { ...(result.lifecycle || {}), owner: lifecycle.owner, start: lifecycle.start, finish: lifecycle.finish, release: lifecycle.release, done: false }
  }
  if (result && lifecycle.holdAttempted && !lifecycle.held) result.lifecycle = { ...(result.lifecycle || {}), owner: lifecycle.owner, start: lifecycle.start, finish: lifecycle.finish, held: false, holdWrite: lifecycle.holdWrite, released: false, done: false }
  if (result && lifecycle.held) result.lifecycle = { ...(result.lifecycle || {}), owner: lifecycle.owner, start: lifecycle.start, finish: lifecycle.finish, held: true, heldCause: HOLD_CAUSE, done: false }
  enterPhase('Run Ledger')
  const detailPath = persistRun(result && result.ok ? 'ok' : `failed:${(result && result.stage) || 'unknown'}`)
  if (result) result.artifacts = { dir: artReport.dir, epicId: artReport.epicId, phases: { ...artPhases }, filing: { ...artReport.filing } }
  if (result) result.detailPath = detailPath || null
}
return dispatchOutcome(result)
