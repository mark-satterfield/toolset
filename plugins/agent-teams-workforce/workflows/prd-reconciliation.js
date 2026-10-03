export const meta = {
  name: 'prd-reconciliation',
  description:
    'Leaf mini — per-repository detailing of an approved architecture delta. One read-only session compares each delta item placed in one repository (one element the delta shows) with the code on that repository\'s main, gives it one status — add, modify, remove, done, or planned-elsewhere — each citing file:line (planned-elsewhere also names the open bead that plans it), gives each ui item its design source — bundle (a single-artifact cds bundle the owner supplied in the packages directory packages it; the newest bundle of a kind and slug is the supplied one), cds (it changes design and no bundle packages it, so it is designed with the CDS design system) or none (it changes no design) ; a bundle or cds item also names its artifact (kind and slug, as a bundle.json names it), so a mockup supplied later is found when the Task is built — and reports upstream dependency changes. The script fails the run, naming the items, when an item is missing or listed twice, carries a status outside that set, or lacks its citation; a failed detailing blocks that repository\'s Spec. The session saves the detailing as recon-<slug>.json and returns no item content; depscore.py recon-facts checks the saved file on disk and returns only the facts the callers branch on (the ids that make work, the ids that do not, each ui work item\'s design source with the bundle and build spec of a bundle item, whether dependencies are current), and the callers hand the file path to the sessions that read it. A saved result is replayed through the same check instead of dispatching the session; a saved file that cannot be read or is not a usable detailing stops the run, naming the file, and the repository is never detailed again behind it.',
  phases: [{ title: 'Detailing', detail: 'one read-only session compares each delta item placed in the repository with the code on its main, and checks upstream dependencies' }],
}
// ===== SHARED BLOCK fable — BEGIN (canonical: scripts/shared-blocks/fable.js; edit there, then: node scripts/shared-blocks.mjs --write) =====
const ownedCoreContracts = "---\nname: subagent-contract\ndescription: >-\n  Shared contract for bounded specialist assignments: preserve role and scope, follow\n  the caller's response format, retain verifiable artifacts, and report incomplete work explicitly.\nuser-invocable: false\n---\n\n# Subagent Contract\n\n## Caller contract comes first\n\nFollow the caller's exact response schema and artifact protocol. Do not prepend `STATUS`, restate the task, add report fields, or append commentary to a machine-consumed response. Put evidence, findings, progress and blockers only in the artifacts or fields the caller provides. An artifact's on-disk schema and the response-reference schema serve different purposes; do not return the artifact body when the caller requests only its path.\n\nWhen an executable submission/checkpoint tool is supplied, use it to validate the authored result, compute bindings and construct the response. Return its successful response unchanged through the requested channel. Do not manually manufacture completion flags or hashes. Structural validation proves neither semantic correctness nor review approval. On failure preserve work and report the exact remaining work or blocker through the caller's supported mechanism; never send a success reference for an incomplete assignment. If the supplied protocol has no failure channel, report that incompatibility to the caller rather than inventing a successful response.\n\nOnly when the caller supplies no response format, use `STATUS: DONE` or `STATUS: BLOCKED` with a concise description of deliverables and verification, or the blocker and what is needed. Claim DONE only when the assigned work is complete and verified. No separate preliminary restatement or generic final report is required.\n\n## Role and scope\n\n- Perform only the role assigned in the agent definition and task. Do not invent requirements, select downstream work or enlarge your authority.\n- Identify the minimal relevant files, artifacts and decisions. Use only allowed tools and preserve file ownership. Read-only reviewers may write caller-authorized result/checkpoint artifacts, never source artifacts.\n- An explicit assignment to repair all baseline failures in an affected repository includes pre-existing failures there. Preserve test-author ownership and required checks; this does not authorize unrelated cleanup, other repositories or invented external resources.\n- Prefer small, reversible changes unless the assignment requires broader change. Report material actions and their outcomes in the existing evidence channel, without adding fields to a fixed schema.\n- Missing required context is a named dependency, not permission to guess. Distinguish facts, justified assumptions and unresolved questions; do not silently complete only the easy portion.\n\n## Skills and authoritative artifacts\n\nRead canonical skill content already delivered in the prompt; do not reload it solely because its name also appears in frontmatter. Assess which other declared skills apply and load those through the Skill tool using their exact names. A name alone is not delivered content. A missing required skill is an explicit dependency; do not substitute recollection. Note material applicability decisions only in existing progress/evidence channels that permit them, never by expanding the return schema.\n\nRead the actual relevant source sections and connected contracts. Shared Markdown, vault notes, diagrams, schemas and JSON stay authoritative at their paths; summaries guide navigation and do not replace source verification. Observe assigned read/edit/create ownership. Preserve content unless its change is assigned. Pass references rather than copying whole documents between agents. When exact copying is required, use deterministic file tools rather than model transcription. Use version/provenance where relevant; do not require hashes merely for semantic editing.\n\nFor durable authoring, checkpoint meaningful progress using the caller's location and executable mechanism where supplied. Record completed work, remaining work and artifact references; blocked progress names the dependency and reason. Checkpoints are progress, not accepted results. On resume verify the checkpoint against actual artifacts and finish missing work without regenerating valid completed documents.\n\n## Resource use and incremental review\n\n- Use tokens conscientiously without compromising required correctness, completeness, safety or evidence. Before a material optional expansion, identify its unresolved need and expected benefit in existing progress. Routine tools need no justification. Do not add a report, review pass, token quota or human approval gate for this rule; omit optional work with no concrete benefit.\n- Makers and reviewers use the same applicable requirements, constraints and completion criteria. Review determines actual correctness, including passing sound work; finding more failures is not success. Do not invent requirements or turn stylistic preferences into blocking defects. Preserve necessary safety and regression checks.\n- Use the caller's finding format to identify the affected location, requirement/dependency at risk, observed evidence and actionable correction with a verifiable pass condition. Distinguish defects, missing evidence and proposed new requirements. Never claim unperformed checks passed.\n- Revise original artifacts incrementally. Retain valid work and applicable evidence. Rereview changed scope and affected dependencies; reopen accepted work only when new evidence or demonstrated impact invalidates its earlier evidence, and state why. Preserve required independent review.\n\n## AWS evidence authority\n\nFor applicable AWS architecture choices, consult actual AWS MCP Server documentation and relevant AWS skills, including applicable Well-Architected principles. Retain source references and the concrete tradeoffs. Existing generated architecture and model recollection do not establish correctness. Makers and reviewers use this same evidence criterion.\n\nApply guidance to stated requirements, deployment, usage and cost constraints rather than hypothetical scale. Surface conflicts with product requirements or owner constraints; do not silently substitute a preferred AWS pattern. Missing required MCP/skill access is a named blocker or uncertainty, never a passed check. Coordinators may research and route AWS questions, but cannot author or approve designs.\n\n\n---\nname: artifact-handoff\ndescription: Share authoritative documents, diagrams and JSON by artifact path, with format-specific validation and resumable checkpoints; never retype full payloads between agents.\n---\n\nShared documents, Markdown, diagrams and other artifacts stay in their authoritative files. Pass paths and brief task context; recipients read the actual files. A summary is navigation, never a substitute source. Edit only explicitly assigned files; preserve accepted work. Do not retype an entire document into another agent's prompt or machine response. Use existing deterministic file operations for exact copies when a copy is explicitly required.\n\nKeep the caller-specified checkpoint current after meaningful work: status, task, completed work, remaining work and artifact paths. On resume read the checkpoint and referenced artifacts, verify current state and complete remaining work. A checkpoint is progress evidence, never acceptance or permission to omit validation.\n\nFor JSON, write the caller's requested JSON object once to its exact candidate path. Use the supplied artifact schema; do not confuse it with the small return schema. Preserve existing completed work and inspect an existing candidate before continuing interrupted work. Return only the candidate path using the caller's structured return schema. Never copy the full artifact into StructuredOutput or prose.\n\nThe workflow's named command runner invokes `scripts/portfolio/jsonartifact.py` with the expected candidate, final path and schema. The script rejects duplicate keys, invalid JSON, schema violations and changes to already accepted results. It writes canonical JSON and an integrity receipt; downstream scripts verify the receipt. Candidates stay outside the accepted result directory. A failed candidate is never treated as a completed step.\n\nThe command runner runs only the exact checked command supplied by the workflow. Validation failure is reported explicitly; it does not authorize rewriting another producer's content or repeating a successful administrative command. Existing legacy artifacts are preserved.\n\nFor Markdown and diagrams, `jsonartifact.py --document PATH` verifies the actual nonempty UTF-8 file and returns its path, raw-byte SHA-256, length and format. It never copies or rewrites the document. This receipt identifies the reviewed version; it is not a semantic quality verdict and does not prohibit later authorized edits. Keep structured metadata separate and refer to the document path instead of embedding its contents.\n\nCandidate completion checkpoints bind the exact candidate path, expected schema hash and caller revision. The workflow derives that revision from actual source-file/corpus byte fingerprints and assignment context; a path alone is not freshness evidence. Changed inputs require a new candidate revision. A saved complete result for the same revision is reused; it is never silently replaced. Fingerprints exclude the producer’s assigned output files to preserve interruption recovery.\n\n## Executable producer contract\n\nUse the caller's canonical schema for both production and review; architecture uses [writer](schemas/architecture-writer.schema.json) and [reviewer](schemas/architecture-review.schema.json). Never maintain a second schema in prose. The [checkpoint schema](schemas/checkpoint.schema.json) is shared by producer status commands.\n\nResolve `scripts/portfolio/artifactcontract.py` from this plugin's root (two directories above this skill). The workflow supplies the candidate path, canonical schema and input revision. Pass exactly one of `--schema-file PATH` or `--schema-json JSON`; both use identical strict parsing, validation and canonical hashing. Prefer the schema file when the caller supplies one. Author a small progress JSON file with `task`, `completed`, `remaining`, and `artifacts`; add `reason` when blocked. Do not put binding hashes or completion flags in that file: the helper computes them.\n\n```bash\npython3 \"$PLUGIN_ROOT/scripts/portfolio/artifactcontract.py\" checkpoint --candidate \"$CANDIDATE\" --schema-file \"$SCHEMA\" --revision \"$REVISION\" --progress-file \"$PROGRESS\" --status in-progress\npython3 \"$PLUGIN_ROOT/scripts/portfolio/artifactcontract.py\" complete --candidate \"$CANDIDATE\" --schema-file \"$SCHEMA\" --revision \"$REVISION\" --progress-file \"$PROGRESS\"\npython3 \"$PLUGIN_ROOT/scripts/portfolio/artifactcontract.py\" status --candidate \"$CANDIDATE\" --schema-file \"$SCHEMA\" --revision \"$REVISION\"\n```\n\nFor a dependency you cannot satisfy, checkpoint with `--status blocked` and its exact `reason` and remaining work. Do not mark incomplete reasoning complete merely to satisfy the schema. `complete` requires no remaining work, validates strict JSON against the canonical schema, canonicalizes the candidate and writes its bound checkpoint. Return only the candidate reference after that command succeeds. `validate` performs schema validation without mutation. Invalid commands return exit 2 with an explicit error.\n\n`complete-unaccepted` means structurally ready for the workflow's existing acceptance operation, not technically correct, approved, or shipped. Reviewers read the authoritative artifacts and independently judge evidence; mechanically valid metadata cannot establish their correctness. Status detects changed candidate bytes and changed input/schema bindings. Resume `in-progress`/`blocked` work from its actual artifacts; do not restart completed reasoning or silently retry an unchanged blocker.\n\nThe coordinator may use `scripts/portfolio/artifactpublish.py --record-argv-json JSON -- <jsonartifact acceptance arguments>` to validate/publish and record provenance in one deterministic invocation. The recorder receives argv, not shell text, and must name the accepted artifact. Pending or rejected candidates are never recorded; recorder failure reports failure and retains the accepted artifact for recovery. This replaces separate administrative agent calls without replacing specialist reasoning or independent review.\n\nFor the actual handoff use `submit` with the same arguments as `complete`: it validates and writes the checkpoint, then emits exactly the response object `{\"artifactPath\":\"...\"}`. Return that object unchanged. The schema describes the on-disk candidate; the response contains only its reference. A failed submission emits an error and never writes a new completion checkpoint. When the caller supplies `--files-root ROOT --files-field FIELD`, submission also verifies every path in that candidate field is relative to ROOT, stays inside it after symlink resolution, and names a nonempty regular file. These are declared authored outputs, not all assigned or future files. `--progress-artifacts-root ROOT` additionally checks explicitly declared progress artifact paths inside that root; use it only when the caller establishes that scope. These checks establish file existence and structure, not whether the reasoning is correct.\n"
const ownedAgentContracts = {"acceptance-criteria-reviewer":{"agentType":"agent-teams-workforce:acceptance-criteria-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"acceptance-criteria-writer":{"agentType":"acceptance-criteria-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"accessibility-validator":{"agentType":"agent-teams-workforce:accessibility-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:a11y-audit","agent-teams-workforce:senior-frontend"]},"advantage-evaluator":{"agentType":"agent-teams-workforce:advantage-evaluator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"adversarial-critique-adjudicator":{"agentType":"agent-teams-workforce:adversarial-critique-adjudicator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-security"]},"adversarial-review-loop-supervisor":{"agentType":"agent-teams-workforce:adversarial-review-loop-supervisor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"ambiguity-detector":{"agentType":"agent-teams-workforce:ambiguity-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"android-compose-implementer":{"agentType":"agent-teams-workforce:android-compose-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"api-contract-designer":{"agentType":"api-contract-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer","agent-teams-workforce:aws-solution-architect"]},"api-documentation-writer":{"agentType":"agent-teams-workforce:api-documentation-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer"]},"api-gateway-cdk-implementer":{"agentType":"api-gateway-cdk-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-gateway","agent-teams-workforce:aws-cdk-development"]},"api-specification-author":{"agentType":"api-specification-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer"]},"appsync-cdk-implementer":{"agentType":"agent-teams-workforce:appsync-cdk-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cdk-development"]},"appsync-client-subscription-implementer":{"agentType":"agent-teams-workforce:appsync-client-subscription-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend"]},"architecture-boundary-guardian":{"agentType":"architecture-boundary-guardian","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect"]},"architecture-conformance-reviewer":{"agentType":"architecture-conformance-reviewer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:arc42","agent-teams-workforce:aws-solution-architect"]},"architecture-decider":{"agentType":"architecture-decider","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect"]},"architecture-decision-workflow-coordinator":{"agentType":"architecture-decision-workflow-coordinator","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-solution-architect"]},"architecture-diagram-author":{"agentType":"agent-teams-workforce:architecture-diagram-author","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:c4-diagramming","agent-teams-workforce:uml-diagramming","agent-teams-workforce:senior-architect"]},"architecture-fitness-function-author":{"agentType":"agent-teams-workforce:architecture-fitness-function-author","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"architecture-impact-analyst":{"agentType":"agent-teams-workforce:architecture-impact-analyst","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:beads-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"architecture-maintainer":{"agentType":"architecture-maintainer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:arc42","agent-teams-workforce:arc42-maintain","agent-teams-workforce:c4-diagramming","agent-teams-workforce:uml-diagramming","agent-teams-workforce:senior-architect"]},"architecture-pattern-challenger":{"agentType":"architecture-pattern-challenger","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect"]},"architecture-tradeoff-skeptic":{"agentType":"architecture-tradeoff-skeptic","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect"]},"athena-redshift-analytics-implementer":{"agentType":"agent-teams-workforce:athena-redshift-analytics-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer"]},"auth-bypass-tester":{"agentType":"agent-teams-workforce:auth-bypass-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops","agent-teams-workforce:cognito"]},"aws-integration-test-runner":{"agentType":"agent-teams-workforce:aws-integration-test-runner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:test-failure-mindset","agent-teams-workforce:cumulative-regression"]},"aws-integration-test-writer":{"agentType":"agent-teams-workforce:aws-integration-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:cumulative-regression"]},"beads-format-validator":{"agentType":"agent-teams-workforce:beads-format-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:beads-contract"]},"bedrock-integration-implementer":{"agentType":"agent-teams-workforce:bedrock-integration-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:bedrock","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:senior-prompt-engineer","agent-teams-workforce:aws-agentic-ai"]},"behavioral-signals-implementer":{"agentType":"agent-teams-workforce:behavioral-signals-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:senior-data-scientist","agent-teams-workforce:product-analytics"]},"bounded-context-mapper":{"agentType":"bounded-context-mapper","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect"]},"brd-traceability-auditor":{"agentType":"agent-teams-workforce:brd-traceability-auditor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"c4-diagram-author":{"agentType":"agent-teams-workforce:c4-diagram-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:c4-diagramming","agent-teams-workforce:senior-architect"]},"cdk-infrastructure-designer":{"agentType":"cdk-infrastructure-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:aws-solution-architect"]},"cdk-infrastructure-drift-detector":{"agentType":"agent-teams-workforce:cdk-infrastructure-drift-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:cloudformation"]},"cdk-stack-author":{"agentType":"cdk-stack-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:cloudformation"]},"cds-finding-reviewer":{"agentType":"agent-teams-workforce:cds-finding-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","cds:apply-design-system","cds:audit-against-system"]},"cds-ui-implementer":{"agentType":"agent-teams-workforce:cds-ui-implementer","skills":["agent-teams-workforce:subagent-contract","cds:apply-design-system","cds:audit-against-system","cds:compose-page"]},"changelog-writer":{"agentType":"agent-teams-workforce:changelog-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:changelog-generator"]},"chassis-extension-implementer":{"agentType":"chassis-extension-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:lambda","agent-teams-workforce:aws-serverless-eda"]},"code-correctness-reviewer":{"agentType":"agent-teams-workforce:code-correctness-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:code-reviewer"]},"code-quality-lead":{"agentType":"agent-teams-workforce:code-quality-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"code-refactoring-specialist":{"agentType":"agent-teams-workforce:code-refactoring-specialist","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:code-reviewer"]},"code-style-and-linting-enforcer":{"agentType":"agent-teams-workforce:code-style-and-linting-enforcer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:code-reviewer"]},"cognito-lambda-trigger-implementer":{"agentType":"agent-teams-workforce:cognito-lambda-trigger-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:cognito","agent-teams-workforce:lambda"]},"completeness-checker":{"agentType":"agent-teams-workforce:completeness-checker","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"complexity-analyzer":{"agentType":"agent-teams-workforce:complexity-analyzer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:tech-debt-tracker"]},"constitutional-agent":{"agentType":"agent-teams-workforce:constitutional-agent","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"constraint-extractor":{"agentType":"agent-teams-workforce:constraint-extractor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"consumer-driven-contract-test-writer":{"agentType":"agent-teams-workforce:consumer-driven-contract-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-test-suite-builder","agent-teams-workforce:cumulative-regression"]},"context-curator":{"agentType":"agent-teams-workforce:context-curator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"contract-violation-tester":{"agentType":"agent-teams-workforce:contract-violation-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-test-suite-builder"]},"cost-architecture-reviewer":{"agentType":"cost-architecture-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-cost-operations","agent-teams-workforce:aws-solution-architect"]},"cost-impact-reviewer":{"agentType":"cost-impact-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cost-operations","agent-teams-workforce:aws-solution-architect"]},"cross-repo-integration-test-coordinator":{"agentType":"agent-teams-workforce:cross-repo-integration-test-coordinator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"cross-service-contract-tester":{"agentType":"agent-teams-workforce:cross-service-contract-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-test-suite-builder"]},"data-consistency-checker":{"agentType":"agent-teams-workforce:data-consistency-checker","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb"]},"data-exposure-scanner":{"agentType":"agent-teams-workforce:data-exposure-scanner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"data-model-specification-author":{"agentType":"data-model-specification-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb","agent-teams-workforce:database-schema-designer"]},"data-pipeline-test-writer":{"agentType":"agent-teams-workforce:data-pipeline-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:cumulative-regression"]},"definition-of-done-enforcer":{"agentType":"agent-teams-workforce:definition-of-done-enforcer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"dependency-change-detector":{"agentType":"agent-teams-workforce:dependency-change-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dependency-auditor"]},"dependency-cve-auditor":{"agentType":"agent-teams-workforce:dependency-cve-auditor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dependency-auditor"]},"dependency-graph-extractor":{"agentType":"agent-teams-workforce:dependency-graph-extractor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"deployment-lead":{"agentType":"agent-teams-workforce:deployment-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"deployment-strategy-decider":{"agentType":"agent-teams-workforce:deployment-strategy-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:cove-prompt-design"]},"documentation-accuracy-reviewer":{"agentType":"agent-teams-workforce:documentation-accuracy-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"documentation-currency-auditor":{"agentType":"agent-teams-workforce:documentation-currency-auditor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"documentation-lead":{"agentType":"agent-teams-workforce:documentation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"domain-boundary-validator":{"agentType":"agent-teams-workforce:domain-boundary-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"domain-event-modeler":{"agentType":"domain-event-modeler","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:aws-solution-architect"]},"dos-resilience-tester":{"agentType":"agent-teams-workforce:dos-resilience-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"dynamodb-access-layer-implementer":{"agentType":"dynamodb-access-layer-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb"]},"dynamodb-cost-optimizer":{"agentType":"dynamodb-cost-optimizer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb","agent-teams-workforce:aws-cost-operations"]},"dynamodb-schema-access-pattern-reviewer":{"agentType":"dynamodb-schema-access-pattern-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb"]},"dynamodb-streams-cdc-implementer":{"agentType":"dynamodb-streams-cdc-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:dynamodb"]},"email-notification-implementer":{"agentType":"agent-teams-workforce:email-notification-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:email-template-builder","agent-teams-workforce:sns"]},"epic-sequencer":{"agentType":"agent-teams-workforce:epic-sequencer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:epic-sequencing"]},"espresso-test-writer":{"agentType":"agent-teams-workforce:espresso-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:tdd-guide","agent-teams-workforce:cumulative-regression"]},"event-api-client-implementer":{"agentType":"agent-teams-workforce:event-api-client-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda"]},"event-driven-consumer-implementer":{"agentType":"event-driven-consumer-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:sqs","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:sns"]},"event-flow-tester":{"agentType":"agent-teams-workforce:event-flow-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda"]},"event-schema-designer":{"agentType":"event-schema-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:eventbridge","agent-teams-workforce:sns","agent-teams-workforce:aws-solution-architect"]},"event-schema-reviewer":{"agentType":"event-schema-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda"]},"failure-mode-analyst":{"agentType":"failure-mode-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:observability-designer","agent-teams-workforce:aws-solution-architect"]},"filing-clerk":{"agentType":"filing-clerk","skills":["agent-teams-workforce:subagent-contract","obsidian:obsidian-cli","obsidian:obsidian-markdown","agent-teams-workforce:arc42","notebooklm","document-classification"]},"finops-analyst":{"agentType":"finops-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-cost-operations"]},"flaky-test-detector":{"agentType":"agent-teams-workforce:flaky-test-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:test-failure-mindset","agent-teams-workforce:find-cause"]},"frontend-performance-optimizer":{"agentType":"agent-teams-workforce:frontend-performance-optimizer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend"]},"github-actions-pipeline-implementer":{"agentType":"agent-teams-workforce:github-actions-pipeline-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops"]},"glue-etl-implementer":{"agentType":"agent-teams-workforce:glue-etl-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer"]},"graphql-schema-designer":{"agentType":"graphql-schema-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer","agent-teams-workforce:aws-solution-architect"]},"graphql-schema-reviewer":{"agentType":"agent-teams-workforce:graphql-schema-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer"]},"implementation-lead":{"agentType":"agent-teams-workforce:implementation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"incident-responder":{"agentType":"agent-teams-workforce:incident-responder","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:find-cause","agent-teams-workforce:validation-protocol"]},"incident-response-runbook-designer":{"agentType":"agent-teams-workforce:incident-response-runbook-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:observability-designer"]},"infrastructure-security-scanner":{"agentType":"infrastructure-security-scanner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops","agent-teams-workforce:aws-cdk-development"]},"injection-attack-tester":{"agentType":"agent-teams-workforce:injection-attack-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"integration-pattern-architect":{"agentType":"integration-pattern-architect","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:aws-solution-architect"]},"integration-testing-lead":{"agentType":"agent-teams-workforce:integration-testing-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"ios-swiftui-implementer":{"agentType":"agent-teams-workforce:ios-swiftui-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"kinesis-stream-implementer":{"agentType":"agent-teams-workforce:kinesis-stream-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:aws-serverless-eda"]},"lambda-performance-optimizer":{"agentType":"lambda-performance-optimizer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:lambda"]},"llm-observability-implementer":{"agentType":"agent-teams-workforce:llm-observability-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:observability-designer","agent-teams-workforce:senior-prompt-engineer","agent-teams-workforce:aws-agentic-ai"]},"matching-algorithm-implementer":{"agentType":"agent-teams-workforce:matching-algorithm-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer"]},"mcp-server-implementer":{"agentType":"agent-teams-workforce:mcp-server-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:mcp-server-builder","agent-teams-workforce:aws-agentic-ai","agent-teams-workforce:aws-mcp-setup"]},"ml-evaluation-tester":{"agentType":"agent-teams-workforce:ml-evaluation-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:senior-data-scientist","agent-teams-workforce:cumulative-regression"]},"mobile-e2e-test-writer":{"agentType":"agent-teams-workforce:mobile-e2e-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"nextjs-component-implementer":{"agentType":"agent-teams-workforce:nextjs-component-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend","agent-teams-workforce:a11y-audit","agent-teams-workforce:senior-fullstack"]},"nfr-analyst":{"agentType":"agent-teams-workforce:nfr-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:product-discovery"]},"okr-writer":{"agentType":"agent-teams-workforce:okr-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-strategist","agent-teams-workforce:product-analytics"]},"openapi-contract-reviewer":{"agentType":"openapi-contract-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer"]},"operational-readiness-reviewer":{"agentType":"operational-readiness-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:observability-designer","agent-teams-workforce:aws-solution-architect"]},"payments-integration-implementer":{"agentType":"agent-teams-workforce:payments-integration-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:stripe-integration-expert","agent-teams-workforce:secrets-manager"]},"performance-benchmark-writer":{"agentType":"agent-teams-workforce:performance-benchmark-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"permission-escalation-tester":{"agentType":"agent-teams-workforce:permission-escalation-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops","agent-teams-workforce:iam"]},"persistence-architecture-specialist":{"agentType":"persistence-architecture-specialist","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:dynamodb","agent-teams-workforce:database-schema-designer","agent-teams-workforce:rds","agent-teams-workforce:aws-solution-architect"]},"persona-profile-writer":{"agentType":"agent-teams-workforce:persona-profile-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:product-analytics"]},"phase-gate-enforcer":{"agentType":"agent-teams-workforce:phase-gate-enforcer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:cumulative-regression"]},"playwright-e2e-web-test-writer":{"agentType":"agent-teams-workforce:playwright-e2e-web-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:a11y-audit","agent-teams-workforce:cumulative-regression"]},"polyrepo-steward":{"agentType":"agent-teams-workforce:polyrepo-steward","skills":["agent-teams-workforce:subagent-contract"]},"power-tools-configuration-implementer":{"agentType":"agent-teams-workforce:power-tools-configuration-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:lambda","agent-teams-workforce:secrets-manager"]},"prd-alignment-verifier":{"agentType":"agent-teams-workforce:prd-alignment-verifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"prd-creation-lead":{"agentType":"agent-teams-workforce:prd-creation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"prd-reality-reconciler":{"agentType":"prd-reality-reconciler","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"prd-trd-traceability-verifier":{"agentType":"agent-teams-workforce:prd-trd-traceability-verifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"prd-validation-analyst":{"agentType":"agent-teams-workforce:prd-validation-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"prd-validation-lead":{"agentType":"agent-teams-workforce:prd-validation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"prd-writer":{"agentType":"agent-teams-workforce:prd-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"production-readiness-review-facilitator":{"agentType":"agent-teams-workforce:production-readiness-review-facilitator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"race-condition-tester":{"agentType":"agent-teams-workforce:race-condition-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"react-native-implementer":{"agentType":"agent-teams-workforce:react-native-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend"]},"readme-writer":{"agentType":"agent-teams-workforce:readme-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"recommendation-engine-implementer":{"agentType":"agent-teams-workforce:recommendation-engine-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer"]},"regression-coverage-reviewer":{"agentType":"agent-teams-workforce:regression-coverage-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:artifact-handoff","agent-teams-workforce:cumulative-regression"]},"regression-impact-assessor":{"agentType":"agent-teams-workforce:regression-impact-assessor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:artifact-handoff","agent-teams-workforce:cumulative-regression"]},"requirements-clarifier":{"agentType":"agent-teams-workforce:requirements-clarifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:product-discovery"]},"requirements-conflict-detector":{"agentType":"agent-teams-workforce:requirements-conflict-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"root-cause-analyst":{"agentType":"agent-teams-workforce:root-cause-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:find-cause","agent-teams-workforce:test-failure-mindset"]},"run-ledger-writer":{"agentType":"agent-teams-workforce:run-ledger-writer","skills":["agent-teams-workforce:subagent-contract"]},"s3-data-lake-implementer":{"agentType":"agent-teams-workforce:s3-data-lake-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:s3"]},"sdlc-pipeline-orchestrator":{"agentType":"agent-teams-workforce:sdlc-pipeline-orchestrator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:beads-contract"]},"security-architecture-designer":{"agentType":"security-architecture-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-security","agent-teams-workforce:iam","agent-teams-workforce:secrets-manager","agent-teams-workforce:aws-solution-architect"]},"security-test-case-designer":{"agentType":"agent-teams-workforce:security-test-case-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-security","agent-teams-workforce:cumulative-regression"]},"slo-error-budget-designer":{"agentType":"slo-error-budget-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:observability-designer","agent-teams-workforce:cloudwatch"]},"smoke-test-author":{"agentType":"agent-teams-workforce:smoke-test-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"spec-authoring-lead":{"agentType":"agent-teams-workforce:spec-authoring-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"spec-currency-validator":{"agentType":"agent-teams-workforce:spec-currency-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"spec-decider":{"agentType":"spec-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:cove-prompt-design"]},"spec-freshness-lead":{"agentType":"agent-teams-workforce:spec-freshness-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"stakeholder-request-intake-writer":{"agentType":"agent-teams-workforce:stakeholder-request-intake-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"task-decomposer":{"agentType":"task-decomposer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:beads-contract"]},"task-decomposition-lead":{"agentType":"agent-teams-workforce:task-decomposition-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:beads-contract"]},"task-dependency-mapper":{"agentType":"task-dependency-mapper","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:beads-contract"]},"task-readiness-runner":{"agentType":"agent-teams-workforce:task-readiness-runner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:beads-contract"]},"tdd-unit-test-generator":{"agentType":"agent-teams-workforce:tdd-unit-test-generator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:tdd-guide","agent-teams-workforce:cumulative-regression"]},"test-command-resolver":{"agentType":"agent-teams-workforce:test-command-resolver","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:test-failure-mindset"]},"test-coverage-gap-reviewer":{"agentType":"agent-teams-workforce:test-coverage-gap-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"test-design-lead":{"agentType":"agent-teams-workforce:test-design-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"test-environment-orchestrator":{"agentType":"test-environment-orchestrator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:aws-mcp-setup"]},"test-failure-parser":{"agentType":"agent-teams-workforce:test-failure-parser","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:test-failure-mindset"]},"test-isolation-specialist":{"agentType":"agent-teams-workforce:test-isolation-specialist","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:tdd-guide","agent-teams-workforce:test-failure-mindset"]},"test-plan-strategy-reviewer":{"agentType":"agent-teams-workforce:test-plan-strategy-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"test-strategy-decider":{"agentType":"agent-teams-workforce:test-strategy-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cove-prompt-design"]},"trd-author":{"agentType":"trd-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"trd-authoring-lead":{"agentType":"agent-teams-workforce:trd-authoring-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"trd-decider":{"agentType":"agent-teams-workforce:trd-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"trd-validator":{"agentType":"agent-teams-workforce:trd-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"ubiquitous-language-writer":{"agentType":"agent-teams-workforce:ubiquitous-language-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"uml-diagram-author":{"agentType":"agent-teams-workforce:uml-diagram-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:uml-diagramming","agent-teams-workforce:senior-architect"]},"user-guide-writer":{"agentType":"agent-teams-workforce:user-guide-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:roadmap-communicator"]},"user-story-reviewer":{"agentType":"agent-teams-workforce:user-story-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:beads-contract"]},"user-story-writer":{"agentType":"agent-teams-workforce:user-story-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"vector-search-embeddings-implementer":{"agentType":"agent-teams-workforce:vector-search-embeddings-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:rag-architect"]},"webauthn-implementer":{"agentType":"agent-teams-workforce:webauthn-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend","agent-teams-workforce:cognito"]},"workflow-command-runner":{"agentType":"agent-teams-workforce:workflow-command-runner","skills":["agent-teams-workforce:artifact-handoff"]},"worktree-independent-verifier":{"agentType":"agent-teams-workforce:worktree-independent-verifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"wsjf-scorer":{"agentType":"agent-teams-workforce:wsjf-scorer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-strategist","agent-teams-workforce:wsjf","agent-teams-workforce:beads-contract"]},"wsjf-scoring-reviewer":{"agentType":"agent-teams-workforce:wsjf-scoring-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-strategist","agent-teams-workforce:wsjf"]},"xcuitest-writer":{"agentType":"agent-teams-workforce:xcuitest-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:tdd-guide","agent-teams-workforce:cumulative-regression"]}}
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
    ? `Before doing the assignment, assess which declared domain skills apply and invoke each applicable skill with the Skill tool using its exact name: ${domainSkills.join(', ')}. Read its instructions and apply the parts relevant to your role and task; record material applicability decisions only in caller-permitted progress or evidence, without inventing extra work. Do not assume frontmatter injected the skill. If required skill content cannot be loaded, report that specific missing dependency; do not substitute memory or a generic agent.\n\n`
    : ''
  const sourceBrief = 'Artifact contract: source files and vault notes are authoritative. Read the referenced source sections needed for this assignment; summaries are navigation, not substitutes. Observe the stated read/edit/create ownership. Preserve existing source unless its change is assigned. Return only the caller\'s required response fields; keep status and evidence in its designated result or checkpoint rather than adding fields or prose to an exact response. Do not reconstruct or retype shared documents for handoff.\n\n'
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
    ...(fableInput.relayExecutionId ? { relayExecutionId: fableInput.relayExecutionId } : {}),
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
  let captureOrdinal = 0
  const RECEIPT_SCHEMA = { type: 'object', additionalProperties: false, required: ['request', 'commandSha256', 'sha256', 'bytes', 'exitCode'], properties: { request: { type: 'string' }, commandSha256: { type: 'string' }, sha256: { type: 'string' }, bytes: { type: 'integer' }, exitCode: { type: 'integer' } } }
  const CAPTURE_SCHEMA = { type: 'object', additionalProperties: false, required: ['exitCode', 'stdout', 'receipt'], properties: { ...SCHEMA.properties, receipt: RECEIPT_SCHEMA } }
  const MANIFEST_SCHEMA = { type: 'object', additionalProperties: false, required: ['receipt'], properties: { receipt: RECEIPT_SCHEMA } }
  const CHUNK_SCHEMA = { type: 'object', additionalProperties: false, required: ['receipt', 'index', 'chunk', 'sha256'], properties: { receipt: RECEIPT_SCHEMA, index: { type: 'integer' }, chunk: { type: 'string' }, sha256: { type: 'string' } } }
  const capturePrompt = command => `Execute this exact checksum-guarded command once in the foreground with Bash timeout 600000. Return its JSON stdout object through the required response schema unchanged. The exitCode inside that object belongs to the captured original command, not the capture helper. Do not execute another command, reconstruct missing output, or replace receipt fields. If the tool fails, report the actual failure; never invent a receipt.\n\n${command}`
  async function captureCommand(dispatch, { label, phase, command, file, readRunner }, ordinal) {
    const argv = shellWords(command)
    const commandSha256 = sha256Json(argv)
    const request = sha256Json({ execution: fableInput.relayExecutionId, invocation: fablePath, ordinal, commandSha256 })
    const runner = readRunner.replace(/[^/]+$/, 'relaycapture.py')
    const common = ['--directory', `${file}.captures`, '--request', request, '--command-sha256', commandSha256]
    const options = { phase, agentType: 'agent-teams-workforce:workflow-command-runner', model: 'sonnet', effort: 'low' }
    const recovered = new Set()
    const send = async (command, opts) => {
      const before = new Set(typeof dispatchFailures === 'undefined' ? [] : dispatchFailures)
      const result = await dispatch(capturePrompt(command), opts)
      if (typeof dispatchFailures !== 'undefined') for (const entry of dispatchFailures) if (!before.has(entry) && entry.label === opts.label && entry.phase === opts.phase) recovered.add(entry)
      return result
    }
    const finish = result => {
      if (typeof dispatchFailures !== 'undefined') for (const entry of recovered) { const index = dispatchFailures.indexOf(entry); if (index >= 0) dispatchFailures.splice(index, 1) }
      if (recovered.size) log(`RELAY_CAPTURE_RECOVERED ${JSON.stringify({ label, request, recoveredDispatches: recovered.size })}`)
      return result
    }
    const valid = receipt => receipt && receipt.request === request && receipt.commandSha256 === commandSha256 && HEX.test(String(receipt.sha256)) && Number.isInteger(receipt.bytes) && receipt.bytes >= 0 && receipt.bytes <= 1048576 && Number.isInteger(receipt.exitCode)
    const same = (a, b) => valid(a) && canonicalJson(a) === canonicalJson(b)
    const matches = (text, digest) => { try { return sha256Ascii(text) === digest } catch (_) { return false } }
    const out = await send(pythonLine(runner, ['capture', ...common, '--argv-json', canonicalJson(argv)]), { ...options, label, schema: CAPTURE_SCHEMA })
    if (!out && typeof dispatchInterruption !== 'undefined' && dispatchInterruption) return null
    let receipt = out && out.receipt
    if (out && valid(receipt) && typeof out.stdout === 'string' && out.stdout.length === receipt.bytes && matches(out.stdout, receipt.sha256) && out.exitCode === receipt.exitCode) return finish(out)
    log(`RELAY_CAPTURE_RECOVERY ${JSON.stringify({ label, request, reason: 'capture copy failed byte or invocation validation; reading saved output only' })}`)
    // Recover even when the model damaged the independent receipt: the file is bound to
    // the nonce + invocation + command we hold, not to any value the model copied.
    receipt = null
    for (let attempt = 0; attempt < 2; attempt++) {
      const manifest = await send(pythonLine(runner, ['manifest', ...common]), { ...options, label: `${label}:receipt${attempt + 1}`, schema: MANIFEST_SCHEMA })
      if (!manifest && typeof dispatchInterruption !== 'undefined' && dispatchInterruption) return null
      if (manifest && valid(manifest.receipt)) { receipt = manifest.receipt; break }
    }
    if (!valid(receipt)) return { captureError: 'the exact invocation has no valid saved capture receipt' }
    if (receipt.bytes > 65536) return { captureError: `saved output is ${receipt.bytes} bytes, exceeding the 65536-byte bounded copy recovery limit; original command was not rerun` }
    let stdout = ''
    const count = Math.ceil(receipt.bytes / 1024)
    for (let index = 0; index < count; index++) {
      let accepted = null
      for (let attempt = 0; attempt < 2; attempt++) {
        const chunk = await send(pythonLine(runner, ['chunk', ...common, '--sha256', receipt.sha256, '--index', String(index)]), { ...options, label: `${label}:chunk${index + 1}:${attempt + 1}`, schema: CHUNK_SCHEMA })
        if (!chunk && typeof dispatchInterruption !== 'undefined' && dispatchInterruption) return null
        if (chunk && same(chunk.receipt, receipt) && chunk.index === index && typeof chunk.chunk === 'string' && chunk.chunk.length === Math.min(1024, receipt.bytes - index * 1024) && HEX.test(String(chunk.sha256)) && matches(chunk.chunk, chunk.sha256)) { accepted = chunk.chunk; break }
      }
      if (accepted === null) return { captureError: `saved capture chunk ${index + 1}/${count} failed validation after two reads` }
      stdout += accepted
    }
    if (sha256Ascii(stdout) !== receipt.sha256) return { captureError: 'reconstructed capture does not match the original saved byte digest' }
    return finish({ exitCode: receipt.exitCode, stdout, receipt })
  }
  /** Runs a command once. A damaged copy can only re-read its exact saved receipt. */
  async function exec(dispatch, { label, phase, command, file = null, readRunner = null }) {
    const ordinal = captureOrdinal++
    const out = file && readRunner && fableInput.relayExecutionId
      ? await captureCommand(dispatch, { label, phase, command, file, readRunner }, ordinal)
      : await dispatch(prompt(command), { label, phase, agentType: 'agent-teams-workforce:workflow-command-runner', model: 'sonnet', effort: 'low', schema: SCHEMA })
    if (out && out.captureError) {
      const error = `RELAY_COPY_RECOVERY_EXHAUSTED ${JSON.stringify({ label, relayFile: file, attempts: 2, reason: out.captureError })}`
      log(error)
      return { ok: false, paused: true, recoveryKind: 'relay-copy-recovery', error }
    }
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
  function artifactBrief(candidate, schema, revision = '', helper) {
    if (typeof helper !== 'string' || !helper) throw new Error('artifactBrief requires the artifactcontract.py helper path')
    const binding = ['--candidate', candidate, '--schema-json', canonicalJson(schema), '--revision', revision]
    const command = (operation, extra = []) => ['python3', helper, operation, ...binding, ...extra].map(quote).join(' ')
    const progress = `${candidate}.progress.json`
    const submit = command('submit', ['--progress-file', progress])
    return `\n\nAUTHORITATIVE ARTIFACT HANDOFF: Write the complete JSON result ONCE to ${candidate}, using the schema in the submission command below. Maintain ${progress} with task (string), completed and remaining (string arrays), and artifacts (path array); include reason when blocked.
Submission command: ${submit}
After meaningful progress use that same command, replacing only the operation argument 'submit' with 'checkpoint' and appending --status in-progress. For blocked work append --status blocked instead, with reason and remaining work recorded. After finishing the assignment run the submission command unchanged. The script validates the candidate, computes its bound completion checkpoint and prints the exact return object. Only after exit 0, pass that stdout object unchanged to StructuredOutput; do not construct a second return object or copy the artifact contents into it. Do not calculate hashes or manually mark incomplete work complete. Correct reported errors before returning; a failed submission is not completion. Structural validation is not semantic review. On resume use the same command with operation 'status' instead of 'submit' and omit --progress-file and its value; read the checkpoint and actual artifacts first, preserving completed work and finishing only missing work. Preserve all candidate, schema and revision arguments across these operations. Shared Markdown, diagrams and other documents remain authoritative at their paths; read them directly, never replace them with summaries. Do not write the final accepted result; the workflow validates and publishes the candidate.`
  }
  async function acceptArtifact(dispatch, { label, phase, runner, candidate, file, schema, relayFile, returned = null, revision = '', keys = [], counts = [], projection = '', probe = false, recordArgv = [], researchAgent = '', researchRepo = '' }) {
    if (returned && returned.artifactPath !== candidate) return { ok: false, error: `invalid artifact reference: expected ${candidate}` }
    const args = ['python3', runner.replace(/[^/]+$/, 'jsonartifact.py'), '--candidate', candidate, '--final', file, '--schema-json', canonicalJson(schema), ...(revision ? ['--revision', revision] : []), ...(keys.length ? ['--keys', keys.join(',')] : []), ...(counts.length ? ['--counts', counts.join(',')] : []), ...(projection ? ['--projection', projection] : []), ...(probe ? ['--probe'] : []), ...(probe && researchAgent && researchRepo ? ['--research-agent', researchAgent, '--research-repo', researchRepo] : []), ...(!returned ? ['--recover'] : [])]
    if (!Array.isArray(recordArgv) || recordArgv.some(word => typeof word !== 'string' || !word)) return { ok: false, error: 'invalid artifact recorder argv' }
    const argv = recordArgv.length ? ['python3', runner.replace(/[^/]+$/, 'artifactpublish.py'), '--record-argv-json', canonicalJson(recordArgv), '--', ...args.slice(2)] : args
    const result = await run(dispatch, { label, phase, runner, argv, file: relayFile })
    if (!result.ok) return result
    if (result.exitCode !== 0) return { ok: false, error: `artifact validation failed: ${JSON.stringify(result.json)}`, relayFile }
    const receipt = result.json
    if (probe && receipt && receipt.pending === true) return { ok: true, pending: true, ...(receipt.research ? { research: receipt.research } : {}) }
    if (recordArgv.length && (!receipt || receipt.recorded !== true)) return { ok: false, error: 'artifact provenance recording not confirmed', relayFile }
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
//   artifacts: { dir, relDir?, epicId, script, phase, inputs?, slug } (required: the detailing lives only in recon-<slug>.json),
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

const STATUSES = ['add', 'modify', 'remove', 'done', 'planned-elsewhere']

function artifactsFrom(x) {
  if (!x || typeof x !== 'object') return null
  return ['dir', 'script', 'epicId', 'phase'].every((k) => typeof x[k] === 'string' && x[k]) ? x : null
}
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
const ART = artifactsFrom(a.artifacts)
const artSlug = ART && hasText(ART.slug) ? ART.slug : null
const reconPath = ART && artSlug ? `${ART.dir}/recon-${artSlug}.json` : null
const depscorePath = hasText(a.depscore) && a.depscore.trim().startsWith('/') ? a.depscore.trim() : null
const replayFile = a.replay && a.replay.files && a.replay.files.recon
const replayPath = typeof replayFile === 'string' && replayFile.startsWith('/') ? replayFile : null

const refuse = (why) => ({ ok: false, stage: 'input', deterministicFailure: true, headline: `Detailing refused its input: ${why}`, reason: why, error: why })
if (repos.length !== 1) return dispatchOutcome(refuse(`detailing is scoped to ONE repository; ${repos.length} were supplied`))
if (!hasText(delta.deltaDir)) return dispatchOutcome(refuse('no delta supplied: delta.deltaDir names the views the items come from'))
if (!placed.length) return dispatchOutcome(refuse(`no delta item is placed in ${repos[0]}`))
if (!reconPath) return dispatchOutcome(refuse(`no artifact directory and slug were supplied for ${repos[0]}: the detailing exists only as recon-<slug>.json in the Epic's artifact directory, which the sessions downstream read by path`))
if (!depscorePath) return dispatchOutcome(refuse('no absolute depscore.py path was supplied in `depscore`: depscore.py recon-facts reads the saved detailing'))

phase('Detailing')

/** The relay runner for any program other than depscore.py: relayrun.py beside depscore.py. */
const RELAY_RUNNER = depscorePath.replace(/[^/]+$/, 'relayrun.py')
/** This repository's relay files, under the Epic's artifact directory, numbered so a run's names are deterministic. */
const RELAY_DIR = `${ART.dir}/relay/recon-${artSlug}`
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
  const named = Array.isArray(f.failedItems) ? f.failedItems.map((x) => `${x.id}: ${x.problem}`) : []
  const more = Number(f.problemCount) > named.length ? ` (and ${Number(f.problemCount) - named.length} more)` : ''
  const what = hasText(f.problem) ? f.problem : `${named.join('; ')}${more}`
  return stopped(stage, `The detailing of ${repos[0]} in ${file} is not usable — ${what}${after || ''}`, {
    file,
    failedItems: Array.isArray(f.failedItems) ? f.failedItems : [],
    deterministicFailure: true,
  })
}

/** What the owner does to have a repository whose saved detailing stopped the replay detailed again. */
const REDO = `. To detail ${repos[0]} again, delete ${replayPath || reconPath} and remove the step ${ART.phase} from ${ART.dir}/STEPS.md; the step is not redone behind a saved file`
let facts = null
let resumed = false
if (replayPath) {
  const read = await readFacts(replayPath, 'replay:recon-facts')
  if (read.error) {
    return dispatchOutcome(stopped('detailing-replay', `The saved detailing ${replayPath} of ${repos[0]} could not be read: ${read.error}${REDO}.`, {
      file: replayPath,
      ...(read.dispatchFailed ? { dispatchFailed: true, dispatchFailures: dispatchDeaths('Detailing') } : {}),
    }))
  }
  if (read.facts.ok !== true) return dispatchOutcome(unusable(read.facts, replayPath, 'detailing-replay', REDO))
  facts = read.facts
  resumed = true
  log(`Detailing replayed from ${replayPath} (${facts.itemCount} item(s), ${facts.bytes} bytes on disk)`)
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
  if (listed.error) {
    return dispatchOutcome(stopped('detailing-bundles', `The cds bundles in ${packagesDir} could not be listed for ${repos[0]}: ${listed.error}.`, {
      ...(listed.dispatchFailed ? { dispatchFailed: true, dispatchFailures: dispatchDeaths('Detailing') } : {}),
    }))
  }
  bundles = listed.bundles
  log(`Detailing of ${repos[0]}: ${bundles.length} supplied cds bundle(s)${packagesDir ? ` in ${packagesDir}` : ' (no packages directory)'}`)
}
const bundleLines = bundles
  .map((b) => `  - ${b.kind} \`${b.slug}\`${b.shell && b.shell.name ? ` (in shell ${b.shell.name})` : ''}, created ${b.createdAt}\n      bundle: ${b.path}\n      build spec: ${b.buildSpec}${b.buildSpecExists === false ? ' (MISSING on disk)' : ''}\n      design: ${b.design}\n      styles: ${b.styles}`)
  .join('\n')

const itemLines = placed
  .map((i) => `- ${i.id}: ${i.element}${Array.isArray(i.views) && i.views.length ? `\n    delta views: ${i.views.join('; ')}` : ''}`)
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

THE APPROVED TARGET is ${delta.targetDir || '(the folder above the delta)'}, and the change alone, its delta, is ${delta.deltaDir}. What the delta views say about an element is what it becomes; read the target views where a delta view needs their context.

THE ITEMS PLACED IN THIS REPOSITORY (each one element the delta shows):
${itemLines}

Give every item above exactly one entry, with one status:
- add      — the delta adds the element and the code on \`main\` does not hold it. \`from\` is "absent"; \`to\` is what the delta adds.
- modify   — the code holds the element and the delta changes it. \`from\` is what the code holds; \`to\` is what the delta makes it.
- remove   — the delta removes the element and the code still holds it. \`from\` is what the code holds; \`to\` is "removed".
- done     — the code on \`main\` already holds the element as the delta shows it. \`from\` and \`to\` are both that state.
- planned-elsewhere — an open bead of another Epic (a Story or Task planned and not built) already plans this change. Name it in \`plannedBy\` (the bead id; read beads with \`bd list\`, \`bd show\`, \`bd search\` only).

SOURCE EVIDENCE HANDOFF. ${hasText(a.surveyPath) ? `Use relevant entries from the existing survey ${a.surveyPath}, including its evidenceRefs (path, heading, repo, revision, url; unused fields empty).` : 'No survey path was supplied; use the target/delta and bounded source evidence, identifying any unknowns.'} Resolve the exact main commit in this repository once and retain it with the repository path and file:line in each item's existing evidence strings, linked to that item's id and the originating claim/coverage or TRD requirement IDs when supplied. Keep cited document headings or URL/retrieval revision when relevant. Reuse unchanged evidence sufficient for the status; before another read, name the changed revision, unsupported claim or unanswered question in that item's from/evidence. When main changed, check the cited files/integration dependencies that can affect that item; do not resurvey unrelated source. Legacy citations without a revision require a targeted freshness check, not a fabricated commit. Preserve existing working/stub/absent/unknown distinctions and historical evidence.

Cite evidence for every status in \`evidence\`: a \`file:line\` on \`main\` you read. For \`add\`, cite the file and line where the element attaches (the route table, the stack, the module that will hold it). A \`planned-elsewhere\` item carries its bead id in \`plannedBy\` and, like every status, a \`file:line\`: where the planned change attaches in the code on \`main\`. An item with no citation fails the run.

EXISTING CODE IS EVIDENCE TO INSPECT, NOT AN ASSUMPTION OF CORRECTNESS. In this same read-only pass, follow the relevant entrypoint into the implementation, its consumed/published contracts, configuration and focused tests. Reuse supplied survey citations to narrow the reading; do not resurvey the fleet. In each item's existing \`from\` and \`evidence\`, distinguish behavior supported by the inspected path from incomplete wiring, stubs, absence and unresolved behavior. Name what the tests assert and their limits: reading a mocked test is not a passing test or live-runtime proof. A matching name, import, class, file or mock is not enough for \`done\`. Use \`modify\` for an existing element with an evidenced gap, and \`add\` for a missing element at its cited attachment point. If a material unknown prevents choosing a status, report that uncertainty as an error rather than inventing completeness or replacement work. Preserve verified parts and compatible published contracts; justify any necessary replacement from requirements and concrete evidence. An existing repository is the implementation home unless the approved architecture explicitly establishes a different owner; the presence of a PRD or missing implementation alone does not require a new repository, service or product feature.

Also classify the SURFACE each item lives on, in \`surface\`: ui | service | infra | data | unknown.

${uiCheck ? `═══ EVERY UI ITEM TAKES ONE DESIGN SOURCE ═══

For every item whose \`surface\` is \`ui\`, decide its design source from the delta and the code:

- bundle — a cds bundle listed below packages the artifact (the Page, Shell or View) the item
  builds. The owner supplied that mockup, so the bundle is the target state: its
  \`spec/build-spec.md\` together with its composed \`design/<kind>.html\` and its own \`styles/\`.
- cds — the item changes design (layout, components, styles, visual states, or a new screen)
  and no listed bundle packages it. The implementing agent designs it with the CDS design
  system; there is nothing to cite.
- none — the item changes no design: copy or label text, or data wired into an existing
  element without changing how it looks. It touches no design or stylesheet and is built like
  any other code change.

THE SUPPLIED cds BUNDLES — each packages exactly one artifact; the newest of a kind and slug is
listed, older ones are not supplied:
${bundleLines || '  (none: no bundle is supplied, so no item takes bundle)'}

Match an item to a bundle only when the bundle packages the artifact that item builds: read the
bundle's build spec and design, and the approved target/delta views with their scoped design
references (linked source views included). The PRD (${hasText(prdInput.path) ? prdInput.path : 'no PRD path supplied'})
may name a visual reference that helps identify the artifact; it carries no package paths.
Use only the bundles listed above, at the paths listed. Do not package, copy or regenerate a
bundle, and do not cite a directory that is not listed. When no listed bundle packages the
item, it takes cds or none, decided by whether it changes design.

The loose composed artifacts may help you understand the existing design; they are not
supplied mockups and never make an item a bundle item:
${mocksDir ? `  composed pages and views: ${mocksDir}` : '  composed pages and views: (no directory supplied)'}
${shellsDir ? `  composed shells: ${shellsDir}` : '  composed shells: (no directory supplied)'}

Record one entry per \`ui\` item in \`uiAuthority.uiItems\`: \`item\` (the item id),
\`designSource\` (bundle | cds | none), \`reason\` (one sentence: which bundle packages it, or
what design it changes, or why it changes none); for a bundle or cds item, \`artifact\`:
\`{ kind, slug }\`, the Page, Shell or View the item builds, named as a cds bundle's
\`bundle.json\` names it (kind page | shell | view; for a bundle item, the listed bundle's kind
and slug; for a cds item, the slug a bundle of that artifact would carry: the artifact's name
in lower-case words joined by hyphens, matching an existing composed artifact's slug where one
exists). A mockup can arrive any time before the Task is built: the build looks for a bundle
of this artifact then. For a bundle item only: \`bundle\` (the
bundle directory exactly as listed), \`buildSpec\` (its build spec exactly as listed) and
\`sections\` (the IDs in that build spec's Sections table — S1, S2, … — that the item builds;
an empty list when it builds the whole artifact or the table carries no IDs). The Spec cites
these and every Task that builds the item carries them in its build contract. List every
artifact path you opened in \`uiAuthority.artifactsConsulted\` and the mocks directory in
\`uiAuthority.mocksDir\`.` : `═══ THIS REPOSITORY HOLDS NO UI ═══

Its items take no design source and \`uiAuthority\` stays empty.`}

═══ SEARCH BUDGET ═══

Work item by item and stop searching for each the moment its status is settled. Cover every
item once before you deepen any of them, and when the budget is spent, stop and return your
structured output with what you have.

═══ CHECK 2 — upstream dependency changes ═══

Upstream dependencies the work relies on:
${dependencies.length ? dependencies.map((d, i) => `${i + 1}. ${d}`).join('\n') : '(none declared in args — discover them from the repository\'s manifests, lockfiles and imports)'}

Determine whether any upstream contract, shared schema, event, library version, or interface the delta assumes has changed in a way that invalidates it. Check the dependencies THIS repository consumes, as its manifests, lockfiles and imports on \`main\` show them. Record under \`dependencyChanges\`:
- current: true if no invalidating upstream change is found, false otherwise.
- changeFindings: each invalidating change (dependency, change, invalidates).
- evidence: how you verified the dependency state (under 60 words).

═══ THE RESULT IS A FILE, NOT YOUR REPLY ═══

1. Write your whole detailing, as ONE JSON object, to ${reconPath} with the Write tool, replacing the file if it exists (Read it first if the Write tool asks you to). Write no other file. Its keys:
   - \`items\`: one object per item above: \`id\`, \`element\`, \`status\` (${STATUSES.join(' | ')}), \`from\`, \`to\`, \`evidence\` (a list of strings, each \`file:line\` you read with what it shows), \`plannedBy\` (the bead id, for planned-elsewhere only), \`surface\` (ui | service | infra | data | unknown).
   - \`evidenceSummary\`: a string.
   - \`uiAuthority\`: \`uiItems\` (each \`{ item, designSource, reason, artifact?, bundle?, buildSpec?, sections? }\`), \`mocksDir\`, \`artifactsConsulted\`, as described above; empty values when the repository holds no UI.
   - \`dependencyChanges\`: \`current\` (true or false), \`changeFindings\` (each \`{ dependency, change, invalidates }\`), \`evidence\`.
2. Return ONLY \`saved\` (true when the file is written), \`itemCount\` (the number of entries in \`items\`) and, when anything failed, \`error\` (what failed). Do NOT return the detailing itself: the workflow records and checks the file on disk, and every session after you reads it by its path.`,
  {
    label: 'detail:delta-and-dependencies',
    phase: 'Detailing',
    effort: 'medium',
    agentType: 'prd-reality-reconciler',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['saved', 'itemCount'],
      properties: { saved: { type: 'boolean' }, itemCount: { type: 'integer' }, error: { type: 'string' } },
    },
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
  if (session.saved !== true) {
    return dispatchOutcome(stopped('detailing-save', `The detailing session for ${repos[0]} did not save ${reconPath}: ${hasText(session.error) ? session.error.trim().slice(0, 600) : 'it reported saved=false and gave no reason'}.`))
  }
  const recorded = await recordDetailing()
  if (recorded.error) {
    return dispatchOutcome(stopped('detailing-save', `The detailing of ${repos[0]} was saved to ${reconPath} but not recorded: ${recorded.error}.`, {
      ...(recorded.dispatchFailed ? { dispatchFailed: true, dispatchFailures: dispatchDeaths('Detailing') } : {}),
    }))
  }
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
const counts = Object.fromEntries(STATUSES.map((s) => [s, Number((facts.counts || {})[s]) || 0]))
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

log(`Detailing of ${repos[0]} (${detailingFile}): ${facts.itemCount} item(s) — ${STATUSES.map((s) => `${counts[s]} ${s}`).join(', ')}.`)

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
