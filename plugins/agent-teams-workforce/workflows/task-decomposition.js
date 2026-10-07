export const meta = {
  name: 'task-decomposition',
  description:
    'Leaf mini — decomposes ONE Spec into TASKS ONLY, parented to the Story that Spec pairs with, in the Story\'s single repo. A Task is build work: the Spec\'s acceptance criteria are the tests inside the build Tasks, written by their Red step, so no Task only writes tests. Tasks are made only for the delta items the repository\'s detailing marks add, modify or remove: depscore.py plan-tasks refuses a Task that cites none of them in requirementIds, and a done or planned-elsewhere item gets no Task. An open Task of another Epic in the same repository that already plans the work is not duplicated: the Tasks that need it carry its id in blockedByExternal, and write-task writes that blocks edge. A Task with the web-ui surface gets in its build contract the design source of the ui items it cites, from the detailing\'s uiAuthority (cds_design_source): bundle, with the supplied cds bundle and the build-spec.md citations (cds_bundle_path, cds_build_specs); cds, designed with the CDS design system; or none, a change with no design impact. A bundle or cds Task also records its artifact (cds_artifact: the kind and slug a bundle.json names), so task-to-deploy builds from a mockup supplied any time before the Task is built. plan-tasks refuses a web-ui Task whose ui items are of two artifacts and a bundle Task with no build-spec citation. A Story with nothing to build gets no Tasks and goes straight to deploy and verify. One maker session decomposes, names the dependency edges and sizes every task, and saves the result as tasks-<slug>.json; the script validates and accepts the authored candidate, records it, and writes each Task bead through the checked relay: depscore.py plan-tasks reads that file, runs no bd command, and lists the Tasks in build order with their elab_keys (it makes repeated task keys unique as K, K-2, K-3, applying an edge on K to each, drops edges that do not join two known tasks, and refuses a cyclic graph); then the script runs one depscore.py write-task command per Task, one at a time in that order, each writing ONE Task bead under the Epic\'s Story for the slug, found in beads, with its metadata, size fingerprint and blocks edges to the Tasks written before it. With replay: true the maker does not run, and the script runs the same commands from the saved tasks-<slug>.json. Whether the beads landed is read from beads by depscore.py elaboration-finish, not judged here.',
  phases: [
    { title: 'Decompose', detail: 'one maker session: Spec -> tasks + dependency edges + job sizes; the script writes each Task bead with one depscore.py write-task command' },
  ],
}
// ===== SHARED BLOCK fable — BEGIN (canonical: scripts/shared-blocks/fable.js; edit there, then: node scripts/shared-blocks.mjs --write) =====
const ownedCoreContracts = "---\nname: subagent-contract\ndescription: >-\n  Shared contract for bounded specialist assignments: preserve role and scope, follow\n  the caller's response format, retain verifiable artifacts, and report incomplete work explicitly.\nuser-invocable: false\n---\n\n# Subagent Contract\n\n## Caller contract comes first\n\nFollow the caller's exact response schema and artifact protocol. Do not prepend `STATUS`, restate the task, add report fields, or append commentary to a machine-consumed response. Put evidence, findings, progress and blockers only in the artifacts or fields the caller provides. An artifact's on-disk schema and the response-reference schema serve different purposes; do not return the artifact body when the caller requests only its path.\n\nWhen the caller supplies a response schema, your only reply is the StructuredOutput call that carries it; in artifact mode that call carries the `{artifactPath}` the submission tool emits. A prose report never substitutes for that call. Reserve your last turns for submission: when the turn budget runs low, stop working, put the remaining work in the schema's fields and submit.\n\nWhen an executable submission/checkpoint tool is supplied, use it to validate the authored result, compute bindings and construct the response. Return its successful response unchanged through the requested channel. Do not manually manufacture completion flags or hashes. Structural validation proves neither semantic correctness nor review approval. On failure preserve work and report the exact remaining work or blocker through the caller's supported mechanism; never send a success reference for an incomplete assignment. If the supplied protocol has no failure channel, report that incompatibility to the caller rather than inventing a successful response.\n\nOnly when the caller supplies no response format, use `STATUS: DONE` or `STATUS: BLOCKED` with a concise description of deliverables and verification, or the blocker and what is needed. Claim DONE only when the assigned work is complete and verified. No separate preliminary restatement or generic final report is required.\n\n## Role and scope\n\n- Perform only the role assigned in the agent definition and task. Do not invent requirements, select downstream work or enlarge your authority.\n- Identify the minimal relevant files, artifacts and decisions. Use only allowed tools and preserve file ownership. Read-only reviewers may write caller-authorized result/checkpoint artifacts, never source artifacts.\n- An explicit assignment to repair all baseline failures in an affected repository includes pre-existing failures there. Preserve test-author ownership and required checks; this does not authorize unrelated cleanup, other repositories or invented external resources.\n- Prefer small, reversible changes unless the assignment requires broader change. Report material actions and their outcomes in the existing evidence channel, without adding fields to a fixed schema.\n- Missing required context is a named dependency, not permission to guess. Distinguish facts, justified assumptions and unresolved questions; do not silently complete only the easy portion.\n\n## Skills and authoritative artifacts\n\nRead canonical skill content already delivered in the prompt; do not reload it solely because its name also appears in frontmatter. Assess which other declared skills apply and load those through the Skill tool using their exact names. A name alone is not delivered content. A missing required skill is an explicit dependency; do not substitute recollection. Note material applicability decisions only in existing progress/evidence channels that permit them, never by expanding the return schema.\n\nRead the actual relevant source sections and connected contracts. Shared Markdown, vault notes, diagrams, schemas and JSON stay authoritative at their paths; summaries guide navigation and do not replace source verification. Observe assigned read/edit/create ownership. Preserve content unless its change is assigned. Pass references rather than copying whole documents between agents. When exact copying is required, use deterministic file tools rather than model transcription. Use version/provenance where relevant; do not require hashes merely for semantic editing.\n\nFor durable authoring, checkpoint meaningful progress using the caller's location and executable mechanism where supplied. Record completed work, remaining work and artifact references; blocked progress names the dependency and reason. Checkpoints are progress, not accepted results. On resume verify the checkpoint against actual artifacts and finish missing work without regenerating valid completed documents.\n\n## Resource use and incremental review\n\n- Use tokens conscientiously without compromising required correctness, completeness, safety or evidence. Before a material optional expansion, identify its unresolved need and expected benefit in existing progress. Routine tools need no justification. Do not add a report, review pass, token quota or human approval gate for this rule; omit optional work with no concrete benefit.\n- Makers and reviewers use the same applicable requirements, constraints and completion criteria. Review determines actual correctness, including passing sound work; finding more failures is not success. Do not invent requirements or turn stylistic preferences into blocking defects. Preserve necessary safety and regression checks.\n- Use the caller's finding format to identify the affected location, requirement/dependency at risk, observed evidence and actionable correction with a verifiable pass condition. Distinguish defects, missing evidence and proposed new requirements. Never claim unperformed checks passed.\n- Revise original artifacts incrementally. Retain valid work and applicable evidence. Rereview changed scope and affected dependencies; reopen accepted work only when new evidence or demonstrated impact invalidates its earlier evidence, and state why. Preserve required independent review.\n\n## Technical gaps are decided, not escalated\n\nWhere the approved or effective architecture, a requirement or an owner answer is silent, unclear or self-contradictory on a technical matter, decide it by best practice, with AWS Well-Architected guidance and AWS documentation as the evidence (see AWS evidence authority below). Record the decision, the gap it closes and its cited evidence in your result, and continue. A technical matter is any question of how the system works: services, patterns, interfaces, data, values and limits, security and privacy controls, cost and operations. A recorded decision is a claim reviewers check like any other; it is not an open item.\n\nTwo things go to the owner, through the channel the caller provides for them: two of the owner's business requirements that no design can satisfy together, and a conflict in arc42 section 2, which only the owner writes (constraints that contradict each other, or that no design can meet together with the business requirements). Nothing else does. Never put a technical question to the owner or any person, and never hold work waiting for a technical answer.\n\n## The approved architecture is authoritative\n\nThe approved (effective) architecture and the owner's answers are authoritative. Older documents, repository READMEs and existing code are evidence of the current state: they show what exists and what still has to change, never that the approved architecture or an owner answer is wrong. Where they disagree with the approved architecture, the approved architecture holds and the difference is work to plan, not a conflict to raise. The approved architecture changes only through a reviewed target backed by requirements and evidence, or a reviewed correction from what a Story built.\n\n## AWS evidence authority\n\nBefore any AWS claim, design choice or question, check the AWS MCP Server documentation tools (`search_documentation`, `read_documentation`, `retrieve_skill`) and the relevant AWS plugin skills (`aws-core:*`, for example `aws-core:aws-cdk`, `aws-core:aws-serverless`, `aws-core:aws-iam`, `aws-core:aws-networking`, `aws-core:aws-well-architected-review`), including the applicable Well-Architected principles. A question AWS documentation can answer is answered from it and never reaches the owner. Retain source references and the concrete tradeoffs. Existing generated architecture and model recollection do not establish correctness. Makers and reviewers use this same evidence criterion.\n\nApply guidance to stated requirements, deployment, usage and cost constraints rather than hypothetical scale. Where AWS guidance conflicts with a business requirement or a section 2 constraint, the requirement or constraint holds: record the conflict and the design that honours it, and do not silently substitute a preferred AWS pattern. Missing required MCP/skill access is a named blocker or uncertainty, never a passed check. Coordinators may research and route AWS questions, but cannot author or approve designs.\n"
const ownedArtifactContract = "---\nname: artifact-handoff\ndescription: Share authoritative documents, diagrams and JSON by artifact path, with format-specific validation and resumable checkpoints; never retype full payloads between agents.\n---\n\n## Executable output mode\n\nThe dispatcher selects `OUTPUT_MODE` from its response schema and validates an explicit mode against that schema before dispatch. `artifact` means a single `artifactPath` reference to a caller-specified candidate; the JSON candidate, progress and submission rules below apply. `inline` means a small caller-defined status, routing or control response: return that exact schema directly and do not invent candidate files or checkpoints. `machine` is the deterministic command runner protocol; its executable hook supplies the response and no model-authored payload is permitted. Merely loading this skill does not change the selected mode or grant write access. In standalone use without an explicit mode, apply artifact rules only when the caller supplies a candidate path and artifact schema; otherwise honor its inline response contract.\n\nShared documents, Markdown, diagrams and other artifacts stay in their authoritative files. Pass paths and brief task context; recipients read the actual files. A summary is navigation, never a substitute source. Edit only explicitly assigned files; preserve accepted work. Do not retype an entire document into another agent's prompt or machine response. Use existing deterministic file operations for exact copies when a copy is explicitly required.\n\nKeep the caller-specified checkpoint current after meaningful work: status, task, completed work, remaining work and artifact paths. On resume read the checkpoint and referenced artifacts, verify current state and complete remaining work. A checkpoint is progress evidence, never acceptance or permission to omit validation.\n\nFor JSON, write the caller's requested JSON object once to its exact candidate path. Use the supplied artifact schema; do not confuse it with the small return schema. Preserve existing completed work and inspect an existing candidate before continuing interrupted work. Return only the candidate path using the caller's structured return schema. Never copy the full artifact into StructuredOutput or prose.\n\nThe producer directly reads its inputs, authors its outputs and runs its own submission/checkpoint helper. The workflow's named command runner performs only coordinator acceptance and provenance operations: it invokes `scripts/portfolio/jsonartifact.py` with the expected candidate, final path and schema. The script rejects duplicate keys, invalid JSON, schema violations and changes to already accepted results. It writes canonical JSON and an integrity receipt; downstream scripts verify the receipt. Candidates stay outside the accepted result directory. A failed candidate is never treated as a completed step.\n\nThe command runner runs only the exact checked command supplied by the workflow. Validation failure is reported explicitly; it does not authorize rewriting another producer's content or repeating a successful administrative command. Existing legacy artifacts are preserved.\n\nFor Markdown and diagrams, `jsonartifact.py --document PATH` verifies the actual nonempty UTF-8 file and returns its path, raw-byte SHA-256, length and format. It never copies or rewrites the document. This receipt identifies the reviewed version; it is not a semantic quality verdict and does not prohibit later authorized edits. Keep structured metadata separate and refer to the document path instead of embedding its contents.\n\nCandidate completion checkpoints bind the exact candidate path, expected schema hash and caller revision. The workflow derives that revision from actual source-file/corpus byte fingerprints and assignment context; a path alone is not freshness evidence. Changed inputs require a new candidate revision. A saved complete result for the same revision is reused; it is never silently replaced. Fingerprints exclude the producer’s assigned output files to preserve interruption recovery.\n\n## Executable producer contract\n\nUse the caller's canonical schema for both production and review; architecture uses [writer](schemas/architecture-writer.schema.json) and [reviewer](schemas/architecture-review.schema.json). Never maintain a second schema in prose. The [checkpoint schema](schemas/checkpoint.schema.json) is shared by producer status commands.\n\nResolve `scripts/portfolio/artifactcontract.py` from this plugin's root (two directories above this skill). The workflow supplies the candidate path, canonical schema and input revision. Pass exactly one of `--schema-file PATH` or `--schema-json JSON`; both use identical strict parsing, validation and canonical hashing. Prefer the schema file when the caller supplies one. Author a small progress JSON file with `task`, `completed`, `remaining`, and `artifacts`; add `reason` when blocked. Do not put binding hashes or completion flags in that file: the helper computes them.\n\n```bash\npython3 \"$PLUGIN_ROOT/scripts/portfolio/artifactcontract.py\" checkpoint --candidate \"$CANDIDATE\" --schema-file \"$SCHEMA\" --revision \"$REVISION\" --progress-file \"$PROGRESS\" --status in-progress\npython3 \"$PLUGIN_ROOT/scripts/portfolio/artifactcontract.py\" complete --candidate \"$CANDIDATE\" --schema-file \"$SCHEMA\" --revision \"$REVISION\" --progress-file \"$PROGRESS\"\npython3 \"$PLUGIN_ROOT/scripts/portfolio/artifactcontract.py\" status --candidate \"$CANDIDATE\" --schema-file \"$SCHEMA\" --revision \"$REVISION\"\n```\n\nFor a dependency you cannot satisfy, checkpoint with `--status blocked` and its exact `reason` and remaining work. Do not mark incomplete reasoning complete merely to satisfy the schema. `complete` requires no remaining work, validates strict JSON against the canonical schema, canonicalizes the candidate and writes its bound checkpoint. Return only the candidate reference after that command succeeds. `validate` performs schema validation without mutation. Invalid commands return exit 2 with an explicit error.\n\n`complete-unaccepted` means structurally ready for the workflow's existing acceptance operation, not technically correct, approved, or shipped. Reviewers read the authoritative artifacts and independently judge evidence; mechanically valid metadata cannot establish their correctness. Status detects changed candidate bytes and changed input/schema bindings. Resume `in-progress`/`blocked` work from its actual artifacts; do not restart completed reasoning or silently retry an unchanged blocker.\n\nThe coordinator may use `scripts/portfolio/artifactpublish.py --record-argv-json JSON -- <jsonartifact acceptance arguments>` to validate/publish and record provenance in one deterministic invocation. The recorder receives argv, not shell text, and must name the accepted artifact. Pending or rejected candidates are never recorded; recorder failure reports failure and retains the accepted artifact for recovery. This replaces separate administrative agent calls without replacing specialist reasoning or independent review.\n\nFor the actual handoff use `submit` with the same arguments as `complete`: it validates and writes the checkpoint, then emits exactly the response object `{\"artifactPath\":\"...\"}`. Return that object unchanged. The schema describes the on-disk candidate; the response contains only its reference. A failed submission emits an error and never writes a new completion checkpoint. When the caller supplies `--files-root ROOT --files-field FIELD`, submission also verifies every path in that candidate field is relative to ROOT, stays inside it after symlink resolution, and names a nonempty regular file. These are declared authored outputs, not all assigned or future files. `--progress-artifacts-root ROOT` additionally checks explicitly declared progress artifact paths inside that root; use it only when the caller establishes that scope. These checks establish file existence and structure, not whether the reasoning is correct.\n"
const ownedBaselineContract = "---\nname: architecture-baseline\ndescription: Assess the effective architecture in arc42 against one PRD, find what it does not yet serve or represent, build out the architecture from non-effective documents, existing repository code and the AWS MCP Server where it falls short, and keep arc42 updated with a delta for every change. Selects justified retention, change, replacement, addition or retirement without assuming a new design is required.\nuser-invocable: false\n---\n\n# Assessing the effective architecture for a PRD\n\n## The architecture phase\n\nThe architecture is the current effective architecture in arc42: the canonical views whose `lifecycle_state` is `effective`. There is no separate baseline architecture. Every PRD builds on the effective architecture and leaves it updated, so it stays current as PRDs are processed. The architecture phase runs for every PRD and is never skipped; it is not architecture creation. It has three steps:\n\n1. **Assess.** Using the PRD as the guide, find and analyze the effective architecture to judge whether it meets the PRD's needs, capability by capability.\n2. **Build out.** Where the effective architecture does not completely serve the PRD, build it out from the non-effective architecture documents, with the code in the existing repositories on `main` as guidance and the AWS MCP Server as the authority on best practice (see below). Building out includes independent review and approval of the proposal.\n3. **Update arc42.** Integrate the approved result into arc42 as the new effective architecture, with a delta that records the change.\n\n## Authority and evidence\n\nRead the caller's architecture MODEL, specifically `reference/architecture-documentation-model.md#Assessing existing architecture and implementation` beneath the supplied architecture root when that is the project's model layout. The project model owns its document versions, review states and maintenance obligations; this skill applies them to bounded workflow assignments without inventing a second authority policy.\n\nThe owner's explicit instructions and applicable requirements and constraints establish what the work must accomplish. Apply their stated scope. Existing code, CDK, tests, drafts and incidental implementation choices are evidence of the current state; their existence does not make them binding decisions or make retention the goal. The effective architecture is a reviewed starting point, not an immutable prohibition on better justified changes. Read an actual decision and its applicability before treating it as authoritative; do not infer an owner decision from a file, an old implementation or an agent-authored statement.\n\nCompare the current system with the required target. Retain what is suitable; change, replace, add or retire what the evidence and requirements justify. Do not preserve stale design merely because it exists, and do not replace suitable work merely because a different design is possible. Explain the relevant requirement, defect, constraint or AWS guidance and the tradeoff behind a proposed change. A recommendation is evidence to assess in context, not an automatic requirement to redesign. Iteration is expected: preserve provenance and useful findings, revise the affected architecture and implementation work, and use normal Git history to make changes reviewable and reversible.\n\n## Evolve the architecture one PRD at a time\n\nAn effective document is the approved architecture under the knowledge and requirements available when it was approved, not a permanent constraint on future work. Assess the current PRD against the relevant effective views, repository behavior and connected contracts. Expand that scope only where the impact evidence requires it; do not load or redesign all PRDs to approve one. A later PRD may justify superseding a previously sound decision. Explain the new requirement or evidence, update the affected canonical views and implementation handoff, and retain unrelated valid decisions and review evidence. Unknown future requirements are not present constraints or reasons to block approval.\n\n## Assess the effective architecture before selecting work\n\nUse the caller's authoritative PRD, repository code on `main`, CDK, interfaces, data and event schemas, tests, existing arc42 views, open targets and relevant AWS documentation. Repository code and CDK represent the intended deployed system; no separate live-account inventory or deployment-access gate is required by this contract.\n\nArchitecture includes responsibilities, business behavior, interfaces, data, interactions and runtime flows as well as infrastructure. A Lambda or table declaration in CDK does not establish what the application does. For a behavioral capability, inspect the relevant implementation, entrypoints, wiring, contracts and tests. Keep behavioral evidence separate from infrastructure evidence. A test file is evidence of a test, not evidence that it passed. Cite precise sources and distinguish established behavior, inference and uncertainty. Only a genuinely infrastructure-only or documentation-only obligation may use that narrower scope; explain its applicability.\n\nRead each relevant document's actual `lifecycle_state`. `effective` and `in-review` are the existing review states; versions (`effective`, `target`, `delta`, `built`) describe the document's place in the architecture model. These dimensions are not interchangeable. An approved design need not have been implemented. Unreviewed documentation and existing code may be useful and correct, but still need validation. Missing documentation is not proof that code is absent; existing code is not proof that the required behavior is complete or suitable.\n\n## Check what the effective architecture does not yet represent\n\nEven when the effective views serve a capability, arc42 can hold content they do not yet reflect. For every capability the PRD needs, check it against:\n\n- the owner's constraints in section 2 (`02-architecture-constraints/`), including constraints added or changed since the effective views were approved;\n- canonical arc42 views still `in-review`, and other arc42 content not yet effective (for example section 4 strategy or section 8 concepts in review);\n- open targets under `target/` and build records under `built/` that show the capability's elements.\n\nA constraint or document that applies to the capability and that its effective views do not represent is a cited gap: name the constraint or document (path and heading) and the effective view that does not represent it. Give that capability `designAction` `modify` when the design must change to honour it, or `documentationAction` `update` when only the documentation lags; either places the capability in design scope. Content that does not apply to the PRD's capabilities is not in scope; mention it in the summary. When nothing is unrepresented, say so for each capability, with the documents checked. This check is part of every assessment and of every independent review of a capability left unchanged, including a review-only Check.\n\n## Build out from every available input\n\nWhen the effective architecture does not completely serve the PRD, authors build the target from:\n\n- the effective views, as the reviewed starting point;\n- the non-effective architecture documents named above, as design input: validate them and adopt what suits this PRD, rather than only avoiding contradiction with them;\n- the code in the existing repositories on `main`, as guidance: it may already be exactly the design the PRD needs, so reuse it when it is; it may also be stale and far out of date, so judge it against the PRD, the effective views and AWS best practice before following it, and never treat its existence as a reason to keep it;\n- the AWS MCP Server's documentation and skills (with the `aws-core` skills and AWS Well-Architected guidance), as the authority on best practice: every AWS design choice follows them, and where code or an older document disagrees with them, the best practice wins unless a business requirement or a section 2 constraint says otherwise.\n\n## Close over what the work rests on\n\nA PRD names the capabilities it needs, not the foundations they run on. The work of the approved delta rests on other elements the effective architecture shows: a table on its database cluster, the cluster on its network, a handler on its event bus or user pool, a service on a shared library or on a repository that does not exist yet. The handoff to implementation is complete only when every element the delta's work transitively rests on is built and current on `main`, is planned by an open bead of any Epic, or is itself carried as implementation work. After integration, the architecture step's Closure phase walks the effective views from every delta item and records each element that is absent, stale against the effective views, or planned elsewhere, with the repository that deploys it or the repository to create. These become prerequisite items: placed in their own repository, detailed and specified like any delta item, built by their own Tasks, and ordered before the Tasks that need them. A prerequisite an open bead already plans gets no new Task; the Tasks that need it are blocked by that bead. Existing code is evidence of the built state and may be stale; AWS best practice decides what the element must be.\n\n## Produce the canonical assessment\n\nThe caller supplies [the assessment schema](../artifact-handoff/schemas/architecture-baseline.schema.json) as `survey.baseline`. Each entry's `id` is exactly its surveyed capability name and its `requirements` match that capability's requirement references. Record the current state, required target, suitability evidence, rationale and unresolved conflicts. Do not use structural validity as a substitute for judging the evidence.\n\nKeep design, documentation and implementation actions separate:\n\n- A suitable approved design with missing implementation needs implementation work, not another design proposal.\n- Suitable existing behavior with missing or incomplete architecture documentation needs documentation and its review, without invented replacement code.\n- An existing unreviewed design may need validation and approval, or a bounded correction; it does not automatically need a competing proposal.\n- An unsuitable existing implementation may need change, replacement or retirement, including when its older documentation was approved.\n- A fully suitable, evidenced current capability can retain its design and implementation. Record that conclusion and evidence explicitly.\n- Different capabilities and repositories in one PRD may take different actions. Preserve those distinctions in the target and implementation handoff.\n\n`disposition` describes the implementation intent: retain, change, replace, add, retire or undetermined. It is not a document lifecycle state. Unknown evidence remains unknown; never convert it to absence, completion or permission to rebuild. The deterministic helper checks capability coverage, action consistency, required evidence categories and source freshness. It cannot establish that a cited handler implements the requirement: the appropriate independent reviewer must examine that meaning.\n\n## Bounded authoring, review and maintenance\n\nThe default is check and approve: a PRD the effective architecture and the code already serve, with nothing in arc42 left unrepresented, is independently verified and approved without design authoring. A finding in that review that the effective architecture lacks design or documentation sends the assessment back for reassessment of the affected capabilities, which then enter design scope. Select only the authors and reviewers needed for the assessed obligations and remaining gaps. No PRD automatically requires a database, API, integration, competing design or every specialty. Review relevant current claims and their affected dependencies; retain still-valid evidence when unrelated files change. Changes to cited behavior or connected contracts require targeted reassessment.\n\nWhen design authoring is needed, the coordinator names one of the selected existing authors as accountable for the combined target's coherence. This is an assignment within the chosen work, not a new agent, a fixed lead specialty or an extra dispatch. Assign that author the integration views and order its final reconciliation after the contributing outputs it needs exist. Other authors own their bounded subject views; no author must certify a later author's unwritten output. A review-only or unchanged assessment has no design owner because it has no design-authoring assignment.\n\nKeep maker, reviewer and approval responsibilities separate. An assessment does not approve a design, and a machine-generated unchanged handoff does not replace independent review. After approval, update every affected architecture view and its connected documentation at the appropriate scopes. Carry implementation additions, modifications, replacements and retirements into the TRD, specifications and tasks even when no new architecture authoring is needed. A durable unchanged target may carry zero design changes while still carrying implementation work.\n\nEvery change to the effective architecture has a delta: authored design or documentation changes are delta views beside the target, and approving existing in-review views is recorded in the target's delta handoff. A PRD the effective architecture already serves still gets a delta handoff that says so, with its implementation work.\n\nApproval leaves the covered canonical arc42 documentation correct and approved (`lifecycle_state: effective`); it does not claim implementation. Integrate reviewed target changes into the canonical views, correcting or removing superseded content at every affected scope. A target, delta or built document alone cannot satisfy canonical publication. Existing in-review canonical views may be approved in place after review; already correct and approved views need no gratuitous rewrite. Record the exact affected files so publication can be verified before completion.\n\nUse the caller's executable artifact submission and checkpoint commands. Preserve accepted work and provenance; update the assessment when its relevant inputs change. Do not add private copies of this policy to workflow prompts: workflows supply paths, schemas, task scope and executable gates, while this skill owns the assessment principles.\n"
const ownedAgentContracts = {"acceptance-criteria-reviewer":{"artifactCapable":false,"agentType":"agent-teams-workforce:acceptance-criteria-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"acceptance-criteria-writer":{"artifactCapable":true,"agentType":"acceptance-criteria-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"accessibility-validator":{"artifactCapable":true,"agentType":"agent-teams-workforce:accessibility-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:a11y-audit","agent-teams-workforce:senior-frontend"]},"advantage-evaluator":{"artifactCapable":false,"agentType":"agent-teams-workforce:advantage-evaluator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"adversarial-critique-adjudicator":{"artifactCapable":false,"agentType":"agent-teams-workforce:adversarial-critique-adjudicator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-security"]},"adversarial-review-loop-supervisor":{"artifactCapable":false,"agentType":"agent-teams-workforce:adversarial-review-loop-supervisor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"ambiguity-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:ambiguity-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"android-compose-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:android-compose-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:graphrag-lookup"]},"api-contract-designer":{"artifactCapable":true,"agentType":"api-contract-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"api-documentation-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:api-documentation-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer"]},"api-gateway-cdk-implementer":{"artifactCapable":true,"agentType":"api-gateway-cdk-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-gateway","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:graphrag-lookup"]},"api-specification-author":{"artifactCapable":true,"agentType":"api-specification-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer"]},"appsync-cdk-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:appsync-cdk-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:graphrag-lookup"]},"appsync-client-subscription-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:appsync-client-subscription-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend","agent-teams-workforce:graphrag-lookup"]},"architecture-boundary-guardian":{"artifactCapable":true,"agentType":"architecture-boundary-guardian","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"architecture-conformance-reviewer":{"artifactCapable":true,"agentType":"architecture-conformance-reviewer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:arc42","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"architecture-decider":{"artifactCapable":true,"agentType":"architecture-decider","skills":["agent-teams-workforce:architecture-baseline","agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect"]},"architecture-decision-workflow-coordinator":{"artifactCapable":true,"agentType":"architecture-decision-workflow-coordinator","skills":["agent-teams-workforce:architecture-baseline","agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"architecture-diagram-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:architecture-diagram-author","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:architecture-diagramming","agent-teams-workforce:c4-diagramming","agent-teams-workforce:uml-diagramming","agent-teams-workforce:senior-architect","agent-teams-workforce:graphrag-lookup"]},"architecture-fitness-function-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:architecture-fitness-function-author","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"architecture-impact-analyst":{"artifactCapable":false,"agentType":"agent-teams-workforce:architecture-impact-analyst","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:beads-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:graphrag-lookup"]},"architecture-maintainer":{"artifactCapable":true,"agentType":"architecture-maintainer","skills":["agent-teams-workforce:architecture-baseline","agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:arc42","agent-teams-workforce:arc42-maintain","agent-teams-workforce:c4-diagramming","agent-teams-workforce:uml-diagramming","agent-teams-workforce:senior-architect","agent-teams-workforce:graphrag-lookup"]},"architecture-pattern-challenger":{"artifactCapable":true,"agentType":"architecture-pattern-challenger","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"architecture-tradeoff-skeptic":{"artifactCapable":true,"agentType":"architecture-tradeoff-skeptic","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"athena-redshift-analytics-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:athena-redshift-analytics-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:graphrag-lookup"]},"auth-bypass-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:auth-bypass-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops","agent-teams-workforce:cognito"]},"aws-integration-test-runner":{"artifactCapable":true,"agentType":"agent-teams-workforce:aws-integration-test-runner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:test-failure-mindset","agent-teams-workforce:cumulative-regression"]},"aws-integration-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:aws-integration-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:cumulative-regression"]},"beads-format-validator":{"artifactCapable":true,"agentType":"agent-teams-workforce:beads-format-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:beads-contract"]},"bedrock-integration-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:bedrock-integration-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:bedrock","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:senior-prompt-engineer","agent-teams-workforce:aws-agentic-ai","agent-teams-workforce:graphrag-lookup"]},"behavioral-signals-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:behavioral-signals-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:senior-data-scientist","agent-teams-workforce:product-analytics","agent-teams-workforce:graphrag-lookup"]},"bounded-context-mapper":{"artifactCapable":true,"agentType":"bounded-context-mapper","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"brd-traceability-auditor":{"artifactCapable":true,"agentType":"agent-teams-workforce:brd-traceability-auditor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"c4-diagram-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:c4-diagram-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:architecture-diagramming","agent-teams-workforce:c4-diagramming","agent-teams-workforce:senior-architect","agent-teams-workforce:graphrag-lookup"]},"cdk-infrastructure-designer":{"artifactCapable":true,"agentType":"cdk-infrastructure-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"cdk-infrastructure-drift-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:cdk-infrastructure-drift-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:cloudformation"]},"cdk-stack-author":{"artifactCapable":true,"agentType":"cdk-stack-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:cloudformation"]},"cds-finding-reviewer":{"artifactCapable":false,"agentType":"agent-teams-workforce:cds-finding-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","cds:apply-design-system","cds:audit-against-system"]},"cds-ui-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:cds-ui-implementer","skills":["agent-teams-workforce:subagent-contract","cds:apply-design-system","cds:audit-against-system","cds:compose-page","agent-teams-workforce:graphrag-lookup"]},"changelog-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:changelog-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:changelog-generator"]},"chassis-extension-implementer":{"artifactCapable":true,"agentType":"chassis-extension-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:lambda","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:graphrag-lookup"]},"code-correctness-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:code-correctness-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:code-reviewer"]},"code-quality-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:code-quality-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"code-refactoring-specialist":{"artifactCapable":true,"agentType":"agent-teams-workforce:code-refactoring-specialist","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:code-reviewer","agent-teams-workforce:graphrag-lookup"]},"code-style-and-linting-enforcer":{"artifactCapable":true,"agentType":"agent-teams-workforce:code-style-and-linting-enforcer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:code-reviewer"]},"cognito-lambda-trigger-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:cognito-lambda-trigger-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:cognito","agent-teams-workforce:lambda","agent-teams-workforce:graphrag-lookup"]},"completeness-checker":{"artifactCapable":false,"agentType":"agent-teams-workforce:completeness-checker","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"complexity-analyzer":{"artifactCapable":false,"agentType":"agent-teams-workforce:complexity-analyzer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:tech-debt-tracker"]},"constitutional-agent":{"artifactCapable":false,"agentType":"agent-teams-workforce:constitutional-agent","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"constraint-extractor":{"artifactCapable":true,"agentType":"agent-teams-workforce:constraint-extractor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"consumer-driven-contract-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:consumer-driven-contract-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-test-suite-builder","agent-teams-workforce:cumulative-regression"]},"context-curator":{"artifactCapable":false,"agentType":"agent-teams-workforce:context-curator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"contract-violation-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:contract-violation-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-test-suite-builder"]},"cost-architecture-reviewer":{"artifactCapable":true,"agentType":"cost-architecture-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-cost-operations","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"cost-impact-reviewer":{"artifactCapable":true,"agentType":"cost-impact-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cost-operations","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"cross-repo-integration-test-coordinator":{"artifactCapable":false,"agentType":"agent-teams-workforce:cross-repo-integration-test-coordinator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"cross-service-contract-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:cross-service-contract-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-test-suite-builder"]},"data-consistency-checker":{"artifactCapable":true,"agentType":"agent-teams-workforce:data-consistency-checker","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb"]},"data-exposure-scanner":{"artifactCapable":true,"agentType":"agent-teams-workforce:data-exposure-scanner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"data-model-specification-author":{"artifactCapable":true,"agentType":"data-model-specification-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb","agent-teams-workforce:database-schema-designer"]},"data-pipeline-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:data-pipeline-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:cumulative-regression"]},"definition-of-done-enforcer":{"artifactCapable":true,"agentType":"agent-teams-workforce:definition-of-done-enforcer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"dependency-change-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:dependency-change-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dependency-auditor"]},"dependency-cve-auditor":{"artifactCapable":true,"agentType":"agent-teams-workforce:dependency-cve-auditor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dependency-auditor"]},"dependency-graph-extractor":{"artifactCapable":true,"agentType":"agent-teams-workforce:dependency-graph-extractor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"deployment-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:deployment-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"deployment-strategy-decider":{"artifactCapable":false,"agentType":"agent-teams-workforce:deployment-strategy-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:cove-prompt-design"]},"documentation-accuracy-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:documentation-accuracy-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"documentation-currency-auditor":{"artifactCapable":true,"agentType":"agent-teams-workforce:documentation-currency-auditor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"documentation-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:documentation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"domain-boundary-validator":{"artifactCapable":true,"agentType":"agent-teams-workforce:domain-boundary-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"domain-event-modeler":{"artifactCapable":true,"agentType":"domain-event-modeler","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"dos-resilience-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:dos-resilience-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"dynamodb-access-layer-implementer":{"artifactCapable":true,"agentType":"dynamodb-access-layer-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb","agent-teams-workforce:graphrag-lookup"]},"dynamodb-cost-optimizer":{"artifactCapable":true,"agentType":"dynamodb-cost-optimizer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb","agent-teams-workforce:aws-cost-operations"]},"dynamodb-schema-access-pattern-reviewer":{"artifactCapable":true,"agentType":"dynamodb-schema-access-pattern-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb"]},"dynamodb-streams-cdc-implementer":{"artifactCapable":true,"agentType":"dynamodb-streams-cdc-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:dynamodb","agent-teams-workforce:graphrag-lookup"]},"email-notification-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:email-notification-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:email-template-builder","agent-teams-workforce:sns","agent-teams-workforce:graphrag-lookup"]},"epic-sequencer":{"artifactCapable":true,"agentType":"agent-teams-workforce:epic-sequencer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:epic-sequencing"]},"espresso-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:espresso-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:tdd-guide","agent-teams-workforce:cumulative-regression"]},"event-api-client-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:event-api-client-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:graphrag-lookup"]},"event-driven-consumer-implementer":{"artifactCapable":true,"agentType":"event-driven-consumer-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:sqs","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:sns","agent-teams-workforce:graphrag-lookup"]},"event-flow-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:event-flow-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda"]},"event-schema-designer":{"artifactCapable":true,"agentType":"event-schema-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:eventbridge","agent-teams-workforce:sns","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"event-schema-reviewer":{"artifactCapable":true,"agentType":"event-schema-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda"]},"failure-mode-analyst":{"artifactCapable":true,"agentType":"failure-mode-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:observability-designer","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"filing-clerk":{"artifactCapable":true,"agentType":"filing-clerk","skills":["agent-teams-workforce:subagent-contract","obsidian:obsidian-cli","obsidian:obsidian-markdown","agent-teams-workforce:arc42","notebooklm","document-classification"]},"finops-analyst":{"artifactCapable":false,"agentType":"finops-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-cost-operations"]},"flaky-test-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:flaky-test-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:test-failure-mindset","agent-teams-workforce:find-cause"]},"frontend-performance-optimizer":{"artifactCapable":true,"agentType":"agent-teams-workforce:frontend-performance-optimizer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend"]},"github-actions-pipeline-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:github-actions-pipeline-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:graphrag-lookup"]},"glue-etl-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:glue-etl-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:graphrag-lookup"]},"graphql-schema-designer":{"artifactCapable":true,"agentType":"graphql-schema-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"graphql-schema-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:graphql-schema-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer"]},"implementation-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:implementation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:graphrag-lookup"]},"incident-responder":{"artifactCapable":true,"agentType":"agent-teams-workforce:incident-responder","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:find-cause","agent-teams-workforce:validation-protocol"]},"incident-response-runbook-designer":{"artifactCapable":true,"agentType":"agent-teams-workforce:incident-response-runbook-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:observability-designer"]},"infrastructure-security-scanner":{"artifactCapable":true,"agentType":"infrastructure-security-scanner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops","agent-teams-workforce:aws-cdk-development"]},"injection-attack-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:injection-attack-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"integration-pattern-architect":{"artifactCapable":true,"agentType":"integration-pattern-architect","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"integration-testing-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:integration-testing-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"ios-swiftui-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:ios-swiftui-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:graphrag-lookup"]},"kinesis-stream-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:kinesis-stream-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:graphrag-lookup"]},"lambda-performance-optimizer":{"artifactCapable":true,"agentType":"lambda-performance-optimizer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:lambda"]},"llm-observability-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:llm-observability-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:observability-designer","agent-teams-workforce:senior-prompt-engineer","agent-teams-workforce:aws-agentic-ai","agent-teams-workforce:graphrag-lookup"]},"matching-algorithm-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:matching-algorithm-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:graphrag-lookup"]},"mcp-server-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:mcp-server-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:mcp-server-builder","agent-teams-workforce:aws-agentic-ai","agent-teams-workforce:aws-mcp-setup","agent-teams-workforce:graphrag-lookup"]},"ml-evaluation-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:ml-evaluation-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:senior-data-scientist","agent-teams-workforce:cumulative-regression"]},"mobile-e2e-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:mobile-e2e-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"nextjs-component-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:nextjs-component-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend","agent-teams-workforce:a11y-audit","agent-teams-workforce:senior-fullstack","agent-teams-workforce:graphrag-lookup"]},"nfr-analyst":{"artifactCapable":false,"agentType":"agent-teams-workforce:nfr-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:product-discovery"]},"okr-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:okr-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-strategist","agent-teams-workforce:product-analytics"]},"openapi-contract-reviewer":{"artifactCapable":false,"agentType":"openapi-contract-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer"]},"operational-readiness-reviewer":{"artifactCapable":true,"agentType":"operational-readiness-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:observability-designer","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"payments-integration-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:payments-integration-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:stripe-integration-expert","agent-teams-workforce:secrets-manager","agent-teams-workforce:graphrag-lookup"]},"performance-benchmark-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:performance-benchmark-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"permission-escalation-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:permission-escalation-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops","agent-teams-workforce:iam"]},"persistence-architecture-specialist":{"artifactCapable":true,"agentType":"persistence-architecture-specialist","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:dynamodb","agent-teams-workforce:database-schema-designer","agent-teams-workforce:rds","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"persona-profile-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:persona-profile-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:product-analytics"]},"phase-gate-enforcer":{"artifactCapable":false,"agentType":"agent-teams-workforce:phase-gate-enforcer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:cumulative-regression"]},"playwright-e2e-web-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:playwright-e2e-web-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:a11y-audit","agent-teams-workforce:cumulative-regression"]},"polyrepo-steward":{"artifactCapable":true,"agentType":"agent-teams-workforce:polyrepo-steward","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:graphrag-lookup"]},"power-tools-configuration-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:power-tools-configuration-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:lambda","agent-teams-workforce:secrets-manager","agent-teams-workforce:graphrag-lookup"]},"prd-alignment-verifier":{"artifactCapable":true,"agentType":"agent-teams-workforce:prd-alignment-verifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"prd-creation-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:prd-creation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"prd-reality-reconciler":{"artifactCapable":true,"agentType":"prd-reality-reconciler","skills":["agent-teams-workforce:architecture-baseline","agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:graphrag-lookup"]},"prd-trd-traceability-verifier":{"artifactCapable":true,"agentType":"agent-teams-workforce:prd-trd-traceability-verifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"prd-validation-analyst":{"artifactCapable":true,"agentType":"agent-teams-workforce:prd-validation-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"prd-validation-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:prd-validation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"prd-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:prd-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"production-readiness-review-facilitator":{"artifactCapable":false,"agentType":"agent-teams-workforce:production-readiness-review-facilitator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"race-condition-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:race-condition-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"react-native-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:react-native-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend","agent-teams-workforce:graphrag-lookup"]},"readme-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:readme-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"recommendation-engine-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:recommendation-engine-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:graphrag-lookup"]},"regression-coverage-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:regression-coverage-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:artifact-handoff","agent-teams-workforce:cumulative-regression"]},"regression-impact-assessor":{"artifactCapable":true,"agentType":"agent-teams-workforce:regression-impact-assessor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:artifact-handoff","agent-teams-workforce:cumulative-regression"]},"requirements-clarifier":{"artifactCapable":false,"agentType":"agent-teams-workforce:requirements-clarifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:product-discovery"]},"requirements-conflict-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:requirements-conflict-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"root-cause-analyst":{"artifactCapable":false,"agentType":"agent-teams-workforce:root-cause-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:find-cause","agent-teams-workforce:test-failure-mindset","agent-teams-workforce:graphrag-lookup"]},"run-ledger-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:run-ledger-writer","skills":["agent-teams-workforce:subagent-contract"]},"s3-data-lake-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:s3-data-lake-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:s3","agent-teams-workforce:graphrag-lookup"]},"sdlc-pipeline-orchestrator":{"artifactCapable":false,"agentType":"agent-teams-workforce:sdlc-pipeline-orchestrator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:beads-contract"]},"security-architecture-designer":{"artifactCapable":true,"agentType":"security-architecture-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-security","agent-teams-workforce:iam","agent-teams-workforce:secrets-manager","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"security-test-case-designer":{"artifactCapable":true,"agentType":"agent-teams-workforce:security-test-case-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-security","agent-teams-workforce:cumulative-regression"]},"slo-error-budget-designer":{"artifactCapable":false,"agentType":"slo-error-budget-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:observability-designer","agent-teams-workforce:cloudwatch"]},"smoke-test-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:smoke-test-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"spec-authoring-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:spec-authoring-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"spec-currency-validator":{"artifactCapable":true,"agentType":"agent-teams-workforce:spec-currency-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"spec-decider":{"artifactCapable":false,"agentType":"spec-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:cove-prompt-design"]},"spec-freshness-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:spec-freshness-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"stakeholder-request-intake-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:stakeholder-request-intake-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"task-decomposer":{"artifactCapable":true,"agentType":"task-decomposer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:beads-contract","agent-teams-workforce:graphrag-lookup"]},"task-decomposition-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:task-decomposition-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:beads-contract","agent-teams-workforce:graphrag-lookup"]},"task-dependency-mapper":{"artifactCapable":true,"agentType":"task-dependency-mapper","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:beads-contract"]},"task-readiness-runner":{"artifactCapable":false,"agentType":"agent-teams-workforce:task-readiness-runner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:beads-contract"]},"tdd-unit-test-generator":{"artifactCapable":true,"agentType":"agent-teams-workforce:tdd-unit-test-generator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:tdd-guide","agent-teams-workforce:cumulative-regression"]},"test-command-resolver":{"artifactCapable":false,"agentType":"agent-teams-workforce:test-command-resolver","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:test-failure-mindset"]},"test-coverage-gap-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:test-coverage-gap-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"test-design-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:test-design-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"test-environment-orchestrator":{"artifactCapable":true,"agentType":"test-environment-orchestrator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:aws-mcp-setup"]},"test-failure-parser":{"artifactCapable":false,"agentType":"agent-teams-workforce:test-failure-parser","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:test-failure-mindset"]},"test-isolation-specialist":{"artifactCapable":true,"agentType":"agent-teams-workforce:test-isolation-specialist","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:tdd-guide","agent-teams-workforce:test-failure-mindset"]},"test-plan-strategy-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:test-plan-strategy-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"test-strategy-decider":{"artifactCapable":false,"agentType":"agent-teams-workforce:test-strategy-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cove-prompt-design"]},"trd-author":{"artifactCapable":true,"agentType":"trd-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"trd-authoring-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:trd-authoring-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"trd-decider":{"artifactCapable":false,"agentType":"agent-teams-workforce:trd-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"trd-validator":{"artifactCapable":false,"agentType":"agent-teams-workforce:trd-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"ubiquitous-language-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:ubiquitous-language-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"uml-diagram-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:uml-diagram-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:architecture-diagramming","agent-teams-workforce:uml-diagramming","agent-teams-workforce:senior-architect","agent-teams-workforce:graphrag-lookup"]},"user-guide-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:user-guide-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:roadmap-communicator"]},"user-story-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:user-story-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:beads-contract"]},"user-story-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:user-story-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"vector-search-embeddings-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:vector-search-embeddings-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:rag-architect","agent-teams-workforce:graphrag-lookup"]},"webauthn-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:webauthn-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend","agent-teams-workforce:cognito","agent-teams-workforce:graphrag-lookup"]},"workflow-command-runner":{"artifactCapable":false,"agentType":"agent-teams-workforce:workflow-command-runner","skills":[]},"worktree-independent-verifier":{"artifactCapable":false,"agentType":"agent-teams-workforce:worktree-independent-verifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"wsjf-scorer":{"artifactCapable":true,"agentType":"agent-teams-workforce:wsjf-scorer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-strategist","agent-teams-workforce:wsjf","agent-teams-workforce:beads-contract"]},"wsjf-scoring-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:wsjf-scoring-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-strategist","agent-teams-workforce:wsjf"]},"xcuitest-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:xcuitest-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:tdd-guide","agent-teams-workforce:cumulative-regression"]}}
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
  const { outputMode: _mode, architectureBaseline = false, ...runtimeOptions } = options || {}
  options = { ...runtimeOptions, agentType: contract.agentType }
  const domainSkills = contract.skills.filter(name => !['agent-teams-workforce:subagent-contract', 'agent-teams-workforce:artifact-handoff'].includes(name))
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
      if (out.bridge !== true) return { captureError: 'deterministic StructuredOutput handoff hook did not run; captured output is retained and no model-copy fallback is permitted' }
      if (out.state === 'not-started') { operation = 'registered'; continue }
      if (out.state !== 'completed') return { captureError: out.error || 'registered command outcome unknown; original command will not repeat' }
      const receipt = out.receipt
      let exact = false
      try { exact = receipt && receipt.request === request && receipt.commandSha256 === commandSha256 && receipt.exitCode === out.exitCode && Number.isInteger(out.exitCode) && Number.isSafeInteger(receipt.bytes) && receipt.bytes >= 0 && receipt.bytes <= 1048576 && typeof out.stdout === 'string' && out.stdout.length === receipt.bytes && HEX.test(String(receipt.sha256)) && sha256Ascii(out.stdout) === receipt.sha256 } catch (_) { exact = false }
      if (!exact) return { captureError: 'machine handoff failed current request/command/exit/byte verification' }
      if (typeof dispatchFailures !== 'undefined') for (const entry of recovered) { const at = dispatchFailures.indexOf(entry); if (at >= 0) dispatchFailures.splice(at, 1) }
      return { exitCode: out.exitCode, stdout: out.stdout, receipt, machine: true }
    }
    return { captureError: 'registered command could not hand back its result after three bounded machine attempts' }
  }
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
    const registered = fableInput.relayExecutionId && fableInput.relayRequestDir && fableInput.relayCaptureScript
    const out = registered
      ? await registeredCommand(dispatch, { label, phase, command }, ordinal)
      : fableRecovery
        ? file && readRunner && fableInput.relayExecutionId
          ? await captureCommand(dispatch, { label, phase, command, file, readRunner }, ordinal)
          : await dispatch(prompt(command), { label, phase, agentType: 'agent-teams-workforce:workflow-command-runner', model: 'sonnet', effort: 'low', schema: SCHEMA })
        : { captureError: 'deterministic relay registry is unavailable: launch with the updated host relayExecutionId, relayRequestDir and relayCaptureScript contract' }
    if (out && out.captureError) {
      const error = `RELAY_COPY_RECOVERY_EXHAUSTED ${JSON.stringify({ label, relayFile: file, attempts: 2, reason: out.captureError })}`
      log(error)
      return { ok: false, paused: true, recoveryKind: 'relay-copy-recovery', error }
    }
    if (!out) return { ok: false, noResult: true, error: `the ${label} runner returned no result` }
    let got = parse(out.stdout, file)
    if (got.why && out.machine) return { ok: false, error: `${label}: exact saved command output is invalid: ${got.why}` }
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
    return `\n\nARTIFACT CONTRACT DATA:
Candidate: ${candidate}
Progress: ${progress}
Input revision: ${revision}
Submission command: ${submit}
Checkpoint command: ${command('checkpoint', ['--progress-file', progress])}
Status command: ${command('status')}`
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
    if (probe && receipt && receipt.blocked === true) {
      const detail = { candidate, revision, reason: String(receipt.reason || 'producer blocked'), remaining: receipt.remaining || [] }
      return { ok: false, blocked: true, resumable: true, error: `ARTIFACT_BLOCKED ${JSON.stringify(detail)}`, ...detail }
    }
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
//   spec: { id?, title?, description?, source?, repoPath? }, story: { id?, key?, title? },
//   specDocs?: [{ path, ref }], repoPath?, pluginRoot,
//   detailingPath?: <absolute path of the repository's saved delta detailing, recon-<slug>.json; the maker reads it>,
//   artifacts: { dir, relDir?, epicId, script, phase, slug, inputs? },
//   beads: { script, repo, epicId, projectRoot? }  (script: the absolute depscore.py path),
//   packagesDir?: string (the packages directory every cds bundle a Task cites must sit in; omitted accepts the bundles the detailing cites),
//   replay?: true
// }
// returns { ok, resumed?, spec, repoPath, story: { id, elabKey }, tasks, edges, summary }; tasks, edges and
//           summary carry what the writing session relayed, and are empty or null where it relayed nothing,
//           or { ok: false, stage, reason, dispatchFailed? }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}

function artifactsFrom(x) {
  if (!x || typeof x !== 'object') return null
  return ['dir', 'script', 'epicId', 'phase'].every((k) => typeof x[k] === 'string' && x[k]) ? x : null
}
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
/** The save instruction appended to the maker's prompt; the workflow checks and records the file after the maker returns. */
const ART = artifactsFrom(a.artifacts)
const artSlug = ART && typeof ART.slug === 'string' && ART.slug ? ART.slug : 'repo'
const hasText = (v) => typeof v === 'string' && v.trim().length > 0
const beadsFrom = (x) => (x && typeof x === 'object' && ['script', 'repo', 'epicId'].every((k) => hasText(x[k])) ? x : null)
const BEADS = beadsFrom(a.beads)

const spec = a.spec || {}
const story = a.story || {}

const specRef = spec.id || spec.title || '(unspecified spec)'
const storyRef = story.key || null
const repoPath = spec.repoPath || a.repoPath || null

const specDocs = (Array.isArray(a.specDocs) ? a.specDocs : [])
  .map((d) => (typeof d === 'string' ? { path: d, ref: null } : d && typeof d === 'object' ? d : null))
  .filter((d) => d && typeof d.path === 'string' && d.path.trim())
  .map((d) => ({ path: d.path.trim(), ref: typeof d.ref === 'string' && d.ref.trim() ? d.ref.trim() : null }))
const docsBlock = specDocs.length
  ? `\n\nSPEC DOCUMENTS — THE CONTRACT. The text above is a navigation aid only; the API contract, data model, event contracts, error handling, acceptance criteria and Definition of Done are in these files. Read the sections each task needs before you decompose:\n${specDocs
      .map((d) => `- ${d.path}${d.ref ? `  (cite as: ${d.ref})` : ''}`)
      .join('\n')}`
  : '\n\nSPEC DOCUMENTS: none were supplied, so the text above is all there is.'

const writtenPath = ART ? `${ART.dir}/story-${artSlug}.written.json` : null
const existingBlock = writtenPath
  ? `\n\nEXISTING TASKS under this Story: read the file ${writtenPath} — the result of writing this Story — and take its "existingTasks" list (none when the file or the list is absent or empty). When a task you write covers the same work as one of them, set its \`reuses\` to that task's exact elabKey; otherwise set \`reuses\` to null. Never reuse one elabKey for two tasks.\n\nOPEN TASKS OF OTHER EPICS in this repository: take the "otherEpicTasks" list of the same file (none when it is absent or empty). When work you would give a task is already planned by one of them, or by a bead a \`planned-elsewhere\` item names, do not write that task: put that Task's id in \`blockedByExternal\` of every task of yours that needs the work built first. Otherwise set \`blockedByExternal\` to an empty list.`
  : '\n\nEXISTING TASKS: none. Set every task\'s `reuses` to null and its `blockedByExternal` to an empty list.'

const detailingPath = typeof a.detailingPath === 'string' && a.detailingPath.trim().startsWith('/') ? a.detailingPath.trim() : null
const detailingBlock = detailingPath
  ? `\n\nTHE DELTA DETAILING of this repository is the file ${detailingPath}. Read it: its \`items\` give each delta item its id (the ids \`requirementIds\` cites), its status, its element, the \`from\` and \`to\` state, its surface and its evidence; its \`uiAuthority.uiItems\` give each \`ui\` item its design source — bundle (a cds bundle the owner supplied, with its build spec), cds (designed with the CDS design system) or none (no design change).`
  : ''
const specBlock = `Spec ${spec.id || ''}: ${spec.title || ''}
${spec.description || ''}
${spec.source ? `Source: ${spec.source}` : ''}
Repository: ${repoPath || '(repo path not provided)'}
Parent Story: ${storyRef}${story.title ? ` — ${story.title}` : ''}${detailingBlock}${docsBlock}${existingBlock}`

// The surface names tdd-red and integration select writers and suites by.
const SURFACES = ['api-contract', 'event-chain', 'auth', 'performance', 'web-ui', 'ios', 'android', 'cross-platform-mobile', 'ml', 'data-pipeline']

const taskSchema = {
  type: 'object',
  additionalProperties: false,
  required: ['key', 'title', 'description', 'type', 'acceptanceCriteria', 'definitionOfDone', 'specPaths', 'specSections', 'requirementIds', 'surfaces', 'reuses', 'blockedByExternal'],
  properties: {
    key: { type: 'string' },
    title: { type: 'string' },
    description: { type: 'string' },
    type: { type: 'string', enum: ['task'] },
    acceptanceCriteria: { type: 'array', items: { type: 'string' } },
    definitionOfDone: { type: 'array', items: { type: 'string' } },
    specPaths: { type: 'array', items: { type: 'string' } },
    specSections: { type: 'array', items: { type: 'string' } },
    requirementIds: { type: 'array', items: { type: 'string' } },
    decisionIds: { type: 'array', items: { type: 'string' } },
    reuses: { type: ['string', 'null'] },
    blockedByExternal: { type: 'array', items: { type: 'string' } },
    surfaces: { type: ['array', 'null'], items: { type: 'string', enum: SURFACES } },
  },
}
const testStrategySchema = {
  type: ['object', 'null'],
  additionalProperties: false,
  required: ['pyramid', 'coverageThreshold', 'envMatrix', 'source'],
  properties: {
    pyramid: { type: 'string' },
    coverageThreshold: { type: 'string' },
    envMatrix: { type: 'array', items: { type: 'string' } },
    source: { type: 'string' },
  },
}

const writable = !!(ART && BEADS && hasText(repoPath))
const taskArgs = writable
  ? [
      `--dir ${shq(ART.dir)} --slug ${shq(artSlug)} --repo ${shq(repoPath)}`,
      hasText(BEADS.projectRoot) ? `--project-root ${shq(BEADS.projectRoot)}` : '',
      hasText(a.packagesDir) ? `--packages-dir ${shq(a.packagesDir.trim())}` : '',
    ].filter(Boolean).join(' ')
  : ''
/** The relay files of this Story's commands, numbered so a run's names are deterministic. */
const RELAY_DIR = writable ? `${ART.dir}/relay/tasks-${artSlug}` : ''
const RELAY_RUNNER = writable ? BEADS.script.replace(/[^/]+$/, 'relayrun.py') : ''
let relaySeq = 0
function relayFile(label) {
  relaySeq += 1
  return `${RELAY_DIR}/${String(relaySeq).padStart(3, '0')}-${String(label).replace(/[^A-Za-z0-9._-]+/g, '-')}.json`
}
const depscore = (label, tail, repo) => relayKit.depscore(settleAgent, { label, phase: 'Decompose', script: BEADS.script, repo: repo || null, tail, file: relayFile(label) })
/**
 * Writes each Task bead from the saved tasks-<slug>.json: depscore.py plan-tasks lists the Tasks in
 * build order, then one depscore.py write-task per Task, in that order, stopping at the first that
 * fails. Returns { plan, written, error }: written holds each write-task result checked through the relay.
 */
async function writeTasks() {
  const plan = await depscore('beads:plan-tasks', `plan-tasks ${taskArgs}`, null)
  if (plan.error) return { plan: null, written: [], error: `depscore.py plan-tasks: ${plan.error}` }
  if (!Array.isArray(plan.tasks)) return { plan: null, written: [], error: 'depscore.py plan-tasks printed no task list' }
  const written = []
  for (const t of plan.tasks) {
    const key = t && hasText(t.key) ? t.key.trim() : ''
    if (!key) return { plan, written, error: 'depscore.py plan-tasks listed a task with no key' }
    const external = (Array.isArray(t.blockedByExternal) ? t.blockedByExternal : []).filter(hasText).map((x) => x.trim())
    const tail = `write-task --epic ${shq(BEADS.epicId)} --key ${shq(key)} ${taskArgs}${external.length ? ` --blocked-by-external ${shq(external.join(','))}` : ''}`
    const w = await depscore(`beads:write-task:${key}`, tail, BEADS.repo)
    if (w.error) return { plan, written, error: `depscore.py write-task ${key}: ${w.error}` }
    if (!w.task || w.task.key !== key || !hasText(w.task.id)) return { plan, written, error: `depscore.py write-task ${key}: no verified Task id for the requested key` }
    written.push(w)
  }
  return { plan, written, error: '' }
}
/** Records the saved tasks-<slug>.json with the artifact script's `record`; returns '' or why it was not recorded. */
async function recordTasks() {
  const inputs = (Array.isArray(ART.inputs) ? ART.inputs : []).filter(hasText)
  const argv = ['python3', ART.script, 'record', `${ART.dir}/tasks-${artSlug}.json`, '--epic', ART.epicId, '--phase', ART.phase, ...(inputs.length ? ['--inputs', ...inputs] : [])]
  const r = await relayKit.run(settleAgent, { label: 'record:tasks', phase: 'Decompose', runner: RELAY_RUNNER, argv, file: relayFile('record:tasks'), keys: ['sha256', 'bytes'], tail: 20 })
  if (!r.ok) return r.error
  return r.exitCode === 0 ? '' : `the record command exited ${r.exitCode}: ${String(r.stderrTail || r.stdoutTail || '').trim().slice(0, 600)}`
}

phase('Decompose')
log(`Decomposing, sequencing, and sizing ${specRef}`)

const wsjfTaskSchema = {
  type: 'object',
  additionalProperties: false,
  required: ['key', 'jobSize', 'sizeLow', 'sizeHigh', 'sizeConfidence', 'rationale'],
  properties: {
    key: { type: 'string' },
    jobSize: { type: 'number' },
    sizeLow: { type: 'number' },
    sizeHigh: { type: 'number' },
    sizeConfidence: { type: 'integer' },
    rationale: { type: 'string' },
  },
}

const WSJF_SKILL_DIR = typeof a.pluginRoot === 'string' && a.pluginRoot.startsWith('/') ? `${a.pluginRoot.replace(/\/+$/, '')}/skills/wsjf` : null
const JOB_SIZE_BRIEF = `Size each task under "Job Size" in the \`agent-teams-workforce:wsjf\` rubric${WSJF_SKILL_DIR ? ` (${WSJF_SKILL_DIR}/SKILL.md)` : ''}: the relative amount of work to deliver the task's outcome, judged against the agent pipeline as the reference capability — not calendar time and not human effort. Weigh volume, complexity, knowledge and uncertainty together to place it. The scale is Fibonacci (1, 2, 3, 5, 8, 13, 21, and upward); compare with the rubric's reference jobs. Every size carries \`sizeLow\` and \`sizeHigh\`, the plausible range with the size inside it, and \`sizeConfidence\`, an integer percent. Value, time criticality and risk reduction are inherited from the parent Epic and computed from the dependency graph, and are NOT yours to assign. A Task above 13 should have been split: say so in your notes, and record the size you judged.`

if (!writable) {
  return dispatchOutcome({ ok: false, stage: 'input', reason: 'no artifact directory, beads target or repository was supplied, so the Task beads cannot be written', spec: specRef })
}
const replayed = a.replay === true
if (replayed) log(`Decompose replayed: the Tasks are written from the saved tasks-${artSlug}.json`)
const decompositionSchema = {
      type: 'object',
      additionalProperties: false,
      required: ['tasks', 'testStrategy', 'rationale', 'edges', 'scores'],
      properties: {
        tasks: { type: 'array', items: taskSchema },
        testStrategy: testStrategySchema,
        rationale: { type: 'string' },
        edges: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['from', 'to'],
            properties: {
              from: { type: 'string' },
              to: { type: 'string' },
            },
          },
        },
        scores: { type: 'array', items: wsjfTaskSchema },
        notes: { type: 'string' },
      },
    }
const candidateFile = `${ART.dir}/candidates/tasks-${artSlug}.json`
const inputBinding = replayed ? null : await relayKit.artifactRevision(settleAgent, { label: 'decompose:inputs', phase: 'Decompose', runner: RELAY_RUNNER, files: [...new Set([...(ART.inputs || []), ...specDocs.map(d => d.path), detailingPath, writtenPath].filter(hasText))], relayFile: relayFile('decompose-inputs'), context: { spec, story, repoPath } })
if (inputBinding && !inputBinding.ok) return dispatchOutcome({ ok: false, stage: 'decompose', reason: inputBinding.error })
const inputRevision = inputBinding ? inputBinding.revision : ''
const makeTasks = () => settleAgent(
  `Three maker jobs on the Spec below, in order, one pass. Do NOT write code.

JOB 1 — DECOMPOSE (return in \`tasks\` + \`rationale\`): decompose the Spec into TASKS. Each task is a coherent piece of the Story's work within the single repository named below that one agent can test and build in one session, with testable acceptance criteria. A small Story may be one task.
- A task is BUILD work: it changes code, infrastructure or documentation. The Spec's acceptance criteria are the tests of the build tasks: each build task carries in \`acceptanceCriteria\` the criteria it satisfies, and its Red step writes those tests before it builds. A task whose only work is writing or running tests is never emitted.
- Only a delta item the detailing marks \`add\`, \`modify\` or \`remove\` makes work; a \`done\` or \`planned-elsewhere\` item gets no task. Every task cites in \`requirementIds\` at least one such item it builds: depscore.py plan-tasks refuses a task that cites none, and no bead is written.
- Every such item, a prerequisite item included, is built by a task. An item the delta lists another item as requiring is built before it: depscore.py plan-tasks writes that edge, and the bead that plans a \`planned-elsewhere\` required item as a blocker, from the delta's \`requires\` relations, and refuses the plan when a required item marked add, modify or remove has no task.
- When nothing needs building, return an empty \`tasks\` list with empty \`edges\` and \`scores\`, and say why in \`rationale\`. The Story then has no Tasks and goes straight to deploy and verify. Give each a unique local "key" (T1, T2, …). You emit TASKS ONLY — every item has type "task". Do not emit an Epic, a Story, or a loose feature: the Epic and the Story already exist upstream, and every task you emit is a child of the Story named below.

EVIDENCE CONTINUITY. In each task's existing description, retain the detailing/spec's exact repository path, source commit, file:line or document heading and the obligation IDs linked by requirementIds. State what that evidence already establishes and the concrete remaining gap. Reuse sufficient evidence at the same main revision. Before another source read, name the changed revision, missing evidence or unanswered question that calls for it; check only the relevant paths and affected integration dependencies. If the main revision changed or a legacy citation has no revision, refresh only the affected evidence and record the new revision while preserving the historical citation. Do not claim an unchanged source proves tests ran. A working path stays preserved, a stub names its missing behavior, and a missing integration cites its attachment point; none warrants a fresh fleet survey.

EXISTING-REPOSITORY TASKS ARE INCREMENTAL CHANGES. In this same decomposition pass, use the detailing's citations and inspect the relevant existing entrypoints, implementation, contracts and focused tests in the named repository. Do not repeat a fleet survey. Code may be working, incomplete, a stub or unverified: neither trust it solely because it exists nor replace it wholesale because its provenance is uncertain. In each task's existing \`description\`, identify the inspected current behavior with file:line references, the concrete gap, affected files/integration points, required behavioral change and supported behavior/contracts to preserve. The task's \`acceptanceCriteria\` and \`definitionOfDone\` specify how to verify that change and the relevant regression boundary; distinguish tests merely read from results actually observed. Reuse evidenced working parts. Any replacement must have a requirement-backed reason and respect the approved architecture. Missing code becomes a bounded implementation task in the existing owner, not a new feature/service/repository by default. If current code materially contradicts a detailing status or the spec, report the conflict in \`rationale\`/\`notes\` for correction instead of silently changing the approved scope or inventing build work.

Every task also carries its CONTRACT, taken from the spec documents listed below:
- \`specPaths\`: the spec documents this task builds against, cited EXACTLY as the "cite as" value given for each. At least one.
- \`specSections\`: the headings or anchors inside those documents that define this task.
- \`requirementIds\`: the delta item ids (D1, D2, …) the task builds, as the detailing below lists them, and the TRD requirement ids it satisfies.
- \`decisionIds\`: the architecture views the spec documents cite for the part of the design this task builds, each a path relative to the arc42 folder with its \`#<heading>\` where the spec gives one. Copy them; never invent one.
- \`definitionOfDone\`: the Definition of Done items that apply to this task, from the spec's DoD.
- \`blockedByExternal\`: the ids of open Tasks of other Epics that must be built before this task, as described under OPEN TASKS OF OTHER EPICS below; an empty list when there are none.
- \`surfaces\`: the boundaries the task touches, from the enum only (${SURFACES.join(', ')}). An empty list means it touches none of them; null means the spec does not settle it. A task that builds a \`ui\` delta item carries \`web-ui\` and cites that item's id in \`requirementIds\`: write-task then records in its contract the design source of the items it cites — bundle (the supplied cds bundle and the \`build-spec.md\` Sections the detailing resolved; the builder builds from it and is audited against it), cds (the builder designs with the CDS design system and is audited against the live design system) or none (no design change, built like any other code); a bundle or cds task also records the artifact (kind and slug) its UI is, and the build uses the newest bundle of that artifact supplied when the task is built. A task builds one artifact: keep the ui items of different artifacts in different tasks, since depscore.py plan-tasks refuses a task that cites ui items of two artifacts.
And once for the whole set, \`testStrategy\`: the test strategy the spec states (pyramid, coverageThreshold, envMatrix, and the section it came from as \`source\`), or null when the spec states none.

JOB 2 — SEQUENCE (return in \`edges\`): the dependencies between the tasks as a DIRECTED ACYCLIC graph. An edge "from -> to" means "from must be built before to", and both ends are keys of tasks you returned.

JOB 3 — SIZE EVERY TASK (return in \`scores\`): ${JOB_SIZE_BRIEF} Return one entry per task: its \`key\`, its \`jobSize\`, \`sizeLow\`, \`sizeHigh\`, \`sizeConfidence\`, and a one-line \`rationale\`.

${specBlock}${relayKit.artifactBrief(candidateFile, decompositionSchema, inputRevision, RELAY_RUNNER.replace(/[^/]+$/, 'artifactcontract.py'))}`,
  {
    label: 'decompose:sequence-and-score',
    effort: 'medium',
    phase: 'Decompose',
    agentType: 'task-decomposer',
    schema: relayKit.ARTIFACT_SCHEMA,
  }
)
if (dispatchInterruption) return dispatchOutcome({ ok: false, stage: 'decompose', spec: specRef })
let taskFacts = null
let recordError = ''
if (!replayed) {
  const saved = await relayKit.authorArtifact(settleAgent, { label: 'save:tasks', phase: 'Decompose', runner: RELAY_RUNNER, candidate: candidateFile, file: `${ART.dir}/tasks-${artSlug}.json`, schema: decompositionSchema, revision: inputRevision, relayFile: relayFile('accepted-tasks'), keys: ['tasks.key', 'tasks.title'] }, makeTasks, () => !!dispatchInterruption)
  taskFacts = saved.facts
  if (!saved.ok) {
    const deaths = dispatchDeaths('Decompose')
    return dispatchOutcome({
      ok: false,
      stage: 'decompose',
      reason: `tasks-${artSlug}.json was not accepted as the authoritative decomposition, so no Task bead was written: ${saved.error || 'not saved'}`,
      spec: specRef,
      ...(deaths.length ? { dispatchFailed: true, dispatchFailures: deaths } : {}),
    })
  }
  recordError = await recordTasks()
  if (recordError) return dispatchOutcome({ ok: false, stage: 'persistence', reason: recordError, spec: specRef, artifactPath: `${ART.dir}/tasks-${artSlug}.json`, persistErrors: [recordError] })
}
const ran = await writeTasks()
if (ran.error) log(`Story story:${artSlug}: the Task beads were not all written — ${ran.error}`)
const plan = ran.plan
const written = ran.written.filter((w) => w && w.task)
const writtenTasks = written.length
  ? written.map((w) => w.task)
  : plan
    ? plan.tasks.map((t) => ({ key: t.key, elabKey: t.elabKey, id: null, action: null, title: t.title, dependsOn: t.dependsOn, outsideBlockers: [] }))
    : (taskFacts && Array.isArray(taskFacts.tasks) ? taskFacts.tasks : []).map((t) => ({ key: t.key, elabKey: null, id: null, action: null, title: t.title, dependsOn: [], outsideBlockers: [] }))
const edges = { added: 0, removed: 0, standing: 0 }
for (const w of written) for (const k of Object.keys(edges)) edges[k] += Number(w.edges && w.edges[k]) || 0
const actions = written.map((w) => w.task.action)
const summary = written.length
  ? {
      created: actions.filter((x) => x === 'created').length,
      updated: actions.filter((x) => x === 'updated').length,
      unchanged: actions.filter((x) => x === 'unchanged' || x === 'unchanged-started').length,
    }
  : null
if (taskFacts && !taskFacts.tasks.length) log(`Story story:${artSlug}: no Tasks; rationale is in ${ART.dir}/tasks-${artSlug}.json`)
log(`Story story:${artSlug}: ${written.length} write-task result(s) relayed${summary ? ` ${JSON.stringify(summary)}` : ''}; beads is read at finish`)

return dispatchOutcome({
  ok: !ran.error,
  ...(ran.error ? { stage: 'task-write', reason: ran.error, artifactPath: `${ART.dir}/tasks-${artSlug}.json` } : {}),
  ...(replayed ? { resumed: true } : {}),
  spec: specRef,
  repoPath,
  story: { id: story.id || null, elabKey: `story:${artSlug}` },
  tasks: writtenTasks,
  edges,
  summary,
  ...(ran.error ? { writeError: ran.error } : {}),
  ...(recordError ? { persistErrors: [`tasks-${artSlug}.json: ${recordError}`] } : {}),
})
