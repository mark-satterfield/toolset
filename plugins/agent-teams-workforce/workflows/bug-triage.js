export const meta = {
  name: 'bug-triage',
  description:
    'Bug front-end. Turns a symptom (a bug bead) into an implementation-ready contract: reproduction, root cause, blast radius, and the expected-behavior acceptance criteria the shared tail builds against. Also SIZES the bug: a defect whose honest fix is a redesign is escalated as needing a PRD and Epic rather than being squeezed through the fix path, because a bug ticket is not a licence to rebuild a subsystem unreviewed. Read-only — produces no code changes.',
  phases: [{ title: 'Triage', detail: 'root-cause analysis + scope sizing + expected-behavior contract' }],
}
// ===== SHARED BLOCK fable — BEGIN (canonical: scripts/shared-blocks/fable.js; edit there, then: node scripts/shared-blocks.mjs --write) =====
const ownedCoreContracts = "---\nname: subagent-contract\ndescription: >-\n  Shared contract for bounded specialist assignments: preserve role and scope, follow\n  the caller's response format, retain verifiable artifacts, and report incomplete work explicitly.\nuser-invocable: false\n---\n\n# Subagent Contract\n\n## Caller contract comes first\n\nFollow the caller's exact response schema and artifact protocol. Do not prepend `STATUS`, restate the task, add report fields, or append commentary to a machine-consumed response. Put evidence, findings, progress and blockers only in the artifacts or fields the caller provides. An artifact's on-disk schema and the response-reference schema serve different purposes; do not return the artifact body when the caller requests only its path.\n\nWhen an executable submission/checkpoint tool is supplied, use it to validate the authored result, compute bindings and construct the response. Return its successful response unchanged through the requested channel. Do not manually manufacture completion flags or hashes. Structural validation proves neither semantic correctness nor review approval. On failure preserve work and report the exact remaining work or blocker through the caller's supported mechanism; never send a success reference for an incomplete assignment. If the supplied protocol has no failure channel, report that incompatibility to the caller rather than inventing a successful response.\n\nOnly when the caller supplies no response format, use `STATUS: DONE` or `STATUS: BLOCKED` with a concise description of deliverables and verification, or the blocker and what is needed. Claim DONE only when the assigned work is complete and verified. No separate preliminary restatement or generic final report is required.\n\n## Role and scope\n\n- Perform only the role assigned in the agent definition and task. Do not invent requirements, select downstream work or enlarge your authority.\n- Identify the minimal relevant files, artifacts and decisions. Use only allowed tools and preserve file ownership. Read-only reviewers may write caller-authorized result/checkpoint artifacts, never source artifacts.\n- An explicit assignment to repair all baseline failures in an affected repository includes pre-existing failures there. Preserve test-author ownership and required checks; this does not authorize unrelated cleanup, other repositories or invented external resources.\n- Prefer small, reversible changes unless the assignment requires broader change. Report material actions and their outcomes in the existing evidence channel, without adding fields to a fixed schema.\n- Missing required context is a named dependency, not permission to guess. Distinguish facts, justified assumptions and unresolved questions; do not silently complete only the easy portion.\n\n## Skills and authoritative artifacts\n\nRead canonical skill content already delivered in the prompt; do not reload it solely because its name also appears in frontmatter. Assess which other declared skills apply and load those through the Skill tool using their exact names. A name alone is not delivered content. A missing required skill is an explicit dependency; do not substitute recollection. Note material applicability decisions only in existing progress/evidence channels that permit them, never by expanding the return schema.\n\nRead the actual relevant source sections and connected contracts. Shared Markdown, vault notes, diagrams, schemas and JSON stay authoritative at their paths; summaries guide navigation and do not replace source verification. Observe assigned read/edit/create ownership. Preserve content unless its change is assigned. Pass references rather than copying whole documents between agents. When exact copying is required, use deterministic file tools rather than model transcription. Use version/provenance where relevant; do not require hashes merely for semantic editing.\n\nFor durable authoring, checkpoint meaningful progress using the caller's location and executable mechanism where supplied. Record completed work, remaining work and artifact references; blocked progress names the dependency and reason. Checkpoints are progress, not accepted results. On resume verify the checkpoint against actual artifacts and finish missing work without regenerating valid completed documents.\n\n## Resource use and incremental review\n\n- Use tokens conscientiously without compromising required correctness, completeness, safety or evidence. Before a material optional expansion, identify its unresolved need and expected benefit in existing progress. Routine tools need no justification. Do not add a report, review pass, token quota or human approval gate for this rule; omit optional work with no concrete benefit.\n- Makers and reviewers use the same applicable requirements, constraints and completion criteria. Review determines actual correctness, including passing sound work; finding more failures is not success. Do not invent requirements or turn stylistic preferences into blocking defects. Preserve necessary safety and regression checks.\n- Use the caller's finding format to identify the affected location, requirement/dependency at risk, observed evidence and actionable correction with a verifiable pass condition. Distinguish defects, missing evidence and proposed new requirements. Never claim unperformed checks passed.\n- Revise original artifacts incrementally. Retain valid work and applicable evidence. Rereview changed scope and affected dependencies; reopen accepted work only when new evidence or demonstrated impact invalidates its earlier evidence, and state why. Preserve required independent review.\n\n## AWS evidence authority\n\nFor applicable AWS architecture choices, consult actual AWS MCP Server documentation and relevant AWS skills, including applicable Well-Architected principles. Retain source references and the concrete tradeoffs. Existing generated architecture and model recollection do not establish correctness. Makers and reviewers use this same evidence criterion.\n\nApply guidance to stated requirements, deployment, usage and cost constraints rather than hypothetical scale. Surface conflicts with product requirements or owner constraints; do not silently substitute a preferred AWS pattern. Missing required MCP/skill access is a named blocker or uncertainty, never a passed check. Coordinators may research and route AWS questions, but cannot author or approve designs.\n"
const ownedArtifactContract = "---\nname: artifact-handoff\ndescription: Share authoritative documents, diagrams and JSON by artifact path, with format-specific validation and resumable checkpoints; never retype full payloads between agents.\n---\n\n## Executable output mode\n\nThe dispatcher selects `OUTPUT_MODE` from its response schema and validates an explicit mode against that schema before dispatch. `artifact` means a single `artifactPath` reference to a caller-specified candidate; the JSON candidate, progress and submission rules below apply. `inline` means a small caller-defined status, routing or control response: return that exact schema directly and do not invent candidate files or checkpoints. `machine` is the deterministic command runner protocol; its executable hook supplies the response and no model-authored payload is permitted. Merely loading this skill does not change the selected mode or grant write access. In standalone use without an explicit mode, apply artifact rules only when the caller supplies a candidate path and artifact schema; otherwise honor its inline response contract.\n\nShared documents, Markdown, diagrams and other artifacts stay in their authoritative files. Pass paths and brief task context; recipients read the actual files. A summary is navigation, never a substitute source. Edit only explicitly assigned files; preserve accepted work. Do not retype an entire document into another agent's prompt or machine response. Use existing deterministic file operations for exact copies when a copy is explicitly required.\n\nKeep the caller-specified checkpoint current after meaningful work: status, task, completed work, remaining work and artifact paths. On resume read the checkpoint and referenced artifacts, verify current state and complete remaining work. A checkpoint is progress evidence, never acceptance or permission to omit validation.\n\nFor JSON, write the caller's requested JSON object once to its exact candidate path. Use the supplied artifact schema; do not confuse it with the small return schema. Preserve existing completed work and inspect an existing candidate before continuing interrupted work. Return only the candidate path using the caller's structured return schema. Never copy the full artifact into StructuredOutput or prose.\n\nThe producer directly reads its inputs, authors its outputs and runs its own submission/checkpoint helper. The workflow's named command runner performs only coordinator acceptance and provenance operations: it invokes `scripts/portfolio/jsonartifact.py` with the expected candidate, final path and schema. The script rejects duplicate keys, invalid JSON, schema violations and changes to already accepted results. It writes canonical JSON and an integrity receipt; downstream scripts verify the receipt. Candidates stay outside the accepted result directory. A failed candidate is never treated as a completed step.\n\nThe command runner runs only the exact checked command supplied by the workflow. Validation failure is reported explicitly; it does not authorize rewriting another producer's content or repeating a successful administrative command. Existing legacy artifacts are preserved.\n\nFor Markdown and diagrams, `jsonartifact.py --document PATH` verifies the actual nonempty UTF-8 file and returns its path, raw-byte SHA-256, length and format. It never copies or rewrites the document. This receipt identifies the reviewed version; it is not a semantic quality verdict and does not prohibit later authorized edits. Keep structured metadata separate and refer to the document path instead of embedding its contents.\n\nCandidate completion checkpoints bind the exact candidate path, expected schema hash and caller revision. The workflow derives that revision from actual source-file/corpus byte fingerprints and assignment context; a path alone is not freshness evidence. Changed inputs require a new candidate revision. A saved complete result for the same revision is reused; it is never silently replaced. Fingerprints exclude the producer’s assigned output files to preserve interruption recovery.\n\n## Executable producer contract\n\nUse the caller's canonical schema for both production and review; architecture uses [writer](schemas/architecture-writer.schema.json) and [reviewer](schemas/architecture-review.schema.json). Never maintain a second schema in prose. The [checkpoint schema](schemas/checkpoint.schema.json) is shared by producer status commands.\n\nResolve `scripts/portfolio/artifactcontract.py` from this plugin's root (two directories above this skill). The workflow supplies the candidate path, canonical schema and input revision. Pass exactly one of `--schema-file PATH` or `--schema-json JSON`; both use identical strict parsing, validation and canonical hashing. Prefer the schema file when the caller supplies one. Author a small progress JSON file with `task`, `completed`, `remaining`, and `artifacts`; add `reason` when blocked. Do not put binding hashes or completion flags in that file: the helper computes them.\n\n```bash\npython3 \"$PLUGIN_ROOT/scripts/portfolio/artifactcontract.py\" checkpoint --candidate \"$CANDIDATE\" --schema-file \"$SCHEMA\" --revision \"$REVISION\" --progress-file \"$PROGRESS\" --status in-progress\npython3 \"$PLUGIN_ROOT/scripts/portfolio/artifactcontract.py\" complete --candidate \"$CANDIDATE\" --schema-file \"$SCHEMA\" --revision \"$REVISION\" --progress-file \"$PROGRESS\"\npython3 \"$PLUGIN_ROOT/scripts/portfolio/artifactcontract.py\" status --candidate \"$CANDIDATE\" --schema-file \"$SCHEMA\" --revision \"$REVISION\"\n```\n\nFor a dependency you cannot satisfy, checkpoint with `--status blocked` and its exact `reason` and remaining work. Do not mark incomplete reasoning complete merely to satisfy the schema. `complete` requires no remaining work, validates strict JSON against the canonical schema, canonicalizes the candidate and writes its bound checkpoint. Return only the candidate reference after that command succeeds. `validate` performs schema validation without mutation. Invalid commands return exit 2 with an explicit error.\n\n`complete-unaccepted` means structurally ready for the workflow's existing acceptance operation, not technically correct, approved, or shipped. Reviewers read the authoritative artifacts and independently judge evidence; mechanically valid metadata cannot establish their correctness. Status detects changed candidate bytes and changed input/schema bindings. Resume `in-progress`/`blocked` work from its actual artifacts; do not restart completed reasoning or silently retry an unchanged blocker.\n\nThe coordinator may use `scripts/portfolio/artifactpublish.py --record-argv-json JSON -- <jsonartifact acceptance arguments>` to validate/publish and record provenance in one deterministic invocation. The recorder receives argv, not shell text, and must name the accepted artifact. Pending or rejected candidates are never recorded; recorder failure reports failure and retains the accepted artifact for recovery. This replaces separate administrative agent calls without replacing specialist reasoning or independent review.\n\nFor the actual handoff use `submit` with the same arguments as `complete`: it validates and writes the checkpoint, then emits exactly the response object `{\"artifactPath\":\"...\"}`. Return that object unchanged. The schema describes the on-disk candidate; the response contains only its reference. A failed submission emits an error and never writes a new completion checkpoint. When the caller supplies `--files-root ROOT --files-field FIELD`, submission also verifies every path in that candidate field is relative to ROOT, stays inside it after symlink resolution, and names a nonempty regular file. These are declared authored outputs, not all assigned or future files. `--progress-artifacts-root ROOT` additionally checks explicitly declared progress artifact paths inside that root; use it only when the caller establishes that scope. These checks establish file existence and structure, not whether the reasoning is correct.\n"
const ownedAgentContracts = {"acceptance-criteria-reviewer":{"artifactCapable":false,"agentType":"agent-teams-workforce:acceptance-criteria-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"acceptance-criteria-writer":{"artifactCapable":true,"agentType":"acceptance-criteria-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"accessibility-validator":{"artifactCapable":true,"agentType":"agent-teams-workforce:accessibility-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:a11y-audit","agent-teams-workforce:senior-frontend"]},"advantage-evaluator":{"artifactCapable":false,"agentType":"agent-teams-workforce:advantage-evaluator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"adversarial-critique-adjudicator":{"artifactCapable":false,"agentType":"agent-teams-workforce:adversarial-critique-adjudicator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-security"]},"adversarial-review-loop-supervisor":{"artifactCapable":false,"agentType":"agent-teams-workforce:adversarial-review-loop-supervisor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"ambiguity-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:ambiguity-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"android-compose-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:android-compose-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"api-contract-designer":{"artifactCapable":true,"agentType":"api-contract-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer","agent-teams-workforce:aws-solution-architect"]},"api-documentation-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:api-documentation-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer"]},"api-gateway-cdk-implementer":{"artifactCapable":true,"agentType":"api-gateway-cdk-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-gateway","agent-teams-workforce:aws-cdk-development"]},"api-specification-author":{"artifactCapable":true,"agentType":"api-specification-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer"]},"appsync-cdk-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:appsync-cdk-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cdk-development"]},"appsync-client-subscription-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:appsync-client-subscription-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend"]},"architecture-boundary-guardian":{"artifactCapable":true,"agentType":"architecture-boundary-guardian","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect"]},"architecture-conformance-reviewer":{"artifactCapable":true,"agentType":"architecture-conformance-reviewer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:arc42","agent-teams-workforce:aws-solution-architect"]},"architecture-decider":{"artifactCapable":true,"agentType":"architecture-decider","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect"]},"architecture-decision-workflow-coordinator":{"artifactCapable":true,"agentType":"architecture-decision-workflow-coordinator","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-solution-architect"]},"architecture-diagram-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:architecture-diagram-author","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:c4-diagramming","agent-teams-workforce:uml-diagramming","agent-teams-workforce:senior-architect"]},"architecture-fitness-function-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:architecture-fitness-function-author","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"architecture-impact-analyst":{"artifactCapable":false,"agentType":"agent-teams-workforce:architecture-impact-analyst","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:beads-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"architecture-maintainer":{"artifactCapable":true,"agentType":"architecture-maintainer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:arc42","agent-teams-workforce:arc42-maintain","agent-teams-workforce:c4-diagramming","agent-teams-workforce:uml-diagramming","agent-teams-workforce:senior-architect"]},"architecture-pattern-challenger":{"artifactCapable":true,"agentType":"architecture-pattern-challenger","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect"]},"architecture-tradeoff-skeptic":{"artifactCapable":true,"agentType":"architecture-tradeoff-skeptic","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect"]},"athena-redshift-analytics-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:athena-redshift-analytics-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer"]},"auth-bypass-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:auth-bypass-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops","agent-teams-workforce:cognito"]},"aws-integration-test-runner":{"artifactCapable":true,"agentType":"agent-teams-workforce:aws-integration-test-runner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:test-failure-mindset","agent-teams-workforce:cumulative-regression"]},"aws-integration-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:aws-integration-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:cumulative-regression"]},"beads-format-validator":{"artifactCapable":true,"agentType":"agent-teams-workforce:beads-format-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:beads-contract"]},"bedrock-integration-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:bedrock-integration-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:bedrock","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:senior-prompt-engineer","agent-teams-workforce:aws-agentic-ai"]},"behavioral-signals-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:behavioral-signals-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:senior-data-scientist","agent-teams-workforce:product-analytics"]},"bounded-context-mapper":{"artifactCapable":true,"agentType":"bounded-context-mapper","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect"]},"brd-traceability-auditor":{"artifactCapable":true,"agentType":"agent-teams-workforce:brd-traceability-auditor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"c4-diagram-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:c4-diagram-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:c4-diagramming","agent-teams-workforce:senior-architect"]},"cdk-infrastructure-designer":{"artifactCapable":true,"agentType":"cdk-infrastructure-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:aws-solution-architect"]},"cdk-infrastructure-drift-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:cdk-infrastructure-drift-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:cloudformation"]},"cdk-stack-author":{"artifactCapable":true,"agentType":"cdk-stack-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:cloudformation"]},"cds-finding-reviewer":{"artifactCapable":false,"agentType":"agent-teams-workforce:cds-finding-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","cds:apply-design-system","cds:audit-against-system"]},"cds-ui-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:cds-ui-implementer","skills":["agent-teams-workforce:subagent-contract","cds:apply-design-system","cds:audit-against-system","cds:compose-page"]},"changelog-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:changelog-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:changelog-generator"]},"chassis-extension-implementer":{"artifactCapable":true,"agentType":"chassis-extension-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:lambda","agent-teams-workforce:aws-serverless-eda"]},"code-correctness-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:code-correctness-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:code-reviewer"]},"code-quality-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:code-quality-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"code-refactoring-specialist":{"artifactCapable":true,"agentType":"agent-teams-workforce:code-refactoring-specialist","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:code-reviewer"]},"code-style-and-linting-enforcer":{"artifactCapable":true,"agentType":"agent-teams-workforce:code-style-and-linting-enforcer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:code-reviewer"]},"cognito-lambda-trigger-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:cognito-lambda-trigger-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:cognito","agent-teams-workforce:lambda"]},"completeness-checker":{"artifactCapable":false,"agentType":"agent-teams-workforce:completeness-checker","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"complexity-analyzer":{"artifactCapable":false,"agentType":"agent-teams-workforce:complexity-analyzer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:tech-debt-tracker"]},"constitutional-agent":{"artifactCapable":false,"agentType":"agent-teams-workforce:constitutional-agent","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"constraint-extractor":{"artifactCapable":true,"agentType":"agent-teams-workforce:constraint-extractor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"consumer-driven-contract-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:consumer-driven-contract-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-test-suite-builder","agent-teams-workforce:cumulative-regression"]},"context-curator":{"artifactCapable":false,"agentType":"agent-teams-workforce:context-curator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"contract-violation-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:contract-violation-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-test-suite-builder"]},"cost-architecture-reviewer":{"artifactCapable":true,"agentType":"cost-architecture-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-cost-operations","agent-teams-workforce:aws-solution-architect"]},"cost-impact-reviewer":{"artifactCapable":true,"agentType":"cost-impact-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cost-operations","agent-teams-workforce:aws-solution-architect"]},"cross-repo-integration-test-coordinator":{"artifactCapable":false,"agentType":"agent-teams-workforce:cross-repo-integration-test-coordinator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"cross-service-contract-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:cross-service-contract-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-test-suite-builder"]},"data-consistency-checker":{"artifactCapable":true,"agentType":"agent-teams-workforce:data-consistency-checker","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb"]},"data-exposure-scanner":{"artifactCapable":true,"agentType":"agent-teams-workforce:data-exposure-scanner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"data-model-specification-author":{"artifactCapable":true,"agentType":"data-model-specification-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb","agent-teams-workforce:database-schema-designer"]},"data-pipeline-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:data-pipeline-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:cumulative-regression"]},"definition-of-done-enforcer":{"artifactCapable":true,"agentType":"agent-teams-workforce:definition-of-done-enforcer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"dependency-change-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:dependency-change-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dependency-auditor"]},"dependency-cve-auditor":{"artifactCapable":true,"agentType":"agent-teams-workforce:dependency-cve-auditor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dependency-auditor"]},"dependency-graph-extractor":{"artifactCapable":true,"agentType":"agent-teams-workforce:dependency-graph-extractor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"deployment-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:deployment-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"deployment-strategy-decider":{"artifactCapable":false,"agentType":"agent-teams-workforce:deployment-strategy-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:cove-prompt-design"]},"documentation-accuracy-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:documentation-accuracy-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"documentation-currency-auditor":{"artifactCapable":true,"agentType":"agent-teams-workforce:documentation-currency-auditor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"documentation-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:documentation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"domain-boundary-validator":{"artifactCapable":true,"agentType":"agent-teams-workforce:domain-boundary-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"domain-event-modeler":{"artifactCapable":true,"agentType":"domain-event-modeler","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:aws-solution-architect"]},"dos-resilience-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:dos-resilience-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"dynamodb-access-layer-implementer":{"artifactCapable":true,"agentType":"dynamodb-access-layer-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb"]},"dynamodb-cost-optimizer":{"artifactCapable":true,"agentType":"dynamodb-cost-optimizer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb","agent-teams-workforce:aws-cost-operations"]},"dynamodb-schema-access-pattern-reviewer":{"artifactCapable":true,"agentType":"dynamodb-schema-access-pattern-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb"]},"dynamodb-streams-cdc-implementer":{"artifactCapable":true,"agentType":"dynamodb-streams-cdc-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:dynamodb"]},"email-notification-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:email-notification-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:email-template-builder","agent-teams-workforce:sns"]},"epic-sequencer":{"artifactCapable":true,"agentType":"agent-teams-workforce:epic-sequencer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:epic-sequencing"]},"espresso-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:espresso-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:tdd-guide","agent-teams-workforce:cumulative-regression"]},"event-api-client-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:event-api-client-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda"]},"event-driven-consumer-implementer":{"artifactCapable":true,"agentType":"event-driven-consumer-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:sqs","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:sns"]},"event-flow-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:event-flow-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda"]},"event-schema-designer":{"artifactCapable":true,"agentType":"event-schema-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:eventbridge","agent-teams-workforce:sns","agent-teams-workforce:aws-solution-architect"]},"event-schema-reviewer":{"artifactCapable":true,"agentType":"event-schema-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda"]},"failure-mode-analyst":{"artifactCapable":true,"agentType":"failure-mode-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:observability-designer","agent-teams-workforce:aws-solution-architect"]},"filing-clerk":{"artifactCapable":true,"agentType":"filing-clerk","skills":["agent-teams-workforce:subagent-contract","obsidian:obsidian-cli","obsidian:obsidian-markdown","agent-teams-workforce:arc42","notebooklm","document-classification"]},"finops-analyst":{"artifactCapable":false,"agentType":"finops-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-cost-operations"]},"flaky-test-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:flaky-test-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:test-failure-mindset","agent-teams-workforce:find-cause"]},"frontend-performance-optimizer":{"artifactCapable":true,"agentType":"agent-teams-workforce:frontend-performance-optimizer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend"]},"github-actions-pipeline-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:github-actions-pipeline-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops"]},"glue-etl-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:glue-etl-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer"]},"graphql-schema-designer":{"artifactCapable":true,"agentType":"graphql-schema-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer","agent-teams-workforce:aws-solution-architect"]},"graphql-schema-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:graphql-schema-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer"]},"implementation-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:implementation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"incident-responder":{"artifactCapable":true,"agentType":"agent-teams-workforce:incident-responder","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:find-cause","agent-teams-workforce:validation-protocol"]},"incident-response-runbook-designer":{"artifactCapable":true,"agentType":"agent-teams-workforce:incident-response-runbook-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:observability-designer"]},"infrastructure-security-scanner":{"artifactCapable":true,"agentType":"infrastructure-security-scanner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops","agent-teams-workforce:aws-cdk-development"]},"injection-attack-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:injection-attack-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"integration-pattern-architect":{"artifactCapable":true,"agentType":"integration-pattern-architect","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:aws-solution-architect"]},"integration-testing-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:integration-testing-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"ios-swiftui-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:ios-swiftui-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"kinesis-stream-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:kinesis-stream-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:aws-serverless-eda"]},"lambda-performance-optimizer":{"artifactCapable":true,"agentType":"lambda-performance-optimizer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:lambda"]},"llm-observability-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:llm-observability-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:observability-designer","agent-teams-workforce:senior-prompt-engineer","agent-teams-workforce:aws-agentic-ai"]},"matching-algorithm-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:matching-algorithm-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer"]},"mcp-server-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:mcp-server-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:mcp-server-builder","agent-teams-workforce:aws-agentic-ai","agent-teams-workforce:aws-mcp-setup"]},"ml-evaluation-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:ml-evaluation-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:senior-data-scientist","agent-teams-workforce:cumulative-regression"]},"mobile-e2e-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:mobile-e2e-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"nextjs-component-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:nextjs-component-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend","agent-teams-workforce:a11y-audit","agent-teams-workforce:senior-fullstack"]},"nfr-analyst":{"artifactCapable":false,"agentType":"agent-teams-workforce:nfr-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:product-discovery"]},"okr-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:okr-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-strategist","agent-teams-workforce:product-analytics"]},"openapi-contract-reviewer":{"artifactCapable":false,"agentType":"openapi-contract-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer"]},"operational-readiness-reviewer":{"artifactCapable":true,"agentType":"operational-readiness-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:observability-designer","agent-teams-workforce:aws-solution-architect"]},"payments-integration-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:payments-integration-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:stripe-integration-expert","agent-teams-workforce:secrets-manager"]},"performance-benchmark-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:performance-benchmark-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"permission-escalation-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:permission-escalation-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops","agent-teams-workforce:iam"]},"persistence-architecture-specialist":{"artifactCapable":true,"agentType":"persistence-architecture-specialist","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:dynamodb","agent-teams-workforce:database-schema-designer","agent-teams-workforce:rds","agent-teams-workforce:aws-solution-architect"]},"persona-profile-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:persona-profile-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:product-analytics"]},"phase-gate-enforcer":{"artifactCapable":false,"agentType":"agent-teams-workforce:phase-gate-enforcer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:cumulative-regression"]},"playwright-e2e-web-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:playwright-e2e-web-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:a11y-audit","agent-teams-workforce:cumulative-regression"]},"polyrepo-steward":{"artifactCapable":true,"agentType":"agent-teams-workforce:polyrepo-steward","skills":["agent-teams-workforce:subagent-contract"]},"power-tools-configuration-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:power-tools-configuration-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:lambda","agent-teams-workforce:secrets-manager"]},"prd-alignment-verifier":{"artifactCapable":true,"agentType":"agent-teams-workforce:prd-alignment-verifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"prd-creation-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:prd-creation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"prd-reality-reconciler":{"artifactCapable":true,"agentType":"prd-reality-reconciler","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"prd-trd-traceability-verifier":{"artifactCapable":true,"agentType":"agent-teams-workforce:prd-trd-traceability-verifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"prd-validation-analyst":{"artifactCapable":true,"agentType":"agent-teams-workforce:prd-validation-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"prd-validation-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:prd-validation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"prd-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:prd-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"production-readiness-review-facilitator":{"artifactCapable":false,"agentType":"agent-teams-workforce:production-readiness-review-facilitator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"race-condition-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:race-condition-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"react-native-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:react-native-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend"]},"readme-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:readme-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"recommendation-engine-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:recommendation-engine-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer"]},"regression-coverage-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:regression-coverage-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:artifact-handoff","agent-teams-workforce:cumulative-regression"]},"regression-impact-assessor":{"artifactCapable":true,"agentType":"agent-teams-workforce:regression-impact-assessor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:artifact-handoff","agent-teams-workforce:cumulative-regression"]},"requirements-clarifier":{"artifactCapable":false,"agentType":"agent-teams-workforce:requirements-clarifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:product-discovery"]},"requirements-conflict-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:requirements-conflict-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"root-cause-analyst":{"artifactCapable":false,"agentType":"agent-teams-workforce:root-cause-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:find-cause","agent-teams-workforce:test-failure-mindset"]},"run-ledger-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:run-ledger-writer","skills":["agent-teams-workforce:subagent-contract"]},"s3-data-lake-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:s3-data-lake-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:s3"]},"sdlc-pipeline-orchestrator":{"artifactCapable":false,"agentType":"agent-teams-workforce:sdlc-pipeline-orchestrator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:beads-contract"]},"security-architecture-designer":{"artifactCapable":true,"agentType":"security-architecture-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-security","agent-teams-workforce:iam","agent-teams-workforce:secrets-manager","agent-teams-workforce:aws-solution-architect"]},"security-test-case-designer":{"artifactCapable":true,"agentType":"agent-teams-workforce:security-test-case-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-security","agent-teams-workforce:cumulative-regression"]},"slo-error-budget-designer":{"artifactCapable":false,"agentType":"slo-error-budget-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:observability-designer","agent-teams-workforce:cloudwatch"]},"smoke-test-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:smoke-test-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"spec-authoring-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:spec-authoring-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"spec-currency-validator":{"artifactCapable":true,"agentType":"agent-teams-workforce:spec-currency-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"spec-decider":{"artifactCapable":false,"agentType":"spec-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:cove-prompt-design"]},"spec-freshness-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:spec-freshness-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"stakeholder-request-intake-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:stakeholder-request-intake-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"task-decomposer":{"artifactCapable":true,"agentType":"task-decomposer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:beads-contract"]},"task-decomposition-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:task-decomposition-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:beads-contract"]},"task-dependency-mapper":{"artifactCapable":true,"agentType":"task-dependency-mapper","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:beads-contract"]},"task-readiness-runner":{"artifactCapable":false,"agentType":"agent-teams-workforce:task-readiness-runner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:beads-contract"]},"tdd-unit-test-generator":{"artifactCapable":true,"agentType":"agent-teams-workforce:tdd-unit-test-generator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:tdd-guide","agent-teams-workforce:cumulative-regression"]},"test-command-resolver":{"artifactCapable":false,"agentType":"agent-teams-workforce:test-command-resolver","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:test-failure-mindset"]},"test-coverage-gap-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:test-coverage-gap-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"test-design-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:test-design-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"test-environment-orchestrator":{"artifactCapable":true,"agentType":"test-environment-orchestrator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:aws-mcp-setup"]},"test-failure-parser":{"artifactCapable":false,"agentType":"agent-teams-workforce:test-failure-parser","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:test-failure-mindset"]},"test-isolation-specialist":{"artifactCapable":true,"agentType":"agent-teams-workforce:test-isolation-specialist","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:tdd-guide","agent-teams-workforce:test-failure-mindset"]},"test-plan-strategy-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:test-plan-strategy-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"test-strategy-decider":{"artifactCapable":false,"agentType":"agent-teams-workforce:test-strategy-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cove-prompt-design"]},"trd-author":{"artifactCapable":true,"agentType":"trd-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"trd-authoring-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:trd-authoring-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"trd-decider":{"artifactCapable":false,"agentType":"agent-teams-workforce:trd-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"trd-validator":{"artifactCapable":false,"agentType":"agent-teams-workforce:trd-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"ubiquitous-language-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:ubiquitous-language-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"uml-diagram-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:uml-diagram-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:uml-diagramming","agent-teams-workforce:senior-architect"]},"user-guide-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:user-guide-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:roadmap-communicator"]},"user-story-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:user-story-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:beads-contract"]},"user-story-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:user-story-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"vector-search-embeddings-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:vector-search-embeddings-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:rag-architect"]},"webauthn-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:webauthn-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend","agent-teams-workforce:cognito"]},"workflow-command-runner":{"artifactCapable":false,"agentType":"agent-teams-workforce:workflow-command-runner","skills":[]},"worktree-independent-verifier":{"artifactCapable":false,"agentType":"agent-teams-workforce:worktree-independent-verifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"wsjf-scorer":{"artifactCapable":true,"agentType":"agent-teams-workforce:wsjf-scorer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-strategist","agent-teams-workforce:wsjf","agent-teams-workforce:beads-contract"]},"wsjf-scoring-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:wsjf-scoring-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-strategist","agent-teams-workforce:wsjf"]},"xcuitest-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:xcuitest-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:tdd-guide","agent-teams-workforce:cumulative-regression"]}}
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
  const schema = options && options.schema
  const artifactSchema = schema && schema.type === 'object' && Array.isArray(schema.required) && schema.required.length === 1 && schema.required[0] === 'artifactPath' && schema.properties && schema.properties.artifactPath && schema.properties.artifactPath.type === 'string'
  const outputMode = (options && options.outputMode) || (artifactSchema ? 'artifact' : 'inline')
  if (!['artifact', 'inline', 'machine'].includes(outputMode) || (outputMode === 'artifact') !== !!artifactSchema || (outputMode === 'machine' && (key !== 'workflow-command-runner' || !schema || !schema.properties || !schema.properties.bridge))) throw new Error(`OUTPUT_CONTRACT_MISMATCH: ${suppliedType}: ${outputMode}`)
  if (outputMode === 'artifact' && contract && !contract.artifactCapable) throw new Error(`ARTIFACT_CAPABILITY_MISMATCH: ${suppliedType} requires Write and Bash for its declared artifact contract`)
  const { outputMode: _mode, ...runtimeOptions } = options || {}
  options = { ...runtimeOptions, agentType: contract.agentType }
  const domainSkills = contract.skills.filter(name => !['agent-teams-workforce:subagent-contract', 'agent-teams-workforce:artifact-handoff'].includes(name))
  const contracts = outputMode === 'machine' ? '' : ownedCoreContracts + (outputMode === 'artifact' ? '\n\n' + ownedArtifactContract : '')
  const skillData = outputMode !== 'machine' && domainSkills.length ? `Declared domain skills: ${domainSkills.join(', ')}\n\n` : ''
  const identity = { invocationPath: fablePath, ordinal: fableAgentOrdinal++, agentType: (options && options.agentType) || null, label: (options && options.label) || null }
  const isFable = fableTypes.has(String(identity.agentType || '').replace(/^agent-teams-workforce:/, ''))
  const cutoffs = (fableRecovery && fableRecovery.cutoffs) || {}
  const cutoff = Number.isInteger(cutoffs[fablePath]) && cutoffs[fablePath] >= 0 ? cutoffs[fablePath] : 0
  const call = isFable && fableRecovery && identity.ordinal >= cutoff ? { ...options, model: 'opus' } : options
  fableEvent('start', identity)
  try {
    const result = await agent(`OUTPUT_MODE: ${outputMode}\n\n${contracts}\n\n${skillData}${prompt}`, call)
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

// Dispatch failures retain their identities and diagnostics; bounded retry policy is below.
const dispatchFailures = []
// The dispatch deaths belonging to the named phases (every death when none is named).
// A phase whose PRODUCING agents died has no artifact to judge, so its caller must not
// adjudicate it and must not spend a retry on it — that is the `dispatchFailed` contract.
function dispatchDeaths(...phases) {
  const named = phases.filter(Boolean)
  if (!named.length) return dispatchFailures.slice()
  const set = new Set(named)
  return dispatchFailures.filter((f) => set.has(f.phase))
}
function settleSchemaName(o) {
  if (typeof o.schemaName === 'string' && o.schemaName) return o.schemaName
  const s = o.schema
  if (!s || typeof s !== 'object') return null
  if (typeof s.title === 'string' && s.title) return s.title
  const req = Array.isArray(s.required) && s.required.length ? s.required : Object.keys(s.properties || {})
  return req.length ? `{${req.join(', ')}}` : null
}
function settleTranscript(err, label) {
  const e = err && typeof err === 'object' ? err : {}
  for (const k of ['transcriptPath', 'transcript', 'agentPath', 'logPath']) {
    if (typeof e[k] === 'string' && e[k]) return e[k]
  }
  const id = typeof e.agentId === 'string' && e.agentId ? e.agentId : null
  if (id) return `agent-${id}.jsonl in this run's workflow transcript directory`
  return `the agent-<id>.jsonl in this run's workflow transcript directory whose agent-<id>.meta.json description is ${JSON.stringify(label)}`
}
// Account exhaustion interrupts; transport failures use the caller's bounded retry policy.
function failureCause(err) { return dispatchFailureCause(err) }
function failureCauseFor(label) {
  const entry = dispatchFailures.slice().reverse().find((item) => item.label === label)
  return entry ? entry.cause || 'deterministic' : null
}
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
      dispatchFailures.push({ agentType: o.agentType || null, label: o.label || null, phase: o.phase || null, outcome: 'skipped', cause: 'deterministic', attempt, message: null, note: name + ': returned nothing', schema: settleSchemaName(o), transcript: settleTranscript(null, name) })
      log(name + ': returned nothing')
      return null
    } catch (err) {
      const plan = dispatchRetry(err, name, attempt, waitedMs, policy, typeof setTimeout === 'function')
      const message = String((err && err.message) || err)
      const entry = { agentType: o.agentType || null, label: o.label || null, phase: o.phase || null, outcome: 'threw', cause: plan.cause, attempt, message: message.slice(0, 300), note: name + ': ' + message.slice(0, 160), schema: settleSchemaName(o), transcript: settleTranscript(err, name) }
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

// ── A LIMIT BELONGS WHERE THE DATA IS MADE, AND AN OVERAGE IS A FLAG ─────────────
//
// Two rules, and they are different rules.
//
// ONE: a limit is never a JSON-Schema maxItems/minItems/maxLength. A schema bound cannot
// trim an over-long answer — the runtime rejects the WHOLE result, the caller receives a
// bare null it cannot tell from a dead agent, and the run halts. One really did, on 61
// items against a bound of 60, claiming files were unread that had been read. So a limit
// is STATED in the prompt and COUNTED here, once the result is in hand.
//
// TWO, and it decides whether a limit may be stated at all: a limit belongs at the layer
// where the data is CREATED, not where it is read. A dispatch that AUTHORS its output —
// criteria, findings, a persona, a draft — chooses its own volume, so a ceiling stated to
// it is a real instruction it can honour. A dispatch that READS or EXTRACTS — an
// inventory of what exists, the evidence found in a repository, the ids it was handed,
// what git printed — has a volume that is a property of the source. Telling it "at most
// N" instructs it to truncate, which loses information, or to lie. Those dispatches get
// NO stated ceiling; bounding what they may DRAW ON (which repository, which files) is
// the guard that works, and it already lives in their prompts. Where a read's volume
// genuinely ought to be smaller, the fix belongs upstream, in whatever made the data.
//
// BOTH kinds are still counted here, because a wildly unexpected count is exactly the
// signal worth having, and nothing is ever truncated, dropped, reordered or summarised at
// any multiple. The count is a GRADUATED FLAG: modestly over the expected figure is
// ordinary variation and reads as an observation; at SCRUTINY_MULTIPLE times it or more,
// the shape is no longer variation — it is what padding, a misread assignment or
// duplicated entries look like — and it is logged prominently so a person looks. 2x is
// the threshold because a single band has to sit above the honest overshoots this
// pipeline actually produces (61 against 60 is 1.02x; the worst recorded lens overshoot
// is well under 1.5x) and below the runaway enumerations the limits exist to catch. It is
// a flag for a person, never a thing the code acts on: neither branch alters control flow.
//
// This block is identical in every workflow script on purpose. Workflow scripts have no
// import mechanism, so a shared helper is shared by being the same text everywhere.
const limitFindings = []
const SCRUTINY_MULTIPLE = 2
function checkLimit(where, what, value, expected, min) {
  const n = Array.isArray(value) ? value.length : typeof value === 'string' ? value.length : null
  if (n === null) return value
  if (typeof expected === 'number' && n > expected) {
    const ratio = expected > 0 ? n / expected : Infinity
    const scrutinise = ratio >= SCRUTINY_MULTIPLE
    limitFindings.push({ where, what, count: n, expected, ratio: Math.round(ratio * 100) / 100, severity: scrutinise ? 'scrutinise' : 'observation' })
    log(
      scrutinise
        ? `⚠ ${where}: ${what} returned ${n} where ${expected} was expected — ${Math.round(ratio * 10) / 10}x. Every item is kept and nothing downstream changes, but a count this far over is the shape of padding, a misread assignment or duplicated entries: worth a look.`
        : `${where}: ${what} returned ${n} where ${expected} was expected — over by ${n - expected}; every item is kept.`
    )
  }
  if (typeof min === 'number' && n < min) {
    limitFindings.push({ where, what, count: n, expected: min, severity: 'under' })
    log(`${where}: ${what} returned ${n}, under the ${min} this asked for — carried through as returned.`)
  }
  return value
}

// args: { bead: { id, title, description, repoPath?, repoHints?, inventoryCommand? } }
//
// `repoPath` is the repository when the caller knows it. It is NOT required: a Bug is
// filed against a SYMPTOM, and which repository the defect lives in is a finding of the
// diagnosis — the blast radius names the code at fault, and the code at fault is in a
// repository. So when no repoPath is supplied the diagnosing agent is told to LOCATE it,
// from the symptom, the repository inventory (`inventoryCommand`) and any names the caller merely
// suspects (`repoHints`), and to report it CONFIRMED — an absolute path that exists and is
// a git repository — or to report that it could not. A guessed repository is not an
// answer: bug-fix validates what comes back and refuses what it cannot use.
const __a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const bead = __a.bead || {}
const repoKnown = !!String(bead.repoPath || '').trim()
const repo = repoKnown ? bead.repoPath : '(NOT KNOWN — locating it is part of this diagnosis; see below)'

const repoHints = (Array.isArray(bead.repoHints) ? bead.repoHints : []).map((h) => String(h == null ? '' : h).trim()).filter(Boolean)
const inventoryCommand = String(bead.inventoryCommand || '').trim()
const LOCATE_REPO =
  repoKnown
    ? ''
    : `

THE REPOSITORY IS NOT KNOWN, AND FINDING IT IS PART OF THIS DIAGNOSIS. Locate the repository whose source contains the code at fault. Start from the symptom and the blast radius; list the repositories this project has and where each is checked out on this machine ${inventoryCommand ? `by running \`${inventoryCommand}\`` : 'by asking the polyrepo-steward'}${repoHints.length ? `; the caller suspects it may be one of: ${repoHints.join(', ')} — a suspicion, not an answer` : ''}. Report repoPath as the ABSOLUTE path of that repository — the repository itself, not a worktree beneath it and not a subdirectory — and only after you have CONFIRMED the directory exists and is a git repository. If you cannot confirm one, report repoPath as an empty string and say in repoResolution which repositories you examined and why none was confirmed. A guessed repository sends a pipeline that writes code, commits and opens a pull request into a tree nobody chose; an honest empty answer does not.`

phase('Triage')

// What a bug is EXPECTED to contain, used to flag a count worth a look and stated to
// nobody. How many distinct defects sit behind one symptom is a fact about the code, not
// a volume the analyst chooses, so capping it would only buy a shorter list than the
// truth. A bug that really does carry twenty has an answer already — the `needs-prd`
// sizing step below rules it a redesign — and that ruling needs the full enumeration to
// be made on. The MINIMUM is stated, because "at least one" demands completeness rather
// than brevity: a diagnosis with no enumerated defect leaves the contract with nothing
// to cover.
const DEFECTS_EXPECTED = 20

// 1) Diagnosis — read-only analyst. Separation of duties: this agent does not fix.
const analysis = await settleAgent(
  `Diagnose this bug. You are READ-ONLY — do not change code. Work within the repository at: ${repo}

Bug ${bead.id || ''}: ${bead.title || ''}
${bead.description || ''}

Deliver:
- reproduction: the minimal, concrete steps/conditions that trigger the defect.
- rootCause: the precise mechanism and code location (file:line where possible), as prose.
- defects: the SAME root cause, ENUMERATED — one entry per distinct defect, each with a short stable id (D1, D2, ...), its mechanism, and the file and line where it lives. One bead frequently contains several distinct defects, and returning them only as one paragraph of prose leaves everything downstream with nothing countable: the acceptance criteria are then written against a blob and cannot be bounded, indexed, or checked for coverage. Return exactly one entry per defect you would fix separately — not one per file, not one per symptom. AT LEAST ONE entry, always: a bug with no enumerated defect leaves the contract below with nothing to cover. There is no ceiling on the count — a bug that honestly contains fifteen distinct defects has fifteen, and the answer to that is the \`needs-prd\` sizing below, never a shorter list.
- affectedFiles: the files that must change to fix it (paths).
- blastRadius: the callers, flows, and services impacted if the bug ships or the fix regresses.
- surfaces: which surfaces from the CLOSED SET below the fix actually touches. This decides which specialist test writers run downstream, so it is a real decision, not a label:
    api-contract           a published REST/GraphQL/event schema that consumers depend on
    event-chain            the event delivery path between publisher and consumer
    auth                   authentication, authorization, or permission evaluation
    performance            a stated performance budget or latency/throughput requirement
    web-ui                 web user interface
    ios                    native iOS
    android                native Android
    cross-platform-mobile  React Native or other cross-platform mobile
    ml                     matching, recommendation, ranking, or embeddings
    data-pipeline          ETL, CDC, or stream processing
  Return ONLY surfaces the CHANGE touches — not surfaces the surrounding code happens to sit near. Return an empty list when the fix is confined to internal logic, which is the common case. Each surface you name costs a full additional test-authoring agent; each one you omit leaves that surface with no specialist coverage.
- repoPath: the ABSOLUTE path of the repository the defect lives in${repoKnown ? ' — echo the repository you were given' : ''}.
- repoResolution: how you confirmed the repository${repoKnown ? ' (one line; it was supplied)' : ', or why none could be confirmed'}.${LOCATE_REPO}`,
  {
    label: 'triage:diagnosis',
    phase: 'Triage',
    agentType: 'agent-teams-workforce:root-cause-analyst',
    schema: {
      type: 'object',
      additionalProperties: false,
      // The repository is REQUIRED when it is not known: it is the finding the caller builds
      // in, and an omitted field reads the same as an honest "could not locate" (empty string).
      required: ['reproduction', 'rootCause', 'defects', 'affectedFiles', 'blastRadius', 'surfaces', ...(repoKnown ? [] : ['repoPath', 'repoResolution'])],
      properties: {
        reproduction: { type: 'string' },
        rootCause: { type: 'string' },
        // At least one — stated in the brief above, and counted once the result is in
        // hand. Never bound here: a bound on this list answers a one-over enumeration by
        // destroying the reproduction, the root cause and the repository resolution along
        // with it, and triage then has nothing at all.
        defects: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['id', 'mechanism'],
            properties: {
              id: { type: 'string' },
              mechanism: { type: 'string' },
              file: { type: 'string' },
              line: { type: 'integer' },
            },
          },
        },
        affectedFiles: { type: 'array', items: { type: 'string' } },
        blastRadius: { type: 'string' },
        repoPath: { type: 'string' },
        repoResolution: { type: 'string' },
        surfaces: {
          type: 'array',
          items: {
            type: 'string',
            enum: [
              'api-contract',
              'event-chain',
              'auth',
              'performance',
              'web-ui',
              'ios',
              'android',
              'cross-platform-mobile',
              'ml',
              'data-pipeline',
            ],
          },
        },
      },
    },
  }
)

// A dead dispatch is not a diagnosis, a sizing or a contract. Each death returns the
// `dispatchFailed` shape every other mini returns, so the caller reports it under the
// environment stage and never checkpoints it as a contract.
const triageDied = (what) => {
  const deaths = dispatchDeaths('Triage')
  const reason = `the triage ${what} returned nothing — ${deaths.map((f) => f.note).join('; ') || 'no dispatch was recorded'}`
  log(`Triage: ${reason}`)
  return { ok: false, dispatchFailed: true, dispatchFailures: deaths, reason }
}
if (!analysis) return dispatchOutcome(triageDied('diagnosis'))

// 1b) SIZING — is this a fix, or a redesign wearing a bug ticket?
//
// The repository the fix is built in. A supplied one is the answer; otherwise it is what
// the diagnosis LOCATED, reported as a finding beside the blast radius. Never a guess made
// here: an empty string is carried as null and the caller refuses to write without one.
// Measured here so the count is observed on the needs-prd path too. An observation only:
// every defect is carried forward, and the `at least one` is the only thing asked for.
checkLimit('Triage', 'defects', Array.isArray(analysis.defects) ? analysis.defects : [], DEFECTS_EXPECTED, 1)
// A diagnosis that enumerated no defect still names a root cause, and that root cause is the
// one defect: it becomes D1, so the contract's coverage join has an id to resolve against
// instead of criteria pointing at a defect nobody listed.
const enumerated = (Array.isArray(analysis.defects) ? analysis.defects : []).filter((d) => d && d.id)
const defects = enumerated.length ? enumerated : [{ id: 'D1', mechanism: String(analysis.rootCause || 'the diagnosed root cause') }]
const resolvedRepoPath = repoKnown ? bead.repoPath : String((analysis && analysis.repoPath) || '').trim() || null
if (!repoKnown) log(`Triage: repository ${resolvedRepoPath ? `located at ${resolvedRepoPath}` : 'NOT located'} — ${(analysis && analysis.repoResolution) || 'no resolution reported'}`)

// A bug can be worked directly, or it can turn out to need a PRD and an Epic. The
// difference matters: the fix path has no PRD validation, no architecture ruling,
// and no spec — so a defect whose honest remedy is "redesign how this service
// stores its data" would get that redesign built by an implementer, unreviewed,
// on the authority of a bug ticket. That is how an architecture decision gets made
// by accident, which is the failure this workforce exists to prevent.
//
// A DIFFERENT agent sizes it — the diagnostician has just invested in a root cause
// and is the worst-placed judge of whether fixing it is too big.
const sizing = await settleAgent(
  `Size this bug. It has been diagnosed; decide whether its honest remedy is a FIX or a REDESIGN. You are READ-ONLY and you are NOT proposing the remedy — only sizing it.

Answer "needs-prd" when the honest fix would: change a public contract or event schema, alter the data model, cross a service boundary, require an architecture decision the effective architecture does not cover, or amount to rebuilding a component rather than correcting it.

Answer "fix" when the defect is a mistake in existing behavior that can be corrected within the current design — the common case. Do not inflate a real bug into a project; most bugs are bugs.

The cost of each error is not symmetric. Calling a redesign a "fix" ships an unreviewed architecture change on a bug ticket. Calling a fix a "redesign" costs a PRD nobody needed. Prefer "fix" when genuinely balanced, and "needs-prd" when the remedy touches a contract, a schema, or a boundary.

Bug ${bead.id || ''}: ${bead.title || ''}
${bead.description || ''}

Root cause found: ${analysis.rootCause}
Files that must change: ${(analysis.affectedFiles || []).join(', ') || 'n/a'}
Blast radius: ${analysis.blastRadius}`,
  {
    label: 'triage:sizing',
    phase: 'Triage',
    agentType: 'architecture-boundary-guardian',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['scope', 'rationale'],
      properties: {
        scope: { type: 'string', enum: ['fix', 'needs-prd'] },
        rationale: { type: 'string' },
        contractsTouched: { type: 'array', items: { type: 'string' } },
      },
    },
  }
)

// A missing verdict must not silently become "fix" — that is the expensive error — and it
// is not a "needs-prd" ruling either, so a dead sizing stops the run as a dispatch death.
if (!sizing) return dispatchOutcome(triageDied('sizing'))
const scope = sizing.scope || 'needs-prd'
const scopeRationale = sizing.rationale || 'sizing returned no rationale'
if (scope === 'needs-prd') {
  log(`Bug ${bead.id || ''} sized as NEEDS-PRD: ${scopeRationale}`)
  return dispatchOutcome({
    bead,
    repoPath: resolvedRepoPath,
    repoResolution: (analysis && analysis.repoResolution) || null,
    scope,
    scopeRationale,
    contractsTouched: sizing.contractsTouched || [],
    reproduction: analysis.reproduction,
    rootCause: analysis.rootCause,
    defects,
    affectedFiles: analysis.affectedFiles,
    blastRadius: analysis.blastRadius,
    acceptanceCriteria: [],
    ...(limitFindings.length ? { limitFindings } : {}),
    note:
      'This defect needs a PRD and an Epic, not a fix. Its honest remedy changes a contract, ' +
      'schema, or boundary, and the fix path has no PRD validation, no architecture ruling, and ' +
      'no spec to review it against. Promote it: /agent-teams-workforce:start-prd, or dispatch ' +
      'prd-to-spec with { request } built from the diagnosis above. Promotion is a human decision.',
  })
}

// 2) Expected-behavior contract — the "spec-lite" a bug lacks, as testable AC.
//    A different agent than the diagnostician (no self-authoring of its own contract).
//
// SCOPED BY CONSTRUCTION. This step used to receive a prose root cause with no expected
// range, no defect index, and no scope rule — and a four-defect bug produced eighteen-plus
// criteria, several of them repo-wide greps. The downstream coverage reviewer then
// blocked on partial coverage of criteria Red could never legitimately turn red, and the
// Red gate exhausted without one line of production code being written.
//
// The defect index is what fixed that: coverage becomes an exact join — every defectId
// resolves, every defect has at least one criterion — instead of a judgment call, and it
// is computed below from the result. The range is stated to the writer and OBSERVED
// afterwards; it is never a schema bound, because a bound does not trim an over-long
// list, it destroys the whole contract and halts the bug fix at triage.
// Unique, because they become a schema enum below and a repeated enum value is an invalid
// schema: a diagnosis that reused an id would otherwise kill the contract writer's dispatch.
const defectIds = [...new Set(defects.map((d) => String(d.id)))]
const AC_MIN = Math.max(1, defectIds.length)
const AC_MAX = Math.max(2, defectIds.length * 2)
log(`Triage: ${defectIds.length} defect(s) — acceptance criteria expected in the range ${AC_MIN}..${AC_MAX}`)

const contractSchema = (ids) => ({
  type: 'object',
  additionalProperties: false,
  required: ['acceptanceCriteria'],
  properties: {
    acceptanceCriteria: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['defectId', 'given', 'when', 'then'],
        properties: {
          defectId: ids.length ? { type: 'string', enum: ids } : { type: 'string' },
          given: { type: 'string' },
          when: { type: 'string' },
          then: { type: 'string' },
        },
      },
    },
    // Sibling output, deliberately NOT passed to tdd-red. A repo-wide invariant is a
    // lint rule or a pre-commit hook, landed by the path that already commits — the
    // coverage reviewer never sees it and therefore structurally cannot block the
    // Red gate on a criterion Red can never turn red.
    lintRules: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['pattern', 'rationale'],
        properties: {
          pattern: { type: 'string' },
          rationale: { type: 'string' },
          scope: { type: 'string' },
        },
      },
    },
  },
})
const contract = await settleAgent(
  `Write the expected-behavior contract for this bug fix as testable given/when/then acceptance criteria — the correct behavior the fix must satisfy and that a failing test will encode. Do NOT write code.

ONE OR TWO CRITERIA PER DEFECT, and every criterion carries the id of the defect it covers. Every defect below must have at least one. Between ${AC_MIN} and ${AC_MAX} criteria in total — if you are heading past ${AC_MAX} you are enumerating variants of one behaviour, and every criterion you write is one Red must encode.

A CRITERION DESCRIBES AN EXECUTION, NOT THE REPOSITORY. Apply this test to everything you are about to write: **if it would still be checkable with the change reverted, it is not an acceptance criterion.** "No occurrence of \`redis://\` anywhere in the repo" passes that test trivially — it is checkable before, during and after the fix, against code nobody touched — which is exactly what makes it a LINT RULE wearing an acceptance-criterion costume. Return those in \`lintRules\` instead. They are real and they are worth enforcing; they are just not something a failing test can encode, and putting them here blocks the build on a grep no Red phase can legitimately make fail.

Bug ${bead.id || ''}: ${bead.title || ''}
Reproduction: ${analysis.reproduction}
Root cause: ${analysis.rootCause}
Files the fix must change: ${(analysis.affectedFiles || []).join(', ') || 'n/a'}

Defects to cover (use these ids exactly):
${defects.map((d) => `- ${d.id}: ${d.mechanism}${d.file ? ` [${d.file}${d.line ? `:${d.line}` : ''}]` : ''}`).join('\n')}`,
  {
    label: 'triage:expected-behavior',
    phase: 'Triage',
    agentType: 'acceptance-criteria-writer',
    schema: contractSchema(defectIds),
  }
)

// A contract with no criteria gives Red nothing to encode, so a dead writer stops here.
if (!contract) return dispatchOutcome(triageDied('expected-behavior writer'))

// Coverage is an exact join, not a judgment: every enumerated defect must have at least
// one criterion pointing at it.
const authoredAc = (Array.isArray(contract.acceptanceCriteria) ? contract.acceptanceCriteria : []).filter(Boolean)
const coveredIds = () => new Set(authoredAc.map((x) => String(x.defectId || '')))
// A defect with no criterion gets no test and no fix, so the writer is asked ONCE more, for
// those defects only — a re-dispatch with materially different input, not a blind retry.
const firstUncovered = defectIds.filter((id) => !coveredIds().has(id))
if (firstUncovered.length) {
  log(`Triage: defect(s) with no acceptance criterion: ${firstUncovered.join(', ')} — asking the writer to cover them`)
  const gap = await settleAgent(
    `The expected-behavior contract for this bug fix covers every defect below EXCEPT the ones listed. Write one or two testable given/when/then acceptance criteria for EACH listed defect, and nothing else — no criterion for a defect not listed, no repo-wide grep (return one in \`lintRules\` if you find one). Do NOT write code.

Bug ${bead.id || ''}: ${bead.title || ''}
Reproduction: ${analysis.reproduction}
Root cause: ${analysis.rootCause}

Defects still uncovered (use these ids exactly):
${defects.filter((d) => firstUncovered.includes(String(d.id))).map((d) => `- ${d.id}: ${d.mechanism}${d.file ? ` [${d.file}${d.line ? `:${d.line}` : ''}]` : ''}`).join('\n')}`,
    {
      label: 'triage:expected-behavior-uncovered',
      phase: 'Triage',
      agentType: 'acceptance-criteria-writer',
      schema: contractSchema(firstUncovered),
    }
  )
  // Defects with no criterion would ship with no test and no fix, so a dead follow-up is a
  // dispatch death like any other triage step, not a contract to build on.
  if (!gap) return dispatchOutcome(triageDied('expected-behavior writer (uncovered defects)'))
  authoredAc.push(...(Array.isArray(gap.acceptanceCriteria) ? gap.acceptanceCriteria : []).filter(Boolean))
  if (Array.isArray(gap.lintRules)) {
    contract.lintRules = [...(Array.isArray(contract.lintRules) ? contract.lintRules : []), ...gap.lintRules]
  }
}
const uncoveredDefects = defectIds.filter((id) => !coveredIds().has(id))
// Asked twice and still uncovered: those defects would get no test and no fix while the run
// reported the bug fixed, so the contract is refused rather than built. The writer answered
// both times, so this is not a dispatch death; it is reported under triage, naming the defects.
if (uncoveredDefects.length) {
  const reason = `the expected-behavior contract still covers no criterion for defect(s) ${uncoveredDefects.join(', ')} after the writer was asked for exactly those — a fix built on it would leave them untested and unfixed`
  log(`⚠ Triage: ${reason}`)
  return dispatchOutcome({
    ok: false,
    contractIncomplete: true,
    reason,
    uncoveredDefects,
    bead,
    repoPath: resolvedRepoPath,
    repoResolution: (analysis && analysis.repoResolution) || null,
    scope,
    scopeRationale,
    reproduction: analysis.reproduction,
    rootCause: analysis.rootCause,
    defects,
    affectedFiles: analysis.affectedFiles,
    blastRadius: analysis.blastRadius,
    acceptanceCriteria: authoredAc,
    ...(limitFindings.length ? { limitFindings } : {}),
  })
}
// The range is an expectation, not a gate: every criterion is carried through either way.
checkLimit('Triage', `acceptance criteria for ${defectIds.length} defect(s)`, authoredAc, AC_MAX, AC_MIN)
const lintRules = (Array.isArray(contract.lintRules) ? contract.lintRules : []).filter(Boolean)
if (lintRules.length) log(`Triage: ${lintRules.length} repo-wide invariant(s) routed to lint, not to the Red phase`)

return dispatchOutcome({
  bead,
  repoPath: resolvedRepoPath,
  repoResolution: (analysis && analysis.repoResolution) || null,
  scope,
  scopeRationale,
  reproduction: analysis.reproduction,
  rootCause: analysis.rootCause,
  defects,
  affectedFiles: analysis.affectedFiles,
  blastRadius: analysis.blastRadius,
  // Consumed by tdd-red to DERIVE its test writers. Empty means unit tests only,
  // which is the correct answer for a fix confined to internal logic.
  surfaces: analysis.surfaces || [],
  acceptanceCriteria: authoredAc,
  uncoveredDefects: [],
  ...(limitFindings.length ? { limitFindings } : {}),
  // Repo-wide invariants the writer routed out of the acceptance criteria. Recorded in the
  // run journal; no phase reads them, and they are never handed to the Red phase.
  lintRules,
})
