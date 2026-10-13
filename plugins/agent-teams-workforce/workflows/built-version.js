export const meta = {
  name: 'built-version',
  description:
    "Records what a Story built, after its deploy to AWS dev is verified and before its pull request. It runs as the child steps of the Story's deploy:built-version journal step (journal: { path, run, step }): it reads the Story's step journal once through the checked relay, plans its child steps when the step has none, begins at the first child step that is not done, and reports each step started, done with its artifacts and the steps its result adds, or failed with its cause, as a STEP-JOURNAL line on its log. The child steps are defined in skills/pipeline-contracts/schemas/pipeline-steps.json: snapshot, compare, and, when the comparison records a difference, correct, review (a review with findings adds a correction and another review), approve and remove. One prd-reality-reconciler session compares the code on the Story's branch with the effective views for the Story's repository and the Epic's delta items placed in it, and writes each difference as a view in built/<subject>/ (in-review), citing file:line. A Story with no difference writes nothing. When a difference exists, depscore.py arch-state confirms every built view is in-review, the architecture-maintainer corrects the effective version from the built views, the architecture-conformance-reviewer checks the correction (the review fails the step when the correction does not conform after 2 corrections that answered findings), depscore.py arch-approve sets the corrected files to effective, and depscore.py arch-built-remove deletes the built views the effective version now matches — those the architecture-maintainer reports matched and the architecture-conformance-reviewer confirms in matchedBuiltViews — and commits the removal. depscore.py arch-snapshot measures what each session wrote: the comparison may write only under built/<subject>/, and the files the correction wrote are reviewed whether reported or not. A write under arc42 section 2 fails the run and is undone: depscore.py arch-constraints fingerprints that folder before and after and copies it aside, and depscore.py arch-constraints-restore puts it back. Returns { ok, stage, beadId, headline, differences, builtFiles, architectureUpdate, conformance, approval, removal }, with step naming the step that failed.",
  phases: [
    { title: 'Compare', detail: "a prd-reality-reconciler session compares the Story branch's code with the effective views and the delta items, and writes each difference to built/<subject>/" },
    { title: 'Correct', detail: 'the architecture-maintainer corrects the effective version from the built views; the architecture-conformance-reviewer checks it; depscore.py arch-approve sets the corrected files to effective' },
    { title: 'Remove', detail: 'depscore.py arch-built-remove deletes the built views the effective version now matches and commits the removal' },
  ],
}
// ===== SHARED BLOCK fable — BEGIN (canonical: scripts/shared-blocks/fable.js; filled from skills/pipeline-contracts/schemas/driver-surface.schema.json; edit there, then: node scripts/shared-blocks.mjs --write) =====
const ownedCoreContracts = "---\nname: subagent-contract\ndescription: Bounded specialist work in direct sessions, with file outputs and independent validation.\nuser-invocable: false\n---\n\n# Direct specialist session\n\nPerform the role in your definition. The brief gives a bead, the journal step id, the request,\ninput paths and an output path. It names only the inputs this step needs. The skills your\ndefinition lists are in your context; read the applicable contract before writing. The artifact-handoff skill is the shared producer/reviewer authority.\nWrite the result file; Python validates it, records it in the step journal and keeps pipeline state.\nStart another agent only when your definition has a `startsRoles` list, and only agents with\nthose roles. An agent that was started by another agent starts no one. Never invoke a Workflow\nor a command runner. When the brief carries ARTIFACT CONTRACT DATA, write the progress\nfile it names and record a checkpoint or the submission only by running the artifactcontract.py\ncommands it gives; never write a checkpoint sidecar any other way. The progress file's fields are\ndefined by the artifact-handoff skill (schemas/checkpoint.schema.json, $defs/Progress). If resumed,\ninspect and continue the existing result and input files; retain completed valid work.\n\nOnly assigned files are writable. Reviewers may write their result, never the reviewed source.\nNever write arc42 section 2, expose secrets or touch apps/marketing repositories. Never run keeper\nor supervisor. Agents do not write pipeline beads; Python owns those writes. If reading beads is\nneeded, use the central atw-bd wrapper from beads-contract. No agent creates a bug or loose Task.\nRead repository AGENTS.md before an authorized repository edit; input-only reads do not require\nloading every repository's instruction tree.\n\nMissing inputs are named dependencies, not permission to invent facts. Distinguish observed\nfacts, assumptions and unresolved questions in the artifact's supported fields. Do not mark your\nown work approved. Code that no pipeline built is a hint of how something\nwas once solved and may be stale. A difference between such code and arc42 is never a discrepancy\nand never a finding. The matrix marks each element's code `none`, `legacy`, `built` or `deployed`;\nonly `built` and `deployed` code is trusted and is expected to match the architecture.\n\n## Helpers and the journal\n\nAn agent that starts other agents inside its own session and then continues follows one pattern,\nwith `atw-step-journal` and the journal file its brief names:\n\n1. Write your own output first: the file your definition names as your first output.\n2. When you start your first agent, add it as a child step of your own step\n   (`atw-step-journal add --parent <your step> --agent <agent> --description \"<what it does>\"\n   --purpose \"<why>\"`), and add one last child step whose description is \"Finish\", with yourself\n   as the agent and your own step in its `inputs`. `--steps-json` adds several child steps in one\n   write.\n3. Add each further agent as a child before \"Finish\" (`--after <sibling id>`). Mark each child\n   running when you start it (`atw-step-journal start --step <id>`), and record the request file\n   you wrote for it at once (`atw-step-journal artifact --step <id> --name request --kind file\n   --path <path>`). When the agent returns, record the file it returned as the artifact `answer`\n   and mark the child done (`atw-step-journal done --step <id>`).\n4. When your work is complete, record your result as the artifact of \"Finish\", under the name\n   your definition gives it, and mark \"Finish\" done. Your own step is then done.\n5. After an interruption the script launches the first child that is not done: an agent left\n   running is launched from the `request` file its step holds, and \"Finish\" is launched as you.\n   Launched for \"Finish\", read your own output, the `answer` files and your partial result, and\n   continue.\n\nThe names are fixed, because the script reads them: `request` (or `question`, for a question file\nto `architecture-question.schema.json`) for what an agent is asked, `answer` for what a specialist\nreturned, `ruling` for a decider's ruling, `review` for a review. A step is handed the artifacts\nof the steps its `inputs` name, and of the steps below them.\n\nAn agent that adds steps for the script to run, and starts no agent itself, records the file a\nstep needs on its own step under the same names and names its own step in that step's `inputs`.\n\nAn agent that starts no other agent adds no step.\n\n## Resource use and incremental review\n\n- Use tokens conscientiously without compromising required correctness, completeness, safety or evidence. Before a material optional expansion, identify its unresolved need and expected benefit in existing progress. Routine tools need no justification. Do not add a report, review pass, token quota or human approval gate for this rule; omit optional work with no concrete benefit.\n- Makers and reviewers use the same applicable requirements, constraints and completion criteria. Review determines actual correctness, including passing sound work; finding more failures is not success. Do not invent requirements or turn stylistic preferences into blocking defects. Preserve necessary safety and regression checks.\n- Use the caller's finding format to identify the affected location, requirement/dependency at risk, observed evidence and actionable correction with a verifiable pass condition. Distinguish defects, missing evidence and proposed new requirements. Never claim unperformed checks passed.\n- Revise original artifacts incrementally. Retain valid work and applicable evidence. Rereview changed scope and affected dependencies; reopen accepted work only when new evidence or demonstrated impact invalidates its earlier evidence, and state why. Preserve required independent review.\n\n## Technical gaps are decided, not escalated\n\nWhere the approved or effective architecture, a requirement or an owner answer is silent, unclear or self-contradictory on a technical matter, decide it by best practice, with AWS Well-Architected guidance and AWS documentation as the evidence (see AWS evidence authority below). Record the decision, the gap it closes and its cited evidence in your result, and continue. A technical matter is any question of how the system works: services, patterns, interfaces, data, values and limits, security and privacy controls, cost and operations. A recorded decision is a claim reviewers check like any other; it is not an open item. No agent ends with \"these two documents disagree\". Where one statement is in an effective document and the other is not, the effective one stands without discussion. Otherwise the agent responsible for the work settles it and records the settlement in the matrix.\n\nOwner-only facts (credentials, money and destructive actions outside AWS dev), irreconcilable business requirements and section 2 conflicts go through the caller's owner channel. Technical choices remain with the specialists. Never put a technical question to the owner or any person, and never hold work waiting for a technical answer.\n\n## The approved architecture is authoritative\n\nThe approved (effective) architecture and the owner's answers are authoritative. Older documents, repository READMEs and existing code are evidence of the current state: they show what exists and what still has to change, never that the approved architecture or an owner answer is wrong. Where they disagree with the approved architecture, the approved architecture holds and the difference is work to plan, not a conflict to raise. The approved architecture changes only through the solutions architect's decisions, written by the maintainer and reviewed, or a reviewed correction from what a Story built.\n\n## AWS evidence authority\n\nBefore any AWS claim, design choice or question, check the AWS MCP Server documentation tools (`search_documentation`, `read_documentation`, `retrieve_skill`) and the relevant AWS plugin skills (`aws-core:*`, for example `aws-core:aws-cdk`, `aws-core:aws-serverless`, `aws-core:aws-iam`, `aws-core:aws-networking`, `aws-core:aws-well-architected-review`), including the applicable Well-Architected principles. A question AWS documentation can answer is answered from it and never reaches the owner. Retain source references and the concrete tradeoffs. Existing generated architecture and model recollection do not establish correctness. Makers and reviewers use this same evidence criterion.\n\nApply guidance to stated requirements, deployment, usage and cost constraints rather than hypothetical scale. Where AWS guidance conflicts with a business requirement or a section 2 constraint, the requirement or constraint holds: record the conflict and the design that honours it, and do not silently substitute a preferred AWS pattern. Missing required MCP/skill access is a named blocker or uncertainty, never a passed check. Coordinators may research and route AWS questions, but cannot author or approve designs.\n"
const ownedArtifactContract = "---\nname: artifact-handoff\ndescription: Shared file contracts for direct specialist sessions; producers and consumers read the same schemas and completion rules.\n---\n\n# Direct artifact handoff\n\nRead [Epic contracts](epic-contracts.md) for the artifact assigned to this session, including its\nfields, interpretation and completion criteria. JSON schemas are in [schemas/](schemas/).\nProducers and reviewers use this same contract; a reviewer cannot add unstated requirements.\n\nThe brief contains only a bead id, labeled absolute input paths, an absolute output path, and a\none-line outcome. Read the named files yourself. Write the complete result to the exact output\npath. Write only assigned outputs.\nFor a JSON output write one strict JSON value with unique keys; for a document write nonempty\nUTF-8 Markdown. Do not paste file contents into a response. A final reply may name the result path.\n\nPython validates the file against the schema, checks declared document citations and records the\nfile in the step journal. The agent does not accept its own result, compute revision bindings,\nsubmit StructuredOutput, or run artifact checkpoint or\nsubmission helpers. There is no machine mode or command-runner handoff in direct sessions.\nA structurally valid artifact is not automatically a semantically correct one.\n\nOn a corrective pass, read the labeled validation-errors input and the existing output, repair the\nspecific findings and affected references, and preserve valid work. On interruption retain the\nactual files; resumption continues those files. Do not fabricate completion for missing reasoning.\nNamed missing inputs or remaining uncertainties belong in the contract's existing evidence fields;\nnever add fields to a closed schema or return a success reference for absent work.\n\n## Generated contract types\n\nEach schema in [schemas/](schemas/) is the one definition of its contract. Python code never\nrestates a key, type or allowed value: it imports the module that\n`scripts/generate_contract_types.py` generates from the schema, and\n`scripts/check_contract_types.py` fails when a generated module is stale. Run\n`python3 scripts/generate_contract_types.py` after changing a schema.\n\n| Schema | Generated module |\n|---|---|\n| `schemas/task-deps.schema.json` (Cross-Story Task dependencies) | `scripts/task_deps_contract.py` |\n"
const ownedBaselineContract = "---\nname: architecture-baseline\ndescription: The one set of criteria that the solutions architect works to and the reviewers review against, with the level of each.\n---\n\n# Architecture criteria\n\nRead [the review standard](review-standard.md) before designing, writing, reviewing or\nruling on architecture, a TRD or a spec. It is the common basis: the solutions architect\ndevelops the architecture and the TRD to exactly these criteria, the spec authors develop the\nspecs to them, and reviewers apply exactly these and no others. `review-criteria.json` beside\nit holds the same criteria as data: each criterion's id, level, home document and text, the\nagents responsible for each level with its review point, and for each reviewer group its\nreviewer, the criteria it covers and the rule that selects it. The standard is written from\nthat file by `artifact-handoff/scripts/review_criteria.py`, so a criterion is changed in\n`review-criteria.json` and nowhere else.\n\nEvery criterion has a level: architecture (arc42), technical requirement (the TRD) or\nimplementation (the specs and Tasks). A criterion is satisfied by the document that is its\nhome. Nobody asks a document for detail below its level.\n\nAn effective document is approved design. It is not evidence that anything is built, and it\nis not a permanent constraint on a later PRD.\n\nThe matrix records what is approved and what code is trusted. Read it through `atw-matrix`.\n\n## The files the team hands on\n\nEach file an agent of the architecture team writes has one schema, in\n`${CLAUDE_PLUGIN_ROOT}/skills/artifact-handoff/schemas/`. A definition names its files by\nschema file name, for example `architecture-result.schema.json`; read the schema there before\nwriting the file. Every shape is defined once, in `architecture-result.schema.json`, and the\nother schema files refer to it.\n"
const ownedAgentContracts = {"acceptance-criteria-reviewer":{"artifactCapable":false,"agentType":"agent-teams-workforce:acceptance-criteria-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"acceptance-criteria-writer":{"artifactCapable":true,"agentType":"acceptance-criteria-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:artifact-handoff"]},"accessibility-validator":{"artifactCapable":true,"agentType":"agent-teams-workforce:accessibility-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:a11y-audit","agent-teams-workforce:senior-frontend"]},"advantage-evaluator":{"artifactCapable":false,"agentType":"agent-teams-workforce:advantage-evaluator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"adversarial-critique-adjudicator":{"artifactCapable":false,"agentType":"agent-teams-workforce:adversarial-critique-adjudicator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-security"]},"adversarial-review-loop-supervisor":{"artifactCapable":false,"agentType":"agent-teams-workforce:adversarial-review-loop-supervisor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"ambiguity-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:ambiguity-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"android-compose-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:android-compose-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:graphrag-lookup"]},"api-contract-designer":{"artifactCapable":true,"agentType":"api-contract-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:api-design-reviewer","agent-teams-workforce:architecture-baseline"]},"api-documentation-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:api-documentation-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer"]},"api-gateway-cdk-implementer":{"artifactCapable":true,"agentType":"api-gateway-cdk-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-gateway","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"api-specification-author":{"artifactCapable":true,"agentType":"api-specification-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer","agent-teams-workforce:artifact-handoff","agent-teams-workforce:skillspoke-events","agent-teams-workforce:architecture-baseline"]},"appsync-cdk-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:appsync-cdk-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"appsync-client-subscription-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:appsync-client-subscription-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend","agent-teams-workforce:graphrag-lookup"]},"architecture-boundary-guardian":{"artifactCapable":true,"agentType":"architecture-boundary-guardian","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:architecture-baseline"]},"architecture-conformance-reviewer":{"artifactCapable":true,"agentType":"architecture-conformance-reviewer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:arc42","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:architecture-baseline"]},"architecture-decider":{"artifactCapable":true,"agentType":"architecture-decider","skills":["agent-teams-workforce:architecture-baseline","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect"]},"architecture-diagram-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:architecture-diagram-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:architecture-diagramming","agent-teams-workforce:c4-diagramming","agent-teams-workforce:uml-diagramming","agent-teams-workforce:architecture-baseline"]},"architecture-fitness-function-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:architecture-fitness-function-author","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"architecture-impact-analyst":{"artifactCapable":false,"agentType":"agent-teams-workforce:architecture-impact-analyst","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:beads-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:graphrag-lookup"]},"architecture-maintainer":{"artifactCapable":true,"agentType":"agent-teams-workforce:architecture-maintainer","skills":["agent-teams-workforce:architecture-baseline","agent-teams-workforce:subagent-contract","agent-teams-workforce:arc42-maintain","agent-teams-workforce:c4-diagramming","agent-teams-workforce:uml-diagramming"]},"architecture-pattern-challenger":{"artifactCapable":true,"agentType":"architecture-pattern-challenger","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:architecture-baseline"]},"architecture-team-lead":{"artifactCapable":true,"agentType":"agent-teams-workforce:architecture-team-lead","skills":["agent-teams-workforce:architecture-baseline","agent-teams-workforce:subagent-contract"]},"architecture-tradeoff-skeptic":{"artifactCapable":true,"agentType":"architecture-tradeoff-skeptic","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:architecture-baseline"]},"athena-redshift-analytics-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:athena-redshift-analytics-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:graphrag-lookup"]},"auth-bypass-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:auth-bypass-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops","agent-teams-workforce:cognito"]},"aws-integration-test-runner":{"artifactCapable":true,"agentType":"agent-teams-workforce:aws-integration-test-runner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:test-failure-mindset","agent-teams-workforce:cumulative-regression"]},"aws-integration-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:aws-integration-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:cumulative-regression"]},"aws-solutions-architect":{"artifactCapable":true,"agentType":"aws-solutions-architect","skills":["agent-teams-workforce:architecture-baseline","agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:senior-security","agent-teams-workforce:graphrag-lookup"]},"beads-format-validator":{"artifactCapable":true,"agentType":"agent-teams-workforce:beads-format-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:beads-contract"]},"bedrock-integration-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:bedrock-integration-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:bedrock","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:senior-prompt-engineer","agent-teams-workforce:aws-agentic-ai","agent-teams-workforce:graphrag-lookup"]},"behavioral-signals-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:behavioral-signals-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:senior-data-scientist","agent-teams-workforce:product-analytics","agent-teams-workforce:graphrag-lookup"]},"bounded-context-mapper":{"artifactCapable":true,"agentType":"bounded-context-mapper","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:architecture-baseline"]},"brd-traceability-auditor":{"artifactCapable":true,"agentType":"agent-teams-workforce:brd-traceability-auditor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"built-architecture-comparer":{"artifactCapable":true,"agentType":"agent-teams-workforce:built-architecture-comparer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:architecture-baseline"]},"c4-diagram-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:c4-diagram-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:architecture-diagramming","agent-teams-workforce:c4-diagramming","agent-teams-workforce:architecture-baseline"]},"cdk-infrastructure-designer":{"artifactCapable":true,"agentType":"cdk-infrastructure-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:resource-naming","agent-teams-workforce:architecture-baseline"]},"cdk-infrastructure-drift-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:cdk-infrastructure-drift-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:cloudformation"]},"cdk-stack-author":{"artifactCapable":true,"agentType":"cdk-stack-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:cloudformation","agent-teams-workforce:resource-naming"]},"cds-finding-reviewer":{"artifactCapable":false,"agentType":"agent-teams-workforce:cds-finding-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","cds:apply-design-system","cds:audit-against-system"]},"cds-ui-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:cds-ui-implementer","skills":["agent-teams-workforce:subagent-contract","cds:apply-design-system","cds:audit-against-system","cds:compose-page","agent-teams-workforce:graphrag-lookup"]},"changelog-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:changelog-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:changelog-generator"]},"chassis-extension-implementer":{"artifactCapable":true,"agentType":"chassis-extension-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:lambda","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming","agent-teams-workforce:skillspoke-events"]},"code-correctness-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:code-correctness-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:code-reviewer"]},"code-quality-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:code-quality-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"code-refactoring-specialist":{"artifactCapable":true,"agentType":"agent-teams-workforce:code-refactoring-specialist","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:code-reviewer","agent-teams-workforce:graphrag-lookup"]},"code-style-and-linting-enforcer":{"artifactCapable":true,"agentType":"agent-teams-workforce:code-style-and-linting-enforcer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:code-reviewer"]},"cognito-lambda-trigger-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:cognito-lambda-trigger-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:cognito","agent-teams-workforce:lambda","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"completeness-checker":{"artifactCapable":false,"agentType":"agent-teams-workforce:completeness-checker","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"complexity-analyzer":{"artifactCapable":false,"agentType":"agent-teams-workforce:complexity-analyzer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:tech-debt-tracker"]},"constitutional-agent":{"artifactCapable":false,"agentType":"agent-teams-workforce:constitutional-agent","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"constraint-extractor":{"artifactCapable":true,"agentType":"agent-teams-workforce:constraint-extractor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"consumer-driven-contract-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:consumer-driven-contract-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-test-suite-builder","agent-teams-workforce:cumulative-regression"]},"context-curator":{"artifactCapable":false,"agentType":"agent-teams-workforce:context-curator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"contract-violation-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:contract-violation-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-test-suite-builder"]},"cost-architecture-reviewer":{"artifactCapable":true,"agentType":"cost-architecture-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-cost-operations","agent-teams-workforce:architecture-baseline"]},"cost-impact-reviewer":{"artifactCapable":true,"agentType":"cost-impact-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-cost-operations","agent-teams-workforce:architecture-baseline"]},"cross-repo-integration-test-coordinator":{"artifactCapable":false,"agentType":"agent-teams-workforce:cross-repo-integration-test-coordinator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"cross-service-contract-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:cross-service-contract-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-test-suite-builder"]},"data-consistency-checker":{"artifactCapable":true,"agentType":"agent-teams-workforce:data-consistency-checker","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb"]},"data-exposure-scanner":{"artifactCapable":true,"agentType":"agent-teams-workforce:data-exposure-scanner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"data-model-specification-author":{"artifactCapable":true,"agentType":"data-model-specification-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb","agent-teams-workforce:database-schema-designer","agent-teams-workforce:artifact-handoff","agent-teams-workforce:architecture-baseline"]},"data-pipeline-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:data-pipeline-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:cumulative-regression"]},"definition-of-done-enforcer":{"artifactCapable":true,"agentType":"agent-teams-workforce:definition-of-done-enforcer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"dependency-change-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:dependency-change-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dependency-auditor"]},"dependency-cve-auditor":{"artifactCapable":true,"agentType":"agent-teams-workforce:dependency-cve-auditor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dependency-auditor"]},"dependency-graph-extractor":{"artifactCapable":true,"agentType":"agent-teams-workforce:dependency-graph-extractor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"deployment-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:deployment-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"deployment-strategy-decider":{"artifactCapable":false,"agentType":"agent-teams-workforce:deployment-strategy-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:cove-prompt-design"]},"documentation-accuracy-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:documentation-accuracy-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"documentation-currency-auditor":{"artifactCapable":true,"agentType":"agent-teams-workforce:documentation-currency-auditor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"documentation-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:documentation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"domain-boundary-validator":{"artifactCapable":true,"agentType":"agent-teams-workforce:domain-boundary-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"domain-event-modeler":{"artifactCapable":true,"agentType":"domain-event-modeler","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:architecture-baseline","agent-teams-workforce:skillspoke-events"]},"dos-resilience-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:dos-resilience-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"dynamodb-access-layer-implementer":{"artifactCapable":true,"agentType":"dynamodb-access-layer-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"dynamodb-cost-optimizer":{"artifactCapable":true,"agentType":"dynamodb-cost-optimizer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb","agent-teams-workforce:aws-cost-operations"]},"dynamodb-schema-access-pattern-reviewer":{"artifactCapable":true,"agentType":"dynamodb-schema-access-pattern-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb"]},"dynamodb-streams-cdc-implementer":{"artifactCapable":true,"agentType":"dynamodb-streams-cdc-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:dynamodb","agent-teams-workforce:graphrag-lookup"]},"email-notification-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:email-notification-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:email-template-builder","agent-teams-workforce:sns","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:skillspoke-events"]},"epic-sequencer":{"artifactCapable":true,"agentType":"agent-teams-workforce:epic-sequencer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:epic-sequencing"]},"espresso-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:espresso-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:tdd-guide","agent-teams-workforce:cumulative-regression"]},"event-api-client-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:event-api-client-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming","agent-teams-workforce:skillspoke-events"]},"event-driven-consumer-implementer":{"artifactCapable":true,"agentType":"event-driven-consumer-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:sqs","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:sns","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming","agent-teams-workforce:skillspoke-events"]},"event-flow-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:event-flow-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda"]},"event-schema-designer":{"artifactCapable":true,"agentType":"event-schema-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:eventbridge","agent-teams-workforce:architecture-baseline","agent-teams-workforce:skillspoke-events"]},"event-schema-reviewer":{"artifactCapable":true,"agentType":"event-schema-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:skillspoke-events"]},"failure-mode-analyst":{"artifactCapable":true,"agentType":"failure-mode-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:observability-designer","agent-teams-workforce:architecture-baseline"]},"filing-clerk":{"artifactCapable":true,"agentType":"filing-clerk","skills":["agent-teams-workforce:subagent-contract","obsidian:obsidian-cli","obsidian:obsidian-markdown","agent-teams-workforce:arc42","notebooklm","document-classification"]},"finops-analyst":{"artifactCapable":false,"agentType":"finops-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-cost-operations"]},"flaky-test-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:flaky-test-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:test-failure-mindset","agent-teams-workforce:find-cause"]},"frontend-performance-optimizer":{"artifactCapable":true,"agentType":"agent-teams-workforce:frontend-performance-optimizer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend"]},"github-actions-pipeline-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:github-actions-pipeline-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"glue-etl-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:glue-etl-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:graphrag-lookup"]},"graphql-schema-designer":{"artifactCapable":true,"agentType":"graphql-schema-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:api-design-reviewer","agent-teams-workforce:architecture-baseline"]},"graphql-schema-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:graphql-schema-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer"]},"implementation-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:implementation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:graphrag-lookup"]},"incident-response-runbook-designer":{"artifactCapable":true,"agentType":"agent-teams-workforce:incident-response-runbook-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:observability-designer"]},"infrastructure-security-scanner":{"artifactCapable":true,"agentType":"infrastructure-security-scanner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops","agent-teams-workforce:aws-cdk-development"]},"injection-attack-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:injection-attack-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"integration-pattern-architect":{"artifactCapable":true,"agentType":"integration-pattern-architect","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:architecture-baseline"]},"integration-testing-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:integration-testing-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"ios-swiftui-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:ios-swiftui-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:graphrag-lookup"]},"kinesis-stream-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:kinesis-stream-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"lambda-performance-optimizer":{"artifactCapable":true,"agentType":"lambda-performance-optimizer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:lambda"]},"llm-observability-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:llm-observability-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:observability-designer","agent-teams-workforce:senior-prompt-engineer","agent-teams-workforce:aws-agentic-ai","agent-teams-workforce:graphrag-lookup"]},"matching-algorithm-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:matching-algorithm-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:graphrag-lookup"]},"mcp-server-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:mcp-server-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:mcp-server-builder","agent-teams-workforce:aws-agentic-ai","agent-teams-workforce:aws-mcp-setup","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"ml-evaluation-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:ml-evaluation-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:senior-data-scientist","agent-teams-workforce:cumulative-regression"]},"mobile-e2e-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:mobile-e2e-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"nextjs-component-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:nextjs-component-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend","agent-teams-workforce:a11y-audit","agent-teams-workforce:senior-fullstack","agent-teams-workforce:graphrag-lookup"]},"nfr-analyst":{"artifactCapable":false,"agentType":"agent-teams-workforce:nfr-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:product-discovery"]},"okr-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:okr-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-strategist","agent-teams-workforce:product-analytics"]},"openapi-contract-reviewer":{"artifactCapable":false,"agentType":"openapi-contract-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer","agent-teams-workforce:skillspoke-events","agent-teams-workforce:artifact-handoff","agent-teams-workforce:architecture-baseline"]},"operational-readiness-reviewer":{"artifactCapable":true,"agentType":"operational-readiness-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:observability-designer","agent-teams-workforce:architecture-baseline"]},"payments-integration-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:payments-integration-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:stripe-integration-expert","agent-teams-workforce:secrets-manager","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:skillspoke-events"]},"performance-benchmark-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:performance-benchmark-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"permission-escalation-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:permission-escalation-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops","agent-teams-workforce:iam"]},"persistence-architecture-specialist":{"artifactCapable":true,"agentType":"persistence-architecture-specialist","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:dynamodb","agent-teams-workforce:database-schema-designer","agent-teams-workforce:architecture-baseline"]},"persona-profile-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:persona-profile-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:product-analytics"]},"phase-gate-enforcer":{"artifactCapable":false,"agentType":"agent-teams-workforce:phase-gate-enforcer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:cumulative-regression"]},"playwright-e2e-web-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:playwright-e2e-web-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:a11y-audit","agent-teams-workforce:cumulative-regression"]},"polyrepo-steward":{"artifactCapable":true,"agentType":"agent-teams-workforce:polyrepo-steward","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:graphrag-lookup","polyrepo-repo","polyrepo-info","polyrepo-governance","polyrepo-beads"]},"power-tools-configuration-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:power-tools-configuration-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:lambda","agent-teams-workforce:secrets-manager","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"prd-alignment-verifier":{"artifactCapable":true,"agentType":"agent-teams-workforce:prd-alignment-verifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"prd-creation-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:prd-creation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"prd-reality-reconciler":{"artifactCapable":true,"agentType":"prd-reality-reconciler","skills":["agent-teams-workforce:architecture-baseline","agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:graphrag-lookup"]},"prd-trd-traceability-verifier":{"artifactCapable":true,"agentType":"agent-teams-workforce:prd-trd-traceability-verifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"prd-validation-analyst":{"artifactCapable":true,"agentType":"agent-teams-workforce:prd-validation-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"prd-validation-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:prd-validation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"prd-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:prd-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"production-readiness-review-facilitator":{"artifactCapable":false,"agentType":"agent-teams-workforce:production-readiness-review-facilitator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"race-condition-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:race-condition-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"react-native-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:react-native-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend","agent-teams-workforce:graphrag-lookup"]},"readme-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:readme-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"recommendation-engine-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:recommendation-engine-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:graphrag-lookup"]},"regression-coverage-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:regression-coverage-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:artifact-handoff","agent-teams-workforce:cumulative-regression"]},"regression-impact-assessor":{"artifactCapable":true,"agentType":"agent-teams-workforce:regression-impact-assessor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:artifact-handoff","agent-teams-workforce:cumulative-regression"]},"requirements-clarifier":{"artifactCapable":false,"agentType":"agent-teams-workforce:requirements-clarifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:product-discovery"]},"requirements-conflict-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:requirements-conflict-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"root-cause-analyst":{"artifactCapable":false,"agentType":"agent-teams-workforce:root-cause-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:find-cause","agent-teams-workforce:test-failure-mindset","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:artifact-handoff"]},"s3-data-lake-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:s3-data-lake-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:s3","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"sdlc-pipeline-orchestrator":{"artifactCapable":false,"agentType":"agent-teams-workforce:sdlc-pipeline-orchestrator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:beads-contract"]},"security-architecture-designer":{"artifactCapable":true,"agentType":"security-architecture-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-security","agent-teams-workforce:iam","agent-teams-workforce:secrets-manager","agent-teams-workforce:architecture-baseline"]},"security-test-case-designer":{"artifactCapable":true,"agentType":"agent-teams-workforce:security-test-case-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-security","agent-teams-workforce:cumulative-regression"]},"shared-capability-reviewer":{"artifactCapable":false,"agentType":"agent-teams-workforce:shared-capability-reviewer","skills":[]},"slo-error-budget-designer":{"artifactCapable":false,"agentType":"slo-error-budget-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:observability-designer","agent-teams-workforce:cloudwatch"]},"smoke-test-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:smoke-test-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"spec-authoring-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:spec-authoring-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"spec-currency-validator":{"artifactCapable":true,"agentType":"agent-teams-workforce:spec-currency-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"spec-decider":{"artifactCapable":false,"agentType":"spec-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:cove-prompt-design","agent-teams-workforce:artifact-handoff","agent-teams-workforce:architecture-baseline"]},"spec-freshness-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:spec-freshness-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"stakeholder-request-intake-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:stakeholder-request-intake-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"task-decomposer":{"artifactCapable":true,"agentType":"task-decomposer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:beads-contract","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:artifact-handoff","agent-teams-workforce:wsjf"]},"task-decomposition-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:task-decomposition-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:beads-contract","agent-teams-workforce:graphrag-lookup"]},"task-dependency-mapper":{"artifactCapable":true,"agentType":"task-dependency-mapper","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:beads-contract","agent-teams-workforce:artifact-handoff"]},"task-readiness-runner":{"artifactCapable":false,"agentType":"agent-teams-workforce:task-readiness-runner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:beads-contract"]},"tdd-unit-test-generator":{"artifactCapable":true,"agentType":"agent-teams-workforce:tdd-unit-test-generator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:tdd-guide","agent-teams-workforce:cumulative-regression"]},"test-command-resolver":{"artifactCapable":false,"agentType":"agent-teams-workforce:test-command-resolver","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:test-failure-mindset"]},"test-coverage-gap-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:test-coverage-gap-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"test-design-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:test-design-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"test-environment-orchestrator":{"artifactCapable":true,"agentType":"test-environment-orchestrator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:aws-mcp-setup"]},"test-failure-parser":{"artifactCapable":false,"agentType":"agent-teams-workforce:test-failure-parser","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:test-failure-mindset"]},"test-isolation-specialist":{"artifactCapable":true,"agentType":"agent-teams-workforce:test-isolation-specialist","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:tdd-guide","agent-teams-workforce:test-failure-mindset"]},"test-plan-strategy-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:test-plan-strategy-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"test-strategy-decider":{"artifactCapable":false,"agentType":"agent-teams-workforce:test-strategy-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cove-prompt-design"]},"trd-author":{"artifactCapable":true,"agentType":"trd-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:architecture-baseline"]},"trd-authoring-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:trd-authoring-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"trd-decider":{"artifactCapable":false,"agentType":"agent-teams-workforce:trd-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"trd-validator":{"artifactCapable":false,"agentType":"agent-teams-workforce:trd-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:architecture-baseline"]},"ubiquitous-language-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:ubiquitous-language-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"uml-diagram-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:uml-diagram-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:architecture-diagramming","agent-teams-workforce:uml-diagramming","agent-teams-workforce:architecture-baseline"]},"user-guide-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:user-guide-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:roadmap-communicator"]},"user-story-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:user-story-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:beads-contract"]},"user-story-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:user-story-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"vector-search-embeddings-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:vector-search-embeddings-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:rag-architect","agent-teams-workforce:graphrag-lookup"]},"webauthn-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:webauthn-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend","agent-teams-workforce:cognito","agent-teams-workforce:graphrag-lookup"]},"workflow-command-runner":{"artifactCapable":false,"agentType":"agent-teams-workforce:workflow-command-runner","skills":["artifact-handoff"]},"worktree-independent-verifier":{"artifactCapable":false,"agentType":"agent-teams-workforce:worktree-independent-verifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"wsjf-scorer":{"artifactCapable":true,"agentType":"agent-teams-workforce:wsjf-scorer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-strategist","agent-teams-workforce:wsjf","agent-teams-workforce:beads-contract"]},"wsjf-scoring-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:wsjf-scoring-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-strategist","agent-teams-workforce:wsjf"]},"xcuitest-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:xcuitest-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:tdd-guide","agent-teams-workforce:cumulative-regression"]}}
// skills/pipeline-contracts/schemas/driver-surface.schema.json, inlined by shared-blocks.mjs. DRIVER_SURFACE maps
// each x-constant of $defs.DriverEnvironment to its environment variable name and each x-values entry of
// $defs.RateLimitInfo to its wire value, so no workflow names a driver environment variable or a rate-limit value itself.
const DRIVER_SURFACE_SCHEMA = {"$schema":"https://json-schema.org/draft/2020-12/schema","$id":"agent-teams-workforce/skills/pipeline-contracts/schemas/driver-surface.schema.json","title":"Driver module surface","description":"The one definition of the driver (ops/sdlc-automation in the control repository) surface the plugin orchestrator imports, the ATW_* environment the driver hands every child and orchestrator process, and the Claude CLI rate-limit event the driver's quota readers take. scripts/generate_types.py renders scripts/driver_surface_types.py from this file; scripts/check_generated.py fails when that module is stale.","x-driver":{"dirParts":["ops","sdlc-automation"],"dirDoc":"Path parts of the driver directory under ATW_CONTROL_REPO.","modules":[{"module":"headlessenv","constant":"HEADLESSENV_MODULE","protocol":"HeadlessEnvironment","doc":"Driver headlessenv module surface consumed by session setup.","members":[{"name":"DENIED_TOOLS","kind":"attribute","python":"tuple[str, ...]","doc":"Tools every headless and orchestrator agent session is denied, in order."},{"name":"child_env","kind":"method","params":[["scratch","Path"]],"returns":"dict[str, str]","doc":"Build the subprocess environment: DriverEnvironment over the inherited one."}]},{"module":"fablewall","constant":"FABLEWALL_MODULE","protocol":"FableWall","doc":"Driver fablewall module surface consumed by model fallback.","members":[{"name":"is_refusal","kind":"method","params":[["info","object"]],"returns":"bool","doc":"Return whether a RateLimitInfo is a model-specific refusal."},{"name":"reset_of","kind":"method","params":[["info","object"]],"returns":"float | None","doc":"Return the model-specific reset of a RateLimitInfo, in epoch seconds."}]},{"module":"breaker","constant":"BREAKER_MODULE","protocol":"Breaker","doc":"Driver breaker module surface consumed by quota handling.","members":[{"name":"exhausted_reset","kind":"method","params":[["info","object"]],"returns":"float | None","doc":"Return the latest reset among the exhausted windows, in epoch seconds."}]},{"module":"childproc","constant":"CHILDPROC_MODULE","protocol":"ChildProcess","doc":"Driver childproc module termination policy.","members":[{"name":"TERMINATE_GRACE","kind":"attribute","python":"float","doc":"Seconds a terminated child is given before it is killed."}]}]},"$defs":{"DriverEnvironment":{"description":"The ATW_* and process environment the driver hands child and orchestrator processes.","x-details":"headlessenv.child_env(scratch) returns these keys over the inherited os.environ (atw.environment fills only absent or blank values); the keeper, supervisor and orchestrator dispatch add ATW_STOP_FILE, ATW_EXECUTION_ID and ATW_ORCH_IDLE.","type":"object","x-python":{"typeddict":"DriverEnvironment"},"properties":{"ATW_PROJECT_ROOT":{"type":"string","minLength":1,"description":"Absolute path of the project root.","x-constant":"PROJECT_ROOT_ENV"},"ATW_PRD_EPIC_SYNC":{"type":"string","minLength":1,"description":"Path of the PRD-to-Epic sync script.","x-constant":"PRD_EPIC_SYNC_ENV"},"ATW_PRD_EPIC_VERIFY":{"type":"string","minLength":1,"description":"Path of the PRD-to-Epic verify script.","x-constant":"PRD_EPIC_VERIFY_ENV"},"ATW_FLEET_DIR":{"type":"string","minLength":1,"description":"The fleet directory: SKILLSPOKE_APP_ROOT, else the control repository's parent.","x-constant":"FLEET_DIR_ENV"},"ATW_CONTROL_REPO":{"type":"string","minLength":1,"description":"Absolute path of the control repository (SKILLSPOKE_CC, else the driver's repository root). The driver modules live under it at DRIVER_DIR_PARTS.","x-constant":"CONTROL_REPO_ENV"},"ATW_ARCH_PATH":{"type":"string","minLength":1,"description":"The architecture root; set only when the driver knows one. Readers use args.archPath first and fall back to it.","x-constant":"ARCH_PATH_ENV"},"ATW_DESIGN_PACKAGES_DIR":{"type":"string","minLength":1,"description":"The owner's cds design packages directory; optional.","x-constant":"DESIGN_PACKAGES_ENV"},"ATW_PRD_DIR":{"type":"string","minLength":1,"description":"The first PRD root; optional.","x-constant":"PRD_DIR_ENV"},"PATH":{"type":"string","minLength":1,"description":"The controller runtime's bin directory first, de-duplicated.","x-constant":"PATH_ENV"},"TMPDIR":{"type":"string","minLength":1,"description":"The dispatch scratch directory.","x-constant":"TMPDIR_ENV","x-group":"SCRATCH_ENV_KEYS"},"TMP":{"type":"string","minLength":1,"description":"The dispatch scratch directory.","x-constant":"TMP_ENV","x-group":"SCRATCH_ENV_KEYS"},"TEMP":{"type":"string","minLength":1,"description":"The dispatch scratch directory.","x-constant":"TEMP_ENV","x-group":"SCRATCH_ENV_KEYS"},"CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS":{"type":"string","const":"0","description":"Disables the Claude CLI print-mode background wait.","x-constant":"BACKGROUND_WAIT_KEY","x-const-mapping":"BACKGROUND_WAIT_ENV"},"ATW_STOP_FILE":{"type":"string","minLength":1,"description":"Path of the stop marker file; absent means no stop marker. A consumer touches the file (mode 0o600) to request a drain, or tests whether it exists. It only requests a stop: how a stop is classified belongs to the handback contract.","x-constant":"STOP_FILE_ENV","x-file-mode":"STOP_FILE_MODE"},"ATW_EXECUTION_ID":{"type":"string","minLength":1,"description":"The driver execution id. Required for an orchestrator dispatch; set for a headless workflow session only when its arguments carry an executionId.","x-constant":"EXECUTION_ID_ENV"},"ATW_ORCH_IDLE":{"type":"string","pattern":"^[0-9]+(\\.[0-9]+)?$","default":"3600","description":"Orchestrator idle limit in seconds: a positive finite float. A non-finite or non-positive value is a ValueError.","x-constant":"ORCH_IDLE_ENV","x-default-constant":"ORCH_IDLE_DEFAULT"}},"required":["ATW_PROJECT_ROOT","ATW_PRD_EPIC_SYNC","ATW_PRD_EPIC_VERIFY","ATW_FLEET_DIR","ATW_CONTROL_REPO","PATH","TMPDIR","TMP","TEMP","CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS"],"additionalProperties":{"type":"string"}},"StopFileMode":{"description":"Permission bits a consumer creates the stop marker file with.","type":"integer","const":384,"x-python":{"constant":"STOP_FILE_MODE","type":"int","render":"0o600"}},"DeniedTool":{"description":"A tool every headless and orchestrator agent session is denied. DENIED_TOOLS keeps this order.","type":"string","enum":["WebFetch","WebSearch","Artifact","SendMessage","EndConversation","CronCreate","CronDelete","CronList","mcp__claude_ai_Gmail__send_message","mcp__claude_ai_Gmail__reply","mcp__claude_ai_Gmail__forward","mcp__claude_ai_Gmail__create_draft","mcp__claude_ai_Google_Drive__share_file","mcp__claude_ai_Google_Drive__create_file","mcp__plugin_slack_slack__slack_send_message","mcp__plugin_slack_slack__slack_send_message_draft","mcp__plugin_slack_slack__slack_schedule_message"],"x-python":{"literal":"DeniedTool","tuple":"DENIED_TOOLS"}},"TerminateGrace":{"description":"Seconds a terminated child process is given before it is killed.","type":"number","const":10,"x-python":{"constant":"TERMINATE_GRACE","type":"float"}},"ExhaustedUtilization":{"description":"A usage window whose utilization is at or above this value is exhausted.","type":"number","const":1,"x-python":{"constant":"EXHAUSTED_UTILIZATION","type":"float"}},"RateLimitStatus":{"description":"RateLimitInfo.status; only rejected is acted on.","type":"string","enum":["allowed","allowed_warning","rejected"],"x-python":{"literal":"RateLimitStatus","tuple":"RATE_LIMIT_STATUSES","constants":{"rejected":"REJECTED_STATUS"}}},"UsageWindowName":{"description":"The account-wide usage windows. Any other window name is model-specific.","type":"string","enum":["five_hour","seven_day"],"x-python":{"literal":"UsageWindowName","frozenset":"ACCOUNT_WINDOWS"}},"UsageWindow":{"description":"One usage window of a RateLimitInfo.","type":"object","x-python":{"typeddict":"UsageWindow"},"properties":{"utilization":{"type":"number","description":"Exhausted when at or above EXHAUSTED_UTILIZATION."},"resetsAt":{"type":"number","description":"Reset time in epoch seconds."}},"required":["utilization"]},"RateLimitInfo":{"description":"The rate_limit_info of a rate_limit_event: the info argument of the quota readers.","type":"object","x-python":{"typeddict":"RateLimitInfo"},"properties":{"status":{"$ref":"#/$defs/RateLimitStatus"},"unifiedWindows":{"type":"object","additionalProperties":{"$ref":"#/$defs/UsageWindow"},"description":"Window name -> usage window."},"resetsAt":{"type":"number","description":"Top-level reset time in epoch seconds."},"rateLimitType":{"type":"string","description":"The value with meaning here is MODEL_OVERAGE_TYPE.","x-values":{"MODEL_OVERAGE_TYPE":"seven_day_overage_included"}},"overageDisabledReason":{"type":"string","description":"The value with meaning here is OUT_OF_CREDITS_REASON.","x-values":{"OUT_OF_CREDITS_REASON":"out_of_credits"}}},"required":["status"]},"RateLimitEvent":{"description":"One Claude CLI stream-json rate-limit event.","type":"object","x-python":{"typeddict":"RateLimitEvent"},"properties":{"type":{"type":"string","const":"rate_limit_event","x-value-constant":"RATE_LIMIT_EVENT_TYPE"},"rate_limit_info":{"$ref":"#/$defs/RateLimitInfo","x-key-constant":"RATE_LIMIT_INFO_KEY"}},"required":["type","rate_limit_info"]}}}
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
// The model allowance: the driver names the agent types that run on the allowance-limited model
// (fableAgentTypes). When that model refused a call of an earlier dispatch, the driver passes
// fableFallback true and every such agent runs on the fallback model for this dispatch.
const fableInput = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const fableTypes = new Set((Array.isArray(fableInput.fableAgentTypes) ? fableInput.fableAgentTypes : []).map((name) => String(name).replace(/^agent-teams-workforce:/, '')))
const fablePath = fableInput.fableInvocationPath || 'root'
const fableFallback = fableInput.fableFallback === true
let fableChildOrdinal = 0
// The last call the model allowance refused in this script: { agentType, label, message }, or null.
let fableRefusal = null
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
  const agentType = (options && options.agentType) || null
  const isFable = fableTypes.has(String(agentType || '').replace(/^agent-teams-workforce:/, ''))
  const call = isFable && fableFallback ? { ...options, model: 'opus' } : options
  try {
    return await agent(`OUTPUT_MODE: ${outputMode}\n\n${contracts}\n\n${baselineContract}${skillData}${prompt}`, call)
  } catch (error) {
    const message = String((error && error.message) || error)
    if (!isFable || !FABLE_EXHAUSTED.test(message)) throw error
    fableRefusal = { agentType, label: (options && options.label) || null, message }
    log(`${fableRefusal.label || agentType}: the model allowance refused this call: ${message.slice(0, 300)}`)
    return null
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
    ...(fableFallback ? { fableFallback } : {}),
  })
}
// ===== SHARED BLOCK fable — END =====


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
// ===== SHARED BLOCK step-journal — BEGIN (canonical: scripts/shared-blocks/step-journal.js; filled from skills/pipeline-contracts/schemas/{step-journal.schema,pipeline-steps}.json; edit there, then: node scripts/shared-blocks.mjs --write) =====
// ── STEP JOURNAL: the steps of the bead this workflow works on, and the changes it reports ──
//
// A build or deploy workflow runs the steps the bead's step journal lists. It reads the journal
// once, at its start, through the checked relay (bin/atw-step-journal read), keeps a copy in
// memory, and begins at the first step that is not done. It cannot write a file, so it reports
// each change (step started, step done with its artifacts and the steps its result adds, step
// failed with its cause, child steps planned) as one log line the driver applies to the journal
// file with orchestrator/core/journal_lines.py. The copy here changes exactly as the file does:
// it follows step_journal.next_step, start_step and journal_changes.apply_completion.
//
// The line format and the artifact that hands a planned step its parameters are defined in
// skills/pipeline-contracts/schemas/step-journal.schema.json; the step kinds, what each records
// and adds, and the up-front plans in skills/pipeline-contracts/schemas/pipeline-steps.json. Both
// are inlined below by scripts/shared-blocks.mjs. Never restate any part of them in a workflow.
const stepJournal = (() => {
  const WIRE = {"changePrefix":"STEP-JOURNAL ","changePartPrefix":"STEP-JOURNAL-PART ","changeChunk":4000,"plannedForPrefix":"for "}
  const PIPELINES = ({"$schema":"./pipeline-steps.schema.json","pipelines":{"build":{"plan":["build:workspace","build:regression-assess","build:regression-review","build:regression-validate","build:baseline","build:select-implementers","build:refactor","build:refactor-check","build:docs-audit","build:final-suite","build:regression-map","build:regression-map-review","build:regression-verify","build:commit"],"inner":{},"kinds":{"build:workspace":{"description":"Establish the Story's worktree and branch","purpose":"Every step that reads or changes the Task's code works in one tree on the Story's branch","runBy":"task-to-deploy","reads":[],"records":[{"name":"worktree","kind":"directory","holds":"the Story's worktree"},{"name":"branch","kind":"value","holds":"the branch checked out in the worktree, a string"},{"name":"defaultBranch","kind":"value","holds":"the repository's default branch, a string or null"}],"adds":[{"kinds":["build:design-source"],"when":"the Task's surfaces include web-ui and its design source is bundle or cds"},{"kinds":["build:infra-intent"],"when":"the Task's type or a label is in the infrastructure vocabulary"}]},"build:design-source":{"description":"Select the design source the Task's web UI is built from","purpose":"A cds bundle the owner supplied for the Task's artifact is the design the build uses and is audited against","runBy":"task-to-deploy","reads":[],"records":[{"name":"design","kind":"value","holds":"{ designSource, bundle, buildSpecs }: the design source used, the bundle directory or null, and the build spec paths"}],"adds":[]},"build:infra-intent":{"description":"Author the provisioning intent of the infrastructure Task","purpose":"The tests and the code of an infrastructure Task are written to concrete resources, stacks and cross-stack references","runBy":"task-to-deploy","reads":["worktree"],"records":[{"name":"provisioning","kind":"value","holds":"{ provisioningIntent, affectedStacks }"}],"adds":[]},"build:regression-assess":{"description":"Map the Task's change to the current and earlier requirements it can affect","purpose":"Earlier requirements stay covered: the tests are written and run against the cumulative scope, not only this Task","runBy":"task-to-deploy","reads":["worktree","design","provisioning"],"records":[{"name":"regressionPrevious","kind":"file","holds":"the requirements and mappings recorded before this Task"},{"name":"regressionPlan","kind":"file","holds":"the impact scope the regression-impact-assessor wrote"}],"adds":[]},"build:regression-review":{"description":"Review the regression scope against the requirement sources","purpose":"The scope is approved by a reviewer that did not write it","runBy":"task-to-deploy","reads":["worktree","regressionPrevious","regressionPlan"],"records":[{"name":"regressionPlanReview","kind":"file","holds":"the regression-coverage-reviewer's review of the scope"}],"adds":[]},"build:regression-validate":{"description":"Validate the reviewed regression scope","purpose":"The scope is complete and approved before any test is written, and its requirement sources are bound","runBy":"task-to-deploy","reads":["worktree","regressionPlan","regressionPlanReview"],"records":[{"name":"regressionScope","kind":"value","holds":"{ requiredKinds }: the test layers the scope requires"}],"adds":[]},"build:baseline":{"description":"Resolve the repository's suite command and run the suite before any change","purpose":"The command the build is judged by is the one the repository declares, and the tests failing before the Task are known","runBy":"task-to-deploy","reads":["worktree","regressionScope"],"records":[{"name":"suiteCommand","kind":"value","holds":"the command that runs the whole suite, a string"},{"name":"baseline","kind":"value","holds":"{ exitCode, summary, failing, tail, relayFile }: the suite run before any change"}],"adds":[{"kinds":["build:red-write","build:red-check"],"when":"always: one build:red-write per test agent the contract's surfaces call for, then the run that judges them"}]},"build:red-write":{"description":"Write failing tests with {testAgent}","purpose":"The Task's acceptance criteria are encoded as tests that fail before the code exists","runBy":"task-to-deploy","params":["testAgent","testAgents","feedback"],"reads":["worktree","suiteCommand","regressionPlan","testFiles","design","provisioning"],"records":[{"name":"testFiles","kind":"value","holds":"the test files the agent created or changed, a list of paths"},{"name":"redConfirmed","kind":"value","holds":"whether the agent saw its tests fail as intended, a boolean"}],"adds":[]},"build:red-check":{"description":"Run the suite and judge whether the new tests fail cleanly","purpose":"Red holds only when a new test fails, no test file fails to load and no other test regressed","runBy":"task-to-deploy","reads":["worktree","suiteCommand","baseline","testFiles","redRun"],"records":[{"name":"redRun","kind":"value","holds":"{ exitCode, summary, failing, tail, relayFile, reasons }: the suite run and why Red does not hold, when it does not"},{"name":"testPrint","kind":"value","holds":"{ files, treeDigest }: the git blob hash of each test file and the digest of the work tree"}],"adds":[{"kinds":["build:red-write","build:red-check"],"when":"Red does not hold: each test agent is given the suite result, and the suite is judged again"}],"limit":"It fails with red-unsatisfied when four checks have not shown Red, and with no-progress when the suite fails exactly as it did at the check before"},"build:select-implementers":{"description":"Select the implementers whose specialties cover the Task","purpose":"The code is written by the fewest agents whose specialties cover the change, in build order","runBy":"task-to-deploy","reads":["worktree","suiteCommand","baseline","redRun","testFiles","design","provisioning"],"records":[{"name":"implementers","kind":"value","holds":"the implementer agent names, in the order they work"}],"adds":[{"kinds":["build:implement","build:green-check"],"when":"always: one build:implement per selected implementer, then the run that judges them"}]},"build:implement":{"description":"Write the code with {implementer}","purpose":"The failing tests pass with the minimum production change","runBy":"task-to-deploy","params":["implementer","implementers","brief"],"reads":["worktree","suiteCommand","baseline","redRun","greenRun","cdsAudit","testFiles","testDecisions","design","provisioning"],"records":[{"name":"changedFiles","kind":"value","holds":"the files the implementer changed, a list of paths"},{"name":"testIssues","kind":"value","holds":"the tests the implementer names as standing between the code and the contract, a list of { testId, kind, reason, contractRef }"},{"name":"upstreamMissing","kind":"value","holds":"what must exist outside the Task before the suite can pass, a list of { what, evidence }"}],"adds":[]},"build:green-check":{"description":"Run the suite and judge whether it is green","purpose":"The Task is built only when the repository's whole suite exits 0 and the implementers left the tests as they were written","runBy":"task-to-deploy","reads":["worktree","suiteCommand","testFiles","testPrint","implementers","testIssues","upstreamMissing","greenRun"],"records":[{"name":"greenRun","kind":"value","holds":"{ exitCode, summary, failing, tail, relayFile }: the suite run"},{"name":"testPrint","kind":"value","holds":"{ files, treeDigest }: the git blob hash of each test file and the digest of the work tree"}],"adds":[{"kinds":["build:test-ruling","build:green-check"],"when":"the suite is not green and an implementer named tests that stand between the code and the contract"},{"kinds":["build:implement","build:green-check"],"when":"the suite is not green and no named test awaits a ruling: each implementer is given the suite result"}],"limit":"It fails with green-modified-tests when an implementer changed a test file, with blocked-upstream when an implementer named something outside the Task, with no-progress when no file changed and the suite fails exactly as at the check before, and with green when eight checks since the implementers were selected have not shown a green suite"},"build:test-ruling":{"description":"Rule on the tests the implementers named, with tdd-unit-test-generator","purpose":"A test that contradicts the contract is changed by the agent that owns the tests, never by an implementer","runBy":"task-to-deploy","params":["issues"],"reads":["worktree","suiteCommand","greenRun","testFiles","regressionPlan"],"records":[{"name":"testDecisions","kind":"value","holds":"one ruling per named test, a list of { testId, action, reason }"},{"name":"testFiles","kind":"value","holds":"the test files the agent changed, a list of paths"}],"adds":[]},"build:refactor":{"description":"Refactor the code the implementers changed","purpose":"The change is left clear and free of duplication without changing behavior","runBy":"task-to-deploy","reads":["worktree","suiteCommand","changedFiles"],"records":[{"name":"refactorSnapshot","kind":"value","holds":"the git tree id of the work tree before the refactor, a string"},{"name":"refactorChangedFiles","kind":"value","holds":"the files the refactor changed, read from git against the snapshot"},{"name":"refactorReverted","kind":"value","holds":"whether the refactor gave up and the tree was put back at the snapshot, a boolean"}],"adds":[]},"build:refactor-check":{"description":"Run the suite after the refactor","purpose":"A refactor that turns the suite red is undone","runBy":"task-to-deploy","reads":["worktree","suiteCommand","refactorSnapshot","refactorRestored","design"],"records":[{"name":"refactorRun","kind":"value","holds":"{ exitCode, summary, failing, tail, relayFile }: the suite run"}],"adds":[{"kinds":["build:refactor-restore","build:refactor-check"],"when":"the suite is red after the refactor and the tree has not been restored"},{"kinds":["build:cds-audit"],"when":"the suite is green and the Task's web UI has design source bundle or cds"}],"limit":"It fails when the suite is still red after the tree was restored to the snapshot"},"build:refactor-restore":{"description":"Restore the work tree to the snapshot taken before the refactor","purpose":"The suite went red after the refactor","runBy":"task-to-deploy","reads":["worktree","refactorSnapshot"],"records":[{"name":"refactorRestored","kind":"value","holds":"{ restored, evidence }"}],"adds":[]},"build:cds-audit":{"description":"Audit the changed web UI against its design source","purpose":"The UI styles nothing outside the design system the Task was built from","runBy":"task-to-deploy","reads":["worktree","design","implementers","cdsAudit"],"records":[{"name":"cdsAudit","kind":"value","holds":"{ verdict, findings, scriptVersion, violations, gaps }: the audit verdict, the count of violations and gaps, and each as text"}],"adds":[{"kinds":["build:implement","build:green-check","build:cds-audit"],"when":"the first audit finds violations: each implementer is given them, the suite is judged, and the audit runs again"}],"limit":"It fails with cds-audit when violations remain at the audit that follows the correction, and with blocked-upstream when the design system lacks something the UI needs"},"build:docs-audit":{"description":"Audit which documents the change leaves stale","purpose":"Documentation is brought up to date in the same commit as the code","runBy":"task-to-deploy","reads":["worktree","changedFiles","refactorChangedFiles"],"records":[{"name":"staleDocs","kind":"value","holds":"the stale documents, a list of paths"},{"name":"docAssignments","kind":"value","holds":"the stale documents by the documentation agent that owns their kind, a list of { agent, docs }"}],"adds":[{"kinds":["build:docs-write"],"when":"documents are stale: one build:docs-write per documentation agent assigned"}]},"build:docs-write":{"description":"Update the stale documents with {docAgent}","purpose":"The audit named documents the change leaves stale","runBy":"task-to-deploy","params":["docAgent","docs"],"reads":["worktree","changedFiles"],"records":[{"name":"updatedDocs","kind":"value","holds":"the documents the agent updated, a list of paths"}],"adds":[],"together":true},"build:final-suite":{"description":"Run the suite a final time","purpose":"Nothing is committed unless the whole suite exits 0 on the tree as it will be committed","runBy":"task-to-deploy","reads":["worktree","suiteCommand"],"records":[{"name":"finalRun","kind":"value","holds":"{ exitCode, summary, failing, tail, relayFile }: the suite run"}],"adds":[]},"build:regression-map":{"description":"Map each requirement in scope to the tests and commands that prove it","purpose":"Every required test layer of the approved scope names concrete tests and a command that runs them","runBy":"task-to-deploy","reads":["worktree","regressionPlan","regressionPrevious"],"records":[{"name":"regressionMapped","kind":"file","holds":"the final mapping the regression-impact-assessor wrote"}],"adds":[]},"build:regression-map-review":{"description":"Review the regression mapping against the tests as written","purpose":"The mapping is approved by a reviewer that did not write it","runBy":"task-to-deploy","reads":["worktree","regressionMapped","regressionPrevious"],"records":[{"name":"regressionMappedReview","kind":"file","holds":"the regression-coverage-reviewer's review of the mapping"}],"adds":[]},"build:regression-verify":{"description":"Run the mapped regression tests and record their evidence","purpose":"The commit carries fresh per-test evidence for every requirement the change can affect","runBy":"task-to-deploy","reads":["worktree","regressionPlan","regressionMapped","regressionMappedReview"],"records":[{"name":"regressionEvidence","kind":"file","holds":"the verification result and the evidence of each mapped run"}],"adds":[]},"build:commit":{"description":"Commit the Task to the Story's branch","purpose":"The built Task lands on the branch its Story deploys from","runBy":"task-to-deploy","reads":["worktree","branch","defaultBranch","suiteCommand","finalRun"],"records":[{"name":"commit","kind":"value","holds":"the head of the Story's branch after the commit, a string"}],"adds":[]}}},"deploy":{"plan":["deploy:mechanism","deploy:workspace","deploy:commits-ahead","deploy:close"],"inner":{"deploy:fix":["deploy:fix-author","deploy:fix-verify","deploy:fix-commit"],"deploy:built-version":["deploy:built-snapshot","deploy:built-compare"]},"kinds":{"deploy:mechanism":{"description":"Ask what the Story's repository publishes and deploys","purpose":"A repository publishes a package, deploys with CDK, both or neither, and the deploy runs only what applies","runBy":"driver","reads":[],"records":[{"name":"mechanism","kind":"value","holds":"{ repository, publishes, publishCommand, deploys, reason }"}],"adds":[]},"deploy:workspace":{"description":"Open the Story's worktree","purpose":"The deploy runs from the tree that holds the Story's built Tasks","runBy":"driver","reads":["mechanism"],"records":[{"name":"worktree","kind":"directory","holds":"the Story's worktree"},{"name":"branch","kind":"value","holds":"the Story's branch, a string"}],"adds":[{"kinds":["deploy:publish"],"when":"the repository publishes a package"},{"kinds":["deploy:synth"],"when":"the repository deploys with CDK and publishes no package"}]},"deploy:publish":{"description":"Publish the repository's package","purpose":"The repository publishes a package other repositories install","runBy":"driver","reads":["mechanism","worktree"],"records":[{"name":"publishedHead","kind":"value","holds":"the commit the package was published from, a string"},{"name":"deployFailure","kind":"value","holds":"{ step, output, stacks }, recorded only when the publish failed"}],"adds":[{"kinds":["deploy:synth"],"when":"the publish succeeded and the repository deploys with CDK"},{"kinds":["deploy:fix","deploy:publish"],"when":"the publish failed"}],"limit":"It fails when three fixes of this Story's deploy have already run"},"deploy:synth":{"description":"Synthesize the CDK app","purpose":"The cloud assembly names the stacks and the SSM parameters the deploy needs","runBy":"driver","reads":["worktree"],"records":[{"name":"assembly","kind":"directory","holds":"the CDK cloud assembly"},{"name":"deployFailure","kind":"value","holds":"{ step, output, stacks }, recorded only when the synth failed"}],"adds":[{"kinds":["deploy:ssm-check"],"when":"the synth succeeded"},{"kinds":["deploy:fix","deploy:publish","deploy:synth"],"when":"the synth failed: after the fix the package is published again when the repository publishes one, then the app is synthesized again"}],"limit":"It fails when three fixes of this Story's deploy have already run"},"deploy:ssm-check":{"description":"Check that the SSM parameters the stacks read exist","purpose":"A stack that reads a parameter another Story's deploy writes cannot deploy before that parameter exists","runBy":"driver","reads":["assembly"],"records":[{"name":"ssmParameters","kind":"value","holds":"the parameter names the stacks read, all present, a list of strings"}],"adds":[{"kinds":["deploy:deploy"],"when":"every parameter exists"}],"waits":"a parameter the stacks read does not exist yet"},"deploy:deploy":{"description":"Deploy the stacks to AWS dev","purpose":"The Story's Tasks are built and its stacks can be deployed","runBy":"driver","reads":["worktree","assembly"],"records":[{"name":"deployOutput","kind":"value","holds":"{ exitCode, tail }: the exit status of the deploy and the last part of its output"}],"adds":[{"kinds":["deploy:verify"],"when":"always"}]},"deploy:verify":{"description":"Verify that every stack reached a completed status and the worktree is clean","purpose":"The deploy counts only when CloudFormation reports every stack created or updated","runBy":"driver","reads":["worktree","assembly","deployOutput"],"records":[{"name":"stacks","kind":"value","holds":"the status of each stack, a list of { name, status, reason }"},{"name":"deployFailure","kind":"value","holds":"{ step, output, stacks }, recorded only when the deploy or its verification failed"}],"adds":[{"kinds":["deploy:fix","deploy:publish","deploy:synth"],"when":"the deploy or its verification failed: after the fix the package is published again when the repository publishes one, then the app is synthesized again"}],"limit":"It fails when three fixes of this Story's deploy have already run"},"deploy:fix":{"description":"Fix the failed deploy on the Story's branch","purpose":"A publish, synth, deploy or verification of the Story failed","runBy":"driver","params":["failure"],"reads":["worktree","branch","deployFailure"],"records":[{"name":"fix","kind":"value","holds":"{ cause, changedFiles, testsPassed, commit }: what the story-deploy-fix workflow returned"}],"adds":[]},"deploy:fix-author":{"description":"Diagnose the failure and fix it in the worktree, with cdk-stack-author","purpose":"The cause of the failed deploy is found in its output and corrected in the Story's code","runBy":"story-deploy-fix","within":"deploy:fix","reads":[],"records":[{"name":"fixCause","kind":"value","holds":"the cause the agent found, a string"},{"name":"fixTestCommand","kind":"value","holds":"the command that runs the synth assertion tests, a string that may be empty"}],"adds":[]},"deploy:fix-verify":{"description":"Read what the fix changed from git and run the synth assertion tests","purpose":"What the fix changed and whether its tests pass are measured, not taken from the agent's report","runBy":"story-deploy-fix","within":"deploy:fix","reads":["fixCause","fixTestCommand"],"records":[{"name":"fixChangedFiles","kind":"value","holds":"the files the fix changed, read from git status, a list of paths"},{"name":"fixTestsPassed","kind":"value","holds":"whether the synth assertion tests exited 0, a boolean"}],"adds":[],"limit":"It fails with no-change when the fix changed no file"},"deploy:fix-commit":{"description":"Commit the fix to the Story's branch","purpose":"The redeploy runs from a committed tree","runBy":"story-deploy-fix","within":"deploy:fix","reads":["fixCause"],"records":[{"name":"fixCommit","kind":"value","holds":"the head of the Story's branch after the commit, a string"}],"adds":[]},"deploy:commits-ahead":{"description":"Count the commits the Story's branch has that the default branch lacks","purpose":"A Story whose branch holds no commit has nothing to compare, review or merge","runBy":"driver","reads":["worktree","stacks"],"records":[{"name":"commitsAhead","kind":"value","holds":"the number of commits ahead of the default branch, an integer"}],"adds":[{"kinds":["deploy:built-version","deploy:pull-request","deploy:merge-wait"],"when":"the branch holds commits: deploy:built-version only when the Story's delta items are recorded"}]},"deploy:built-version":{"description":"Record what the Story built against the effective architecture","purpose":"The effective architecture describes what is deployed before the Story's pull request opens","runBy":"driver","reads":["worktree","branch"],"records":[{"name":"built","kind":"value","holds":"{ stage, differences, builtFiles }: what the built-version workflow returned, with counts in place of lists"}],"adds":[]},"deploy:built-snapshot":{"description":"Fingerprint the architecture and keep a copy of section 2","purpose":"What each agent writes in the architecture is measured, and the owner's constraints are put back if they change","runBy":"built-version","within":"deploy:built-version","reads":[],"records":[{"name":"constraintsBefore","kind":"value","holds":"{ exists, digest, gitStatus, kept }: the fingerprint of section 2 and where its copy is kept"},{"name":"treeStart","kind":"file","holds":"the fingerprint of every architecture file before the comparison"}],"adds":[]},"deploy:built-compare":{"description":"Compare the code on the Story's branch with the effective architecture","purpose":"Each difference between what was built and what the architecture shows is recorded as a built view","runBy":"built-version","within":"deploy:built-version","reads":["constraintsBefore","treeStart"],"records":[{"name":"differences","kind":"value","holds":"the differences found, a list of { element, itemId, effectiveViews, built, citations, file }"},{"name":"builtFiles","kind":"value","holds":"the built views written, a list of absolute paths"},{"name":"treeCompared","kind":"file","holds":"the fingerprint of every architecture file after the comparison"}],"adds":[{"kinds":["deploy:built-correct","deploy:built-review"],"when":"the comparison recorded differences"}]},"deploy:built-correct":{"description":"Correct the effective architecture to match what was built, with architecture-maintainer","purpose":"The effective architecture differs from what the Story built, or a review found the correction wanting","runBy":"built-version","within":"deploy:built-version","params":["findings"],"reads":["constraintsBefore","builtFiles","treeCompared","treeLast","architectureUpdate"],"records":[{"name":"architectureUpdate","kind":"value","holds":"{ changedFiles, createdFiles, deletedFiles, matched, constraintIssues, contradictions, summary }: every pass together, with the files measured from the tree"},{"name":"changedSinceLast","kind":"value","holds":"the files this pass changed since the pass before, a list of paths"},{"name":"treeLast","kind":"file","holds":"the fingerprint of every architecture file after this pass"}],"adds":[],"limit":"It fails when it wrote in section 2 or outside the effective architecture, and when a pass that answers findings changed no file"},"deploy:built-review":{"description":"Review the correction of the effective architecture, with architecture-conformance-reviewer","purpose":"The correction is checked by a reviewer that did not write it","runBy":"built-version","within":"deploy:built-version","reads":["constraintsBefore","builtFiles","architectureUpdate","changedSinceLast","conformance"],"records":[{"name":"conformance","kind":"value","holds":"{ conforms, findings, reviewedFiles, matchedBuiltViews }"}],"adds":[{"kinds":["deploy:built-correct","deploy:built-review"],"when":"the review has findings"},{"kinds":["deploy:built-approve","deploy:built-remove"],"when":"the correction conforms"}],"limit":"It fails when the correction does not conform after two corrections that answered findings"},"deploy:built-approve":{"description":"Set the corrected architecture files to effective","purpose":"A reviewed correction becomes the effective architecture","runBy":"built-version","within":"deploy:built-version","reads":["constraintsBefore","architectureUpdate","conformance"],"records":[{"name":"approval","kind":"value","holds":"{ promoted, unchanged }: how many files were set to effective and how many already were"}],"adds":[]},"deploy:built-remove":{"description":"Remove the built views the effective architecture now matches","purpose":"A built view exists only while the effective architecture differs from what was built","runBy":"built-version","within":"deploy:built-version","reads":["builtFiles","architectureUpdate","conformance"],"records":[{"name":"removedBuiltViews","kind":"value","holds":"the built views removed, a list of absolute paths"}],"adds":[],"limit":"It fails when a built view remains that the effective architecture does not match"},"deploy:pull-request":{"description":"Push the Story's branch and open its pull request","purpose":"The Story's deploy is verified and its branch holds commits","runBy":"driver","reads":["worktree","branch","stacks","publishedHead"],"records":[{"name":"pullRequest","kind":"value","holds":"the pull request URL, a string"}],"adds":[]},"deploy:merge-wait":{"description":"Wait for the Story's pull request to merge","purpose":"The Story closes only when its code is on the default branch","runBy":"driver","reads":["pullRequest"],"records":[{"name":"pullRequestState","kind":"value","holds":"the state GitHub reports for the pull request, the string MERGED"}],"adds":[],"waits":"the pull request is open and not merged"},"deploy:close":{"description":"Close the Story and remove its worktree and local branch","purpose":"A Story with nothing left to deploy or merge is done","runBy":"driver","reads":["worktree","branch"],"records":[{"name":"closed","kind":"value","holds":"true"}],"adds":[]}}}}}).pipelines || {}
  if (!WIRE.changePrefix || !WIRE.changePartPrefix || !WIRE.changeChunk || !WIRE.plannedForPrefix || !PIPELINES.build || !PIPELINES.deploy) {
    throw new Error('shared block step-journal: the step journal contract was not inlined (run node scripts/shared-blocks.mjs --write)')
  }
  const STEP_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
  const FAILURE_EVIDENCE_CHARS = 4000

  /** An artifact that is a file a step produced. */
  const file = (name, path) => ({ name, kind: 'file', path: String(path) })
  /** An artifact that is a directory a step produced. */
  const directory = (name, path) => ({ name, kind: 'directory', path: String(path) })
  /** An artifact that is a value a step produced; an undefined value is recorded as null. */
  const value = (name, held) => ({ name, kind: 'value', value: held === undefined ? null : held })

  /** Every step of `steps` in walk order: each step before its child steps, siblings in order. */
  const walk = (steps, out = []) => {
    for (const step of steps) {
      out.push(step)
      walk(step.steps, out)
    }
    return out
  }

  /** The copy of one journal step: `key` is its id, or the ref of a step this run added. */
  const copyStep = (raw, params) => {
    const id = String(raw.id || '')
    return {
      key: id,
      id,
      kind: String(raw.script || ''),
      description: String(raw.description || ''),
      purpose: String(raw.purpose || ''),
      status: String(raw.status || 'planned'),
      artifacts: Array.isArray(raw.artifacts) ? raw.artifacts.map((held) => ({ ...held })) : [],
      params: params.get(id) || {},
      steps: (Array.isArray(raw.steps) ? raw.steps : []).map((child) => copyStep(child, params)),
    }
  }

  /** `text` with each {name} replaced by the text parameter of that name. */
  const filled = (text, params, kind) =>
    String(text).replace(/\{([A-Za-z][A-Za-z0-9]*)\}/g, (_match, name) => {
      const held = params ? params[name] : undefined
      if (typeof held !== 'string' || !held) throw new Error(`a step of kind ${kind} needs the text parameter ${name} for its description`)
      return held
    })

  /**
   * Opens the journal a workflow was handed. `journal` is the document atw-step-journal read
   * printed, `run` the name the driver gave this run, `runner` the name of this workflow script as
   * pipeline-steps.json names it, and `under` the id of the step whose child steps this workflow
   * runs (absent for a workflow that runs the bead's outermost steps).
   */
  function open({ journal, run, runner, under = null }) {
    if (!journal || typeof journal !== 'object' || !Array.isArray(journal.steps)) throw new Error('stepJournal.open: no journal was read')
    if (typeof run !== 'string' || !run) throw new Error('stepJournal.open: no run name was supplied')
    const pipeline = PIPELINES[journal.pipeline]
    if (!pipeline) throw new Error(`stepJournal.open: the journal lists ${journal.pipeline} steps, which pipeline-steps.json does not define`)
    const params = new Map()
    for (const raw of walk(journal.steps)) {
      for (const held of Array.isArray(raw.artifacts) ? raw.artifacts : []) {
        const name = String(held.name || '')
        const planned = name.startsWith(WIRE.plannedForPrefix) ? name.slice(WIRE.plannedForPrefix.length) : ''
        if (held.kind === 'value' && STEP_ID.test(planned) && held.value && typeof held.value === 'object') params.set(planned, held.value)
      }
    }
    const roots = journal.steps.map((raw) => copyStep(raw, params))
    const parent = under ? walk(roots).find((step) => step.id === under) || null : null
    if (under && !parent) throw new Error(`stepJournal.open: the journal of ${journal.bead} holds no step ${under}`)
    let changes = 0

    /** Writes one change on the log, as one line or as part lines when it is longer than the chunk. */
    function report(change) {
      changes += 1
      const body = JSON.stringify({ run, n: changes, ...change })
      if (body.length <= WIRE.changeChunk) {
        log(`${WIRE.changePrefix}${body}`)
        return
      }
      const parts = []
      for (let at = 0; at < body.length; ) {
        let end = Math.min(at + WIRE.changeChunk, body.length)
        const last = body.charCodeAt(end - 1)
        if (end < body.length && last >= 0xd800 && last <= 0xdbff) end -= 1
        parts.push(body.slice(at, end))
        at = end
      }
      parts.forEach((part, index) => log(`${WIRE.changePartPrefix}${changes} ${index + 1}/${parts.length} ${part}`))
    }

    const everyStep = () => walk(roots)
    const scope = () => (parent ? parent.steps : roots)
    const kindOf = (key) => {
      const kind = pipeline.kinds[key]
      if (!kind) throw new Error(`pipeline-steps.json defines no ${journal.pipeline} step kind ${key}`)
      return kind
    }
    /** The steps of this workflow's scope before `step` in walk order; every step of the scope when `step` is not one of them. */
    const before = (step) => {
      const all = walk(scope())
      const at = all.indexOf(step)
      return at < 0 ? all : all.slice(0, at)
    }
    /** The step that directly contains `step`, or null for an outermost step. */
    const containerOf = (step) => everyStep().find((candidate) => candidate.steps.includes(step)) || null
    const siblingsOf = (step) => {
      const container = containerOf(step)
      return container ? container.steps : roots
    }
    const heldBy = (step, name) => step.artifacts.filter((held) => held.name === name).map((held) => (held.kind === 'value' ? held.value : held.path))

    /** What a planned step is in the copy, and the plan the driver adds to the journal file. */
    const planned = (adder, entry, ordinal) => {
      const kind = kindOf(entry.kind)
      const handed = entry.params && typeof entry.params === 'object' ? entry.params : null
      const ref = `${adder.key}.${ordinal}`
      const description = filled(kind.description, handed, entry.kind)
      const purpose = typeof entry.purpose === 'string' && entry.purpose.trim() ? entry.purpose.trim() : kind.purpose
      return {
        step: { key: ref, id: '', kind: entry.kind, description, purpose, status: 'planned', artifacts: [], params: handed || {}, steps: [] },
        wire: { plan: { ref, description, purpose, script: entry.kind }, ...(handed ? { params: handed } : {}) },
      }
    }

    return {
      bead: String(journal.bead || ''),
      pipeline: String(journal.pipeline || ''),
      kinds: pipeline.kinds,
      /** The kinds of the child steps pipeline-steps.json plans under a step of `kind` when it first runs. */
      innerPlan: (kind) => (pipeline.inner[kind] || []).map((key) => ({ kind: key })),
      /** The step this workflow runs child steps under, or null. */
      parent: () => parent,
      /** Every step of the journal in walk order. */
      steps: everyStep,
      /** The step this workflow does next: the first step of its scope that has no child steps and is not done. */
      next: () => walk(scope()).find((step) => !step.steps.length && step.status !== 'done') || null,
      /** `step` and the planned steps of its kind that follow it directly, when the kind's steps run together. */
      together(step) {
        if (kindOf(step.kind).together !== true) return [step]
        const siblings = siblingsOf(step)
        const group = [step]
        for (const sibling of siblings.slice(siblings.indexOf(step) + 1)) {
          if (sibling.kind !== step.kind || sibling.steps.length || sibling.status === 'done') break
          group.push(sibling)
        }
        return group
      },
      // The three lookups below read the steps of this workflow's scope: the bead's steps, or the child
      // steps of the step it was handed. A null `step` reads every step of the scope.
      /** The newest artifact named `name` a done step before `step` holds: its value or its path; `fallback` when none holds one. */
      latest(name, step, fallback = null) {
        const earlier = before(step).filter((candidate) => candidate.status === 'done')
        for (let at = earlier.length - 1; at >= 0; at -= 1) {
          const found = heldBy(earlier[at], name)
          if (found.length) return found[found.length - 1]
        }
        return fallback
      },
      /** Every artifact named `name` the done steps before `step` hold, oldest first; with `since`, only those of steps after it. */
      every(name, step, since = null) {
        const earlier = before(step)
        const from = since ? earlier.indexOf(since) + 1 : 0
        return earlier.slice(from).filter((candidate) => candidate.status === 'done').flatMap((candidate) => heldBy(candidate, name))
      },
      /** The done steps before `step` whose kind is one of `kinds`, oldest first; with `since`, only those after it. */
      earlier(kinds, step, since = null) {
        const all = before(step)
        const from = since ? all.indexOf(since) + 1 : 0
        return all.slice(from).filter((candidate) => candidate.status === 'done' && kinds.includes(candidate.kind))
      },
      /** A directory name for the files of `step`, unique in the journal. */
      folder: (step) => step.key.replace(/^([0-9a-f]{8})-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/, '$1').replace(/[^A-Za-z0-9._-]+/g, '-'),
      /** Marks a step running: it starts from its beginning, so the artifacts of an unfinished run of it are dropped. */
      start(step) {
        step.status = 'running'
        step.artifacts = []
        report({ op: 'start', step: step.key })
      },
      /** Records a step's artifacts, adds the steps its result calls for right after it, and marks it done. */
      done(step, artifacts = [], add = []) {
        const added = add.map((entry, index) => planned(step, entry, index + 1))
        const siblings = siblingsOf(step)
        siblings.splice(siblings.indexOf(step) + 1, 0, ...added.map((entry) => entry.step))
        step.artifacts = [...artifacts]
        step.status = 'done'
        report({ op: 'done', step: step.key, ...(artifacts.length ? { artifacts } : {}), ...(added.length ? { add: added.map((entry) => entry.wire) } : {}) })
        return added.map((entry) => entry.step)
      },
      /** Marks a step failed with its cause: { stage, message, evidence? }. */
      fail(step, cause) {
        const stage = String((cause && cause.stage) || step.kind)
        const message = String((cause && cause.message) || 'the step failed').slice(0, FAILURE_EVIDENCE_CHARS)
        const evidence = cause && cause.evidence ? String(cause.evidence).slice(0, FAILURE_EVIDENCE_CHARS) : ''
        step.status = 'failed'
        report({ op: 'fail', step: step.key, failure: JSON.stringify({ stage, message, ...(evidence ? { evidence } : {}) }) })
      },
      /** Plans child steps under the running step this workflow was handed, in the order they run. */
      planUnder(add) {
        if (!parent) throw new Error('stepJournal: this workflow was handed no step to plan child steps under')
        const added = add.map((entry, index) => planned(parent, entry, parent.steps.length + index + 1))
        parent.steps.push(...added.map((entry) => entry.step))
        report({ op: 'add', step: parent.key, add: added.map((entry) => entry.wire) })
        return added.map((entry) => entry.step)
      },
      /**
       * Runs the steps of this workflow's scope from the next one until none is left or one fails.
       * `table` maps a step kind to the function that runs a step of it: `async (step) => ({ artifacts, add })`
       * when the step is done (`add` lists { kind, params?, purpose? } for the steps its result calls for), or
       * `{ fail: { stage, message, evidence?, ...more } }` when it failed. `interrupted()` returns the
       * interruption of this run's dispatches, or null. Returns { ok: true }, or
       * { ok: false, step, fail } for the step that failed.
       */
      async run(table, interrupted = () => null) {
        const mine = Object.keys(pipeline.kinds).filter((key) => pipeline.kinds[key].runBy === runner && (pipeline.kinds[key].within || null) === (parent ? parent.kind : null))
        const missing = mine.filter((key) => typeof table[key] !== 'function')
        if (missing.length) throw new Error(`${runner} has no function for the step kinds ${missing.join(', ')}`)
        const attempt = async (step) => {
          let out = null
          try {
            const perform = table[step.kind]
            out = typeof perform === 'function' ? await perform(step) : { fail: { stage: step.kind, message: `${runner} runs no step of kind ${step.kind || '(none)'}` } }
          } catch (err) {
            out = { fail: { stage: step.kind, message: `the step threw: ${String((err && err.message) || err).slice(0, 400)}` } }
          }
          const stop = interrupted()
          if (stop) return { fail: { stage: stop.stage, message: stop.message, interrupted: true } }
          return out && typeof out === 'object' ? out : { fail: { stage: step.kind, message: 'the step returned nothing' } }
        }
        for (;;) {
          const first = this.next()
          if (!first) return { ok: true }
          const group = this.together(first)
          for (const step of group) this.start(step)
          const outcomes = group.length === 1 ? [await attempt(group[0])] : await parallel(group.map((step) => () => attempt(step)))
          let failed = null
          group.forEach((step, index) => {
            const out = outcomes[index] || { fail: { stage: step.kind, message: 'the step returned nothing' } }
            if (out.fail) {
              this.fail(step, out.fail)
              failed = failed || { ok: false, step, fail: out.fail }
            } else {
              this.done(step, Array.isArray(out.artifacts) ? out.artifacts : [], Array.isArray(out.add) ? out.add : [])
            }
          })
          if (failed) return failed
        }
      },
    }
  }

  /**
   * Reads the journal file through the checked relay: one command, bin/atw-step-journal read.
   * Returns { journal } or { error, noResult }.
   */
  async function read(dispatch, { runner, pluginRoot, path, relayFile, phase }) {
    const result = await relayKit.run(dispatch, { label: 'journal:read', phase, runner, argv: [`${pluginRoot}/bin/atw-step-journal`, 'read', '--journal', path], file: relayFile })
    if (!result.ok) return { error: result.error, noResult: !!result.noResult }
    if (result.exitCode !== 0 || !result.json || !result.json.journal) return { error: `atw-step-journal read exited ${result.exitCode}; its output is in ${relayFile}` }
    return { journal: result.json.journal }
  }

  return { file, directory, value, open, read, pipelines: PIPELINES }
})()
// ===== SHARED BLOCK step-journal — END =====
// ===== SHARED BLOCK architecture-artifacts — BEGIN (canonical: scripts/shared-blocks/architecture-artifacts.js; filled from skills/artifact-handoff/schemas/{architecture-writer,architecture-review,conformance,built-conformance,architecture-common}.schema.json; edit there, then: node scripts/shared-blocks.mjs --write) =====
// Generated from skills/artifact-handoff/schemas/architecture-common.schema.json, architecture-writer.schema.json,
// architecture-review.schema.json, conformance.schema.json and built-conformance.schema.json, with every $ref
// resolved. They are the one definition of these artifacts; never restate any part of them in a workflow.
const WRITER_SCHEMA = {"$schema":"https://json-schema.org/draft/2020-12/schema","description":"One architecture writer's round result (roles proposer and diagram). Coverage rows, evidence references and business conflicts are defined once in architecture-common.schema.json#/$defs; a loader resolves these references against that file.","type":"object","additionalProperties":false,"required":["files","claims","answers","businessConflicts","coverage","summary"],"properties":{"files":{"type":"array","items":{"type":"string"}},"claims":{"type":"array","items":{"description":"One claim the writer makes about a file it wrote, with its citation and evidence.","type":"object","additionalProperties":false,"required":["claimId","claim","file","citation","supersedes","evidenceRefs"],"properties":{"claimId":{"type":"string"},"claim":{"type":"string"},"file":{"type":"string"},"citation":{"type":"string"},"supersedes":{"type":"array","items":{"type":"string"}},"evidenceRefs":{"type":"array","items":{"description":"One piece of evidence. Every field is present; a field the reference does not use is the empty string.","type":"object","additionalProperties":false,"required":["path","heading","repo","revision","url"],"properties":{"path":{"type":"string"},"heading":{"type":"string"},"repo":{"type":"string"},"revision":{"type":"string"},"url":{"type":"string"}}}}}}},"answers":{"type":"array","items":{"description":"The writer's answer to one reviewer finding, by its id.","type":"object","additionalProperties":false,"required":["findingId","response","evidence"],"properties":{"findingId":{"type":"string"},"response":{"description":"How the writer answers one reviewer finding.","type":"string","enum":["fixed","disputed"]},"evidence":{"type":"string"}}}},"businessConflicts":{"type":"array","items":{"description":"Two or more business requirements of the PRD that no design can satisfy together, and why.","type":"object","additionalProperties":false,"required":["requirements","why"],"properties":{"requirements":{"type":"array","items":{"type":"string"}},"why":{"type":"string"}}}},"coverage":{"type":"array","items":{"description":"One obligation of the architecture documentation model and how the architecture covers it.","type":"object","additionalProperties":false,"required":["id","subject","scope","obligation","sources","views","status","action","reason","evidenceRefs","disposition","dispositionReason"],"properties":{"id":{"type":"string"},"subject":{"type":"string"},"scope":{"type":"string"},"obligation":{"type":"string"},"sources":{"type":"array","items":{"type":"string"}},"views":{"type":"array","items":{"type":"string"}},"status":{"description":"How far the architecture covers one obligation. A consumer reads an invalid value as the default.","type":"string","enum":["Present and sufficient","Present but incomplete","Required and absent","Not yet applicable","Not assessed"],"default":"Not assessed"},"action":{"description":"What the change does to the views covering one obligation. A consumer reads an invalid value as the default.","type":"string","enum":["create","update","unchanged","remove","not-applicable","unresolved"],"default":"unresolved"},"reason":{"type":"string"},"evidenceRefs":{"type":"array","items":{"description":"One piece of evidence. Every field is present; a field the reference does not use is the empty string.","type":"object","additionalProperties":false,"required":["path","heading","repo","revision","url"],"properties":{"path":{"type":"string"},"heading":{"type":"string"},"repo":{"type":"string"},"revision":{"type":"string"},"url":{"type":"string"}}}},"disposition":{"description":"Whether a coverage row is required by this change or unrelated historical debt. A consumer reads an invalid value as the default.","type":"string","enum":["required","unrelated-debt"],"default":"required"},"dispositionReason":{"type":"string"}}}},"summary":{"type":"string"},"repairAnswers":{"type":"array","items":{"description":"The writer's answer to one repair request, by its id.","type":"object","additionalProperties":false,"required":["repairId","response"],"properties":{"repairId":{"type":"string"},"response":{"type":"string"}}}}}}
const REVIEW_SCHEMA = {"$schema":"https://json-schema.org/draft/2020-12/schema","description":"One architecture reviewer's round result (roles reviewer and cost). Coverage checks and the review verdict are defined once in architecture-common.schema.json#/$defs; a loader resolves these references against that file.","type":"object","additionalProperties":false,"required":["findings","coverageChecks","resolutions","summary"],"properties":{"findings":{"type":"array","items":{"description":"The reviewer's verdict on one writer claim, with its evidence and the role that owns the fix.","type":"object","additionalProperties":false,"required":["claimId","claim","file","verdict","evidence","owner"],"properties":{"claimId":{"type":"string"},"claim":{"type":"string"},"file":{"type":"string"},"verdict":{"description":"A reviewer's verdict on one claim or one coverage row.","type":"string","enum":["verified","unsupported","wrong"]},"evidence":{"type":"string"},"owner":{"type":"string"}}}},"coverageChecks":{"type":"array","items":{"description":"A reviewer's independent check of one coverage row, by its id.","type":"object","additionalProperties":false,"required":["id","verdict","evidence"],"properties":{"id":{"type":"string"},"verdict":{"description":"A reviewer's verdict on one claim or one coverage row.","type":"string","enum":["verified","unsupported","wrong"]},"evidence":{"type":"string"}}}},"resolutions":{"type":"array","items":{"description":"The reviewer's ruling on a writer's answer to one finding, by the finding's id.","type":"object","additionalProperties":false,"required":["findingId","verdict","evidence"],"properties":{"findingId":{"type":"string"},"verdict":{"description":"Whether the reviewer accepts a writer's answer to one finding.","type":"string","enum":["accepted","rejected"]},"evidence":{"type":"string"}}}},"summary":{"type":"string"},"repairChecks":{"type":"array","items":{"description":"The reviewer's check of one repair, by its id, with the files it checked.","type":"object","additionalProperties":false,"required":["repairId","verdict","evidence","files"],"properties":{"repairId":{"type":"string"},"verdict":{"description":"Whether one repair is verified or must be revised.","type":"string","enum":["verified","revise"]},"evidence":{"type":"string"},"files":{"type":"array","items":{"type":"string"}}}}},"estimates":{"type":"array","items":{"type":"string"}}}}
const CONFORMANCE_SCHEMA = {"$schema":"https://json-schema.org/draft/2020-12/schema","description":"The architecture-conformance-reviewer's result for an integration (architecture.js Integrate, conformance-<n>.json). Conformance findings and coverage checks are defined once in architecture-common.schema.json#/$defs.","type":"object","additionalProperties":false,"required":["conforms","reviewedFiles","findings","coverageChecks","summary"],"properties":{"conforms":{"type":"boolean"},"reviewedFiles":{"type":"array","items":{"type":"string"}},"findings":{"type":"array","items":{"description":"One problem the conformance reviewer found, with its file and evidence.","type":"object","additionalProperties":false,"required":["file","finding","evidence"],"properties":{"file":{"type":"string"},"finding":{"type":"string"},"evidence":{"type":"string"}}}},"coverageChecks":{"type":"array","items":{"description":"A reviewer's independent check of one coverage row, by its id.","type":"object","additionalProperties":false,"required":["id","verdict","evidence"],"properties":{"id":{"type":"string"},"verdict":{"description":"A reviewer's verdict on one claim or one coverage row.","type":"string","enum":["verified","unsupported","wrong"]},"evidence":{"type":"string"}}}},"summary":{"type":"string"}}}
const BUILT_CONFORMANCE_SCHEMA = {"$schema":"https://json-schema.org/draft/2020-12/schema","description":"The architecture-conformance-reviewer's result for a built-version correction (built-version.js Correct). It names the built views the effective version now matches and carries no coverage checks. Conformance findings are defined once in architecture-common.schema.json#/$defs.","type":"object","additionalProperties":false,"required":["conforms","reviewedFiles","matchedBuiltViews","findings","summary"],"properties":{"conforms":{"type":"boolean"},"reviewedFiles":{"type":"array","items":{"type":"string"}},"matchedBuiltViews":{"type":"array","items":{"type":"string"}},"findings":{"type":"array","items":{"description":"One problem the conformance reviewer found, with its file and evidence.","type":"object","additionalProperties":false,"required":["file","finding","evidence"],"properties":{"file":{"type":"string"},"finding":{"type":"string"},"evidence":{"type":"string"}}}},"summary":{"type":"string"}}}
const COVERAGE_ROWS_SCHEMA = {"type":"array","items":{"description":"One obligation of the architecture documentation model and how the architecture covers it.","type":"object","additionalProperties":false,"required":["id","subject","scope","obligation","sources","views","status","action","reason","evidenceRefs","disposition","dispositionReason"],"properties":{"id":{"type":"string"},"subject":{"type":"string"},"scope":{"type":"string"},"obligation":{"type":"string"},"sources":{"type":"array","items":{"type":"string"}},"views":{"type":"array","items":{"type":"string"}},"status":{"description":"How far the architecture covers one obligation. A consumer reads an invalid value as the default.","type":"string","enum":["Present and sufficient","Present but incomplete","Required and absent","Not yet applicable","Not assessed"],"default":"Not assessed"},"action":{"description":"What the change does to the views covering one obligation. A consumer reads an invalid value as the default.","type":"string","enum":["create","update","unchanged","remove","not-applicable","unresolved"],"default":"unresolved"},"reason":{"type":"string"},"evidenceRefs":{"type":"array","items":{"description":"One piece of evidence. Every field is present; a field the reference does not use is the empty string.","type":"object","additionalProperties":false,"required":["path","heading","repo","revision","url"],"properties":{"path":{"type":"string"},"heading":{"type":"string"},"repo":{"type":"string"},"revision":{"type":"string"},"url":{"type":"string"}}}},"disposition":{"description":"Whether a coverage row is required by this change or unrelated historical debt. A consumer reads an invalid value as the default.","type":"string","enum":["required","unrelated-debt"],"default":"required"},"dispositionReason":{"type":"string"}}}}
const EVIDENCE_REFS_SCHEMA = {"type":"array","items":{"description":"One piece of evidence. Every field is present; a field the reference does not use is the empty string.","type":"object","additionalProperties":false,"required":["path","heading","repo","revision","url"],"properties":{"path":{"type":"string"},"heading":{"type":"string"},"repo":{"type":"string"},"revision":{"type":"string"},"url":{"type":"string"}}}}
const CONFLICT_ITEMS_SCHEMA = {"type":"array","items":{"description":"Two or more business requirements of the PRD that no design can satisfy together, and why.","type":"object","additionalProperties":false,"required":["requirements","why"],"properties":{"requirements":{"type":"array","items":{"type":"string"}},"why":{"type":"string"}}}}
const COVERAGE_CHECKS_SCHEMA = {"type":"array","items":{"description":"A reviewer's independent check of one coverage row, by its id.","type":"object","additionalProperties":false,"required":["id","verdict","evidence"],"properties":{"id":{"type":"string"},"verdict":{"description":"A reviewer's verdict on one claim or one coverage row.","type":"string","enum":["verified","unsupported","wrong"]},"evidence":{"type":"string"}}}}
const COVERAGE_STATUSES = ["Present and sufficient","Present but incomplete","Required and absent","Not yet applicable","Not assessed"]
const COVERAGE_ACTIONS = ["create","update","unchanged","remove","not-applicable","unresolved"]
const REVIEW_VERDICTS = ["verified","unsupported","wrong"]
const RESOLUTION_VERDICTS = ["accepted","rejected"]
const REPAIR_VERDICTS = ["verified","revise"]
const ANSWER_RESPONSES = ["fixed","disputed"]
// ===== SHARED BLOCK architecture-artifacts — END =====
// ===== SHARED BLOCK story-deploy-args — BEGIN (canonical: scripts/shared-blocks/story-deploy-args.js; filled from skills/artifact-handoff/schemas/story-deploy-args.schema.json; edit there, then: node scripts/shared-blocks.mjs --write) =====
// Generated from skills/artifact-handoff/schemas/story-deploy-args.schema.json, the one definition of the
// Story deploy workflow arguments. Never restate a key, value or shape of it in a workflow: read it from here.
const STORY_DEPLOY_ARGS_SCHEMA = {"$schema":"https://json-schema.org/draft/2020-12/schema","$id":"https://agent-teams-workforce/skills/artifact-handoff/schemas/story-deploy-args.schema.json","title":"Story deploy workflow arguments","description":"The argument shapes of a Story's deploy. StoryDeployInput is the driver's own story-deploy input; BuiltVersionArgs, StoryDeployFixArgs and DeployMechanismArgs are the arguments the driver sends to the built-version, story-deploy-fix and deploy-mechanism workflows. The built-version and story-deploy-fix workflows run child steps of a step of the Story's step journal, which JournalRef names. The execution-identity keys the lane adds (executionId, supervisorInvocationId) are owned by the execution-identity contract and are not named here, so StoryDeployInput and BuiltVersionArgs admit additional properties.","$defs":{"Composite":{"description":"The composite names that address these shapes (dispatch wire values).","type":"string","enum":["story-deploy","built-version","story-deploy-fix","deploy-mechanism"]},"DeployState":{"description":"The Story's deploy state, bead metadata story_deploy_state: empty when not started, otherwise one of the bead-metadata StoryDeployState values.","anyOf":[{"type":"string","const":""},{"$ref":"../../beads-contract/schemas/bead-metadata.schema.json#/$defs/StoryDeployState"}]},"FailureStep":{"description":"The deploy step that failed.","type":"string","enum":["publish","synth","deploy","verify"]},"VerifiedStackStatus":{"description":"The CloudFormation stack statuses that count as a verified deploy.","type":"string","enum":["CREATE_COMPLETE","UPDATE_COMPLETE"]},"SubjectFolder":{"description":"A subject folder name in archstate.subject_folder form: ASCII, lower-case, runs of characters outside a-z0-9 folded to one hyphen, no hyphen at either end.","type":"string","pattern":"^[a-z0-9]+(-[a-z0-9]+)*$"},"PluginRoot":{"description":"The absolute path of an agent-teams-workforce install, with no '//' and no '..'.","type":"string","pattern":"^(?!.*//)(?!.*\\.\\.)/[A-Za-z0-9._/-]+$"},"StoryRef":{"description":"The Story a deploy works on.","type":"object","additionalProperties":false,"required":["id"],"properties":{"id":{"type":"string","minLength":1,"description":"The Story's beads id."},"title":{"type":"string","description":"The Story's title, possibly empty."}}},"TaskRef":{"description":"One Task, infra or infrastructure child bead of the Story.","type":"object","additionalProperties":false,"required":["id","title"],"properties":{"id":{"type":"string","minLength":1},"title":{"type":"string"}}},"BuiltVersionItem":{"description":"One delta item of the Story's detailing; status uses the detailing (recon) contract's status vocabulary.","type":"object","additionalProperties":false,"required":["id","element"],"properties":{"id":{"type":"string","minLength":1},"element":{"type":"string","minLength":1},"status":{"type":"string","description":"A status from the detailing (recon) contract."},"from":{"type":"string"},"to":{"type":"string"},"evidence":{"type":"array","items":{"type":"string"}}}},"DepscoreRef":{"description":"Where depscore.py runs.","type":"object","additionalProperties":false,"required":["script","repo"],"properties":{"script":{"type":"string","minLength":1,"description":"Absolute path of the plugin's scripts/portfolio/depscore.py."},"repo":{"type":"string","minLength":1,"description":"The control repository (ATW_CONTROL_REPO)."}}},"StackStatus":{"description":"One CloudFormation stack's status after a deploy.","type":"object","additionalProperties":false,"required":["name","status","reason"],"properties":{"name":{"type":"string"},"status":{"type":"string"},"reason":{"type":"string"}}},"DeployFailure":{"description":"The failed deploy step and what it printed.","type":"object","additionalProperties":false,"required":["step","output"],"properties":{"step":{"$ref":"#/$defs/FailureStep"},"output":{"type":"string","description":"The captured tail of the step's output."},"stacks":{"type":"array","items":{"$ref":"#/$defs/StackStatus"}}}},"RelayRef":{"description":"The relay a workflow runs commands through.","type":"object","additionalProperties":false,"required":["runner","dir"],"properties":{"runner":{"type":"string","minLength":1,"description":"Absolute path of relayrun.py."},"dir":{"type":"string","minLength":1,"description":"The Story's own directory for relay files, the same on every dispatch of the Story."}}},"JournalRef":{"description":"The Story's step journal, the run the driver names, and the step whose child steps the workflow runs.","type":"object","additionalProperties":false,"required":["path","run","step"],"properties":{"path":{"type":"string","minLength":1,"description":"Absolute path of the Story's step journal file."},"run":{"type":"string","minLength":1,"description":"The name of this run: every journal change the workflow reports carries it."},"step":{"type":"string","pattern":"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$","description":"The id of the running journal step the workflow performs: its steps are that step's child steps."}}},"StoryDeployInput":{"description":"The driver's own story-deploy input for one Story.","type":"object","required":["story","repoPath","epicId","storySlug","state","attempt","prUrl","publishedHead","builtVersionError","tasks"],"properties":{"story":{"$ref":"#/$defs/StoryRef"},"repoPath":{"type":"string","minLength":1,"description":"The Story's repository root, not its worktree."},"epicId":{"type":"string","description":"The nearest Epic ancestor's bead id; empty means none."},"storySlug":{"type":"string","description":"The bead's elab_key without its Story prefix; empty when the prefix is absent."},"state":{"$ref":"#/$defs/DeployState"},"attempt":{"type":"integer","minimum":0,"description":"Bead metadata story_deploy_attempt."},"prUrl":{"type":"string","description":"Bead metadata story_pr_url."},"publishedHead":{"type":"string","description":"Bead metadata story_published_head."},"builtVersionError":{"type":"string","description":"Bead metadata built_version_error."},"tasks":{"type":"array","items":{"$ref":"#/$defs/TaskRef"},"description":"The Story's child Task, infra and infrastructure beads, sorted by id."}}},"BuiltVersionArgs":{"description":"The arguments of the built-version workflow.","type":"object","required":["story","repoPath","archPath","subject","items","depscore","journal"],"properties":{"beadId":{"type":"string","minLength":1,"description":"The consumer falls back to story.id."},"journal":{"$ref":"#/$defs/JournalRef"},"story":{"$ref":"#/$defs/StoryRef"},"repoPath":{"type":"string","minLength":1,"description":"The Story's worktree (absolute path)."},"repoName":{"type":"string","description":"The basename of the Story's repository root."},"branch":{"type":"string","description":"The worktree's checked-out branch."},"archPath":{"type":"string","minLength":1,"description":"The ATW_ARCH_PATH directory."},"subject":{"$ref":"#/$defs/SubjectFolder"},"items":{"type":"array","items":{"$ref":"#/$defs/BuiltVersionItem"}},"depscore":{"$ref":"#/$defs/DepscoreRef"}}},"StoryDeployFixArgs":{"description":"The arguments of the story-deploy-fix workflow.","type":"object","additionalProperties":false,"required":["story","repoPath","failure","journal","pluginRoot","relay"],"properties":{"beadId":{"type":"string","minLength":1,"description":"The consumer falls back to story.id."},"journal":{"$ref":"#/$defs/JournalRef"},"story":{"$ref":"#/$defs/StoryRef"},"repoPath":{"type":"string","minLength":1,"description":"The Story's worktree."},"branch":{"type":"string"},"defaultBranch":{"type":"string"},"failure":{"$ref":"#/$defs/DeployFailure"},"pluginRoot":{"$ref":"#/$defs/PluginRoot"},"relay":{"$ref":"#/$defs/RelayRef"}}},"DeployMechanismArgs":{"description":"The arguments of the deploy-mechanism workflow.","type":"object","additionalProperties":false,"required":["story","repoPath"],"properties":{"beadId":{"type":"string","minLength":1,"description":"The consumer falls back to story.id."},"story":{"$ref":"#/$defs/StoryRef"},"repoPath":{"type":"string","minLength":1,"description":"The Story's repository, not its worktree."}}}}}
const STORY_DEPLOY_ARGS_DEFS = STORY_DEPLOY_ARGS_SCHEMA.$defs || {}
// Every top-level key of the four argument shapes, in schema order.
const ARG_KEYS = Object.freeze([...new Set(['StoryDeployInput', 'BuiltVersionArgs', 'StoryDeployFixArgs', 'DeployMechanismArgs']
  .flatMap((name) => Object.keys((STORY_DEPLOY_ARGS_DEFS[name] || {}).properties || {})))])
const FAILURE_STEPS = Object.freeze([...((STORY_DEPLOY_ARGS_DEFS.FailureStep || {}).enum || [])])
const VERIFIED_STACK_STATUSES = Object.freeze([...((STORY_DEPLOY_ARGS_DEFS.VerifiedStackStatus || {}).enum || [])])
const STORY_DEPLOY_COMPOSITES = Object.freeze([...((STORY_DEPLOY_ARGS_DEFS.Composite || {}).enum || [])])
const ITEM_KEYS = Object.freeze(Object.keys((STORY_DEPLOY_ARGS_DEFS.BuiltVersionItem || {}).properties || {}))

// Checks `value` against one schema node (the subset the schema uses: local $ref, type object, string,
// integer and array, required, properties, additionalProperties false, enum, const, minLength, minimum,
// pattern) and returns the problems found, each naming its path.
const storyDeployArgsProblems = (node, value, path) => {
  if (node.$ref) {
    const local = '#/$defs/'
    if (!node.$ref.startsWith(local)) return [] // an external definition is checked by its own owner
    return storyDeployArgsProblems(STORY_DEPLOY_ARGS_DEFS[node.$ref.slice(local.length)] || {}, value, path)
  }
  if (node.anyOf) {
    return node.anyOf.some((branch) => storyDeployArgsProblems(branch, value, path).length === 0)
      ? [] : [`${path}: matches none of the allowed forms`]
  }
  if ('const' in node && value !== node.const) return [`${path}: must be ${JSON.stringify(node.const)}`]
  if (node.enum && !node.enum.includes(value)) return [`${path}: must be one of ${node.enum.join(', ')}`]
  if (node.type === 'string') {
    if (typeof value !== 'string') return [`${path}: must be a string`]
    if (node.minLength && value.length < node.minLength) return [`${path}: must not be empty`]
    if (node.pattern && !new RegExp(node.pattern).test(value)) return [`${path}: must match ${node.pattern}`]
    return []
  }
  if (node.type === 'integer') {
    if (!Number.isInteger(value)) return [`${path}: must be an integer`]
    return typeof node.minimum === 'number' && value < node.minimum ? [`${path}: must be at least ${node.minimum}`] : []
  }
  if (node.type === 'array') {
    if (!Array.isArray(value)) return [`${path}: must be an array`]
    return value.flatMap((entry, index) => storyDeployArgsProblems(node.items || {}, entry, `${path}[${index}]`))
  }
  if (node.type === 'object') {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return [`${path}: must be an object`]
    const properties = node.properties || {}
    const missing = (node.required || []).filter((key) => !(key in value)).map((key) => `${path}.${key}: is required`)
    const extra = node.additionalProperties === false
      ? Object.keys(value).filter((key) => !(key in properties)).map((key) => `${path}.${key}: is not an allowed key`)
      : []
    const fields = Object.keys(properties).filter((key) => key in value)
      .flatMap((key) => storyDeployArgsProblems(properties[key], value[key], `${path}.${key}`))
    return [...missing, ...extra, ...fields]
  }
  return []
}

// Parses one workflow's arguments against its schema definition: { ok, value, problems }.
const parseStoryDeployArgs = (name, args) => {
  const definition = STORY_DEPLOY_ARGS_DEFS[name]
  if (!definition) return { ok: false, value: null, problems: [`the schema defines no ${name}`] }
  const problems = storyDeployArgsProblems(definition, args, 'args')
  return { ok: problems.length === 0, value: problems.length === 0 ? args : null, problems }
}
const parseBuiltVersionArgs = (args) => parseStoryDeployArgs('BuiltVersionArgs', args)
const parseStoryDeployFixArgs = (args) => parseStoryDeployArgs('StoryDeployFixArgs', args)
const parseDeployMechanismArgs = (args) => parseStoryDeployArgs('DeployMechanismArgs', args)
// ===== SHARED BLOCK story-deploy-args — END =====
// ===== SHARED BLOCK composite-phases — BEGIN (canonical: skills/pipeline-contracts/schemas/composites.json; edit there, then: python3 skills/pipeline-contracts/scripts/generate_composites.py and node scripts/shared-blocks.mjs --write) =====
// GENERATED by skills/pipeline-contracts/scripts/generate_composites.py from
// skills/pipeline-contracts/schemas/composites.json, the one definition of composite ids, their phases,
// phase titles and role sets. Never restate any part of it in a workflow: change composites.json and
// regenerate. check_composites_contract.py fails when this file is stale.
const COMPOSITE_CONTRACT = Object.freeze({"wire":{"phaseSentinel":"PHASE","progressPrefix":"\u25b8 "},"fallbackPhases":[{"id":"start","title":"Start"},{"id":"work","title":"Work"},{"id":"finish","title":"Finish"}],"composites":{"prd-to-spec":{"runner":"orchestrator","openingKind":"epic","sets":["orchestrated","elaboration"],"phases":[{"id":"epic-lifecycle","title":"Epic Lifecycle"},{"id":"prd","title":"PRD"},{"id":"epic","title":"Epic"},{"id":"architecture","title":"Architecture","event":true},{"id":"trd-authoring","title":"TRD Authoring","event":true},{"id":"repo-scoping","title":"Repo Scoping","event":true},{"id":"spec-authoring","title":"Spec Authoring","event":true},{"id":"task-decomposition","title":"Task Decomposition","event":true},{"id":"task-edges","title":"Task Edges","event":true},{"id":"finish","title":"Finish","event":true},{"id":"run-ledger","title":"Run Ledger"}]},"task-to-deploy":{"runner":"workflow","openingKind":"task","sets":["target-repo","code-build","repo-required","design-aware"],"phases":[{"id":"workspace","title":"Workspace"},{"id":"infra-intent","title":"Infra Intent"},{"id":"regression-scope","title":"Regression Scope"},{"id":"baseline","title":"Baseline"},{"id":"red","title":"Red"},{"id":"green","title":"Green"},{"id":"refactor","title":"Refactor"},{"id":"cds-audit","title":"CDS Audit"},{"id":"documentation","title":"Documentation"},{"id":"commit","title":"Commit"}]},"bug-fix":{"runner":"workflow","openingKind":"task","sets":["target-repo","code-build","bug"],"phases":[{"id":"workspace","title":"Workspace"},{"id":"triage","title":"Triage"},{"id":"red","title":"Red"},{"id":"green","title":"Green"},{"id":"refactor","title":"Refactor"},{"id":"integration","title":"Integration"},{"id":"adversarial","title":"Adversarial"},{"id":"deploy-to-dev","title":"Deploy-to-dev"},{"id":"settle","title":"Settle"},{"id":"run-ledger","title":"Run Ledger"}]},"story-deploy":{"runner":"driver","sets":["story"],"phases":[{"id":"mechanism","title":"Mechanism"},{"id":"workspace","title":"Workspace"},{"id":"publish","title":"Publish"},{"id":"ssm-check","title":"SSM Check"},{"id":"deploy","title":"Deploy"},{"id":"verify","title":"Verify"},{"id":"fix","title":"Fix"},{"id":"built","title":"Built"},{"id":"pull-request","title":"Pull Request"},{"id":"merge-wait","title":"Merge Wait"},{"id":"close","title":"Close"}]},"story-deploy-fix":{"runner":"workflow","sets":["story"],"phases":[{"id":"fix","title":"Fix"},{"id":"commit","title":"Commit"}]},"deploy-mechanism":{"runner":"workflow","sets":["story"],"phases":[{"id":"ask","title":"Ask"}]},"built-version":{"runner":"workflow","sets":["story"],"phases":[{"id":"compare","title":"Compare"},{"id":"correct","title":"Correct"},{"id":"remove","title":"Remove"}]},"probe":{"runner":"probe","sets":["attaching"],"phases":[]}},"retired":{"repair":{"sets":["attaching"]},"incident":{"sets":["attaching"]},"dependency-assessment":{"sets":["former-trigger"]},"task-dependency-assessment":{"sets":["former-trigger"]},"wsjf-scoring":{"sets":["former-trigger"]}}})
const compositePhases = (composite) => {
  const spec = COMPOSITE_CONTRACT.composites[composite]
  if (spec && spec.phases.length) return spec.phases
  if (spec || COMPOSITE_CONTRACT.retired[composite]) return COMPOSITE_CONTRACT.fallbackPhases
  throw new Error(`unknown composite ${composite}`)
}
const compositePhaseTitle = (composite, phase) => {
  const found = compositePhases(composite).find(entry => entry.id === phase)
  if (!found) throw new Error(`composite ${composite} has no phase ${phase}`)
  return found.title
}
// ===== SHARED BLOCK composite-phases — END =====

const dispatchFailures = []

async function run(prompt, opts) {
  let message = 'returned nothing'
  try {
    const out = await fableAgent(prompt, opts)
    if (out) return out
  } catch (err) {
    message = String((err && err.message) || err).slice(0, 300)
  }
  dispatchFailures.push({ label: opts.label, agentType: opts.agentType || null, phase: opts.phase, message })
  log(`${opts.label}: no structured result — ${message}`)
  return null
}

const hasText = (v) => typeof v === 'string' && v.trim().length > 0
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
const listed = (x) => (Array.isArray(x) ? x.filter(hasText).map((s) => s.trim()) : [])

// This workflow's arguments are BuiltVersionArgs in the story-deploy-args shared block; the subject is
// checked against the contract's subject-folder pattern there. The runtime adds its own keys (the
// model-allowance, relay and retry keys), so only the keys that definition declares are parsed.
const COMPOSITE = 'built-version'
const PARENT_KIND = 'deploy:built-version'
const phaseTitle = (id) => compositePhaseTitle(COMPOSITE, id)
function enterPhase(id) {
  phase(phaseTitle(id))
}
const contractArgs = (definition, raw) => {
  const declared = (STORY_DEPLOY_ARGS_DEFS[definition] || {}).properties || {}
  return Object.fromEntries(Object.entries(raw && typeof raw === 'object' ? raw : {}).filter(([key]) => key in declared))
}
const parsedArgs = parseBuiltVersionArgs(contractArgs('BuiltVersionArgs', (typeof args === 'string' ? JSON.parse(args) : args) || {}))
const builtArgs = parsedArgs.value
const story = builtArgs ? builtArgs.story : null
const beadId = builtArgs ? String(builtArgs.beadId || story.id).trim() : ''
const repo = builtArgs ? builtArgs.repoPath.trim().replace(/\/+$/, '') : ''
const archPath = builtArgs ? builtArgs.archPath.trim().replace(/\/+$/, '') : ''
const subject = builtArgs ? builtArgs.subject : ''
const DS = builtArgs ? builtArgs.depscore : null
const items = builtArgs ? builtArgs.items : []
// A review declines to add another correction once this many corrections have answered findings.
const MAX_CORRECTIONS = 2
const DISPATCH_FAILED_STAGE = 'agent-dispatch-failed'

const handback = (ok, stage, headline, extra) => ({ ok, stage, beadId: beadId || null, headline: String(headline || ''), detailPath: null, ...(extra || {}) })
function died(phaseName) {
  const deaths = dispatchFailures.filter((f) => f.phase === phaseName)
  return deaths.length ? { dispatchFailed: true, dispatchFailures: deaths } : {}
}
/** The failure of a step: the dispatch-failed stage when an agent of `phaseName` returned nothing, else `stage`. */
const failed = (phaseName, stage, message, more) => {
  const deaths = phaseName ? died(phaseName) : {}
  return { fail: { stage: deaths.dispatchFailed ? DISPATCH_FAILED_STAGE : stage, message, ...deaths, ...(more || {}) } }
}

if (!parsedArgs.ok) return handback(false, 'input', `the ${COMPOSITE} arguments break their contract: ${parsedArgs.problems.join('; ')}`)
if (!repo) return handback(false, 'input', `no worktree supplied for Story ${beadId}`)
if (!archPath) return handback(false, 'input', "no archPath supplied (the project's architecture directory): there is no effective version to compare the build with")

const ARC42 = `${archPath}/arc42`
const CONSTRAINTS = `${ARC42}/02-architecture-constraints`
const BUILT_DIR = `${archPath}/built/${subject}`
const MENU = `${archPath}/reference/diagram-and-model-types.md`
const MODEL = `${archPath}/reference/architecture-documentation-model.md`

/** Where this workflow keeps its tree fingerprints and relay files: the per-file hashes stay on disk and never pass through a session. */
const SNAP_DIR = `${DS.repo}/.claude/workflow-runs/artifacts/${beadId.replace(/[^A-Za-z0-9._-]+/g, '_')}/built-version`
const PLUGIN_SCRIPTS = '/scripts/portfolio/depscore.py'
const pluginRoot = DS.script.endsWith(PLUGIN_SCRIPTS) ? DS.script.slice(0, -PLUGIN_SCRIPTS.length) : ''
if (!pluginRoot.startsWith('/')) return handback(false, 'input', `depscore.script ${DS.script} is not <plugin>${PLUGIN_SCRIPTS}, so the plugin's commands cannot be found`)
const { file: fileArtifact, value: valueArtifact } = stepJournal
let J = null
let current = null
/** The relay file of a depscore.py command of the running step. */
const relayFile = (label) => `${SNAP_DIR}/relay/${J ? J.folder(current) : 'journal'}/${String(label).replace(/[^A-Za-z0-9._-]+/g, '-')}.json`
/** Runs one depscore.py command through the checked relay; returns its checked JSON output or { error, output }. */
async function depscore(label, phaseName, commandArgs) {
  const out = await relayKit.depscore(run, { label, phase: phaseName, script: DS.script, repo: DS.repo, tail: commandArgs, file: relayFile(label) })
  if (!out.error) return out
  const refusals = out.output && Array.isArray(out.output.refusals) ? out.output.refusals.join('; ') : ''
  return { error: ((out.output && out.output.error) || !refusals) ? out.error : refusals, output: out.output || null }
}

const COMPARE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['differences', 'files', 'summary'],
  properties: {
    differences: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['element', 'effectiveViews', 'built', 'citations', 'file'],
        properties: {
          element: { type: 'string' },
          itemId: { type: 'string' },
          effectiveViews: { type: 'array', items: { type: 'string' } },
          built: { type: 'string' },
          citations: { type: 'array', items: { type: 'string' } },
          file: { type: 'string' },
        },
      },
    },
    files: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
}
const MAINTAIN_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['changedFiles', 'createdFiles', 'deletedFiles', 'matched', 'constraintIssues', 'contradictions', 'summary'],
  properties: {
    changedFiles: { type: 'array', items: { type: 'string' } },
    createdFiles: { type: 'array', items: { type: 'string' } },
    deletedFiles: { type: 'array', items: { type: 'string' } },
    matched: { type: 'array', items: { type: 'string' } },
    constraintIssues: { type: 'array', items: { type: 'string' } },
    contradictions: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
}

const ARCH_WHERE = `THE ARCHITECTURE is at ${archPath}. It is not inside any product repository.
- \`arc42/\` is the effective version: the approved architecture. \`arc42/02-architecture-constraints/README.md\` holds the owner's constraints.
- Each view's frontmatter names its \`view_type\`, \`scope\`, \`subject\` and every element it \`shows\`: that frontmatter is the catalog. Find the views of an element by searching it (\`subject:\` and the \`shows:\` lists) for the element's name, in every section, at every scope.
- \`built/<subject>/\` records what a build delivered where it differs from the effective version.
- The architecture documentation model is ${MODEL}; the view types to choose from are ${MENU}.`

/** Returns the section 2 fingerprint, or { error }; with `keep`, section 2 is also copied aside for a restore. */
const constraintsSnapshot = (label, phaseName, keep) => depscore(label, phaseName, `arch-constraints --arch-root ${shq(archPath)}${keep ? ' --keep' : ''}`)
const sameSnapshot = (x, y) =>
  !!x && !!y && !x.error && !y.error && x.exists === y.exists && x.digest === y.digest && JSON.stringify(x.gitStatus || []) === JSON.stringify(y.gitStatus || [])
/** Returns null when section 2 is unchanged since the snapshot step recorded it, else puts section 2 back from the copy and returns the failure. */
async function constraintsGuard(step, label, phaseName, during) {
  const before = J.latest('constraintsBefore', step)
  const after = await constraintsSnapshot(label, phaseName)
  if (sameSnapshot(before, after)) return null
  const restored = after && after.error ? null : await depscore(`${label}:restore`, phaseName, `arch-constraints-restore --arch-root ${shq(archPath)} --kept ${shq(before && before.kept)}`)
  const restoreNote = !restored ? '' : restored.error ? `; section 2 could not be put back: ${restored.error}` : '; section 2 was put back as it was'
  const why = after && after.error ? after.error : `git status ${JSON.stringify((after && after.gitStatus) || [])}${restoreNote}`
  return failed(null, 'constraints-written', `section 2 changed while ${during}: ${why}`)
}
const TREE_START = `${SNAP_DIR}/tree-start.json`
const TREE_COMPARED = `${SNAP_DIR}/tree-compared.json`
const TREE_LAST = `${SNAP_DIR}/tree-last.json`
/**
 * Fingerprints every file of arc42/, target/ and built/ with depscore.py arch-snapshot: `save` writes
 * the hashes to that file, and each file in `against` (a fingerprint saved earlier) yields the files
 * created, changed and deleted since it, in `diffs`, in that order. Returns the result or { error }.
 */
async function treeSnapshot(label, phaseName, { save, against = [] } = {}) {
  const out = await depscore(label, phaseName, `arch-snapshot --arch-root ${shq(archPath)}${save ? ` --save ${shq(save)}` : ''}${against.map((f) => ` --against ${shq(f)}`).join('')}`)
  if (!out || out.error) return out || { error: 'no result' }
  if (against.length && (!Array.isArray(out.diffs) || out.diffs.length !== against.length)) return { error: 'depscore.py arch-snapshot printed no difference for a saved fingerprint' }
  return out
}
/** Returns diff `i` of a snapshot as absolute paths: { created, changed, deleted }. */
function treeDiff(snap, i) {
  const d = (snap && Array.isArray(snap.diffs) && snap.diffs[i]) || {}
  const abs = (rel) => `${archPath}/${rel}`
  return { created: listed(d.created).map(abs), changed: listed(d.changed).map(abs), deleted: listed(d.deleted).map(abs) }
}
const diffFiles = (d) => [...d.created, ...d.changed, ...d.deleted]

// ---------------------------------------------------------------- Snapshot
async function stepSnapshot(step) {
  enterPhase('compare')
  const before = await constraintsSnapshot('constraints:before', phaseTitle('compare'), true)
  if (!before || before.error || !hasText(before.kept)) return failed(phaseTitle('compare'), 'compare', `section 2 of the architecture could not be fingerprinted and copied before the step: ${(before && before.error) || 'no copy was named'}`)
  const treeBefore = await treeSnapshot('tree:before', phaseTitle('compare'), { save: TREE_START })
  if (!treeBefore || treeBefore.error) return failed(phaseTitle('compare'), 'compare', `the architecture could not be fingerprinted before the step: ${(treeBefore && treeBefore.error) || 'no result'}`)
  return {
    artifacts: [valueArtifact('constraintsBefore', { exists: before.exists, digest: before.digest, gitStatus: before.gitStatus || [], kept: before.kept }), fileArtifact('treeStart', TREE_START)],
  }
}

// ---------------------------------------------------------------- Compare
async function stepCompare(step) {
  enterPhase('compare')
  const treeStart = J.latest('treeStart', step)
  const itemLines = items.length
    ? items
        .map((i) => `- ${i.id}: ${i.element}${hasText(i.status) ? ` [${i.status}]` : ''}${hasText(i.from) || hasText(i.to) ? `\n    change: ${i.from || '(unstated)'} → ${i.to || '(unstated)'}` : ''}`)
        .join('\n')
    : '- (no delta item was recorded for this repository)'
  const compared = await run(
    `You are the prd-reality-reconciler, recording what Story ${beadId}${story.title ? ` (${story.title})` : ''} BUILT. Its deploy to AWS dev succeeded. Compare the code on the Story's branch with the effective version, and record each difference.

THE CODE is the worktree below, at its checked-out HEAD (the Story's branch). Read it there: \`git -C "${repo}" grep -n <term> HEAD\`, \`git -C "${repo}" show HEAD:<path>\`. Change nothing in it.
${repo}${hasText(builtArgs.repoName) ? `\nRepository: ${builtArgs.repoName}` : ''}${hasText(builtArgs.branch) ? `\nBranch: ${builtArgs.branch}` : ''}

${ARCH_WHERE}

THE DELTA ITEMS the Epic placed in this repository:
${itemLines}

DO THIS:
1. Find the effective views that show this repository's elements and each delta item, through the catalog, at every scope.
2. For each element, compare what the code builds with what those views show: components, interfaces, data, events, runtime flows, deployment.
3. For each difference, write one view in ${BUILT_DIR}/, in the section folder the model names for its view type, named for the element it shows. Each view has catalog frontmatter (\`view_type\` from ${MENU}, \`scope\`, \`subject\`, \`shows\`, \`lifecycle_state: in-review\`), a Mermaid diagram where the view type has one, and prose that describes the element as built, citing the code by repository, path and line. Where a view in ${BUILT_DIR}/ already shows the same element, update it in place. Write nothing outside ${BUILT_DIR}/.
4. Where the code matches the effective views, write nothing for it.

Return one entry in \`differences\` per difference: the element, the delta item id where one applies, the effective views it differs from (absolute paths), what was built, the \`file:line\` citations, and the absolute path of the built view that records it. Return in \`files\` the absolute path of every file you wrote or updated under ${BUILT_DIR}/. With no difference, return both empty.`,
    { label: 'built:compare', phase: phaseTitle('compare'), agentType: 'prd-reality-reconciler', effort: 'medium', schema: COMPARE_SCHEMA }
  )
  if (!compared) return failed(phaseTitle('compare'), 'compare', `the prd-reality-reconciler returned no comparison for Story ${beadId}`)
  const differences = (Array.isArray(compared.differences) ? compared.differences : []).filter((d) => d && hasText(d.element))
  const guardCompare = await constraintsGuard(step, 'constraints:after-compare', phaseTitle('compare'), 'the build was compared')
  if (guardCompare) return guardCompare
  const treeCompared = await treeSnapshot('tree:after-compare', phaseTitle('compare'), { save: TREE_COMPARED, against: [treeStart] })
  if (!treeCompared || treeCompared.error) return failed(phaseTitle('compare'), 'compare', `the architecture could not be fingerprinted after the comparison: ${(treeCompared && treeCompared.error) || 'no result'}`)
  const compareWrites = treeDiff(treeCompared, 0)
  const builtFiles = [...new Set([...listed(compared.files), ...differences.map((d) => d.file).filter(hasText).map((f) => f.trim()), ...compareWrites.created, ...compareWrites.changed])]
  const outsideBuilt = [...builtFiles, ...compareWrites.deleted].filter((f) => !f.startsWith(`${BUILT_DIR}/`) || f.split('/').includes('..'))
  if (outsideBuilt.length) return failed(null, 'compare', `the comparison wrote or reports files outside ${BUILT_DIR}: ${outsideBuilt.join(', ')}`)
  const artifacts = [valueArtifact('differences', differences), valueArtifact('builtFiles', builtFiles), fileArtifact('treeCompared', TREE_COMPARED)]
  if (!differences.length && !builtFiles.length) {
    log(`Built: Story ${beadId} built what the effective version shows; nothing written`)
    return { artifacts }
  }
  if (!differences.length || !builtFiles.length) {
    return failed(null, 'compare', `the comparison for Story ${beadId} is incomplete: ${differences.length} difference(s) but ${builtFiles.length} built view(s)`)
  }
  const states = await depscore('built:state', phaseTitle('compare'), `arch-state --arch-files ${shq(builtFiles.join(','))} --arch-root ${shq(archPath)}`)
  if (!states || states.error) return failed(phaseTitle('compare'), 'compare', `depscore.py arch-state did not read the built views: ${(states && states.error) || 'no result'}`)
  const stateOf = states.states && typeof states.states === 'object' ? states.states : {}
  const badState = [
    ...(states.refused || []).map((x) => `${x.path} (${x.reason})`),
    ...(states.failed || []).map((x) => `${x.path} (${x.reason})`),
    ...Object.entries(stateOf).filter(([, s]) => s !== 'in-review').map(([p, s]) => `${p} (lifecycle_state ${s || 'missing'})`),
  ]
  if (badState.length) return failed(null, 'compare', `the built views must be in-review: ${badState.join(', ')}`)
  log(`Built: ${differences.length} difference(s) recorded in ${builtFiles.length} view(s) under ${BUILT_DIR}`)
  return { artifacts, add: [{ kind: 'deploy:built-correct' }, { kind: 'deploy:built-review' }] }
}

// ---------------------------------------------------------------- Correct
const SECTION_2_RULE = `Write nothing under ${CONSTRAINTS}: section 2 holds the owner's constraints, and only the owner changes them; the run fails on any change there. A constraint the build conflicts with goes in \`constraintIssues\`, with the constraint, the built view and the reason.`
const correctTask = (builtFiles) => `Correct the effective version, the folder ${ARC42}, to match what was built, as the architecture documentation model's step 6 describes. The built views are:
${builtFiles.map((f) => `- ${f}`).join('\n')}
For each element a built view shows, find every effective view that shows it through the catalog (\`subject\` and \`shows\`), at every scope, and update it to describe the element as built; add a view where the effective version has none for a built element, in the section folder the model names, named for its subject. Keep every touched view's catalog frontmatter true to what it now shows. Edit in place: no changelog narrative, and no superseded content left beside the new. Leave every \`lifecycle_state\` as you find it: the run sets it after review. Leave ${BUILT_DIR}/ as it is: the run removes each built view once the effective version matches it.
${SECTION_2_RULE}
The result names every file you changed, created or deleted as an absolute path under ${ARC42}, in \`matched\` every built view the effective version now matches, and every contradiction with another effective view or open target.`

const touched = (u) => [...new Set([...listed(u.changedFiles), ...listed(u.createdFiles)])]
const allTouched = (u) => [...touched(u), ...listed(u.deletedFiles)]

async function stepCorrect(step) {
  enterPhase('correct')
  const builtFiles = listed(J.latest('builtFiles', step))
  const treeCompared = J.latest('treeCompared', step)
  const earlier = J.latest('architectureUpdate', step)
  const findings = Array.isArray(step.params.findings) ? step.params.findings : null
  const pass = J.earlier(['deploy:built-correct'], step).length
  const reported = await run(
    findings
      ? `You are the architecture-maintainer, CORRECTING your correction of the effective version (pass ${pass} of ${MAX_CORRECTIONS}). The architecture-conformance-reviewer found the findings below. Correct each one in place, then return the complete report, every pass together.

FINDINGS:
${JSON.stringify(findings, null, 1)}

${correctTask(builtFiles)}`
      : `You are the architecture-maintainer.\n\n${correctTask(builtFiles)}`,
    { label: findings ? `built:correct-${pass}` : 'built:correct', phase: phaseTitle('correct'), agentType: 'architecture-maintainer', effort: 'medium', schema: MAINTAIN_SCHEMA }
  )
  if (!reported) return failed(phaseTitle('correct'), 'correct', findings ? `the architecture-maintainer returned no result for correction ${pass}` : 'the architecture-maintainer returned no result')
  const merged = (key) => [...new Set([...listed(earlier && earlier[key]), ...listed(reported[key])])]
  const u = earlier ? { ...reported, changedFiles: merged('changedFiles'), createdFiles: merged('createdFiles'), deletedFiles: merged('deletedFiles'), matched: merged('matched') } : reported
  // Every file the correction wrote since the comparison is measured from the tree, so an unreported write is reviewed too.
  const now = await treeSnapshot(findings ? `tree:after-correct-${pass}` : 'tree:after-correct', phaseTitle('correct'), { save: TREE_LAST, against: earlier ? [treeCompared, TREE_LAST] : [treeCompared] })
  if (!now || now.error) return failed(phaseTitle('correct'), 'correct', `the architecture could not be fingerprinted after the correction: ${(now && now.error) || 'no result'}`)
  const d = treeDiff(now, 0)
  const unreported = diffFiles(d).filter((f) => !allTouched(u).includes(f))
  if (unreported.length) log(`Correct: files written and not reported, added to the review: ${unreported.join(', ')}`)
  const union = (key, extra) => [...new Set([...listed(u[key]), ...extra])]
  const update = { ...u, changedFiles: union('changedFiles', d.changed), createdFiles: union('createdFiles', d.created), deletedFiles: union('deletedFiles', d.deleted) }
  const changedSinceLast = earlier ? diffFiles(treeDiff(now, 1)) : []
  const inSection2 = allTouched(update).filter((f) => f === CONSTRAINTS || f.startsWith(`${CONSTRAINTS}/`))
  const outside = allTouched(update).filter((f) => !f.startsWith(`${ARC42}/`))
  if (inSection2.length) {
    const guard = await constraintsGuard(step, 'constraints:correct-bounds', phaseTitle('correct'), 'the effective version was corrected')
    if (guard) return guard
    return failed(null, 'correct', `the correction wrote in section 2, which holds the owner's constraints: ${inSection2.join(', ')}`)
  }
  if (outside.length) return failed(null, 'correct', `the correction wrote files outside the effective version ${ARC42}: ${outside.join(', ')}`)
  if (findings && !changedSinceLast.length) {
    return failed(null, 'correct', `correction pass ${pass} changed no file, so a further review would judge the same correction; the findings stand: ${findings.map((f) => `${f.file}: ${f.finding}`).join('; ')}`)
  }
  return { artifacts: [valueArtifact('architectureUpdate', update), valueArtifact('changedSinceLast', changedSinceLast), fileArtifact('treeLast', TREE_LAST)] }
}

async function stepReview(step) {
  enterPhase('correct')
  const builtFiles = listed(J.latest('builtFiles', step))
  const update = J.latest('architectureUpdate', step) || {}
  const previous = J.latest('conformance', step)
  const reviewPass = J.earlier(['deploy:built-review'], step).length + 1
  const corrections = J.earlier(['deploy:built-correct'], step).length - 1
  const againBlock = previous
    ? `\nTHIS IS REVIEW ${reviewPass}. The previous review found the findings below, and correction pass ${corrections} changed these files to answer them: ${listed(J.latest('changedSinceLast', step)).join(', ')}. Confirm each finding is resolved, and check the changed files as fully as the rest.\nPREVIOUS FINDINGS:\n${JSON.stringify(previous.findings || [], null, 1)}\n`
    : ''
  const got = await run(
    `You are the architecture-conformance-reviewer. Check one correction of the effective version to match what a build delivered; report findings and fix nothing.

THE BUILT VIEWS (what was built, citing the code):
${builtFiles.map((f) => `- ${f}`).join('\n')}
THE CORRECTION changed or created these files, every one of which you review:
${touched(update).map((f) => `- ${f}`).join('\n') || '- (none)'}
Files it deleted: ${listed(update.deletedFiles).join(', ') || '(none)'}
${againBlock}
${ARCH_WHERE}

Check that the effective version now describes each element as the built views show it, no more and no less; that every effective view the catalog lists for each built element was updated, at every scope; that new views sit in the section folders the model names with catalog frontmatter true to what they show; that no superseded content remains beside the new and no view contradicts another or an open target; and that nothing under ${CONSTRAINTS} changed. Return in \`reviewedFiles\` the absolute path of every file you checked and found conforming; in \`matchedBuiltViews\` the absolute path of every built view above that the effective version now describes completely, compared by you view by view (a built view goes in this list only when every element it shows reads the same in the effective version); and one finding per problem with its file and evidence. \`conforms\` is true only when there is no finding.`,
    { label: `built:review-${reviewPass}`, phase: phaseTitle('correct'), agentType: 'architecture-conformance-reviewer', effort: 'medium', schema: BUILT_CONFORMANCE_SCHEMA }
  )
  if (!got) return failed(phaseTitle('correct'), 'correct', 'the architecture-conformance-reviewer returned no result')
  // A review that leaves a changed file unreviewed does not conform.
  const missed = touched(update).filter((f) => !listed(got.reviewedFiles).includes(f))
  const conformance = missed.length
    ? { ...got, conforms: false, findings: [...(Array.isArray(got.findings) ? got.findings : []), ...missed.map((f) => ({ file: f, finding: 'changed or created by the correction and not reviewed', evidence: 'absent from reviewedFiles' }))] }
    : got
  const artifacts = [valueArtifact('conformance', conformance)]
  if (conformance.conforms !== true) {
    const findings = Array.isArray(conformance.findings) ? conformance.findings : []
    if (corrections >= MAX_CORRECTIONS) {
      return failed(null, 'correct', `the correction does not conform after ${corrections} correction pass(es): ${findings.map((f) => `${f.file}: ${f.finding}`).join('; ')}`)
    }
    const purpose = `The review found ${findings.length} finding(s) in the correction`
    return { artifacts, add: [{ kind: 'deploy:built-correct', params: { findings }, purpose }, { kind: 'deploy:built-review', purpose: 'The correction was changed to answer the review' }] }
  }
  const guardCorrect = await constraintsGuard(step, 'constraints:after-correct', phaseTitle('correct'), 'the effective version was corrected')
  if (guardCorrect) return guardCorrect
  return { artifacts, add: [{ kind: 'deploy:built-approve' }, { kind: 'deploy:built-remove' }] }
}

async function stepApprove(step) {
  enterPhase('correct')
  const update = J.latest('architectureUpdate', step) || {}
  const conformance = J.latest('conformance', step) || {}
  const toApprove = touched(update)
  if (!toApprove.length) return { artifacts: [valueArtifact('approval', { promoted: 0, unchanged: 0 })] }
  const approval = await depscore('built:approve', phaseTitle('correct'), `arch-approve --arch-files ${shq(toApprove.join(','))} --reviewed-files ${shq(listed(conformance.reviewedFiles).join(','))} --arch-root ${shq(ARC42)}`)
  const n = approval && approval.summary ? approval.summary : null
  const notSet = approval && !approval.error ? [...listed(approval.unreviewed), ...(approval.refused || []).map((x) => x.path), ...(approval.failed || []).map((x) => x.path)] : []
  if (!n || approval.error || notSet.length) {
    const why = !n || approval.error
      ? `depscore.py arch-approve did not run: ${(approval && approval.error) || 'no result'}`
      : `depscore.py arch-approve did not set these corrected files to effective: ${notSet.join(', ')}`
    return failed(phaseTitle('correct'), 'approve', why)
  }
  log(`Approval: ${n.promoted || 0} file(s) set to effective, ${n.unchanged || 0} already effective`)
  return { artifacts: [valueArtifact('approval', { promoted: n.promoted || 0, unchanged: n.unchanged || 0 })] }
}

// ---------------------------------------------------------------- Remove
async function stepRemove(step) {
  enterPhase('remove')
  const builtFiles = listed(J.latest('builtFiles', step))
  const update = J.latest('architectureUpdate', step) || {}
  const conformance = J.latest('conformance', step) || {}
  const reviewerMatched = new Set(listed(conformance.matchedBuiltViews))
  const matched = new Set(listed(update.matched).filter((f) => reviewerMatched.has(f)))
  const unmatched = builtFiles.filter((f) => !matched.has(f))
  const removable = builtFiles.filter((f) => matched.has(f))
  if (removable.length) {
    const message = `docs(architecture): remove the ${subject} built views the effective version now matches`
    const removal = await depscore('built:remove', phaseTitle('remove'), `arch-built-remove --arch-root ${shq(archPath)} --files ${shq(removable.join(','))} --message ${shq(message)}`)
    if (!removal || removal.error) {
      return failed(phaseTitle('remove'), 'remove', `depscore.py arch-built-remove did not remove the matched built views: ${(removal && removal.error) || 'no result'}`)
    }
  }
  if (unmatched.length) {
    return failed(null, 'correct', `the effective version does not yet match these built views, which stay in ${BUILT_DIR}: ${unmatched.join(', ')}`)
  }
  return { artifacts: [valueArtifact('removedBuiltViews', removable)] }
}

const STEPS = {
  'deploy:built-snapshot': stepSnapshot,
  'deploy:built-compare': stepCompare,
  'deploy:built-correct': stepCorrect,
  'deploy:built-review': stepReview,
  'deploy:built-approve': stepApprove,
  'deploy:built-remove': stepRemove,
}
const stepTable = Object.fromEntries(Object.entries(STEPS).map(([kind, perform]) => [kind, async (step) => {
  current = step
  return perform(step)
}]))

enterPhase('compare')
const journalRef = builtArgs.journal
const read = await stepJournal.read(run, { runner: `${pluginRoot}/scripts/portfolio/relayrun.py`, pluginRoot, path: journalRef.path, relayFile: `${SNAP_DIR}/relay/journal/read-${journalRef.run.replace(/[^A-Za-z0-9._-]+/g, '-')}.json`, phase: phaseTitle('compare') })
if (read.error) return handback(false, read.noResult ? DISPATCH_FAILED_STAGE : 'journal', `Story ${beadId}: the step journal ${journalRef.path} could not be read: ${read.error}`)
J = stepJournal.open({ journal: read.journal, run: journalRef.run, runner: COMPOSITE, under: journalRef.step })
if (J.parent().kind !== PARENT_KIND) return handback(false, 'input', `Story ${beadId}: the step ${journalRef.step} is a ${J.parent().kind || 'step with no kind'}, not a ${PARENT_KIND} step`)
if (!J.parent().steps.length) J.planUnder(J.innerPlan(PARENT_KIND))

const ran = await J.run(stepTable)
const differences = J.latest('differences', null, []) || []
const builtFiles = J.latest('builtFiles', null, []) || []
const results = {
  differences,
  builtFiles,
  architectureUpdate: J.latest('architectureUpdate', null),
  conformance: J.latest('conformance', null),
  approval: J.latest('approval', null),
  removal: J.latest('removedBuiltViews', null),
}
if (!ran.ok) {
  const { stage, message, ...more } = ran.fail
  return handback(false, stage, message, { ...results, ...more, step: ran.step.key })
}
if (!differences.length && !builtFiles.length) {
  return handback(true, 'matches', `Story ${beadId}: the build matches the effective version; no built view was written`, { differences: [], builtFiles: [] })
}
return handback(true, 'recorded', `Story ${beadId}: ${differences.length} difference(s) from the effective version recorded, the effective version corrected to match (${touched(results.architectureUpdate || {}).length} file(s) set to effective), and the built views removed`, results)
