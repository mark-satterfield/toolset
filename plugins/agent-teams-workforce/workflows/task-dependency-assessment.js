export const meta = {
  name: 'task-dependency-assessment',
  description:
    "Assesses the build dependencies of ONE Task created outside elaboration and writes its `blocks` edges. The workflow writes the Task's context: the matrix ids the Task states, and for each stack they name the open Tasks that name it or an entry it holds (atw-matrix work --id), what it depends on and what depends on it (atw-matrix deps --of and --on), with the edges standing on the Task in the tracker. One task-dependency-mapper session reads the related Tasks, proposes the edges and checks its proposal; the workflow validates the proposal and runs apply-edges, and writes the stack and entry ids into a Task that states none (its matrix_elements key); it writes nothing into the matrix, and the beads edge alone carries build order. When the edges are applied it triggers wsjf-scoring. With `apply: false` apply-edges runs as a dry run, nothing else is written and no scoring runs.",
  whenToUse: 'A Task was created or changed outside elaboration and needs its build dependencies assessed.',
  phases: [
    { title: 'Assess', detail: 'the workflow writes the context; one task-dependency-mapper session proposes and validates the edges; the workflow runs apply-edges and writes the matrix ids of a Task that states none' },
    { title: 'Score', detail: 'wsjf-scoring over the new edges' },
  ],
}
// ===== SHARED BLOCK fable — BEGIN (canonical: scripts/shared-blocks/fable.js; filled from skills/pipeline-contracts/schemas/driver-surface.schema.json; edit there, then: node scripts/shared-blocks.mjs --write) =====
const ownedCoreContracts = "---\nname: subagent-contract\ndescription: Bounded specialist work in direct sessions, with file outputs and independent validation.\nuser-invocable: false\n---\n\n# Direct specialist session\n\nPerform the role in your definition. The brief gives a bead, the journal step id, the request,\ninput paths and an output path. It names only the inputs this step needs. The skills your\ndefinition lists are in your context; read the applicable contract before writing. The artifact-handoff skill is the shared producer/reviewer authority.\nWrite the result file; Python validates it, records it in the step journal and keeps pipeline state.\nStart another agent only when your definition has a `startsRoles` list, and only agents with\nthose roles, each by the name Claude Code knows it by: the plain name (`trd-author`) for an agent\nwhose definition lists `mcpServers`, which runs from its user-level copy, and\n`agent-teams-workforce:<name>` for every other (`agent-teams-workforce:uml-diagram-author`). An agent that was started by another agent starts no one. Never invoke a Workflow\nor a command runner. When the brief carries ARTIFACT CONTRACT DATA, write the progress\nfile it names and record a checkpoint or the submission only by running the artifactcontract.py\ncommands it gives; never write a checkpoint sidecar any other way. The progress file's fields are\ndefined by the artifact-handoff skill (schemas/checkpoint.schema.json, $defs/Progress). If resumed,\ninspect and continue the existing result and input files; retain completed valid work.\n\nOnly assigned files are writable. Reviewers may write their result, never the reviewed source.\nNever write arc42 section 2, expose secrets or touch apps/marketing repositories. Never run keeper\nor supervisor. Agents do not write pipeline beads; Python owns those writes. If reading beads is\nneeded, use the central atw-bd wrapper from beads-contract. No agent creates a bug or loose Task.\nRead repository AGENTS.md before an authorized repository edit; input-only reads do not require\nloading every repository's instruction tree.\n\nMissing inputs are named dependencies, not permission to invent facts. Distinguish observed\nfacts, assumptions and unresolved questions in the artifact's supported fields. Do not mark your\nown work approved.\n\nThe matrix has one code mark, `verified`, recorded with the commit on a stack, on the entries\nin it and on the relationships the code makes real. The build driver sets it when a Story's\ncode has been built and tested and has passed, including its CI/CD and its CDK. No agent sets\nit. No deployed mark and no merged mark exists, and absent means not verified. Verified means\nreal: the entry or relationship exists, and its code is trusted and is expected to match the\narchitecture. Not verified means it still has to be made real: use it like any other, and\nassume it may still have to be built. Existing code for it is a hint of how something was once\nsolved and may be stale, and a difference between that code and arc42 is never a discrepancy\nand never a finding.\n\n## Helpers and the journal\n\nAn agent that starts other agents inside its own session and then continues follows one pattern,\nwith `atw-step-journal` and the journal file its brief names:\n\n1. Write your own output first: the file your definition names as your first output.\n2. When you start your first agent, add it as a child step of your own step\n   (`atw-step-journal add --parent <your step> --agent <agent> --description \"<what it does>\"\n   --purpose \"<why>\"`, where `<agent>` is the agent's own name, the `name` its definition states,\n   such as `trd-author`; the command refuses a name no agent definition has), and add one last child step whose description is \"Finish\", with yourself\n   as the agent and your own step in its `inputs`. `--steps-json` adds several child steps in one\n   write.\n3. Add each further agent as a child before \"Finish\" (`--after <sibling id>`). Mark each child\n   running when you start it (`atw-step-journal start --step <id>`), and record the request file\n   you wrote for it at once (`atw-step-journal artifact --step <id> --name request --kind file\n   --path <path>`). When the agent returns, record the file it returned as the artifact `answer`\n   and mark the child done (`atw-step-journal done --step <id>`).\n4. When your work is complete, record your result as the artifact of \"Finish\", under the name\n   your definition gives it, and mark \"Finish\" done. Your own step is then done.\n5. After an interruption the script launches the first child that is not done: an agent left\n   running is launched from the `request` file its step holds, and \"Finish\" is launched as you.\n   Launched for \"Finish\", read your own output, the `answer` files and your partial result, and\n   continue.\n\nThe names are fixed, because the script reads them: `request` (or `question`, for a question file\nto `architecture-question.schema.json`) for what an agent is asked, `answer` for what a specialist\nreturned, `ruling` for a decider's ruling, `review` for a review. A step is handed the artifacts\nof the steps its `inputs` name, and of the steps below them.\n\nAn agent that adds steps for the script to run, and starts no agent itself, records the file a\nstep needs on its own step under the same names and names its own step in that step's `inputs`.\n\nAn agent that starts no other agent adds no step.\n\n## Resource use and incremental review\n\n- Use tokens conscientiously without compromising required correctness, completeness, safety or evidence. Before a material optional expansion, identify its unresolved need and expected benefit in existing progress. Routine tools need no justification. Do not add a report, review pass, token quota or human approval gate for this rule; omit optional work with no concrete benefit.\n- Makers and reviewers use the same applicable requirements, constraints and completion criteria. Review determines actual correctness, including passing sound work; finding more failures is not success. Do not invent requirements or turn stylistic preferences into blocking defects. Preserve necessary safety and regression checks.\n- Use the caller's finding format to identify the affected location, requirement/dependency at risk, observed evidence and actionable correction with a verifiable pass condition. Distinguish defects, missing evidence and proposed new requirements. Never claim unperformed checks passed.\n- Revise original artifacts incrementally. Retain valid work and applicable evidence. Rereview changed scope and affected dependencies; reopen accepted work only when new evidence or demonstrated impact invalidates its earlier evidence, and state why. Preserve required independent review.\n\n## Technical gaps are decided, not escalated\n\nWhere the approved or effective architecture, a requirement or an owner answer is silent, unclear or self-contradictory on a technical matter, decide it by best practice, with AWS Well-Architected guidance and AWS documentation as the evidence (see AWS evidence authority below). Record the decision, the gap it closes and its cited evidence in your result, and continue. A technical matter is any question of how the system works: services, patterns, interfaces, data, values and limits, security and privacy controls, cost and operations. A recorded decision is a claim reviewers check like any other; it is not an open item. No agent ends with \"these two documents disagree\". Where one statement is in an effective document and the other is not, the effective one stands without discussion. Otherwise the agent responsible for the work settles it and records the settlement in the matrix.\n\nOwner-only facts (credentials, money and destructive actions outside AWS dev), irreconcilable business requirements and section 2 conflicts go through the caller's owner channel. Technical choices remain with the specialists. Never put a technical question to the owner or any person, and never hold work waiting for a technical answer.\n\n## The approved architecture is authoritative\n\nThe approved (effective) architecture and the owner's answers are authoritative. Older documents, repository READMEs and existing code are evidence of the current state: they show what exists and what still has to change, never that the approved architecture or an owner answer is wrong. Where they disagree with the approved architecture, the approved architecture holds and the difference is work to plan, not a conflict to raise. The approved architecture changes only through the solutions architect's decisions, written by the maintainer and reviewed, or a reviewed correction from what a Story built.\n\n## AWS evidence authority\n\nBefore any AWS claim, design choice or question, check the AWS MCP Server documentation tools (`search_documentation`, `read_documentation`, `retrieve_skill`) and the relevant AWS plugin skills (`aws-core:*`, for example `aws-core:aws-cdk`, `aws-core:aws-serverless`, `aws-core:aws-iam`, `aws-core:aws-networking`, `aws-core:aws-well-architected-review`), including the applicable Well-Architected principles. A question AWS documentation can answer is answered from it and never reaches the owner. Retain source references and the concrete tradeoffs. Existing generated architecture and model recollection do not establish correctness. Makers and reviewers use this same evidence criterion.\n\nApply guidance to stated requirements, deployment, usage and cost constraints rather than hypothetical scale. Where AWS guidance conflicts with a business requirement or a section 2 constraint, the requirement or constraint holds: record the conflict and the design that honours it, and do not silently substitute a preferred AWS pattern. Missing required MCP/skill access is a named blocker or uncertainty, never a passed check. Coordinators may research and route AWS questions, but cannot author or approve designs.\n"
const ownedArtifactContract = "---\nname: artifact-handoff\ndescription: Shared file contracts for direct specialist sessions; producers and consumers read the same schemas and completion rules.\n---\n\n# Direct artifact handoff\n\nRead [Epic contracts](epic-contracts.md) for the artifact assigned to this session, including its\nfields, interpretation and completion criteria. JSON schemas are in [schemas/](schemas/).\nProducers and reviewers use this same contract; a reviewer cannot add unstated requirements.\n\nThe brief contains only a bead id, labeled absolute input paths, an absolute output path, and a\none-line outcome. Read the named files yourself. Write the complete result to the exact output\npath. Write only assigned outputs.\nFor a JSON output write one strict JSON value with unique keys; for a document write nonempty\nUTF-8 Markdown. Do not paste file contents into a response. A final reply may name the result path.\n\nPython validates the file against the schema, checks declared document citations and records the\nfile in the step journal. The agent does not accept its own result, compute revision bindings,\nsubmit StructuredOutput, or run artifact checkpoint or\nsubmission helpers. There is no machine mode or command-runner handoff in direct sessions.\nA structurally valid artifact is not automatically a semantically correct one.\n\nOn a corrective pass, read the labeled validation-errors input and the existing output, repair the\nspecific findings and affected references, and preserve valid work. On interruption retain the\nactual files; resumption continues those files. Do not fabricate completion for missing reasoning.\nNamed missing inputs or remaining uncertainties belong in the contract's existing evidence fields;\nnever add fields to a closed schema or return a success reference for absent work.\n\n## Generated contract types\n\nEach schema in [schemas/](schemas/) is the one definition of its contract. Python code never\nrestates a key, type or allowed value: it imports the module that\n`scripts/generate_contract_types.py` generates from the schema, and\n`scripts/check_contract_types.py` fails when a generated module is stale. Run\n`python3 scripts/generate_contract_types.py` after changing a schema.\n\n| Schema | Generated module |\n|---|---|\n| `schemas/task-deps.schema.json` (Cross-Story Task dependencies) | `scripts/task_deps_contract.py` |\n"
const ownedBaselineContract = "---\nname: architecture-baseline\ndescription: The one set of criteria that the solutions architect works to and the reviewers review against, with the level of each.\n---\n\n# Architecture criteria\n\nRead [the review standard](review-standard.md) before designing, writing, reviewing or\nruling on architecture, a TRD or a spec. It is the common basis: the solutions architect\ndevelops the architecture and the TRD to exactly these criteria, the spec authors develop the\nspecs to them, and reviewers apply exactly these and no others. `review-criteria.json` beside\nit holds the same criteria as data: each criterion's id, level, home document and text, the\nagents responsible for each level with its review point, and for each reviewer group its\nreviewer, the criteria it covers and the rule that selects it. The standard is written from\nthat file by `artifact-handoff/scripts/review_criteria.py`, so a criterion is changed in\n`review-criteria.json` and nowhere else.\n\nEvery criterion has a level: architecture (arc42), technical requirement (the TRD) or\nimplementation (the specs and Tasks). A criterion is satisfied by the document that is its\nhome. Nobody asks a document for detail below its level.\n\nAn effective document is approved design. It is not evidence that anything is built, and it\nis not a permanent constraint on a later PRD.\n\nThe matrix records what is approved and what code is trusted. Read it through `atw-matrix`.\n\n## The files the team hands on\n\nEach file an agent of the architecture team writes has one schema, in\n`${CLAUDE_PLUGIN_ROOT}/skills/artifact-handoff/schemas/`. A definition names its files by\nschema file name, for example `architecture-result.schema.json`; read the schema there before\nwriting the file. Every shape is defined once, in `architecture-result.schema.json`, and the\nother schema files refer to it.\n"
const ownedAgentContracts = {"acceptance-criteria-reviewer":{"artifactCapable":false,"agentType":"agent-teams-workforce:acceptance-criteria-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"acceptance-criteria-writer":{"artifactCapable":true,"agentType":"acceptance-criteria-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:artifact-handoff"]},"accessibility-validator":{"artifactCapable":true,"agentType":"agent-teams-workforce:accessibility-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:a11y-audit","agent-teams-workforce:senior-frontend"]},"advantage-evaluator":{"artifactCapable":false,"agentType":"agent-teams-workforce:advantage-evaluator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"adversarial-critique-adjudicator":{"artifactCapable":false,"agentType":"agent-teams-workforce:adversarial-critique-adjudicator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-security"]},"adversarial-review-loop-supervisor":{"artifactCapable":false,"agentType":"agent-teams-workforce:adversarial-review-loop-supervisor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"ambiguity-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:ambiguity-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"android-compose-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:android-compose-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:graphrag-lookup"]},"api-contract-designer":{"artifactCapable":true,"agentType":"api-contract-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:api-design-reviewer","agent-teams-workforce:architecture-baseline"]},"api-documentation-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:api-documentation-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer"]},"api-gateway-cdk-implementer":{"artifactCapable":true,"agentType":"api-gateway-cdk-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-gateway","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"api-specification-author":{"artifactCapable":true,"agentType":"api-specification-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer","agent-teams-workforce:artifact-handoff","agent-teams-workforce:skillspoke-events","agent-teams-workforce:architecture-baseline"]},"appsync-cdk-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:appsync-cdk-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"appsync-client-subscription-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:appsync-client-subscription-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend","agent-teams-workforce:graphrag-lookup"]},"architecture-boundary-guardian":{"artifactCapable":true,"agentType":"architecture-boundary-guardian","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:architecture-baseline"]},"architecture-conformance-reviewer":{"artifactCapable":true,"agentType":"architecture-conformance-reviewer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:arc42","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:architecture-baseline"]},"architecture-decider":{"artifactCapable":true,"agentType":"architecture-decider","skills":["agent-teams-workforce:architecture-baseline","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect"]},"architecture-diagram-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:architecture-diagram-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:architecture-diagramming","agent-teams-workforce:c4-diagramming","agent-teams-workforce:uml-diagramming","agent-teams-workforce:architecture-baseline"]},"architecture-fitness-function-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:architecture-fitness-function-author","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"architecture-impact-analyst":{"artifactCapable":false,"agentType":"agent-teams-workforce:architecture-impact-analyst","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:beads-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:graphrag-lookup"]},"architecture-maintainer":{"artifactCapable":true,"agentType":"agent-teams-workforce:architecture-maintainer","skills":["agent-teams-workforce:architecture-baseline","agent-teams-workforce:subagent-contract","agent-teams-workforce:arc42-maintain","agent-teams-workforce:c4-diagramming","agent-teams-workforce:uml-diagramming"]},"architecture-pattern-challenger":{"artifactCapable":true,"agentType":"architecture-pattern-challenger","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:architecture-baseline"]},"architecture-team-lead":{"artifactCapable":true,"agentType":"agent-teams-workforce:architecture-team-lead","skills":["agent-teams-workforce:architecture-baseline","agent-teams-workforce:subagent-contract"]},"architecture-tradeoff-skeptic":{"artifactCapable":true,"agentType":"architecture-tradeoff-skeptic","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:architecture-baseline"]},"athena-redshift-analytics-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:athena-redshift-analytics-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:graphrag-lookup"]},"auth-bypass-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:auth-bypass-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops","agent-teams-workforce:cognito"]},"aws-integration-test-runner":{"artifactCapable":true,"agentType":"agent-teams-workforce:aws-integration-test-runner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:test-failure-mindset","agent-teams-workforce:cumulative-regression"]},"aws-integration-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:aws-integration-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:cumulative-regression"]},"aws-solutions-architect":{"artifactCapable":true,"agentType":"aws-solutions-architect","skills":["agent-teams-workforce:architecture-baseline","agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:senior-security","agent-teams-workforce:graphrag-lookup"]},"beads-format-validator":{"artifactCapable":true,"agentType":"agent-teams-workforce:beads-format-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:beads-contract"]},"bedrock-integration-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:bedrock-integration-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:bedrock","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:senior-prompt-engineer","agent-teams-workforce:aws-agentic-ai","agent-teams-workforce:graphrag-lookup"]},"behavioral-signals-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:behavioral-signals-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:senior-data-scientist","agent-teams-workforce:product-analytics","agent-teams-workforce:graphrag-lookup"]},"bounded-context-mapper":{"artifactCapable":true,"agentType":"bounded-context-mapper","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:architecture-baseline"]},"brd-traceability-auditor":{"artifactCapable":true,"agentType":"agent-teams-workforce:brd-traceability-auditor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"built-architecture-comparer":{"artifactCapable":true,"agentType":"agent-teams-workforce:built-architecture-comparer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:architecture-baseline"]},"c4-diagram-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:c4-diagram-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:architecture-diagramming","agent-teams-workforce:c4-diagramming","agent-teams-workforce:architecture-baseline"]},"cdk-infrastructure-designer":{"artifactCapable":true,"agentType":"cdk-infrastructure-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:resource-naming","agent-teams-workforce:architecture-baseline"]},"cdk-infrastructure-drift-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:cdk-infrastructure-drift-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:cloudformation"]},"cdk-stack-author":{"artifactCapable":true,"agentType":"cdk-stack-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:cloudformation","agent-teams-workforce:resource-naming"]},"cds-finding-reviewer":{"artifactCapable":false,"agentType":"agent-teams-workforce:cds-finding-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","cds:apply-design-system","cds:audit-against-system"]},"cds-ui-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:cds-ui-implementer","skills":["agent-teams-workforce:subagent-contract","cds:apply-design-system","cds:audit-against-system","cds:compose-page","agent-teams-workforce:graphrag-lookup"]},"changelog-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:changelog-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:changelog-generator"]},"chassis-extension-implementer":{"artifactCapable":true,"agentType":"chassis-extension-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:lambda","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming","agent-teams-workforce:skillspoke-events"]},"code-correctness-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:code-correctness-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:code-reviewer"]},"code-quality-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:code-quality-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"code-refactoring-specialist":{"artifactCapable":true,"agentType":"agent-teams-workforce:code-refactoring-specialist","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:code-reviewer","agent-teams-workforce:graphrag-lookup"]},"code-style-and-linting-enforcer":{"artifactCapable":true,"agentType":"agent-teams-workforce:code-style-and-linting-enforcer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:code-reviewer"]},"cognito-lambda-trigger-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:cognito-lambda-trigger-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:cognito","agent-teams-workforce:lambda","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"completeness-checker":{"artifactCapable":false,"agentType":"agent-teams-workforce:completeness-checker","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"complexity-analyzer":{"artifactCapable":false,"agentType":"agent-teams-workforce:complexity-analyzer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:tech-debt-tracker"]},"constitutional-agent":{"artifactCapable":false,"agentType":"agent-teams-workforce:constitutional-agent","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"constraint-extractor":{"artifactCapable":true,"agentType":"agent-teams-workforce:constraint-extractor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"consumer-driven-contract-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:consumer-driven-contract-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-test-suite-builder","agent-teams-workforce:cumulative-regression"]},"context-curator":{"artifactCapable":false,"agentType":"agent-teams-workforce:context-curator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"contract-violation-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:contract-violation-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-test-suite-builder"]},"cost-architecture-reviewer":{"artifactCapable":true,"agentType":"cost-architecture-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-cost-operations","agent-teams-workforce:architecture-baseline"]},"cost-impact-reviewer":{"artifactCapable":true,"agentType":"cost-impact-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-cost-operations","agent-teams-workforce:architecture-baseline"]},"cross-repo-integration-test-coordinator":{"artifactCapable":false,"agentType":"agent-teams-workforce:cross-repo-integration-test-coordinator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"cross-service-contract-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:cross-service-contract-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-test-suite-builder"]},"data-consistency-checker":{"artifactCapable":true,"agentType":"agent-teams-workforce:data-consistency-checker","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb"]},"data-exposure-scanner":{"artifactCapable":true,"agentType":"agent-teams-workforce:data-exposure-scanner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"data-model-specification-author":{"artifactCapable":true,"agentType":"data-model-specification-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb","agent-teams-workforce:database-schema-designer","agent-teams-workforce:artifact-handoff","agent-teams-workforce:architecture-baseline"]},"data-pipeline-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:data-pipeline-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:cumulative-regression"]},"definition-of-done-enforcer":{"artifactCapable":true,"agentType":"agent-teams-workforce:definition-of-done-enforcer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"dependency-change-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:dependency-change-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dependency-auditor"]},"dependency-cve-auditor":{"artifactCapable":true,"agentType":"agent-teams-workforce:dependency-cve-auditor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dependency-auditor"]},"dependency-graph-extractor":{"artifactCapable":true,"agentType":"agent-teams-workforce:dependency-graph-extractor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"deployment-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:deployment-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"deployment-strategy-decider":{"artifactCapable":false,"agentType":"agent-teams-workforce:deployment-strategy-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:cove-prompt-design"]},"documentation-accuracy-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:documentation-accuracy-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"documentation-currency-auditor":{"artifactCapable":true,"agentType":"agent-teams-workforce:documentation-currency-auditor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"documentation-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:documentation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"domain-boundary-validator":{"artifactCapable":true,"agentType":"agent-teams-workforce:domain-boundary-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"domain-event-modeler":{"artifactCapable":true,"agentType":"domain-event-modeler","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:architecture-baseline","agent-teams-workforce:skillspoke-events"]},"dos-resilience-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:dos-resilience-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"dynamodb-access-layer-implementer":{"artifactCapable":true,"agentType":"dynamodb-access-layer-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"dynamodb-cost-optimizer":{"artifactCapable":true,"agentType":"dynamodb-cost-optimizer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb","agent-teams-workforce:aws-cost-operations"]},"dynamodb-schema-access-pattern-reviewer":{"artifactCapable":true,"agentType":"dynamodb-schema-access-pattern-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb"]},"dynamodb-streams-cdc-implementer":{"artifactCapable":true,"agentType":"dynamodb-streams-cdc-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:dynamodb","agent-teams-workforce:graphrag-lookup"]},"email-notification-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:email-notification-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:email-template-builder","agent-teams-workforce:sns","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:skillspoke-events"]},"epic-sequencer":{"artifactCapable":true,"agentType":"agent-teams-workforce:epic-sequencer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:epic-sequencing"]},"espresso-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:espresso-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:tdd-guide","agent-teams-workforce:cumulative-regression"]},"event-api-client-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:event-api-client-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming","agent-teams-workforce:skillspoke-events"]},"event-driven-consumer-implementer":{"artifactCapable":true,"agentType":"event-driven-consumer-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:sqs","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:sns","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming","agent-teams-workforce:skillspoke-events"]},"event-flow-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:event-flow-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda"]},"event-schema-designer":{"artifactCapable":true,"agentType":"event-schema-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:eventbridge","agent-teams-workforce:architecture-baseline","agent-teams-workforce:skillspoke-events"]},"event-schema-reviewer":{"artifactCapable":true,"agentType":"event-schema-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:skillspoke-events"]},"failure-mode-analyst":{"artifactCapable":true,"agentType":"failure-mode-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:observability-designer","agent-teams-workforce:architecture-baseline"]},"filing-clerk":{"artifactCapable":true,"agentType":"filing-clerk","skills":["agent-teams-workforce:subagent-contract","obsidian:obsidian-cli","obsidian:obsidian-markdown","agent-teams-workforce:arc42","notebooklm","document-classification"]},"finops-analyst":{"artifactCapable":false,"agentType":"finops-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-cost-operations"]},"flaky-test-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:flaky-test-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:test-failure-mindset","agent-teams-workforce:find-cause"]},"frontend-performance-optimizer":{"artifactCapable":true,"agentType":"agent-teams-workforce:frontend-performance-optimizer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend"]},"github-actions-pipeline-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:github-actions-pipeline-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"glue-etl-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:glue-etl-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:graphrag-lookup"]},"graphql-schema-designer":{"artifactCapable":true,"agentType":"graphql-schema-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:api-design-reviewer","agent-teams-workforce:architecture-baseline"]},"graphql-schema-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:graphql-schema-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer"]},"implementation-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:implementation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:graphrag-lookup"]},"incident-response-runbook-designer":{"artifactCapable":true,"agentType":"agent-teams-workforce:incident-response-runbook-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:observability-designer"]},"infrastructure-security-scanner":{"artifactCapable":true,"agentType":"infrastructure-security-scanner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops","agent-teams-workforce:aws-cdk-development"]},"injection-attack-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:injection-attack-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"integration-pattern-architect":{"artifactCapable":true,"agentType":"integration-pattern-architect","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:architecture-baseline"]},"integration-testing-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:integration-testing-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"ios-swiftui-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:ios-swiftui-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:graphrag-lookup"]},"kinesis-stream-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:kinesis-stream-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"lambda-performance-optimizer":{"artifactCapable":true,"agentType":"lambda-performance-optimizer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:lambda"]},"llm-observability-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:llm-observability-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:observability-designer","agent-teams-workforce:senior-prompt-engineer","agent-teams-workforce:aws-agentic-ai","agent-teams-workforce:graphrag-lookup"]},"matching-algorithm-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:matching-algorithm-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:graphrag-lookup"]},"mcp-server-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:mcp-server-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:mcp-server-builder","agent-teams-workforce:aws-agentic-ai","agent-teams-workforce:aws-mcp-setup","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"ml-evaluation-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:ml-evaluation-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:senior-data-scientist","agent-teams-workforce:cumulative-regression"]},"mobile-e2e-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:mobile-e2e-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"nextjs-component-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:nextjs-component-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend","agent-teams-workforce:a11y-audit","agent-teams-workforce:senior-fullstack","agent-teams-workforce:graphrag-lookup"]},"nfr-analyst":{"artifactCapable":false,"agentType":"agent-teams-workforce:nfr-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:product-discovery"]},"okr-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:okr-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-strategist","agent-teams-workforce:product-analytics"]},"openapi-contract-reviewer":{"artifactCapable":false,"agentType":"openapi-contract-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer","agent-teams-workforce:skillspoke-events","agent-teams-workforce:artifact-handoff","agent-teams-workforce:architecture-baseline"]},"operational-readiness-reviewer":{"artifactCapable":true,"agentType":"operational-readiness-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:observability-designer","agent-teams-workforce:architecture-baseline"]},"payments-integration-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:payments-integration-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:stripe-integration-expert","agent-teams-workforce:secrets-manager","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:skillspoke-events"]},"performance-benchmark-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:performance-benchmark-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"permission-escalation-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:permission-escalation-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops","agent-teams-workforce:iam"]},"persistence-architecture-specialist":{"artifactCapable":true,"agentType":"persistence-architecture-specialist","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:dynamodb","agent-teams-workforce:database-schema-designer","agent-teams-workforce:architecture-baseline"]},"persona-profile-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:persona-profile-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:product-analytics"]},"phase-gate-enforcer":{"artifactCapable":false,"agentType":"agent-teams-workforce:phase-gate-enforcer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:cumulative-regression"]},"playwright-e2e-web-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:playwright-e2e-web-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:a11y-audit","agent-teams-workforce:cumulative-regression"]},"polyrepo-steward":{"artifactCapable":true,"agentType":"agent-teams-workforce:polyrepo-steward","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:polyrepo-repo","agent-teams-workforce:polyrepo-info","agent-teams-workforce:polyrepo-governance","agent-teams-workforce:polyrepo-beads"]},"power-tools-configuration-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:power-tools-configuration-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:lambda","agent-teams-workforce:secrets-manager","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"prd-alignment-verifier":{"artifactCapable":true,"agentType":"agent-teams-workforce:prd-alignment-verifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"prd-creation-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:prd-creation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"prd-trd-traceability-verifier":{"artifactCapable":true,"agentType":"agent-teams-workforce:prd-trd-traceability-verifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"prd-validation-analyst":{"artifactCapable":true,"agentType":"agent-teams-workforce:prd-validation-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"prd-validation-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:prd-validation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"prd-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:prd-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"production-readiness-review-facilitator":{"artifactCapable":false,"agentType":"agent-teams-workforce:production-readiness-review-facilitator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"race-condition-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:race-condition-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"react-native-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:react-native-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend","agent-teams-workforce:graphrag-lookup"]},"readme-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:readme-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"recommendation-engine-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:recommendation-engine-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:graphrag-lookup"]},"regression-coverage-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:regression-coverage-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:artifact-handoff","agent-teams-workforce:cumulative-regression"]},"regression-impact-assessor":{"artifactCapable":true,"agentType":"agent-teams-workforce:regression-impact-assessor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:artifact-handoff","agent-teams-workforce:cumulative-regression"]},"requirements-clarifier":{"artifactCapable":false,"agentType":"agent-teams-workforce:requirements-clarifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:product-discovery"]},"requirements-conflict-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:requirements-conflict-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"root-cause-analyst":{"artifactCapable":false,"agentType":"agent-teams-workforce:root-cause-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:find-cause","agent-teams-workforce:test-failure-mindset","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:artifact-handoff"]},"s3-data-lake-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:s3-data-lake-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:s3","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"sdlc-pipeline-orchestrator":{"artifactCapable":false,"agentType":"agent-teams-workforce:sdlc-pipeline-orchestrator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:beads-contract"]},"security-architecture-designer":{"artifactCapable":true,"agentType":"security-architecture-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-security","agent-teams-workforce:iam","agent-teams-workforce:secrets-manager","agent-teams-workforce:architecture-baseline"]},"security-test-case-designer":{"artifactCapable":true,"agentType":"agent-teams-workforce:security-test-case-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-security","agent-teams-workforce:cumulative-regression"]},"shared-capability-reviewer":{"artifactCapable":false,"agentType":"agent-teams-workforce:shared-capability-reviewer","skills":[]},"slo-error-budget-designer":{"artifactCapable":false,"agentType":"slo-error-budget-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:observability-designer","agent-teams-workforce:cloudwatch"]},"smoke-test-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:smoke-test-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"spec-authoring-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:spec-authoring-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"spec-currency-validator":{"artifactCapable":true,"agentType":"agent-teams-workforce:spec-currency-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"spec-decider":{"artifactCapable":false,"agentType":"spec-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:cove-prompt-design","agent-teams-workforce:artifact-handoff","agent-teams-workforce:architecture-baseline"]},"spec-freshness-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:spec-freshness-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"stakeholder-request-intake-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:stakeholder-request-intake-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"task-decomposer":{"artifactCapable":true,"agentType":"task-decomposer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:beads-contract","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:artifact-handoff","agent-teams-workforce:wsjf"]},"task-dependency-mapper":{"artifactCapable":true,"agentType":"task-dependency-mapper","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:beads-contract","agent-teams-workforce:artifact-handoff"]},"tdd-unit-test-generator":{"artifactCapable":true,"agentType":"agent-teams-workforce:tdd-unit-test-generator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:tdd-guide","agent-teams-workforce:cumulative-regression"]},"test-command-resolver":{"artifactCapable":false,"agentType":"agent-teams-workforce:test-command-resolver","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:test-failure-mindset"]},"test-coverage-gap-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:test-coverage-gap-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"test-design-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:test-design-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"test-environment-orchestrator":{"artifactCapable":true,"agentType":"test-environment-orchestrator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:aws-mcp-setup"]},"test-failure-parser":{"artifactCapable":false,"agentType":"agent-teams-workforce:test-failure-parser","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:test-failure-mindset"]},"test-isolation-specialist":{"artifactCapable":true,"agentType":"agent-teams-workforce:test-isolation-specialist","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:tdd-guide","agent-teams-workforce:test-failure-mindset"]},"test-plan-strategy-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:test-plan-strategy-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"test-strategy-decider":{"artifactCapable":false,"agentType":"agent-teams-workforce:test-strategy-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cove-prompt-design"]},"trd-author":{"artifactCapable":true,"agentType":"trd-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:architecture-baseline"]},"trd-decider":{"artifactCapable":false,"agentType":"agent-teams-workforce:trd-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"trd-validator":{"artifactCapable":false,"agentType":"agent-teams-workforce:trd-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:architecture-baseline"]},"ubiquitous-language-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:ubiquitous-language-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"uml-diagram-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:uml-diagram-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:architecture-diagramming","agent-teams-workforce:uml-diagramming","agent-teams-workforce:architecture-baseline"]},"user-guide-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:user-guide-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:roadmap-communicator"]},"user-story-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:user-story-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:beads-contract"]},"user-story-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:user-story-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"vector-search-embeddings-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:vector-search-embeddings-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:rag-architect","agent-teams-workforce:graphrag-lookup"]},"webauthn-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:webauthn-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend","agent-teams-workforce:cognito","agent-teams-workforce:graphrag-lookup"]},"workflow-command-runner":{"artifactCapable":false,"agentType":"agent-teams-workforce:workflow-command-runner","skills":["artifact-handoff"]},"worktree-independent-verifier":{"artifactCapable":false,"agentType":"agent-teams-workforce:worktree-independent-verifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"wsjf-scorer":{"artifactCapable":true,"agentType":"agent-teams-workforce:wsjf-scorer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-strategist","agent-teams-workforce:wsjf","agent-teams-workforce:beads-contract"]},"wsjf-scoring-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:wsjf-scoring-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-strategist","agent-teams-workforce:wsjf"]},"xcuitest-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:xcuitest-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:tdd-guide","agent-teams-workforce:cumulative-regression"]}}
// skills/pipeline-contracts/schemas/driver-surface.schema.json, inlined by shared-blocks.mjs. DRIVER_SURFACE maps
// each x-constant of $defs.DriverEnvironment to its environment variable name and each x-values entry of
// $defs.RateLimitInfo to its wire value, so no workflow names a driver environment variable or a rate-limit value itself.
const DRIVER_SURFACE_SCHEMA = {"$schema":"https://json-schema.org/draft/2020-12/schema","$id":"agent-teams-workforce/skills/pipeline-contracts/schemas/driver-surface.schema.json","title":"Driver module surface","description":"The one definition of the driver (ops/sdlc-automation in the control repository) surface the plugin orchestrator imports, the ATW_* environment the driver hands every child and orchestrator process, and the Claude CLI rate-limit event the driver's quota readers take. scripts/generate_types.py renders scripts/driver_surface_types.py from this file; scripts/check_generated.py fails when that module is stale.","x-driver":{"dirParts":["ops","sdlc-automation"],"dirDoc":"Path parts of the driver directory under ATW_CONTROL_REPO.","modules":[{"module":"headlessenv","constant":"HEADLESSENV_MODULE","protocol":"HeadlessEnvironment","doc":"Driver headlessenv module surface consumed by session setup.","members":[{"name":"DENIED_TOOLS","kind":"attribute","python":"tuple[str, ...]","doc":"Tools every headless and orchestrator agent session is denied, in order."},{"name":"child_env","kind":"method","params":[["scratch","Path"]],"returns":"dict[str, str]","doc":"Build the subprocess environment: DriverEnvironment over the inherited one."}]},{"module":"fablewall","constant":"FABLEWALL_MODULE","protocol":"FableWall","doc":"Driver fablewall module surface consumed by model fallback.","members":[{"name":"is_refusal","kind":"method","params":[["info","object"]],"returns":"bool","doc":"Return whether a RateLimitInfo is a model-specific refusal."},{"name":"reset_of","kind":"method","params":[["info","object"]],"returns":"float | None","doc":"Return the model-specific reset of a RateLimitInfo, in epoch seconds."}]},{"module":"breaker","constant":"BREAKER_MODULE","protocol":"Breaker","doc":"Driver breaker module surface consumed by quota handling.","members":[{"name":"exhausted_reset","kind":"method","params":[["info","object"]],"returns":"float | None","doc":"Return the latest reset among the exhausted windows, in epoch seconds."}]},{"module":"childproc","constant":"CHILDPROC_MODULE","protocol":"ChildProcess","doc":"Driver childproc module termination policy.","members":[{"name":"TERMINATE_GRACE","kind":"attribute","python":"float","doc":"Seconds a terminated child is given before it is killed."}]}]},"$defs":{"DriverEnvironment":{"description":"The ATW_* and process environment the driver hands child and orchestrator processes.","x-details":"headlessenv.child_env(scratch) returns these keys over the inherited os.environ (atw.environment fills only absent or blank values); the keeper, supervisor and orchestrator dispatch add ATW_STOP_FILE, ATW_EXECUTION_ID and ATW_ORCH_IDLE.","type":"object","x-python":{"typeddict":"DriverEnvironment"},"properties":{"ATW_PROJECT_ROOT":{"type":"string","minLength":1,"description":"Absolute path of the project root.","x-constant":"PROJECT_ROOT_ENV"},"ATW_PRD_EPIC_SYNC":{"type":"string","minLength":1,"description":"Path of the PRD-to-Epic sync script.","x-constant":"PRD_EPIC_SYNC_ENV"},"ATW_PRD_EPIC_VERIFY":{"type":"string","minLength":1,"description":"Path of the PRD-to-Epic verify script.","x-constant":"PRD_EPIC_VERIFY_ENV"},"ATW_CONTROL_REPO":{"type":"string","minLength":1,"description":"Absolute path of the control repository (SKILLSPOKE_CC, else the driver's repository root). The driver modules live under it at DRIVER_DIR_PARTS.","x-constant":"CONTROL_REPO_ENV"},"ATW_ARCH_PATH":{"type":"string","minLength":1,"description":"The architecture root; set only when the driver knows one. Readers use args.archPath first and fall back to it.","x-constant":"ARCH_PATH_ENV"},"ATW_DESIGN_PACKAGES_DIR":{"type":"string","minLength":1,"description":"The owner's cds design packages directory; optional.","x-constant":"DESIGN_PACKAGES_ENV"},"ATW_PRD_DIR":{"type":"string","minLength":1,"description":"The first PRD root; optional.","x-constant":"PRD_DIR_ENV"},"PATH":{"type":"string","minLength":1,"description":"The controller runtime's bin directory first, de-duplicated.","x-constant":"PATH_ENV"},"TMPDIR":{"type":"string","minLength":1,"description":"The dispatch scratch directory.","x-constant":"TMPDIR_ENV","x-group":"SCRATCH_ENV_KEYS"},"TMP":{"type":"string","minLength":1,"description":"The dispatch scratch directory.","x-constant":"TMP_ENV","x-group":"SCRATCH_ENV_KEYS"},"TEMP":{"type":"string","minLength":1,"description":"The dispatch scratch directory.","x-constant":"TEMP_ENV","x-group":"SCRATCH_ENV_KEYS"},"CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS":{"type":"string","const":"0","description":"Disables the Claude CLI print-mode background wait.","x-constant":"BACKGROUND_WAIT_KEY","x-const-mapping":"BACKGROUND_WAIT_ENV"},"ATW_STOP_FILE":{"type":"string","minLength":1,"description":"Path of the stop marker file; absent means no stop marker. A consumer touches the file (mode 0o600) to request a drain, or tests whether it exists. It only requests a stop: how a stop is classified belongs to the handback contract.","x-constant":"STOP_FILE_ENV","x-file-mode":"STOP_FILE_MODE"},"ATW_EXECUTION_ID":{"type":"string","minLength":1,"description":"The driver execution id. Required for an orchestrator dispatch; set for a headless workflow session only when its arguments carry an executionId.","x-constant":"EXECUTION_ID_ENV"},"ATW_ORCH_IDLE":{"type":"string","pattern":"^[0-9]+(\\.[0-9]+)?$","default":"3600","description":"Orchestrator idle limit in seconds: a positive finite float. A non-finite or non-positive value is a ValueError.","x-constant":"ORCH_IDLE_ENV","x-default-constant":"ORCH_IDLE_DEFAULT"}},"required":["ATW_PROJECT_ROOT","ATW_PRD_EPIC_SYNC","ATW_PRD_EPIC_VERIFY","ATW_CONTROL_REPO","PATH","TMPDIR","TMP","TEMP","CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS"],"additionalProperties":{"type":"string"}},"StopFileMode":{"description":"Permission bits a consumer creates the stop marker file with.","type":"integer","const":384,"x-python":{"constant":"STOP_FILE_MODE","type":"int","render":"0o600"}},"DeniedTool":{"description":"A tool every headless and orchestrator agent session is denied. DENIED_TOOLS keeps this order.","type":"string","enum":["WebFetch","WebSearch","Artifact","SendMessage","EndConversation","CronCreate","CronDelete","CronList","mcp__claude_ai_Gmail__send_message","mcp__claude_ai_Gmail__reply","mcp__claude_ai_Gmail__forward","mcp__claude_ai_Gmail__create_draft","mcp__claude_ai_Google_Drive__share_file","mcp__claude_ai_Google_Drive__create_file","mcp__plugin_slack_slack__slack_send_message","mcp__plugin_slack_slack__slack_send_message_draft","mcp__plugin_slack_slack__slack_schedule_message"],"x-python":{"literal":"DeniedTool","tuple":"DENIED_TOOLS"}},"TerminateGrace":{"description":"Seconds a terminated child process is given before it is killed.","type":"number","const":10,"x-python":{"constant":"TERMINATE_GRACE","type":"float"}},"ExhaustedUtilization":{"description":"A usage window whose utilization is at or above this value is exhausted.","type":"number","const":1,"x-python":{"constant":"EXHAUSTED_UTILIZATION","type":"float"}},"RateLimitStatus":{"description":"RateLimitInfo.status; only rejected is acted on.","type":"string","enum":["allowed","allowed_warning","rejected"],"x-python":{"literal":"RateLimitStatus","tuple":"RATE_LIMIT_STATUSES","constants":{"rejected":"REJECTED_STATUS"}}},"UsageWindowName":{"description":"The account-wide usage windows. Any other window name is model-specific.","type":"string","enum":["five_hour","seven_day"],"x-python":{"literal":"UsageWindowName","frozenset":"ACCOUNT_WINDOWS"}},"UsageWindow":{"description":"One usage window of a RateLimitInfo.","type":"object","x-python":{"typeddict":"UsageWindow"},"properties":{"utilization":{"type":"number","description":"Exhausted when at or above EXHAUSTED_UTILIZATION."},"resetsAt":{"type":"number","description":"Reset time in epoch seconds."}},"required":["utilization"]},"RateLimitInfo":{"description":"The rate_limit_info of a rate_limit_event: the info argument of the quota readers.","type":"object","x-python":{"typeddict":"RateLimitInfo"},"properties":{"status":{"$ref":"#/$defs/RateLimitStatus"},"unifiedWindows":{"type":"object","additionalProperties":{"$ref":"#/$defs/UsageWindow"},"description":"Window name -> usage window."},"resetsAt":{"type":"number","description":"Top-level reset time in epoch seconds."},"rateLimitType":{"type":"string","description":"The value with meaning here is MODEL_OVERAGE_TYPE.","x-values":{"MODEL_OVERAGE_TYPE":"seven_day_overage_included"}},"overageDisabledReason":{"type":"string","description":"The value with meaning here is OUT_OF_CREDITS_REASON.","x-values":{"OUT_OF_CREDITS_REASON":"out_of_credits"}}},"required":["status"]},"RateLimitEvent":{"description":"One Claude CLI stream-json rate-limit event.","type":"object","x-python":{"typeddict":"RateLimitEvent"},"properties":{"type":{"type":"string","const":"rate_limit_event","x-value-constant":"RATE_LIMIT_EVENT_TYPE"},"rate_limit_info":{"$ref":"#/$defs/RateLimitInfo","x-key-constant":"RATE_LIMIT_INFO_KEY"}},"required":["type","rate_limit_info"]}}}
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

const dispatchFailures = []
// Returns the recorded dispatch failures of the named phases, or all of them when none is named.
function dispatchDeaths(...phases) {
  const named = phases.filter(Boolean)
  if (!named.length) return dispatchFailures.slice()
  const set = new Set(named)
  return dispatchFailures.filter((f) => set.has(f.phase))
}
function failureCause(err) { return dispatchFailureCause(err) }
async function settleAgent(prompt, opts) {
  if (dispatchInterruption) return null
  const o = opts && typeof opts === 'object' ? opts : {}
  const call = { ...o }
  delete call.retryPolicy
  delete call.schemaName
  delete call.rethrow
  const name = o.label || o.agentType || 'agent'
  const policy = dispatchPolicy(o)
  const mine = []
  let waitedMs = 0
  for (let attempt = 1; ; attempt++) {
    if (dispatchInterruption) return null
    try {
      const out = await fableAgent(prompt, call)
      if (out) {
        for (const entry of mine) { const at = dispatchFailures.indexOf(entry); if (at >= 0) dispatchFailures.splice(at, 1) }
        return out
      }
      dispatchFailures.push({ agentType: o.agentType || null, label: o.label || null, phase: o.phase || null, outcome: 'skipped', cause: 'deterministic', attempt, message: null, note: name + ': returned nothing' })
      log(name + ': returned nothing')
      return null
    } catch (err) {
      const plan = dispatchRetry(err, name, attempt, waitedMs, policy, typeof setTimeout === 'function')
      const message = String((err && err.message) || err)
      const entry = { agentType: o.agentType || null, label: o.label || null, phase: o.phase || null, outcome: 'threw', cause: plan.cause, attempt, message: message.slice(0, 300), note: name + ': ' + message.slice(0, 160) }
      dispatchFailures.push(entry)
      mine.push(entry)
      if (!plan.retry) {
        if (plan.interruption) dispatchInterruption = plan.interruption
        log(name + ': stopped (' + plan.cause + ') — ' + message)
        if (o.rethrow && !plan.interruption) throw err
        return null
      }
      waitedMs += plan.wait
      log(name + ': transient failure; retry ' + (attempt + 1) + '/' + policy.maxAttempts + ' in ' + Math.round(plan.wait / 1000) + 's — ' + message.slice(0, 160))
      await new Promise((resolve) => setTimeout(resolve, plan.wait))
    }
  }
}

// args: {
//   repoPath:     string,   // absolute path of the repository whose `bd` tracker holds the Tasks
//   pluginRoot:   string,   // absolute path of this plugin's root
//   workDir:      string,   // absolute path of a directory for this run's files
//   task:         string,   // the one Task assessed
//   projectRoot?: string,
//   archPath?:    string,
//   score?:       boolean,  // false: do not trigger scoring. Default true.
//   apply?:       boolean,  // false: apply-edges runs as a dry run and nothing else is written. Default true.
// }
// Returns: { ok, stage, beadId, headline, apply, settled, workDir, task, assessment, edges, matrix, scoring,
//            stop, error?, dispatchFailed, dispatchFailures }
// `matrix` is { elements, elementsWritten, failures }: the matrix ids the session named for a Task that
// states none; what became of them (none-named, already-stated, written, refused, or not-written on a dry
// run); and each refused call. Nothing is written into the matrix.
const given = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const PATH_ARGS = ['repoPath', 'pluginRoot', 'workDir']
// The driver surface constant whose environment variable supplies each path arg the caller leaves out.
// Each constant is an x-constant of $defs/DriverEnvironment in
// skills/pipeline-contracts/schemas/driver-surface.schema.json, the one place the variable names live;
// RESOLVE_PY loads the names from that schema. pluginRoot has none of its own: it is the
// agent-teams-workforce install that $CLAUDE_CONFIG_DIR/plugins/installed_plugins.json records.
// workDir has none either: a run without one gets a new directory from mkdtemp.
const ENV_CONSTANT_OF = { repoPath: 'CONTROL_REPO_ENV', archPath: 'ARCH_PATH_ENV', projectRoot: 'PROJECT_ROOT_ENV' }
const OPTIONAL_PATH_ARGS = ['archPath', 'projectRoot']
const isAbsolute = (v) => typeof v === 'string' && v.trim().startsWith('/')
const RESOLVE_PY = `import json, os, tempfile, time
from pathlib import Path
name, wanted, constant_of, given_root = ARGS[0], json.loads(ARGS[1]), json.loads(ARGS[2]), ARGS[3]
out, problems = {}, {}
config = os.environ.get("CLAUDE_CONFIG_DIR", "").strip() or str(Path.home() / ".claude")
reg = Path(config) / "plugins" / "installed_plugins.json"
registry_problem = ""
try:
    plugins = json.loads(reg.read_text(encoding="utf-8")).get("plugins", {})
except (OSError, ValueError) as exc:
    plugins, registry_problem = {}, f"{reg} is unreadable: {exc}"
installs = []
for key, entries in (plugins if isinstance(plugins, dict) else {}).items():
    if key.startswith("agent-teams-workforce@") and isinstance(entries, list):
        installs.extend(e for e in entries if isinstance(e, dict) and isinstance(e.get("installPath"), str))
surface_parts = ("skills", "pipeline-contracts", "schemas", "driver-surface.schema.json")
env_names, surface_problem = {}, ""
for root in ([given_root] if given_root else []) + [e["installPath"] for e in installs]:
    surface = Path(root, *surface_parts)
    if not surface.is_file():
        continue
    try:
        props = json.loads(surface.read_text(encoding="utf-8"))["$defs"]["DriverEnvironment"]["properties"]
        env_names = {spec["x-constant"]: env for env, spec in props.items()}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        surface_problem = f"{surface} is unreadable: {exc}"
    break
else:
    surface_problem = registry_problem or f"{reg} lists no agent-teams-workforce install shipping {'/'.join(surface_parts)}"
env_of = {key: env_names[c] for key, c in constant_of.items() if c in env_names}
out["envOf"] = env_of
def from_env(key):
    var = env_of.get(key, "")
    if not var:
        return surface_problem or f"the driver surface schema names no {constant_of[key]}"
    value = os.environ.get(var, "").strip()
    if not value:
        return f"\${var} is not set"
    if not Path(value).is_absolute() or not Path(value).exists():
        return f"\${var} is {value!r}, which is not an existing absolute path"
    out[key] = os.path.normpath(value)
    return ""
for key in constant_of:
    if key in wanted:
        why = from_env(key)
        if why:
            problems[key] = why
if "pluginRoot" in wanted:
    marker = ("scripts", "portfolio", "depscore.py")
    control_var = env_names.get("CONTROL_REPO_ENV", "")
    control = os.environ.get(control_var, "").strip() if control_var else ""
    control = os.path.normpath(control) if control else ""
    ranked = []
    for e in installs:
        path = e["installPath"]
        if not Path(path, *marker).is_file():
            continue
        if control and e.get("scope") in ("local", "project") and e.get("projectPath") == control:
            ranked.append((0, path))
        elif e.get("scope") == "user":
            ranked.append((1, path))
    if ranked:
        out["pluginRoot"] = os.path.normpath(sorted(ranked)[0][1])
    else:
        problems["pluginRoot"] = registry_problem or (f"{reg} lists no agent-teams-workforce install shipping scripts/portfolio/depscore.py at user scope" + (f" or for \${control_var} ({control})" if control else ""))
if "workDir" in wanted:
    out["workDir"] = os.path.realpath(tempfile.mkdtemp(prefix=f"{name}-"))
out["since"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
out["problems"] = problems
emit(out)`
// Fills each path arg the caller left out, and only from the environment: repoPath, archPath and
// projectRoot from the variables ENV_CONSTANT_OF names (their names loaded from the driver surface
// schema), pluginRoot from the agent-teams-workforce install that
// $CLAUDE_CONFIG_DIR/plugins/installed_plugins.json records (the install for the CONTROL_REPO_ENV
// repository first, else the user-scope one), and workDir from mkdtemp. One runner session reads them,
// dispatched only when an arg is missing. Returns { args, missing, problems, envOf }:
// `missing` names every required arg still without a value, and the caller refuses before dispatching
// any other agent. An optional path arg the environment does not supply stays absent.
async function resolveArgs(given, name, required) {
  const out = { ...given }
  const lacking = [...PATH_ARGS, ...OPTIONAL_PATH_ARGS].filter((k) => !isAbsolute(out[k]))
  const problems = {}
  let envOf = {}
  if (lacking.length) {
    const got = await relayKit.inline(settleAgent, { label: 'resolve-paths', code: RESOLVE_PY, args: [name, JSON.stringify(lacking), JSON.stringify(ENV_CONSTANT_OF), isAbsolute(out.pluginRoot) ? out.pluginRoot.trim() : ''] })
    const found = got.ok ? got.view : {}
    if (!got.ok) problems.resolver = String(got.error || 'the path resolver returned no result').slice(0, 500)
    Object.assign(problems, found.problems && typeof found.problems === 'object' ? found.problems : {})
    envOf = found.envOf && typeof found.envOf === 'object' ? found.envOf : {}
    for (const k of lacking) {
      if (isAbsolute(found[k])) {
        out[k] = found[k].trim()
        log(`${k} was not passed; ${envOf[k] ? `$${envOf[k]} gives` : k === 'workDir' ? 'mkdtemp made' : 'the plugin registry gives'} ${out[k]}`)
      }
    }
    if (!(typeof out.since === 'string' && out.since.trim()) && typeof found.since === 'string') out.since = found.since
  }
  const missing = required.filter((k) => (PATH_ARGS.includes(k) ? !isAbsolute(out[k]) : !(typeof out[k] === 'string' && out[k].trim())))
  return { args: out, missing, problems, envOf }
}
// Names what satisfies `k`: the Workflow arg, or the environment that supplies it.
function remedy(k, envOf) {
  if (envOf[k]) return `pass ${k} in the Workflow args or set $${envOf[k]}`
  if (ENV_CONSTANT_OF[k]) return `pass ${k} in the Workflow args or set the variable ${ENV_CONSTANT_OF[k]} names in skills/pipeline-contracts/schemas/driver-surface.schema.json`
  if (k === 'pluginRoot') return 'pass pluginRoot in the Workflow args or install agent-teams-workforce so $CLAUDE_CONFIG_DIR/plugins/installed_plugins.json (default ~/.claude) records it'
  return `pass ${k} in the Workflow args`
}
// Returns the refusal a workflow gives when a required arg has no value; no other agent has been dispatched.
function refuseArgs(resolved, name) {
  const why = resolved.missing
    .map((k) => `${k} has no value${resolved.problems[k] ? ` (${resolved.problems[k]})` : ''}: ${remedy(k, resolved.envOf || {})}`)
    .join('; ')
  const extra = resolved.problems.resolver ? `; resolver: ${resolved.problems.resolver}` : ''
  const error = `${name} refused before dispatching any agent: ${why}${extra}.`
  log(error)
  return {
    ok: false,
    stage: 'args',
    headline: error,
    error,
    missing: resolved.missing,
    dispatchFailed: dispatchDeaths().length > 0,
    dispatchFailures: dispatchDeaths(),
  }
}
const resolved = await resolveArgs(given, 'task-dependency-assessment', [...PATH_ARGS, 'task'])
if (resolved.missing.length) return dispatchOutcome(refuseArgs(resolved, 'task-dependency-assessment'))
const a = resolved.args
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
const target = String(a.task || '')
const repo = String(a.repoPath || '').replace(/\/+$/, '')
const work = String(a.workDir || '').replace(/\/+$/, '')
const PORTFOLIO = `${String(a.pluginRoot || '').replace(/\/+$/, '')}/scripts/portfolio`
const DS = `${PORTFOLIO}/depscore.py`
const RUNNER = `${PORTFOLIO}/relayrun.py`
const file = (name) => `${work}/${name}`
const cmd = (sub, extra) => `python3 ${shq(DS)} ${sub} -C ${shq(repo)}${extra ? ` ${extra}` : ''}`
const scope = `--task ${shq(target)}`
const applies = a.apply !== false
const project = { repoPath: repo, pluginRoot: a.pluginRoot, archPath: a.archPath, projectRoot: a.projectRoot }

const planFile = file('assess-plan.json')
const contextFile = file('context.json')
// The matrix command and the beads-contract command. The control repository names where the matrix file
// and the tracker are; a matrix read needs no role.
const PLUGIN = String(a.pluginRoot || '').replace(/\/+$/, '')
const MATRIX_BIN = `${PLUGIN}/bin/atw-matrix`
const MATRIX_ENV = { [DRIVER_SURFACE.CONTROL_REPO_ENV]: repo }
const MATRIX = `${DRIVER_SURFACE.CONTROL_REPO_ENV}=${shq(repo)} ${shq(MATRIX_BIN)}`
const BEADS_CONTRACT = `${PLUGIN}/skills/beads-contract/scripts/beads-contract.py`
const BEADS = `python3 ${shq(BEADS_CONTRACT)} -C ${shq(repo)}`
// The key of a Task's metadata that holds the matrix ids it states (bead-metadata.schema.json).
const ELEMENTS_KEY = 'matrix_elements'
const edgesFile = file('edges.json')
const candidateFile = file('candidates/edges.json')
const reasoningFile = file('reasoning.md')
const selfCheckFile = file('validation.json')
const applyFile = file(applies ? 'apply-edges.json' : 'apply-edges-dry-run.json')

// Every depscore.py command runs through the checked relay; its full result is saved in a numbered
// relay file under <workDir>/relay, and the script branches only on the checked copy.
let relaySeq = 0
function depscore(label, tail) {
  relaySeq += 1
  const relayFile = file(`relay/${String(relaySeq).padStart(3, '0')}-${label.replace(/[^A-Za-z0-9._-]+/g, '-')}.json`)
  return relayKit.depscore(settleAgent, { label, phase: 'Assess', script: DS, repo, tail, file: relayFile })
}

phase('Assess')
// The context the session reasons over is written by the script, before the session starts.
const planned = await depscore('assess-plan', `assess-plan --level task ${scope} --out ${shq(planFile)}`)
const context = planned.error ? null : await depscore('assess-context', `assess-context ${scope} --out ${shq(contextFile)}`)
const contextFailure = planned.error ? { step: 'assess-plan', ...planned } : context.error ? { step: 'assess-context', ...context } : null
const contextError = contextFailure ? `${contextFailure.step}: ${contextFailure.error}` : ''

const EDGE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['from', 'to', 'reason', 'confidence'],
  properties: {
    from: { type: 'string' },
    to: { type: 'string' },
    reason: { type: 'string' },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
    answers: { type: 'string' },
  },
}
const WITHDRAWAL_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['from', 'to', 'reason'],
  properties: { from: { type: 'string' }, to: { type: 'string' }, reason: { type: 'string' } },
}
const ASSESS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['proposal', 'valid', 'relatedRead'],
  properties: {
    proposal: {
      type: 'object',
      additionalProperties: false,
      required: ['edges', 'withdrawn', 'elements'],
      properties: {
        edges: { type: 'array', items: EDGE_SCHEMA },
        withdrawn: { type: 'array', items: WITHDRAWAL_SCHEMA },
        elements: { type: 'array', items: { type: 'string', minLength: 1 } },
      },
    },
    valid: { type: 'boolean' },
    findings: { type: 'object' },
    relatedRead: { type: 'array', items: { type: 'string' } },
    unsure: { type: 'array', items: { type: 'string' } },
  },
}
const THE_TEST = `THE TEST. An edge from A to B says B cannot be built until A is built, because B consumes something A provides — an API, a table, an IAM grant, a deployed resource. A producer of an event never depends on a routing rule or its target, and a routing rule or its target never depends on a producer: both depend only on the central event API and the bus. Sharing a domain, a vocabulary, a repository or an Epic is not an edge. Both ends are Tasks: no end is a Story or an Epic. When in doubt an edge is left out, because a false edge serializes work that could run in parallel.`
const priorBlock = typeof a.priorFailure === 'string' && a.priorFailure.trim()
  ? `THE PREVIOUS ASSESSMENT OF THIS ITEM FAILED, on this same content: ${a.priorFailure.trim().slice(0, 2000)}\nWork out why before you start, and do not repeat it.\n\n`
  : ''
const inputBinding = contextError ? null : await relayKit.artifactRevision(settleAgent, { label: 'assess:inputs', phase: 'Assess', runner: RUNNER, files: [contextFile], relayFile: file('relay/assessment-inputs.json'), context: { target, scope } })
if (inputBinding && !inputBinding.ok) return dispatchOutcome({ ok: false, stage: 'Assess', reason: inputBinding.error })
const inputRevision = inputBinding ? inputBinding.revision : ''
const assessPrompt = `${priorBlock}Assess the build dependencies of ONE Task, ${target}, which was created outside elaboration. ${target} is new or has changed.

${THE_TEST}

The workflow has already written ${contextFile}, the material you start from. Its \`task\` holds ${target}'s title, its Epic, \`elements\` (the matrix ids its \`${ELEMENTS_KEY}\` key states: its stack, the entries it builds and the shared capabilities it uses), \`stacks\` (the stacks those ids name, and the stacks that hold the entries they name) and \`unmatched\` (stated ids that are the id of no matrix entry). \`stacks\` lists, for each of those stacks: \`work\`, the open Tasks that name the stack or an entry it holds (\`atw-matrix work --id\`), each as {task, title, status, story, epic, names}; \`dependsOn\`, what the stack depends on (\`atw-matrix deps --of\`); and \`dependents\`, what depends on it (\`atw-matrix deps --on\`), each dependency with its relationship kind and the stack that holds the far end. \`standing\` lists every edge between ${target} and another open Task, in either direction, as {from, to, type, owned, reason, confidence, setBy, setAt} — \`from\` is the Task built first, \`reason\` the one recorded when the edge was set, or null. \`withdrawn\` lists every edge touching ${target} that an earlier assessment WITHDREW, as {from, to, reason, withdrawnBy, withdrawnAt}: that edge was judged not to exist, for the reason recorded. Setting it again is admitted only when you answer that reason.

Read a Task with \`${BEADS} contract <id>\`, which prints its title, its description, the build contract it carries and the matrix ids it states. Read the matrix with \`${MATRIX} <command>\`: a read needs no role, and every command prints one JSON object.

Work in this order:
1. Read ${target}.
2. Name what it consumes and what it provides. When the context's \`task.elements\` is empty, ${target} states no matrix id: find its stack with \`${MATRIX} find --kinds stack --text "<what ${target} builds, in words>"\` and \`${MATRIX} node stack:<id>\`, which returns what the stack holds, name the stack, the entries ${target} builds and the shared capabilities it uses by their matrix ids, and read for that stack what the context would have held: \`${MATRIX} work --id <stack id>\`, \`${MATRIX} deps --of <stack id>\` and \`${MATRIX} deps --on <stack id>\`.
3. Find the related Tasks from the matrix, not by searching: the open Tasks in each stack's \`work\`, and the open Tasks that name a stack ${target}'s stack depends on or that depends on it — \`${MATRIX} work --id <that stack's id>\` for each stack in \`dependsOn\` and \`dependents\`. Among them, the related Tasks are those that provide what ${target} consumes or consume what it provides. Read no Task these lookups did not return.
4. Read in full every related Task, and the Task at the other end of every standing edge.
5. Apply the test in both directions: an edge from another Task to ${target} where ${target} consumes what that Task provides, and an edge from ${target} to another Task where that Task consumes what ${target} provides.
6. Write ${candidateFile} as {"edges": [{"from", "to", "reason", "confidence", "answers"}], "withdrawn": [{"from", "to", "reason"}], "elements": [<matrix id>]}. \`elements\` is [] when the context's \`task.elements\` is not empty; otherwise it holds the matrix ids you named in step 2, the stack first, each the id of an entry the matrix holds, and [] only when the matrix holds no stack for what ${target} builds, which you state in ${reasoningFile}. The workflow writes \`elements\` to ${target}; nothing you return is written into the matrix, and you run no \`put\`, no \`link\` and no write to a bead. \`answers\` is required only on an edge the context's \`withdrawn\` list covers: state why the recorded withdrawal reason is wrong. An edge you cannot answer that way is not set — the earlier judgment stands. \`edges\` holds EVERY edge to or from ${target} that passes the test — a standing one it keeps included — and no edge that does not touch ${target}. \`withdrawn\` holds every standing edge with \`owned: true\` that is not in \`edges\`, with a reason that answers the reason recorded for it. Every reason names the artifact and which Task provides it; \`confidence\` is \`high\`, \`medium\` or \`low\`. A standing edge with \`owned: false\` was made by hand: leave it out of both lists. No edge is a valid result. Write the reasoning, per edge and per withdrawal, to ${reasoningFile}.
7. Validate: \`set -o pipefail; ${cmd('validate', `--edges ${shq(candidateFile)} ${scope}`)} | tee ${shq(selfCheckFile)}\` — revise the file until \`ok\` is true, keeping to THE TEST: an edge that fails the test is dropped, never kept to satisfy the validator; an owned standing edge you drop goes in \`withdrawn\` with a reason. It refuses an edge that does not touch ${target}, an edge whose ends are not both open Tasks, a missing reason, an edge an earlier assessment withdrew that carries no \`answers\`, an owned standing edge left unaccounted, a withdrawal of an edge that is not an owned standing edge, and a cycle against every other Task edge. A cycle you cannot remove by dropping one of your own edges that fails the test — one through an edge with \`owned: false\` — is reported, not forced: record the failed validation, its findings and the cycle in the reasoning document.

Do not run apply-edges or any other command that writes to the tracker or the matrix: the workflow validates the proposal you return, applies it and writes \`elements\` itself.

Record your validation findings, every related item read and any uncertainty in ${reasoningFile}. Return only the authored candidate reference.${relayKit.artifactBrief(candidateFile, ASSESS_SCHEMA.properties.proposal, inputRevision, RUNNER.replace(/[^/]+$/, 'artifactcontract.py'))}`

const assess = () => settleAgent(assessPrompt, {
      label: `task-dependency-mapper:${target}`,
      phase: 'Assess',
      effort: 'medium',
      agentType: 'task-dependency-mapper',
      schema: relayKit.ARTIFACT_SCHEMA,
    })

// The authoritative candidate is validated and published before any tracker mutation.
const saved = !contextError && !dispatchInterruption ? await relayKit.authorArtifact(settleAgent, {
  label: 'save-edges', phase: 'Assess', runner: RUNNER, candidate: candidateFile, file: edgesFile,
  schema: ASSESS_SCHEMA.properties.proposal, revision: inputRevision, relayFile: file('relay/accepted-edges.json'), counts: ['edges', 'withdrawn'], keys: ['elements'],
}, assess, () => !!dispatchInterruption) : null
const accepted = !!(saved && saved.ok)
const validation = saved && saved.ok ? await depscore('validate', `validate --edges ${shq(edgesFile)} ${scope}`) : null
const valid = !!validation && !validation.error && validation.ok === true
const applied = valid
  ? await depscore('apply-edges', `apply-edges --edges ${shq(edgesFile)} --plan ${shq(planFile)} ${scope}${applies ? '' : ' --dry-run'} --out ${shq(applyFile)}`)
  : null
const summary = applied && !applied.error && applied.summary && typeof applied.summary === 'object' ? applied.summary : {}
const settled = !!applied && !applied.error && !summary.validation && summary.applied !== false

// The matrix ids the session named for a Task that states none are written by the workflow into its
// matrix_elements key, once the edges are applied. The call runs in one checked command, which reads from
// the context file whether the Task states an id, and the run is done only when the write was confirmed.
// Nothing is written into the matrix: its architecture side is written only by arc42 (through
// sync-documents) and the architect's recorded design, and the beads edge alone carries build order.
const RECORD_PY = `import json, os, subprocess
added, context_file, element_call = json.loads(ARGS[0]), ARGS[1], json.loads(ARGS[2])
env = dict(os.environ, **added)
with open(context_file, encoding="utf-8") as handle:
    task = json.load(handle).get("task")
stated = task.get("elements") if isinstance(task, dict) else None
if not isinstance(stated, list):
    emit({"error": context_file + " holds no task.elements list"}, 2)
failures = []
def confirmed(call):
    ran = subprocess.run(call, env=env, capture_output=True, text=True, check=False)
    if ran.returncode != 0:
        failures.append({"call": " ".join(call[-8:]), "exit": ran.returncode, "error": (ran.stderr or ran.stdout).strip()[-600:]})
    return ran.returncode == 0
elements = "none-named"
if element_call:
    elements = "already-stated" if stated else ("written" if confirmed(element_call) else "refused")
emit({"elements": elements, "failures": failures})`
const facts = accepted && saved.facts && typeof saved.facts === 'object' ? saved.facts : {}
const namedElements = [...new Set((Array.isArray(facts.elements) ? facts.elements : []).map((id) => String(id || '').trim()).filter(Boolean))]
const elementsCall = namedElements.length ? ['python3', BEADS_CONTRACT, '-C', repo, 'metadata', 'set', target, `${ELEMENTS_KEY}=${JSON.stringify(namedElements)}`] : []
// elements: none-named (the session named no id), already-stated (the Task states ids, so none is written),
// written, refused, or not-written (nothing was recorded: a dry run, or the edges were not applied).
let matrix = { elements: namedElements.length ? 'not-written' : 'none-named', named: namedElements, failures: [] }
const records = settled && applies && namedElements.length > 0
if (records) {
  const wrote = await relayKit.inline(settleAgent, { label: 'record-elements', phase: 'Assess', code: RECORD_PY, args: [JSON.stringify(MATRIX_ENV), contextFile, JSON.stringify(elementsCall)] })
  matrix = wrote.ok
    ? { elements: String(wrote.view.elements || 'refused'), named: namedElements, failures: Array.isArray(wrote.view.failures) ? wrote.view.failures : [] }
    : { elements: 'refused', named: namedElements, failures: [{ call: 'record', exit: null, error: String(wrote.error || 'the recording command returned no result') }], noResult: !!wrote.noResult }
  log(`Matrix ids (${target}): ${matrix.elements}${matrix.elements === 'written' ? ` (${namedElements.join(', ')})` : ''}${matrix.failures.length ? `; refused: ${matrix.failures.slice(0, 3).map((f) => `${f.call}: ${f.error}`).join('; ')}` : ''}`)
}
const recordedOk = !records || (matrix.failures.length === 0 && matrix.elements !== 'refused')
const recordError = recordedOk ? '' : `the matrix ids the assessment named were not written to ${target} (${matrix.elements}): ${matrix.failures.slice(0, 5).map((f) => `${f.call}: ${f.error}`).join('; ') || 'the write was not confirmed'}`
const validationFile = (validation && validation.relayFile) || selfCheckFile
const findingsOf = (v) => {
  if (!v || v.error) return null
  const { relayFile: _f, command: _c, summary: _s, ...report } = v
  return report
}
const stop = accepted && !settled
  ? { task: target, findings: summary.validation || findingsOf(validation) || {}, edgesFile, validationFile, reasoning: reasoningFile }
  : null
const edges = {
  ...summary,
  applied: applies && settled,
  proposed: !applies && settled,
  resultFile: applyFile,
  edgesFile,
  reasoning: reasoningFile,
  uncertaintyPath: reasoningFile,
  ...(settled
    ? {}
    : {
        reason: contextError
          ? `the context could not be written: ${contextError}`
          : !accepted && !(saved && saved.error)
            ? 'the task-dependency-mapper returned no result; the tracker keeps its current edges'
            : !saved || !saved.ok
              ? `the edge proposal could not be saved to ${edgesFile}: ${saved && saved.error || 'not accepted'}; the tracker keeps its current edges`
              : !validation || validation.error
                ? `the edge proposal could not be validated: ${(validation && validation.error) || 'no result'}; the tracker keeps its current edges`
                : !valid
                  ? `the edge proposal failed validation (${validationFile}); the tracker keeps its current edges`
                  : applied.error
                    ? `apply-edges failed: ${applied.error}; the tracker keeps its current edges`
                    : 'the edge proposal was not applied; the tracker keeps its current edges',
      }),
}
if (settled) log(`Edges (${target})${applies ? '' : ', proposed'}: ${summary.added ?? '?'} added, ${summary.converted ?? '?'} converted, ${summary.removed ?? '?'} withdrawn, ${summary.unchanged ?? '?'} unchanged`)
else log(`${target}: ${edges.reason}`)
const assessment = accepted
  ? {
      edgesPath: edgesFile,
      reasoningPath: reasoningFile,
      edgeCount: saved.receipt.counts.edges,
      withdrawnCount: saved.receipt.counts.withdrawn,
      valid,
      saved: { ok: saved.ok, artifactPath: edgesFile },
      applySummary: summary,
    }
  : { failed: true, ...(contextError ? { error: contextError } : {}) }

let scoring = null
const scores = applies && settled && a.score !== false
if (scores) {
  phase('Score')
  try {
    scoring = await settleWorkflow('agent-teams-workforce:wsjf-scoring', { ...project, workDir: file('scoring') })
  } catch (err) {
    scoring = { ok: false, error: String((err && err.message) || err).slice(0, 500) }
  }
}

const storyEdges = summary.storyEdges || null
const storyEdgeLine = !storyEdges
  ? ''
  : storyEdges.ok
    ? `; Story edges ${storyEdges.added || 0} added, ${storyEdges.removed || 0} removed`
    : `; Story edges ${storyEdges.error ? `NOT written — ${storyEdges.error}` : `${storyEdges.added || 0} added, ${storyEdges.removed || 0} removed; NOT written for ${(storyEdges.refusedStories || []).join(', ')}, whose order is contradictory`}${[...(storyEdges.conflicts || []), ...(storyEdges.cycles || [])]
        .map((x) => ` [${(x.stories || []).join(' / ')}${(x.tasks || []).length ? `, Tasks ${x.tasks.join(', ')}` : ''}]`)
        .join('')}`
if (storyEdgeLine) log(`${target}${storyEdgeLine}`)

const scoredOk = !scores || (!!scoring && scoring.ok === true)
const scoringDeaths = scoring && scoring.ok !== true && scoring.stage === 'agent-dispatch-failed' && Array.isArray(scoring.dispatchFailures) ? scoring.dispatchFailures : []
const failure = !settled
  ? `${target}: ${edges.reason}`
  : !recordedOk
    ? `${target}: the edges were applied, but ${recordError}`
    : !scoredOk
      ? `${target}: the edges were applied, but scoring failed: ${(scoring && scoring.error) || 'wsjf-scoring returned no result'}`
      : null
const relayDied = [contextFailure, saved && !saved.ok ? saved : null, validation, applied, matrix].some((r) => r && r.noResult)
return dispatchOutcome({
  ok: settled && recordedOk && scoredOk,
  stage: (contextError || saved) && !relayDied
    ? !settled || !recordedOk ? 'Assess' : !scoredOk ? (scoring && scoring.stage === 'agent-dispatch-failed' ? scoring.stage : 'Score') : 'done'
    : 'agent-dispatch-failed',
  beadId: target,
  headline: failure || `${target}: edges ${applies ? 'applied' : 'proposed'} — ${summary.added ?? '?'} added, ${summary.converted ?? '?'} converted, ${summary.removed ?? '?'} withdrawn, ${summary.unchanged ?? '?'} unchanged; matrix ids ${matrix.elements}${scores ? ', and rescored' : ''}${storyEdgeLine}`,
  apply: applies,
  settled,
  workDir: work,
  task: target,
  assessment,
  edges,
  matrix: { elements: matrix.named, elementsWritten: matrix.elements, failures: matrix.failures },
  scoring,
  stop,
  ...(failure ? { error: failure } : {}),
  dispatchFailed: dispatchDeaths().length + scoringDeaths.length > 0,
  dispatchFailures: [...dispatchDeaths(), ...scoringDeaths],
})
