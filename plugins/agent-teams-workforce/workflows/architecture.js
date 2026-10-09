export const meta = {
  name: 'architecture',
  description:
    "Runs for every PRD and is never skipped. Assesses the effective architecture in arc42 against the PRD, capability by capability, with current repository behavior and CDK, arc42 review states, open work and relevant AWS guidance, and checks that section 2 constraints and non-effective arc42 content (in-review views, open targets) are represented in it. Where the effective architecture falls short, authors build out the target from the non-effective documents, the code in the existing repositories and the AWS MCP Server, under independent review and the decider's approval; a review that finds unrepresented content sends the assessment back so the affected capabilities enter design scope. Preserves explicit per-capability current-to-target actions: retain, change, replace, add or retire; no fixed specialty or proposal quota applies. The approved target and its delta are integrated into canonical arc42 views, independently checked and set effective, correcting or removing superseded content. Suitable existing views can be approved without rewriting; implementation gaps remain in the target/delta handoff even when no architecture change is needed. The Closure phase then walks the effective views from every delta item to the elements its work rests on and writes those not built and current to delta/closure.json as prerequisites. Retain valid saved work and refresh only inputs or evidence that changed.",
  phases: [
    { title: 'Survey', detail: 'the polyrepo-steward names the repositories; a prd-reality-reconciler session assesses, for each capability the PRD needs, the effective views, code on main, open beads and open targets, and what section 2 constraints and non-effective arc42 content the effective views do not yet represent' },
    { title: 'Check', detail: 'when the survey finds every capability served by the effective architecture and the code on main, with nothing in arc42 left unrepresented, one architecture-boundary-guardian session verifies every coverage row and that section 2 constraints and non-effective arc42 content are represented, and the decider rules, with no coordinator and no design authoring; a finding sends the survey back once to reassess the affected capabilities; otherwise the capabilities the survey marks for design, documentation or unresolved evidence form the design scope' },
    { title: 'Rounds', detail: 'the coordinator names each round of proposers, reviewers, diagram authors and cost reviewers; the script runs them and tracks every claim and finding' },
    { title: 'Decide', detail: 'after the team has designed, challenged and settled the target, the architecture-decider approves it, choosing where the team left competing solutions, or returns it to a named proposer; only two business requirements no design can satisfy together, or section 2 constraints the owner wrote that contradict each other or that no design can meet together with the PRD, reach the owner' },
    { title: 'Target', detail: 'depscore.py arch-target writes the approved draft to target/<subject>/ as in-review, each document once: a partial change as target views and delta/ of the change alone, an entirely new architecture as target views that are also its delta, and no architecture change as baseline.json alone (the current views it cites are the future set; no delta). baseline.json always carries that note and the implementation gaps against the code on main' },
    { title: 'Integrate', detail: 'the architecture-maintainer integrates the target into arc42; the architecture-conformance-reviewer checks it; depscore.py arch-approve sets the reviewed files to effective; depscore.py arch-commit commits and pushes the integrated files; with no design or documentation change, depscore.py arch-approve sets the independently approved in-review views to effective with no maintainer' },
    { title: 'Closure', detail: 'never skipped: the polyrepo-steward names what each repository deploys on main; a prd-reality-reconciler session walks the effective views from every build item (delta elements and implementation gaps) to the elements its work rests on and records each one not built and current (absent, stale, or planned by an open bead of any Epic) with the repository that deploys it or the repository to create; depscore.py arch-closure checks it against the build items and the open beads and writes target/<subject>/closure.json, which depscore.py arch-delta merges as prerequisite items' },
  ],
}
// ===== SHARED BLOCK fable — BEGIN (canonical: scripts/shared-blocks/fable.js; edit there, then: node scripts/shared-blocks.mjs --write) =====
const ownedCoreContracts = "---\nname: subagent-contract\ndescription: >-\n  Shared contract for bounded specialist assignments: preserve role and scope, follow\n  the caller's response format, retain verifiable artifacts, and report incomplete work explicitly.\nuser-invocable: false\n---\n\n# Subagent Contract\n\n## Caller contract comes first\n\nFollow the caller's exact response schema and artifact protocol. Do not prepend `STATUS`, restate the task, add report fields, or append commentary to a machine-consumed response. Put evidence, findings, progress and blockers only in the artifacts or fields the caller provides. An artifact's on-disk schema and the response-reference schema serve different purposes; do not return the artifact body when the caller requests only its path.\n\nWhen the caller supplies a response schema, your only reply is the StructuredOutput call that carries it; in artifact mode that call carries the `{artifactPath}` the submission tool emits. A prose report never substitutes for that call. Reserve your last turns for submission: when the turn budget runs low, stop working, put the remaining work in the schema's fields and submit.\n\nWhen an executable submission/checkpoint tool is supplied, use it to validate the authored result, compute bindings and construct the response. Return its successful response unchanged through the requested channel. Do not manually manufacture completion flags or hashes. Structural validation proves neither semantic correctness nor review approval. On failure preserve work and report the exact remaining work or blocker through the caller's supported mechanism; never send a success reference for an incomplete assignment. If the supplied protocol has no failure channel, report that incompatibility to the caller rather than inventing a successful response.\n\nOnly when the caller supplies no response format, use `STATUS: DONE` or `STATUS: BLOCKED` with a concise description of deliverables and verification, or the blocker and what is needed. Claim DONE only when the assigned work is complete and verified. No separate preliminary restatement or generic final report is required.\n\n## Role and scope\n\n- Perform only the role assigned in the agent definition and task. Do not invent requirements, select downstream work or enlarge your authority.\n- Identify the minimal relevant files, artifacts and decisions. Use only allowed tools and preserve file ownership. Read-only reviewers may write caller-authorized result/checkpoint artifacts, never source artifacts.\n- An explicit assignment to repair all baseline failures in an affected repository includes pre-existing failures there. Preserve test-author ownership and required checks; this does not authorize unrelated cleanup, other repositories or invented external resources.\n- Prefer small, reversible changes unless the assignment requires broader change. Report material actions and their outcomes in the existing evidence channel, without adding fields to a fixed schema.\n- Pipeline beads are always read and written in the central beads database, wherever you run: run every `bd` command as `atw-bd` with `bd`'s own arguments, never a plain `bd` (the `beads-contract` skill).\n- Missing required context is a named dependency, not permission to guess. Distinguish facts, justified assumptions and unresolved questions; do not silently complete only the easy portion.\n\n## Skills and authoritative artifacts\n\nRead canonical skill content already delivered in the prompt; do not reload it solely because its name also appears in frontmatter. Assess which other declared skills apply and load those through the Skill tool using their exact names. A name alone is not delivered content. A missing required skill is an explicit dependency; do not substitute recollection. Note material applicability decisions only in existing progress/evidence channels that permit them, never by expanding the return schema.\n\nRead the actual relevant source sections and connected contracts. Shared Markdown, vault notes, diagrams, schemas and JSON stay authoritative at their paths; summaries guide navigation and do not replace source verification. Observe assigned read/edit/create ownership. Preserve content unless its change is assigned. Pass references rather than copying whole documents between agents. When exact copying is required, use deterministic file tools rather than model transcription. Use version/provenance where relevant; do not require hashes merely for semantic editing.\n\nFor durable authoring, checkpoint meaningful progress using the caller's location and executable mechanism where supplied. Record completed work, remaining work and artifact references; blocked progress names the dependency and reason. Checkpoints are progress, not accepted results. On resume verify the checkpoint against actual artifacts and finish missing work without regenerating valid completed documents.\n\n## Resource use and incremental review\n\n- Use tokens conscientiously without compromising required correctness, completeness, safety or evidence. Before a material optional expansion, identify its unresolved need and expected benefit in existing progress. Routine tools need no justification. Do not add a report, review pass, token quota or human approval gate for this rule; omit optional work with no concrete benefit.\n- Makers and reviewers use the same applicable requirements, constraints and completion criteria. Review determines actual correctness, including passing sound work; finding more failures is not success. Do not invent requirements or turn stylistic preferences into blocking defects. Preserve necessary safety and regression checks.\n- Use the caller's finding format to identify the affected location, requirement/dependency at risk, observed evidence and actionable correction with a verifiable pass condition. Distinguish defects, missing evidence and proposed new requirements. Never claim unperformed checks passed.\n- Revise original artifacts incrementally. Retain valid work and applicable evidence. Rereview changed scope and affected dependencies; reopen accepted work only when new evidence or demonstrated impact invalidates its earlier evidence, and state why. Preserve required independent review.\n\n## Technical gaps are decided, not escalated\n\nWhere the approved or effective architecture, a requirement or an owner answer is silent, unclear or self-contradictory on a technical matter, decide it by best practice, with AWS Well-Architected guidance and AWS documentation as the evidence (see AWS evidence authority below). Record the decision, the gap it closes and its cited evidence in your result, and continue. A technical matter is any question of how the system works: services, patterns, interfaces, data, values and limits, security and privacy controls, cost and operations. A recorded decision is a claim reviewers check like any other; it is not an open item.\n\nTwo things go to the owner, through the channel the caller provides for them: two of the owner's business requirements that no design can satisfy together, and a conflict in arc42 section 2, which only the owner writes (constraints that contradict each other, or that no design can meet together with the business requirements). Nothing else does. Never put a technical question to the owner or any person, and never hold work waiting for a technical answer.\n\n## The approved architecture is authoritative\n\nThe approved (effective) architecture and the owner's answers are authoritative. Older documents, repository READMEs and existing code are evidence of the current state: they show what exists and what still has to change, never that the approved architecture or an owner answer is wrong. Where they disagree with the approved architecture, the approved architecture holds and the difference is work to plan, not a conflict to raise. The approved architecture changes only through a reviewed target backed by requirements and evidence, or a reviewed correction from what a Story built.\n\n## AWS evidence authority\n\nBefore any AWS claim, design choice or question, check the AWS MCP Server documentation tools (`search_documentation`, `read_documentation`, `retrieve_skill`) and the relevant AWS plugin skills (`aws-core:*`, for example `aws-core:aws-cdk`, `aws-core:aws-serverless`, `aws-core:aws-iam`, `aws-core:aws-networking`, `aws-core:aws-well-architected-review`), including the applicable Well-Architected principles. A question AWS documentation can answer is answered from it and never reaches the owner. Retain source references and the concrete tradeoffs. Existing generated architecture and model recollection do not establish correctness. Makers and reviewers use this same evidence criterion.\n\nApply guidance to stated requirements, deployment, usage and cost constraints rather than hypothetical scale. Where AWS guidance conflicts with a business requirement or a section 2 constraint, the requirement or constraint holds: record the conflict and the design that honours it, and do not silently substitute a preferred AWS pattern. Missing required MCP/skill access is a named blocker or uncertainty, never a passed check. Coordinators may research and route AWS questions, but cannot author or approve designs.\n"
const ownedArtifactContract = "---\nname: artifact-handoff\ndescription: Share authoritative documents, diagrams and JSON by artifact path, with format-specific validation and resumable checkpoints; never retype full payloads between agents.\n---\n\n## Executable output mode\n\nThe dispatcher selects `OUTPUT_MODE` from its response schema and validates an explicit mode against that schema before dispatch. `artifact` means a single `artifactPath` reference to a caller-specified candidate; the JSON candidate, progress and submission rules below apply. `inline` means a small caller-defined status, routing or control response: return that exact schema directly and do not invent candidate files or checkpoints. `machine` is the deterministic command runner protocol; its executable hook supplies the response and no model-authored payload is permitted. Merely loading this skill does not change the selected mode or grant write access. In standalone use without an explicit mode, apply artifact rules only when the caller supplies a candidate path and artifact schema; otherwise honor its inline response contract.\n\nShared documents, Markdown, diagrams and other artifacts stay in their authoritative files. Pass paths and brief task context; recipients read the actual files. A summary is navigation, never a substitute source. Edit only explicitly assigned files; preserve accepted work. Do not retype an entire document into another agent's prompt or machine response. Use existing deterministic file operations for exact copies when a copy is explicitly required.\n\nKeep the caller-specified checkpoint current after meaningful work: status, task, completed work, remaining work and artifact paths. On resume read the checkpoint and referenced artifacts, verify current state and complete remaining work. A checkpoint is progress evidence, never acceptance or permission to omit validation.\n\nFor JSON, write the caller's requested JSON object once to its exact candidate path. Use the supplied artifact schema; do not confuse it with the small return schema. Preserve existing completed work and inspect an existing candidate before continuing interrupted work. Return only the candidate path using the caller's structured return schema. Never copy the full artifact into StructuredOutput or prose.\n\nThe producer directly reads its inputs, authors its outputs and runs its own submission/checkpoint helper. The workflow's named command runner performs only coordinator acceptance and provenance operations: it invokes `scripts/portfolio/jsonartifact.py` with the expected candidate, final path and schema. The script rejects duplicate keys, invalid JSON and schema violations; a changed result replaces the accepted one, whose bytes are kept as `<name>.prev`. It writes canonical JSON and an integrity receipt; downstream scripts verify the receipt. Candidates stay outside the accepted result directory. A failed candidate is never treated as a completed step.\n\nThe command runner runs only the exact checked command supplied by the workflow. Validation failure is reported explicitly; it does not authorize rewriting another producer's content or repeating a successful administrative command. Existing legacy artifacts are preserved.\n\nFor Markdown and diagrams, `jsonartifact.py --document PATH` verifies the actual nonempty UTF-8 file and returns its path, raw-byte SHA-256, length and format. It never copies or rewrites the document. This receipt identifies the reviewed version; it is not a semantic quality verdict and does not prohibit later authorized edits. Keep structured metadata separate and refer to the document path instead of embedding its contents.\n\nCandidate completion checkpoints bind the exact candidate path, expected schema hash and caller revision. The workflow derives that revision from actual source-file/corpus byte fingerprints and assignment context; a path alone is not freshness evidence. Changed inputs require a new candidate revision. A saved complete result for the same revision is reused. Fingerprints exclude the producer’s assigned output files to preserve interruption recovery.\n\n## Executable producer contract\n\nUse the caller's canonical schema for both production and review; architecture uses [writer](schemas/architecture-writer.schema.json) and [reviewer](schemas/architecture-review.schema.json). Never maintain a second schema in prose. The [checkpoint schema](schemas/checkpoint.schema.json) is shared by producer status commands.\n\nResolve `scripts/portfolio/artifactcontract.py` from this plugin's root (two directories above this skill). The workflow supplies the candidate path, canonical schema and input revision. Pass exactly one of `--schema-file PATH` or `--schema-json JSON`; both use identical strict parsing, validation and canonical hashing. Prefer the schema file when the caller supplies one. Author a small progress JSON file with `task`, `completed`, `remaining`, and `artifacts`; add `reason` when blocked. Do not put binding hashes or completion flags in that file: the helper computes them.\n\n```bash\npython3 \"$PLUGIN_ROOT/scripts/portfolio/artifactcontract.py\" checkpoint --candidate \"$CANDIDATE\" --schema-file \"$SCHEMA\" --revision \"$REVISION\" --progress-file \"$PROGRESS\" --status in-progress\npython3 \"$PLUGIN_ROOT/scripts/portfolio/artifactcontract.py\" complete --candidate \"$CANDIDATE\" --schema-file \"$SCHEMA\" --revision \"$REVISION\" --progress-file \"$PROGRESS\"\npython3 \"$PLUGIN_ROOT/scripts/portfolio/artifactcontract.py\" status --candidate \"$CANDIDATE\" --schema-file \"$SCHEMA\" --revision \"$REVISION\"\n```\n\nFor a dependency you cannot satisfy, checkpoint with `--status blocked` and its exact `reason` and remaining work. Do not mark incomplete reasoning complete merely to satisfy the schema. `complete` validates strict JSON against the canonical schema, canonicalizes the candidate and writes its bound checkpoint. Return only the candidate reference after that command succeeds. `validate` performs schema validation without mutation. Invalid commands return exit 2 with an explicit error.\n\n`complete-unaccepted` means structurally ready for the workflow's existing acceptance operation, not technically correct, approved, or shipped. Reviewers read the authoritative artifacts and independently judge evidence; mechanically valid metadata cannot establish their correctness. Status detects changed candidate bytes and changed input/schema bindings. Resume `in-progress`/`blocked` work from its actual artifacts; do not restart completed reasoning or silently retry an unchanged blocker.\n\nThe coordinator may use `scripts/portfolio/artifactpublish.py --record-argv-json JSON -- <jsonartifact acceptance arguments>` to validate/publish and record provenance in one deterministic invocation. The recorder receives argv, not shell text, and must name the accepted artifact. Pending or rejected candidates are never recorded; a recorder failure is reported in the receipt (`recorded: false`, with the reason) and the accepted artifact stands. This replaces separate administrative agent calls without replacing specialist reasoning or independent review.\n\nFor the actual handoff use `submit` with the same arguments as `complete`: it validates and writes the checkpoint, then emits exactly the response object `{\"artifactPath\":\"...\"}`. Return that object unchanged. The schema describes the on-disk candidate; the response contains only its reference. A failed submission emits an error and never writes a new completion checkpoint. When the caller supplies `--files-root ROOT --files-field FIELD`, submission also verifies every path in that candidate field is relative to ROOT, stays inside it after symlink resolution, and names a nonempty regular file. These are declared authored outputs, not all assigned or future files. `--progress-artifacts-root ROOT` additionally checks explicitly declared progress artifact paths inside that root; use it only when the caller establishes that scope. These checks establish file existence and structure, not whether the reasoning is correct.\n"
const ownedBaselineContract = "---\nname: architecture-baseline\ndescription: Assess the effective architecture in arc42 against one PRD, find what it does not yet serve or represent, build out the architecture from non-effective documents, existing repository code and the AWS MCP Server where it falls short, and keep arc42 updated with a delta for every change. Selects justified retention, change, replacement, addition or retirement without assuming a new design is required.\nuser-invocable: false\n---\n\n# Assessing the effective architecture for a PRD\n\n## The architecture phase\n\nThe architecture is the current effective architecture in arc42: the canonical views whose `lifecycle_state` is `effective`. There is no separate baseline architecture. Every PRD builds on the effective architecture and leaves it updated, so it stays current as PRDs are processed. The architecture phase runs for every PRD and is never skipped; it is not architecture creation. It has three steps:\n\n1. **Assess.** Using the PRD as the guide, find and analyze the effective architecture to judge whether it meets the PRD's needs, capability by capability.\n2. **Build out.** Where the effective architecture does not completely serve the PRD, build it out from the non-effective architecture documents, with the code in the existing repositories on `main` as guidance and the AWS MCP Server as the authority on best practice (see below). Building out includes independent review and approval of the proposal.\n3. **Update arc42.** Integrate the approved result into arc42 as the new effective architecture, with a delta that records the change.\n\n## Authority and evidence\n\nRead the caller's architecture MODEL, specifically `reference/architecture-documentation-model.md#Assessing existing architecture and implementation` beneath the supplied architecture root when that is the project's model layout. The project model owns its document versions, review states and maintenance obligations; this skill applies them to bounded workflow assignments without inventing a second authority policy.\n\nThe owner's explicit instructions and applicable requirements and constraints establish what the work must accomplish. Apply their stated scope. Existing code, CDK, tests, drafts and incidental implementation choices are evidence of the current state; their existence does not make them binding decisions or make retention the goal. The effective architecture is a reviewed starting point, not an immutable prohibition on better justified changes. Read an actual decision and its applicability before treating it as authoritative; do not infer an owner decision from a file, an old implementation or an agent-authored statement.\n\nCompare the current system with the required target. Retain what is suitable; change, replace, add or retire what the evidence and requirements justify. Do not preserve stale design merely because it exists, and do not replace suitable work merely because a different design is possible. Explain the relevant requirement, defect, constraint or AWS guidance and the tradeoff behind a proposed change. A recommendation is evidence to assess in context, not an automatic requirement to redesign. Iteration is expected: preserve provenance and useful findings, revise the affected architecture and implementation work, and use normal Git history to make changes reviewable and reversible.\n\n## Evolve the architecture one PRD at a time\n\nAn effective document is the approved architecture under the knowledge and requirements available when it was approved, not a permanent constraint on future work. Assess the current PRD against the relevant effective views, repository behavior and connected contracts. Expand that scope only where the impact evidence requires it; do not load or redesign all PRDs to approve one. A later PRD may justify superseding a previously sound decision. Explain the new requirement or evidence, update the affected canonical views and implementation handoff, and retain unrelated valid decisions and review evidence. Unknown future requirements are not present constraints or reasons to block approval.\n\n## Assess the effective architecture before selecting work\n\nUse the caller's authoritative PRD, repository code on `main`, CDK, interfaces, data and event schemas, tests, existing arc42 views, open targets and relevant AWS documentation. Repository code and CDK represent the intended deployed system; no separate live-account inventory or deployment-access gate is required by this contract.\n\nArchitecture includes responsibilities, business behavior, interfaces, data, interactions and runtime flows as well as infrastructure. A Lambda or table declaration in CDK does not establish what the application does. For a behavioral capability, inspect the relevant implementation, entrypoints, wiring, contracts and tests. Keep behavioral evidence separate from infrastructure evidence. A test file is evidence of a test, not evidence that it passed. Cite precise sources and distinguish established behavior, inference and uncertainty. Only a genuinely infrastructure-only or documentation-only obligation may use that narrower scope; explain its applicability.\n\nRead each relevant document's actual `lifecycle_state`. `effective` and `in-review` are the existing review states; versions (`effective`, `target`, `delta`, `built`) describe the document's place in the architecture model. These dimensions are not interchangeable. An approved design need not have been implemented. Unreviewed documentation and existing code may be useful and correct, but still need validation. Missing documentation is not proof that code is absent; existing code is not proof that the required behavior is complete or suitable.\n\n## Check what the effective architecture does not yet represent\n\nEven when the effective views serve a capability, arc42 can hold content they do not yet reflect. For every capability the PRD needs, check it against:\n\n- the owner's constraints in section 2 (`02-architecture-constraints/`), including constraints added or changed since the effective views were approved;\n- canonical arc42 views still `in-review`, and other arc42 content not yet effective (for example section 4 strategy or section 8 concepts in review);\n- open targets under `target/` and build records under `built/` that show the capability's elements.\n\nAn open target is design input, not approved design. Its `baseline.json` records `arc42Revision`, the revision of the effective version it was designed against. When that revision is missing, or effective views of the same elements were approved after the target was written (their last commit in the vault is later than the target's), the survey and the Check judge the target possibly stale: validate each part against the current effective views before adopting it, and record in the assessment what was found superseded.\n\nA constraint or document that applies to the capability and that its effective views do not represent is a cited gap: name the constraint or document (path and heading) and the effective view that does not represent it. Give that capability `designAction` `modify` when the design must change to honour it, or `documentationAction` `update` when only the documentation lags; either places the capability in design scope. Content that does not apply to the PRD's capabilities is not in scope; mention it in the summary. When nothing is unrepresented, say so for each capability, with the documents checked. This check is part of every assessment and of every independent review of a capability left unchanged, including a review-only Check.\n\n## Build out from every available input\n\nWhen the effective architecture does not completely serve the PRD, authors build the target from:\n\n- the effective views, as the reviewed starting point;\n- the non-effective architecture documents named above, as design input: validate them and adopt what suits this PRD, rather than only avoiding contradiction with them;\n- the code in the existing repositories on `main`, as guidance: it may already be exactly the design the PRD needs, so reuse it when it is; it may also be stale and far out of date, so judge it against the PRD, the effective views and AWS best practice before following it, and never treat its existence as a reason to keep it;\n- the AWS MCP Server's documentation and skills (with the `aws-core` skills and AWS Well-Architected guidance), as the authority on best practice: every AWS design choice follows them, and where code or an older document disagrees with them, the best practice wins unless a business requirement or a section 2 constraint says otherwise.\n\n## Close over what the work rests on\n\nA PRD names the capabilities it needs, not the foundations they run on. The work of the approved delta rests on other elements the effective architecture shows: a table on its database cluster, the cluster on its network, a handler on its event bus or user pool, a service on a shared library or on a repository that does not exist yet. The handoff to implementation is complete only when every element the delta's work transitively rests on is built and current on `main`, is planned by an open bead of any Epic, or is itself carried as implementation work. After integration, the architecture step's Closure phase walks the effective views from every delta item and records each element that is absent, stale against the effective views, or planned elsewhere, with the repository that deploys it or the repository to create. These become prerequisite items: placed in their own repository, detailed and specified like any delta item, built by their own Tasks, and ordered before the Tasks that need them. A prerequisite an open bead already plans gets no new Task; the Tasks that need it are blocked by that bead. Existing code is evidence of the built state and may be stale; AWS best practice decides what the element must be.\n\n## Produce the canonical assessment\n\nThe caller supplies [the assessment schema](../artifact-handoff/schemas/architecture-baseline.schema.json) as `survey.baseline`. Each entry's `id` is exactly its surveyed capability name and its `requirements` match that capability's requirement references. Record the current state, required target, suitability evidence, rationale and unresolved conflicts. Do not use structural validity as a substitute for judging the evidence.\n\nKeep design, documentation and implementation actions separate:\n\n- A suitable approved design with missing implementation needs implementation work, not another design proposal.\n- Suitable existing behavior with missing or incomplete architecture documentation needs documentation and its review, without invented replacement code.\n- An existing unreviewed design may need validation and approval, or a bounded correction; it does not automatically need a competing proposal.\n- An unsuitable existing implementation may need change, replacement or retirement, including when its older documentation was approved.\n- A fully suitable, evidenced current capability can retain its design and implementation. Record that conclusion and evidence explicitly.\n- Different capabilities and repositories in one PRD may take different actions. Preserve those distinctions in the target and implementation handoff.\n\n`disposition` describes the implementation intent: retain, change, replace, add, retire or undetermined. It is not a document lifecycle state. Unknown evidence remains unknown; never convert it to absence, completion or permission to rebuild. The deterministic helper checks capability coverage, action consistency, required evidence categories and source freshness. It cannot establish that a cited handler implements the requirement: the appropriate independent reviewer must examine that meaning.\n\n## Bounded authoring, review and maintenance\n\nThe default is check and approve: a PRD the effective architecture and the code already serve, with nothing in arc42 left unrepresented, is independently verified and approved without design authoring. A finding in that review that the effective architecture lacks design or documentation sends the assessment back for reassessment of the affected capabilities, which then enter design scope. Select only the authors and reviewers needed for the assessed obligations and remaining gaps. No PRD automatically requires a database, API, integration, competing design or every specialty. Review relevant current claims and their affected dependencies; retain still-valid evidence when unrelated files change. Changes to cited behavior or connected contracts require targeted reassessment.\n\nWhen design authoring is needed, the workflow makes the last selected author accountable for the combined target's coherence. This is an assignment within the chosen work, not a new agent, a fixed lead specialty or an extra dispatch. The coordinator lists that author last and assigns it the integration views, so its final reconciliation runs after the contributing outputs it needs exist. Other authors own their bounded subject views; no author must certify a later author's unwritten output. A review-only or unchanged assessment has no design owner because it has no design-authoring assignment.\n\nKeep maker, reviewer and approval responsibilities separate. An assessment does not approve a design, and a machine-generated unchanged handoff does not replace independent review. After approval, update every affected architecture view and its connected documentation at the appropriate scopes. Carry implementation additions, modifications, replacements and retirements into the TRD, specifications and tasks even when no new architecture authoring is needed. A durable unchanged target may carry zero design changes while still carrying implementation work.\n\nEvery change to the effective architecture has a delta: authored design or documentation changes are delta views beside the target, and approving existing in-review views is recorded in the target's delta handoff. A PRD the effective architecture already serves still gets a delta handoff that says so, with its implementation work.\n\nApproval leaves the covered canonical arc42 documentation correct and approved (`lifecycle_state: effective`); it does not claim implementation. Integrate reviewed target changes into the canonical views, correcting or removing superseded content at every affected scope. A target, delta or built document alone cannot satisfy canonical publication. Existing in-review canonical views may be approved in place after review; already correct and approved views need no gratuitous rewrite. Record the exact affected files so publication can be verified before completion.\n\nUse the caller's executable artifact submission and checkpoint commands. Preserve accepted work and provenance; update the assessment when its relevant inputs change. Do not add private copies of this policy to workflow prompts: workflows supply paths, schemas, task scope and executable gates, while this skill owns the assessment principles.\n"
const ownedAgentContracts = {"acceptance-criteria-reviewer":{"artifactCapable":false,"agentType":"agent-teams-workforce:acceptance-criteria-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"acceptance-criteria-writer":{"artifactCapable":true,"agentType":"acceptance-criteria-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"accessibility-validator":{"artifactCapable":true,"agentType":"agent-teams-workforce:accessibility-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:a11y-audit","agent-teams-workforce:senior-frontend"]},"advantage-evaluator":{"artifactCapable":false,"agentType":"agent-teams-workforce:advantage-evaluator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"adversarial-critique-adjudicator":{"artifactCapable":false,"agentType":"agent-teams-workforce:adversarial-critique-adjudicator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-security"]},"adversarial-review-loop-supervisor":{"artifactCapable":false,"agentType":"agent-teams-workforce:adversarial-review-loop-supervisor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"ambiguity-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:ambiguity-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"android-compose-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:android-compose-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:graphrag-lookup"]},"api-contract-designer":{"artifactCapable":true,"agentType":"api-contract-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"api-documentation-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:api-documentation-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer"]},"api-gateway-cdk-implementer":{"artifactCapable":true,"agentType":"api-gateway-cdk-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-gateway","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"api-specification-author":{"artifactCapable":true,"agentType":"api-specification-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer"]},"appsync-cdk-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:appsync-cdk-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"appsync-client-subscription-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:appsync-client-subscription-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend","agent-teams-workforce:graphrag-lookup"]},"architecture-boundary-guardian":{"artifactCapable":true,"agentType":"architecture-boundary-guardian","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"architecture-conformance-reviewer":{"artifactCapable":true,"agentType":"architecture-conformance-reviewer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:arc42","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"architecture-decider":{"artifactCapable":true,"agentType":"architecture-decider","skills":["agent-teams-workforce:architecture-baseline","agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect"]},"architecture-decision-workflow-coordinator":{"artifactCapable":true,"agentType":"architecture-decision-workflow-coordinator","skills":["agent-teams-workforce:architecture-baseline","agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"architecture-diagram-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:architecture-diagram-author","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:architecture-diagramming","agent-teams-workforce:c4-diagramming","agent-teams-workforce:uml-diagramming","agent-teams-workforce:senior-architect","agent-teams-workforce:graphrag-lookup"]},"architecture-fitness-function-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:architecture-fitness-function-author","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"architecture-impact-analyst":{"artifactCapable":false,"agentType":"agent-teams-workforce:architecture-impact-analyst","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:beads-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:graphrag-lookup"]},"architecture-maintainer":{"artifactCapable":true,"agentType":"architecture-maintainer","skills":["agent-teams-workforce:architecture-baseline","agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:arc42","agent-teams-workforce:arc42-maintain","agent-teams-workforce:c4-diagramming","agent-teams-workforce:uml-diagramming","agent-teams-workforce:senior-architect","agent-teams-workforce:graphrag-lookup"]},"architecture-pattern-challenger":{"artifactCapable":true,"agentType":"architecture-pattern-challenger","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"architecture-tradeoff-skeptic":{"artifactCapable":true,"agentType":"architecture-tradeoff-skeptic","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"athena-redshift-analytics-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:athena-redshift-analytics-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:graphrag-lookup"]},"auth-bypass-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:auth-bypass-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops","agent-teams-workforce:cognito"]},"aws-integration-test-runner":{"artifactCapable":true,"agentType":"agent-teams-workforce:aws-integration-test-runner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:test-failure-mindset","agent-teams-workforce:cumulative-regression"]},"aws-integration-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:aws-integration-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:cumulative-regression"]},"beads-format-validator":{"artifactCapable":true,"agentType":"agent-teams-workforce:beads-format-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:beads-contract"]},"bedrock-integration-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:bedrock-integration-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:bedrock","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:senior-prompt-engineer","agent-teams-workforce:aws-agentic-ai","agent-teams-workforce:graphrag-lookup"]},"behavioral-signals-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:behavioral-signals-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:senior-data-scientist","agent-teams-workforce:product-analytics","agent-teams-workforce:graphrag-lookup"]},"bounded-context-mapper":{"artifactCapable":true,"agentType":"bounded-context-mapper","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"brd-traceability-auditor":{"artifactCapable":true,"agentType":"agent-teams-workforce:brd-traceability-auditor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"c4-diagram-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:c4-diagram-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:architecture-diagramming","agent-teams-workforce:c4-diagramming","agent-teams-workforce:senior-architect","agent-teams-workforce:graphrag-lookup"]},"cdk-infrastructure-designer":{"artifactCapable":true,"agentType":"cdk-infrastructure-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"cdk-infrastructure-drift-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:cdk-infrastructure-drift-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:cloudformation"]},"cdk-stack-author":{"artifactCapable":true,"agentType":"cdk-stack-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cdk-development","agent-teams-workforce:cloudformation","agent-teams-workforce:resource-naming"]},"cds-finding-reviewer":{"artifactCapable":false,"agentType":"agent-teams-workforce:cds-finding-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","cds:apply-design-system","cds:audit-against-system"]},"cds-ui-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:cds-ui-implementer","skills":["agent-teams-workforce:subagent-contract","cds:apply-design-system","cds:audit-against-system","cds:compose-page","agent-teams-workforce:graphrag-lookup"]},"changelog-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:changelog-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:changelog-generator"]},"chassis-extension-implementer":{"artifactCapable":true,"agentType":"chassis-extension-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:lambda","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"code-correctness-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:code-correctness-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:code-reviewer"]},"code-quality-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:code-quality-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"code-refactoring-specialist":{"artifactCapable":true,"agentType":"agent-teams-workforce:code-refactoring-specialist","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:code-reviewer","agent-teams-workforce:graphrag-lookup"]},"code-style-and-linting-enforcer":{"artifactCapable":true,"agentType":"agent-teams-workforce:code-style-and-linting-enforcer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:code-reviewer"]},"cognito-lambda-trigger-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:cognito-lambda-trigger-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:cognito","agent-teams-workforce:lambda","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"completeness-checker":{"artifactCapable":false,"agentType":"agent-teams-workforce:completeness-checker","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"complexity-analyzer":{"artifactCapable":false,"agentType":"agent-teams-workforce:complexity-analyzer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:tech-debt-tracker"]},"constitutional-agent":{"artifactCapable":false,"agentType":"agent-teams-workforce:constitutional-agent","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"constraint-extractor":{"artifactCapable":true,"agentType":"agent-teams-workforce:constraint-extractor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"consumer-driven-contract-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:consumer-driven-contract-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-test-suite-builder","agent-teams-workforce:cumulative-regression"]},"context-curator":{"artifactCapable":false,"agentType":"agent-teams-workforce:context-curator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"contract-violation-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:contract-violation-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-test-suite-builder"]},"cost-architecture-reviewer":{"artifactCapable":true,"agentType":"cost-architecture-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-cost-operations","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"cost-impact-reviewer":{"artifactCapable":true,"agentType":"cost-impact-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-cost-operations","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"cross-repo-integration-test-coordinator":{"artifactCapable":false,"agentType":"agent-teams-workforce:cross-repo-integration-test-coordinator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"cross-service-contract-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:cross-service-contract-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-test-suite-builder"]},"data-consistency-checker":{"artifactCapable":true,"agentType":"agent-teams-workforce:data-consistency-checker","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb"]},"data-exposure-scanner":{"artifactCapable":true,"agentType":"agent-teams-workforce:data-exposure-scanner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"data-model-specification-author":{"artifactCapable":true,"agentType":"data-model-specification-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb","agent-teams-workforce:database-schema-designer"]},"data-pipeline-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:data-pipeline-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:cumulative-regression"]},"definition-of-done-enforcer":{"artifactCapable":true,"agentType":"agent-teams-workforce:definition-of-done-enforcer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"dependency-change-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:dependency-change-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dependency-auditor"]},"dependency-cve-auditor":{"artifactCapable":true,"agentType":"agent-teams-workforce:dependency-cve-auditor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dependency-auditor"]},"dependency-graph-extractor":{"artifactCapable":true,"agentType":"agent-teams-workforce:dependency-graph-extractor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"deployment-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:deployment-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"deployment-strategy-decider":{"artifactCapable":false,"agentType":"agent-teams-workforce:deployment-strategy-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:cove-prompt-design"]},"documentation-accuracy-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:documentation-accuracy-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"documentation-currency-auditor":{"artifactCapable":true,"agentType":"agent-teams-workforce:documentation-currency-auditor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"documentation-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:documentation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"domain-boundary-validator":{"artifactCapable":true,"agentType":"agent-teams-workforce:domain-boundary-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"domain-event-modeler":{"artifactCapable":true,"agentType":"domain-event-modeler","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"dos-resilience-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:dos-resilience-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"dynamodb-access-layer-implementer":{"artifactCapable":true,"agentType":"dynamodb-access-layer-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"dynamodb-cost-optimizer":{"artifactCapable":true,"agentType":"dynamodb-cost-optimizer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb","agent-teams-workforce:aws-cost-operations"]},"dynamodb-schema-access-pattern-reviewer":{"artifactCapable":true,"agentType":"dynamodb-schema-access-pattern-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:dynamodb"]},"dynamodb-streams-cdc-implementer":{"artifactCapable":true,"agentType":"dynamodb-streams-cdc-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:dynamodb","agent-teams-workforce:graphrag-lookup"]},"email-notification-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:email-notification-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:email-template-builder","agent-teams-workforce:sns","agent-teams-workforce:graphrag-lookup"]},"epic-sequencer":{"artifactCapable":true,"agentType":"agent-teams-workforce:epic-sequencer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:epic-sequencing"]},"espresso-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:espresso-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:tdd-guide","agent-teams-workforce:cumulative-regression"]},"event-api-client-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:event-api-client-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"event-driven-consumer-implementer":{"artifactCapable":true,"agentType":"event-driven-consumer-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:sqs","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:sns","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"event-flow-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:event-flow-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda"]},"event-schema-designer":{"artifactCapable":true,"agentType":"event-schema-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:eventbridge","agent-teams-workforce:sns","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"event-schema-reviewer":{"artifactCapable":true,"agentType":"event-schema-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:aws-serverless-eda"]},"failure-mode-analyst":{"artifactCapable":true,"agentType":"failure-mode-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:observability-designer","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"filing-clerk":{"artifactCapable":true,"agentType":"filing-clerk","skills":["agent-teams-workforce:subagent-contract","obsidian:obsidian-cli","obsidian:obsidian-markdown","agent-teams-workforce:arc42","notebooklm","document-classification"]},"finops-analyst":{"artifactCapable":false,"agentType":"finops-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:aws-cost-operations"]},"flaky-test-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:flaky-test-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:test-failure-mindset","agent-teams-workforce:find-cause"]},"frontend-performance-optimizer":{"artifactCapable":true,"agentType":"agent-teams-workforce:frontend-performance-optimizer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend"]},"github-actions-pipeline-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:github-actions-pipeline-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"glue-etl-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:glue-etl-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:graphrag-lookup"]},"graphql-schema-designer":{"artifactCapable":true,"agentType":"graphql-schema-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"graphql-schema-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:graphql-schema-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer"]},"implementation-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:implementation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:graphrag-lookup"]},"incident-responder":{"artifactCapable":true,"agentType":"agent-teams-workforce:incident-responder","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:find-cause","agent-teams-workforce:validation-protocol"]},"incident-response-runbook-designer":{"artifactCapable":true,"agentType":"agent-teams-workforce:incident-response-runbook-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:observability-designer"]},"infrastructure-security-scanner":{"artifactCapable":true,"agentType":"infrastructure-security-scanner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops","agent-teams-workforce:aws-cdk-development"]},"injection-attack-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:injection-attack-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"integration-pattern-architect":{"artifactCapable":true,"agentType":"integration-pattern-architect","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-architect","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"integration-testing-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:integration-testing-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"ios-swiftui-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:ios-swiftui-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:graphrag-lookup"]},"kinesis-stream-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:kinesis-stream-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:aws-serverless-eda","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"lambda-performance-optimizer":{"artifactCapable":true,"agentType":"lambda-performance-optimizer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:lambda"]},"llm-observability-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:llm-observability-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:observability-designer","agent-teams-workforce:senior-prompt-engineer","agent-teams-workforce:aws-agentic-ai","agent-teams-workforce:graphrag-lookup"]},"matching-algorithm-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:matching-algorithm-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:graphrag-lookup"]},"mcp-server-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:mcp-server-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:mcp-server-builder","agent-teams-workforce:aws-agentic-ai","agent-teams-workforce:aws-mcp-setup","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"ml-evaluation-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:ml-evaluation-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:senior-data-scientist","agent-teams-workforce:cumulative-regression"]},"mobile-e2e-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:mobile-e2e-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"nextjs-component-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:nextjs-component-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend","agent-teams-workforce:a11y-audit","agent-teams-workforce:senior-fullstack","agent-teams-workforce:graphrag-lookup"]},"nfr-analyst":{"artifactCapable":false,"agentType":"agent-teams-workforce:nfr-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:product-discovery"]},"okr-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:okr-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-strategist","agent-teams-workforce:product-analytics"]},"openapi-contract-reviewer":{"artifactCapable":false,"agentType":"openapi-contract-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:api-design-reviewer"]},"operational-readiness-reviewer":{"artifactCapable":true,"agentType":"operational-readiness-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:observability-designer","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"payments-integration-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:payments-integration-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:stripe-integration-expert","agent-teams-workforce:secrets-manager","agent-teams-workforce:graphrag-lookup"]},"performance-benchmark-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:performance-benchmark-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"permission-escalation-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:permission-escalation-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops","agent-teams-workforce:iam"]},"persistence-architecture-specialist":{"artifactCapable":true,"agentType":"persistence-architecture-specialist","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:dynamodb","agent-teams-workforce:database-schema-designer","agent-teams-workforce:rds","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"persona-profile-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:persona-profile-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:product-analytics"]},"phase-gate-enforcer":{"artifactCapable":false,"agentType":"agent-teams-workforce:phase-gate-enforcer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:cumulative-regression"]},"playwright-e2e-web-test-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:playwright-e2e-web-test-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:a11y-audit","agent-teams-workforce:cumulative-regression"]},"polyrepo-steward":{"artifactCapable":true,"agentType":"agent-teams-workforce:polyrepo-steward","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:graphrag-lookup"]},"power-tools-configuration-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:power-tools-configuration-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:lambda","agent-teams-workforce:secrets-manager","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"prd-alignment-verifier":{"artifactCapable":true,"agentType":"agent-teams-workforce:prd-alignment-verifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"prd-creation-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:prd-creation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"prd-reality-reconciler":{"artifactCapable":true,"agentType":"prd-reality-reconciler","skills":["agent-teams-workforce:architecture-baseline","agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:graphrag-lookup"]},"prd-trd-traceability-verifier":{"artifactCapable":true,"agentType":"agent-teams-workforce:prd-trd-traceability-verifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"prd-validation-analyst":{"artifactCapable":true,"agentType":"agent-teams-workforce:prd-validation-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"prd-validation-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:prd-validation-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"prd-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:prd-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:prd-writer"]},"production-readiness-review-facilitator":{"artifactCapable":false,"agentType":"agent-teams-workforce:production-readiness-review-facilitator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"race-condition-tester":{"artifactCapable":true,"agentType":"agent-teams-workforce:race-condition-tester","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-secops"]},"react-native-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:react-native-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend","agent-teams-workforce:graphrag-lookup"]},"readme-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:readme-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"recommendation-engine-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:recommendation-engine-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-ml-engineer","agent-teams-workforce:graphrag-lookup"]},"regression-coverage-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:regression-coverage-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:artifact-handoff","agent-teams-workforce:cumulative-regression"]},"regression-impact-assessor":{"artifactCapable":true,"agentType":"agent-teams-workforce:regression-impact-assessor","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:artifact-handoff","agent-teams-workforce:cumulative-regression"]},"requirements-clarifier":{"artifactCapable":false,"agentType":"agent-teams-workforce:requirements-clarifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:product-discovery"]},"requirements-conflict-detector":{"artifactCapable":true,"agentType":"agent-teams-workforce:requirements-conflict-detector","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"root-cause-analyst":{"artifactCapable":false,"agentType":"agent-teams-workforce:root-cause-analyst","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:find-cause","agent-teams-workforce:test-failure-mindset","agent-teams-workforce:graphrag-lookup"]},"run-ledger-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:run-ledger-writer","skills":["agent-teams-workforce:subagent-contract"]},"s3-data-lake-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:s3-data-lake-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-data-engineer","agent-teams-workforce:s3","agent-teams-workforce:graphrag-lookup","agent-teams-workforce:resource-naming"]},"sdlc-pipeline-orchestrator":{"artifactCapable":false,"agentType":"agent-teams-workforce:sdlc-pipeline-orchestrator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:beads-contract"]},"security-architecture-designer":{"artifactCapable":true,"agentType":"security-architecture-designer","skills":["agent-teams-workforce:artifact-handoff","agent-teams-workforce:subagent-contract","agent-teams-workforce:senior-security","agent-teams-workforce:iam","agent-teams-workforce:secrets-manager","agent-teams-workforce:aws-solution-architect","agent-teams-workforce:graphrag-lookup"]},"security-test-case-designer":{"artifactCapable":true,"agentType":"agent-teams-workforce:security-test-case-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-security","agent-teams-workforce:cumulative-regression"]},"slo-error-budget-designer":{"artifactCapable":false,"agentType":"slo-error-budget-designer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:observability-designer","agent-teams-workforce:cloudwatch"]},"smoke-test-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:smoke-test-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa"]},"spec-authoring-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:spec-authoring-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"spec-currency-validator":{"artifactCapable":true,"agentType":"agent-teams-workforce:spec-currency-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"spec-decider":{"artifactCapable":false,"agentType":"spec-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect","agent-teams-workforce:cove-prompt-design"]},"spec-freshness-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:spec-freshness-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"stakeholder-request-intake-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:stakeholder-request-intake-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery"]},"task-decomposer":{"artifactCapable":true,"agentType":"task-decomposer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:beads-contract","agent-teams-workforce:graphrag-lookup"]},"task-decomposition-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:task-decomposition-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration","agent-teams-workforce:beads-contract","agent-teams-workforce:graphrag-lookup"]},"task-dependency-mapper":{"artifactCapable":true,"agentType":"task-dependency-mapper","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:beads-contract"]},"task-readiness-runner":{"artifactCapable":false,"agentType":"agent-teams-workforce:task-readiness-runner","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:beads-contract"]},"tdd-unit-test-generator":{"artifactCapable":true,"agentType":"agent-teams-workforce:tdd-unit-test-generator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:tdd-guide","agent-teams-workforce:cumulative-regression"]},"test-command-resolver":{"artifactCapable":false,"agentType":"agent-teams-workforce:test-command-resolver","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:test-failure-mindset"]},"test-coverage-gap-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:test-coverage-gap-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"test-design-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:test-design-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"test-environment-orchestrator":{"artifactCapable":true,"agentType":"test-environment-orchestrator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-devops","agent-teams-workforce:aws-mcp-setup"]},"test-failure-parser":{"artifactCapable":false,"agentType":"agent-teams-workforce:test-failure-parser","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:test-failure-mindset"]},"test-isolation-specialist":{"artifactCapable":true,"agentType":"agent-teams-workforce:test-isolation-specialist","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:tdd-guide","agent-teams-workforce:test-failure-mindset"]},"test-plan-strategy-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:test-plan-strategy-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cumulative-regression"]},"test-strategy-decider":{"artifactCapable":false,"agentType":"agent-teams-workforce:test-strategy-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:cove-prompt-design"]},"trd-author":{"artifactCapable":true,"agentType":"trd-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"trd-authoring-lead":{"artifactCapable":false,"agentType":"agent-teams-workforce:trd-authoring-lead","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:agent-orchestration"]},"trd-decider":{"artifactCapable":false,"agentType":"agent-teams-workforce:trd-decider","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"trd-validator":{"artifactCapable":false,"agentType":"agent-teams-workforce:trd-validator","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"ubiquitous-language-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:ubiquitous-language-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-architect"]},"uml-diagram-author":{"artifactCapable":true,"agentType":"agent-teams-workforce:uml-diagram-author","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:architecture-diagramming","agent-teams-workforce:uml-diagramming","agent-teams-workforce:senior-architect","agent-teams-workforce:graphrag-lookup"]},"user-guide-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:user-guide-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:roadmap-communicator"]},"user-story-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:user-story-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-discovery","agent-teams-workforce:beads-contract"]},"user-story-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:user-story-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"vector-search-embeddings-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:vector-search-embeddings-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:rag-architect","agent-teams-workforce:graphrag-lookup"]},"webauthn-implementer":{"artifactCapable":true,"agentType":"agent-teams-workforce:webauthn-implementer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-frontend","agent-teams-workforce:cognito","agent-teams-workforce:graphrag-lookup"]},"workflow-command-runner":{"artifactCapable":false,"agentType":"agent-teams-workforce:workflow-command-runner","skills":[]},"worktree-independent-verifier":{"artifactCapable":false,"agentType":"agent-teams-workforce:worktree-independent-verifier","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol"]},"wsjf-scorer":{"artifactCapable":true,"agentType":"agent-teams-workforce:wsjf-scorer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-strategist","agent-teams-workforce:wsjf","agent-teams-workforce:beads-contract"]},"wsjf-scoring-reviewer":{"artifactCapable":true,"agentType":"agent-teams-workforce:wsjf-scoring-reviewer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:product-strategist","agent-teams-workforce:wsjf"]},"xcuitest-writer":{"artifactCapable":true,"agentType":"agent-teams-workforce:xcuitest-writer","skills":["agent-teams-workforce:subagent-contract","agent-teams-workforce:validation-protocol","agent-teams-workforce:senior-qa","agent-teams-workforce:tdd-guide","agent-teams-workforce:cumulative-regression"]}}
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


let dispatchInterruption = null
function dispatchOutcome(result) {
  return dispatchInterruption ? { ...result, ok: false, paused: true, resumable: true, dispatchFailed: true, stage: dispatchInterruption.stage, reason: dispatchInterruption.message, headline: dispatchInterruption.message, dispatchInterruption } : result
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
const dispatchFailures = []

async function run(prompt, opts) {
  if (dispatchInterruption) return null
  let message = 'returned nothing'
  try {
    const out = await fableAgent(prompt, opts)
    if (out) return out
  } catch (err) {
    message = String((err && err.message) || err)
    const cause = dispatchFailureCause(err)
    if (cause !== 'deterministic') dispatchInterruption = { stage: cause === 'exhausted' ? 'account-quota-exhausted' : 'api-unavailable', message }
  }
  dispatchFailures.push({ label: opts.label, agentType: opts.agentType || null, phase: opts.phase, message })
  log(`${opts.label}: no structured result — ${message}`)
  return null
}

function died(phaseName) {
  const deaths = dispatchFailures.filter((f) => f.phase === phaseName)
  return deaths.length
    ? { dispatchFailed: true, dispatchFailures: deaths, reason: deaths.map((f) => `${f.label}: ${f.message}`).join('; ') }
    : {}
}

return dispatchOutcome(await (async () => {
// args: { prd: { id?, title?, path?, body? }, epic: { id }, archPath, subject?, repoPath?, seedRepos?,
//   maxRounds?, depscore: { script, repo },
//   artifacts: { dir, relDir?, epicId, script, phase, inputs?, beadId? } }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const hasText = (v) => typeof v === 'string' && v.trim().length > 0
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
const listed = (x) => (Array.isArray(x) ? x.filter(hasText).map((s) => s.trim()) : [])

const prd = a.prd && typeof a.prd === 'object' ? a.prd : {}
const epicId = String((a.epic && (a.epic.id || a.epic.beadId)) || '').trim()
const archPath = hasText(a.archPath) ? a.archPath.trim().replace(/\/+$/, '') : ''
const ART = a.artifacts && typeof a.artifacts === 'object' && hasText(a.artifacts.dir) && hasText(a.artifacts.script) ? a.artifacts : null
const DS = a.depscore && typeof a.depscore === 'object' && hasText(a.depscore.script) && hasText(a.depscore.repo) ? a.depscore : null
const MAX_ROUNDS = Number.isInteger(a.maxRounds) && a.maxRounds > 0 ? a.maxRounds : 6
const MAX_CORRECTIONS = 2

function refuse(why) {
  return { ok: false, stage: 'input', deterministicFailure: true, error: why, reason: why }
}
if (!archPath) return refuse("no archPath supplied (the project's ATW_ARCH_PATH) — there is no architecture to design from or integrate into. Set ATW_ARCH_PATH for the run, or pass archPath to this mini.")
if (!hasText(prd.path) && !hasText(prd.body)) return refuse('no PRD supplied: pass prd.path (or prd.body)')
if (!epicId) return refuse('no Epic supplied: pass epic.id')
if (!ART) return refuse("no artifacts directory or recorder supplied: the architecture step saves its survey, round results and decision under the Epic's working directory, so a stopped run resumes from them")
if (!DS) return refuse('no depscore script and beads repository supplied: the target write, the section 2 check and the approval run through depscore.py')

const ARC42 = `${archPath}/arc42`
const CONSTRAINTS = `${ARC42}/02-architecture-constraints`
const MENU = `${archPath}/reference/diagram-and-model-types.md`
const MODEL = `${archPath}/reference/architecture-documentation-model.md`
const WORK = `${ART.dir}/architecture`
const DRAFT = `${WORK}/draft`
const ROUNDS_DIR = `${WORK}/rounds`
const SURVEY_MD = `${WORK}/survey.md`
const SURVEY_JSON = `${WORK}/survey.json`
const DECISION_MD = `${WORK}/decision.md`
const DECISION_JSON = `${WORK}/decision.json`
const TARGET_JSON = `${WORK}/target.json`
const UPDATE_JSON = `${WORK}/architecture-update.json`
const LEDGER_JSON = `${WORK}/ledger.json`
const TREE_START = `${WORK}/tree-start.json`
const TREE_LAST = `${WORK}/tree-last.json`
const TARGET_CHECK = `${WORK}/target-check.json`
const prdRef = hasText(prd.path) ? `the document at ${prd.path}. Read it in full: every requirement in it is in scope.` : `\n${prd.body}`
const prdBase = hasText(prd.path) ? String(prd.path).split('/').pop().replace(/\.md$/i, '') : ''
const beadPrefix = epicId.includes('-') ? `${epicId.split('-')[0]}-` : ''
const FORBID = [epicId, beadPrefix, prd.id, prdBase].filter(hasText)


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
   * printed ('bd-timeout' when bd reported the beads server failed), else 'other'.
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
      const cause = r.view.cause === 'bd-timeout' ? 'bd-timeout' : 'other'
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

/** Where the full results relayed to this script are saved, one numbered file per command. */
const RELAY_DIR = `${WORK}/relay`
/** scripts/portfolio/relayrun.py, beside depscore.py: runs any other program, and checks or writes saved JSON, through the checked relay. */
const RELAY_RUNNER = DS.script.replace(/[^/]+$/, 'relayrun.py')
let relaySeq = 0
/** The next relay file, named for its label. */
function nextRelayFile(label) {
  relaySeq += 1
  return `${RELAY_DIR}/${String(relaySeq).padStart(3, '0')}-${String(label).replace(/[^A-Za-z0-9._-]+/g, '-')}.json`
}
/** Runs one depscore.py command through the checked relay; returns the facts it printed with `relayFile`, or { error, exception? }. */
function depscore(label, phaseName, commandArgs) {
  return relayKit.depscore(run, { label, phase: phaseName, script: DS.script, repo: DS.repo, tail: commandArgs, file: nextRelayFile(label) })
}
/** The artifact recorder's command for one saved file. */
function recordArgv(file) {
  const inputs = (Array.isArray(ART.inputs) ? ART.inputs : []).filter(hasText)
  return ['python3', ART.script, 'record', file, '--epic', ART.epicId, '--phase', ART.phase, ...(inputs.length ? ['--inputs', ...inputs] : [])]
}
/** Records saved files with the artifact recorder, one checked command each; returns the files it did not record. */
async function recordFiles(label, phaseName, files) {
  const failed = []
  for (const f of files) {
    const name = String(f).split('/').pop()
    const r = await relayKit.run(run, { label: `${label}:${name}`, phase: phaseName, runner: RELAY_RUNNER, argv: recordArgv(f), file: nextRelayFile(`${label}-${name}`) })
    if (!r.ok || r.exitCode !== 0) failed.push(f)
  }
  if (failed.length) log(`${label}: the recorder did not record ${failed.join(', ')}`)
  return failed
}
/** Publish the one authored candidate; only its compact receipt crosses the agent boundary. */
const ARTIFACT_RETURN_SCHEMA = { type: 'object', additionalProperties: false, required: ['artifactPath'], properties: { artifactPath: { type: 'string' } } }
function artifactBrief(candidate, schema, revision = '') {
  return relayKit.artifactBrief(candidate, schema, revision, DS.script.replace(/[^/]+$/, 'artifactcontract.py'))
}
async function sourceRevision(label, phaseName, files, context) {
  const result = await relayKit.artifactRevision(run, { label, phase: phaseName, runner: RELAY_RUNNER, files: [...new Set(files.filter(hasText))], context, relayFile: nextRelayFile(label) })
  if (!result.ok) {
    if (!dispatchInterruption) { dispatchFailures.push({ label, phase: phaseName, message: result.error }); log(`${label}: ${result.error}`) }
    return null
  }
  return result.revision
}
async function probeArtifact(label, phaseName, candidate, file, schema, revision = '', projection = '', researchAgent = '') {
  if (dispatchInterruption) return null
  const result = await relayKit.acceptArtifact(run, { label: `${label}:resume-candidate`, phase: phaseName, runner: RELAY_RUNNER, candidate, file, schema, revision, projection, probe: true, researchAgent, researchRepo: DS.repo, recordArgv: recordArgv(file), relayFile: nextRelayFile(`${label}-resume-candidate`) })
  if (!result.ok) {
    if (!dispatchInterruption) { dispatchFailures.push({ label, phase: phaseName, message: result.error }); log(`${label}: ${result.error}`) }
    return null
  }
  if (result.pending) {
    const research = result.research
    if (research && (research.candidate !== candidate || research.revision !== revision || research.agentType !== researchAgent.replace(AGENT_PREFIX, '') || research.artifactPath !== `${candidate}.${revision}.research.json` || !/^[a-f0-9]{64}$/.test(research.sha256) || !Number.isSafeInteger(research.bytes) || research.bytes < 1 || !Number.isSafeInteger(research.toolPairs) || research.toolPairs < 1)) throw new Error('invalid research recovery receipt')
    if (research) log(`${label}: recovered ${research.toolPairs} completed research tool pair(s); review still incomplete`)
    return { pending: true, ...(research ? { research } : {}) }
  }
  log(`${label}: reused complete validated candidate; specialist not redispatched`)
  return { artifactPath: candidate, acceptedReceipt: result.receipt }
}
async function acceptArtifact(label, phaseName, candidate, file, schema, returned, revision = '', projection = '') {
  if (dispatchInterruption) return null
  const fail = (message) => { dispatchFailures.push({ label, phase: phaseName, agentType: 'agent-teams-workforce:workflow-command-runner', message }); log(`${label}: ${message}`); return null }
  const accepted = returned && returned.acceptedReceipt ? { ok: true, receipt: returned.acceptedReceipt } : await relayKit.acceptArtifact(run, { label: `${label}:accept`, phase: phaseName, runner: RELAY_RUNNER, candidate, file, schema, returned, revision, projection, recordArgv: recordArgv(file), relayFile: nextRelayFile(`${label}-accept`) })
  if (!accepted.ok) return dispatchInterruption ? null : fail(accepted.error)
  if (!returned) log(`${label}: recovered complete saved candidate without repeating the specialist`)
  return accepted.receipt
}

const ARCH_WHERE = `THE ARCHITECTURE is at ${archPath}. It is not inside any product repository.
- \`arc42/\` is the effective architecture version; each file's lifecycle_state separately says whether it is approved (effective) or still in-review. \`arc42/02-architecture-constraints/README.md\` holds the owner's constraints; read it in full. \`arc42/04-solution-strategy/README.md\` holds the enterprise-level strategy; read it. Every other section is the design so far, as views.
- The constraints are the owner's; the effective architecture, the non-effective documents and the code are evidence assessed under the architecture-baseline skill.
- Each view's frontmatter names its \`view_type\`, \`scope\`, \`subject\` and every element it \`shows\`: that frontmatter is the catalog. Find the views of an element by searching it (\`subject:\` and the \`shows:\` lists) for the element's name, in every section, at every scope.
- \`target/<subject>/\` folders are open targets (designs in progress) and \`built/<subject>/\` folders record builds that differ from the effective version. Read every open target, build record and in-review view that shows an element this PRD touches: they are input to this design, and the designs must not contradict each other. Section 2 constraints and non-effective content the effective views do not yet represent are checked as the architecture-baseline skill describes.
- The architecture documentation model is ${MODEL}; the view types to choose from are ${MENU}.
- \`lifecycle_state\` is per file: \`effective\` was reviewed and approved; \`in-review\` is input to check, never assumed vetted.`

const INPUTS_RULE = `YOUR INPUTS are the PRD, the effective version and the open targets above, the code on each relevant repository's \`main\` (read it as committed there: \`git -C <repo> grep -n <term> main\`, \`git -C <repo> show main:<path>\`), the open beads (other Epics' Stories and Tasks planned but not built), and the AWS documentation through the AWS MCP Server's tools and skills. What is deployed in AWS is not an input: run no AWS describe, list or get call against an account. Repository application code and CDK are the implementation/infrastructure source of truth; CDK resource names alone do not establish behavior. Distinguish reviewed architecture and code traceable to it from unreviewed input that needs validation. Cite what you rely on: a view by its absolute path and heading, code by repository, path and line on \`main\`, AWS behaviour by the documentation URL you read.`

const PRD_RULE = `THE PRD STATES WHAT, NEVER HOW. It holds the business and end-user requirements: what the seeker and the business get, and the results someone outside the system could observe. Anything in it about how the system works — mechanisms, services, technologies, response shapes and codes, contracts, telemetry, release mechanics, engineering numbers such as latencies, limits and thresholds — is not a requirement: ignore it, and never treat it as a defect. The architecture team decides every technical aspect itself, from the effective architecture, the code and the AWS documentation through the AWS MCP tools and skills. Where the PRD leaves a technical value open, the team chooses it and states the reason and evidence. Where two requirements seem to pull against each other, the team designs the solution that best satisfies both, putting the seeker's privacy and data protection first, and records that as a design decision with its reason. None of this is a question for the owner.`

const BUSINESS_CONFLICT_RULE = `List in \`businessConflicts\` only two BUSINESS requirements of the PRD that no design whatsoever could satisfy together (each with the requirement and why no design can satisfy both). A technical gap, an open value, a "how" in the PRD, or a tension a design can resolve is never one: the team resolves those. This list is almost always empty.`

const DRAFT_RULES = `THE DRAFT TARGET is the folder ${DRAFT}. It has the arc42 section layout (\`05-building-block-view/…\`, \`06-runtime-view/…\`, \`07-deployment-view/…\`, \`08-crosscutting-concepts/…\`, and \`03-context-and-scope/\` or \`04-solution-strategy/\` only when the change reaches them) and a \`delta/\` folder beside them.
- A target view is the view as it will read once approved: a changed copy of each effective view that shows a changed element, at every scope where the element appears, and coverage for new elements according to the applicable obligations in ${MODEL}. Extend a sufficient shared view when it answers the required reader question; create a new view only when no existing or shared view supplies the required coverage. Catalog every covered element in \`shows\`. Copy an effective view into the draft before you change it, at the same relative path.
- \`delta/\` holds the views that show only what changes between the effective version and the target. Specs and Tasks are made from it.
- Write each document once. A partial change (an element the effective version already shows changes): the target views plus a \`delta/\` of the change alone. An entirely new architecture (no effective view shows any element you draw): the target views alone, with no \`delta/\`; they are both the future and the delta. No architecture change: write no view at all.
- \`baseline.json\` is the baseline handoff the workflow writes from the survey: the effective views each capability relies on, the implementation gaps between the future set and the code on \`main\`, and a note naming which of the three cases the draft is. Read it; never edit it or list it in \`files\`.
- Every view is Markdown with catalog frontmatter (\`view_type\` from ${MENU}, \`scope\`, \`subject\`, \`shows\`, \`lifecycle_state: in-review\`), a Mermaid diagram where the view type has one, and prose.
- Nothing goes under \`02-architecture-constraints/\`: section 2 holds the owner's constraints.
- Name files and folders for their subject, never for the PRD, the Epic, a bead or a date. Write no history, decision record, rule or open item into a view.
- Write nothing in ${archPath}: the target reaches the architecture only after approval.`

const AGENT_PREFIX = 'agent-teams-workforce:'
const USER_LEVEL_AGENTS = new Set([
  'api-contract-designer',
  'graphql-schema-designer',

  'integration-pattern-architect',
  'persistence-architecture-specialist',
  'security-architecture-designer',
  'cdk-infrastructure-designer',
  'event-schema-designer',
  'domain-event-modeler',
  'bounded-context-mapper',
  'architecture-pattern-challenger',
  'architecture-tradeoff-skeptic',
  'architecture-boundary-guardian',
  'operational-readiness-reviewer',
  'failure-mode-analyst',
  'cost-architecture-reviewer',
  'cost-impact-reviewer',
])
const dispatchName = (name) => (USER_LEVEL_AGENTS.has(name) ? name : `${AGENT_PREFIX}${name}`)

const ROSTER = {
  proposer: {
    'integration-pattern-architect': 'integration between services: event and API patterns, sync or async, service boundaries',
    'persistence-architecture-specialist': 'persistence: table, key and index design from the access patterns',
    'security-architecture-designer': 'security: trust boundaries, identity and access, encryption, threat model',
    'cdk-infrastructure-designer': 'infrastructure: CDK stacks and constructs, function boundaries, packaging',
    'event-schema-designer': 'event schemas within the event envelope the architecture establishes',
    'api-contract-designer': 'REST API contracts',
    'graphql-schema-designer': 'GraphQL schemas',
    'domain-event-modeler': 'domain events, their flows and contracts',
    'bounded-context-mapper': 'domain boundaries and the relationships between contexts',
  },
  diagram: {
    'architecture-diagram-author': 'views of any type in the list of view types, at any scope',
    'c4-diagram-author': 'C4 views: system context, container, component',
    'uml-diagram-author': 'UML views: sequence, state, activity, class',
  },
  reviewer: {
    'architecture-pattern-challenger': 'critiques concrete structural weaknesses in the retained design without authoring another proposal',
    'architecture-tradeoff-skeptic': 'hidden assumptions and optimistic estimates behind a tradeoff',
    'architecture-boundary-guardian': 'coupling across contexts; conflicts with the constraints; departures from established patterns without reason and evidence',
    'operational-readiness-reviewer': 'operational burden: monitoring, alerting, runbooks',
    'failure-mode-analyst': 'failure modes: throttling, duplicate delivery, downstream unavailability, poison messages',
  },
  cost: {
    'cost-architecture-reviewer': 'the cost of the design, with the unit math shown',
    'cost-impact-reviewer': 'where the cost of the design changes shape as usage grows',
  },
}
const WRITER_ROLES = ['proposer', 'diagram']
const REVIEW_ROLES = ['reviewer', 'cost']
const roleOf = (name) => Object.keys(ROSTER).find((role) => Object.prototype.hasOwnProperty.call(ROSTER[role], name)) || null
const rosterText = Object.keys(ROSTER)
  .map((role) => `${role}:\n${Object.entries(ROSTER[role]).map(([n, w]) => `  - ${n} — ${w}`).join('\n')}`)
  .join('\n')
const ROSTER_ARG = Object.keys(ROSTER).map((role) => `${role}=${Object.keys(ROSTER[role]).join(',')}`).join(';')

/** The owner the coordinator assigned to each finding that had none: finding id -> writer. */
const assigned = new Map()
/**
 * Reads the step's saved work on disk with depscore.py arch-resume, which folds every saved round
 * result into the claim and finding ledger, writes it to ledger.json for the sessions that read
 * it, and prints only the facts the control flow branches on. No saved content comes back here:
 * sessions get file paths. Returns the facts or { error }.
 */
async function readFacts(label, phaseName, roundPlan = null) {
  const assign = [...assigned].map(([id, w]) => `${id}=${w}`).join(',')
  const command = `arch-resume --work-dir ${shq(WORK)} --roster ${shq(ROSTER_ARG)}${assign ? ` --assign ${shq(assign)}` : ''}${roundPlan ? ` --round-plan ${shq(JSON.stringify(roundPlan))}` : ''}`
  const out = await depscore(label, phaseName, command)
  if (!out || out.error) return { error: (out && out.error) || 'depscore.py arch-resume printed nothing', exception: (out && out.exception) || '' }
  const empty = { rounds: {}, integration: {}, coverage: {}, repairs: {} }
  const missing = Object.keys(empty).filter((k) => !out[k] || typeof out[k] !== 'object')
  if (missing.length) log(`${label}: depscore.py arch-resume printed no ${missing.join(', ')}; taken as empty`)
  for (const k of missing) out[k] = empty[k]
  out.coverage.gaps = listed(out.coverage.gaps)
  out.rounds.openFindings = (Array.isArray(out.rounds.openFindings) ? out.rounds.openFindings : [])
    .filter((f) => f && hasText(f.id))
    .map((f) => ({ id: f.id, owner: String(f.owner || ''), answered: f.answered === true }))
  const overlaps = Array.isArray(out.rounds.overlapWarnings) ? out.rounds.overlapWarnings.length : 0
  if (overlaps) log(`Rounds: ${overlaps} reviewer overlap warning(s), listed under result.rounds.overlapWarnings in ${out.relayFile}`)
  if (hasText(out.rounds.planKept)) log(`Rounds: ${out.rounds.planKept} (result.rounds.planKept in ${out.relayFile})`)
  const warnings = listed(out.warnings)
  if (warnings.length) log(`${label}: ${warnings.length} warning(s) reading the saved work, listed under result.warnings in ${out.relayFile}`)
  return out
}
/** The number of coverage notes arch-resume reports: what the coordinator routes and the decider reads, never a gate. */
const gapCount = (f) => listed(f && f.coverage && f.coverage.gaps).length
/** Where the approved coverage rows are: the relay file of the arch-resume run that read them (result.coverage.checksNeeded); arch-review-check reads them there. */
const coverageRowsOf = (f) => ({ file: String((f && f.relayFile) || ''), rows: Number(f && f.coverage && f.coverage.rows) || 0 })

/** The result file of one dispatch of round n, as depscore.py arch-resume names it. */
const resultFile = (n, d) => `${ROUNDS_DIR}/r${n}-${d.seq}-${d.role}-${d.agentType}.json`
/**
 * Returns the dispatches of a saved pending plan, ready to run: the identity and completion
 * arch-resume reports for each. Task, files, answers and assigned claims are always read from
 * the authoritative plan entry in ledger.json, including reconciled legacy plans.
 */
function planDispatches(pp) {
  // The loader can reconcile a retained plan. Never override it with stale in-memory scope.
  return (Array.isArray(pp && pp.dispatches) ? pp.dispatches : []).map((c) => ({ ...c, task: '', files: null, answers: null, file: resultFile(pp.round, c) }))
}

const CONFLICT_ITEMS = {
  type: 'array',
  items: {
    type: 'object',
    additionalProperties: false,
    required: ['requirements', 'why'],
    properties: { requirements: { type: 'array', items: { type: 'string' } }, why: { type: 'string' } },
  },
}
const REPOS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['repositories'],
  properties: {
    repositories: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['name', 'path', 'role', 'lifecycle'],
        properties: { name: { type: 'string' }, path: { type: 'string' }, role: { type: 'string' }, lifecycle: { type: 'string' } },
      },
    },
  },
}
// Consumed by: archresume coverage folding and architecture.js decisionNotes — stable
// ids preserve absent obligations; MODEL evidence supplies semantics, not a plugin menu.
// Consumed by archevidence: local section/main revision binding and external provenance.
const EVIDENCE_REFS = { type: 'array', items: { type: 'object', additionalProperties: false,
  required: ['path', 'heading', 'repo', 'revision', 'url'], properties: {
    path: { type: 'string' }, heading: { type: 'string' }, repo: { type: 'string' },
    revision: { type: 'string' }, url: { type: 'string' },
  } } }
const COVERAGE_SCHEMA = {
  type: 'array', items: {
    type: 'object', additionalProperties: false,
    required: ['id', 'subject', 'scope', 'obligation', 'sources', 'views', 'status', 'action', 'reason', 'evidenceRefs', 'disposition', 'dispositionReason'],
    properties: {
      id: { type: 'string' }, subject: { type: 'string' }, scope: { type: 'string' },
      obligation: { type: 'string' }, sources: { type: 'array', items: { type: 'string' } },
      views: { type: 'array', items: { type: 'string' } }, status: { type: 'string', enum: ['Present and sufficient', 'Present but incomplete', 'Required and absent', 'Not yet applicable', 'Not assessed'] },
      action: { type: 'string', enum: ['create', 'update', 'unchanged', 'remove', 'not-applicable', 'unresolved'] },
      reason: { type: 'string' },
      evidenceRefs: EVIDENCE_REFS, disposition: { type: 'string', enum: ['required', 'unrelated-debt'] }, dispositionReason: { type: 'string' },
    },
  },
}
// Consumed by: archfiles.review_check — a verified check with evidence per approved row id;
// reviewer prose is read by the decider.
const COVERAGE_CHECKS_SCHEMA = {
  type: 'array', items: {
    type: 'object', additionalProperties: false,
    required: ['id', 'verdict', 'evidence'],
    properties: {
      id: { type: 'string' },
      verdict: { type: 'string', enum: ['verified', 'unsupported', 'wrong'] }, evidence: { type: 'string' },
    },
  },
}
const COVERAGE_RULE = `COVERAGE is evidence in the existing survey/round results and ${LEDGER_JSON}, not another architecture version. Read ${MODEL} for applicable obligations and ${MENU} for selection/construction. Inventory relevant subjects from the design, repositories and contracts independently of catalog hits. Include required views that do not exist, every affected scope and horizontal concern; unrelated historical debt is non-blocking and is reported in your summary.
Each coverage row has a stable id, subject, scope, obligation (MODEL path and heading), sources (inventory/design evidence), views (absolute paths, including expected missing paths), status (the MODEL's assessment result), action and reason. Preserve ids across rounds; omitted ids remain in the ledger. Writers replace only their assigned rows; use draft paths for created/updated views, draft/delta descriptions for removals, and canonical paths only for unchanged views. After completing work, update status to Present and sufficient; Not yet applicable pairs with action not-applicable. Incomplete, absent and Not assessed statuses are reported to the decider. An unknown relevant obligation uses action unresolved. Not-applicable and unchanged need concrete reasons and evidence; no-change targets still assess applicable coverage. Never invent design to fill diagrams. Diagram declarations require actual diagrams; verify rendering, readability, semantics, links and metadata as the MODEL requires, reporting limitations honestly.
Reviewers return one coverageCheck per row id they check, with an independent verdict and evidence. A missing view or obligation can be a finding without an author claim. Recheck rows a writer revised after your check.
Set disposition=required by default. For mistakenly inventoried unrelated historical debt, use unrelated-debt with dispositionReason proving it does not affect this change or dependencies; preserve its honest MODEL status. An independent verified check makes that disposition nonblocking. Retain the row and summarize it; never erase IDs.
EvidenceRefs bind relevant views by absolute path and unique heading (empty means whole file), repository code by absolute repo, main commit revision and repository-relative path, or external docs by url and version/retrieval revision. Unused fields are empty strings. Include relevant dependencies. Source movement requires refreshed evidence; reading test source is not a test run.`

// ===== SHARED BLOCK architecture-baseline — BEGIN (canonical: scripts/shared-blocks/architecture-baseline.js; edit there, then: node scripts/shared-blocks.mjs --write) =====
// Generated from the canonical assessment schema (architecture-baseline.schema.json).
const BASELINE_SCHEMA = {"type":"array","minItems":1,"items":{"type":"object","additionalProperties":false,"required":["id","kind","requirements","subjects","documents","code","awsGuidance","designAction","documentationAction","implementationAction","rationale","conflicts","current","target","disposition","suitabilityEvidenceRefs"],"properties":{"id":{"type":"string","minLength":1},"requirements":{"type":"array","items":{"type":"string","minLength":1},"minItems":1},"subjects":{"type":"array","items":{"type":"string","minLength":1},"minItems":1},"documents":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["path","version","lifecycle_state"],"properties":{"path":{"type":"string","minLength":1},"version":{"type":"string","enum":["effective","target","delta","built"]},"lifecycle_state":{"type":"string","enum":["effective","in-review"]}}}},"code":{"type":"object","additionalProperties":false,"required":["state","behaviorEvidenceRefs","infrastructureEvidenceRefs"],"properties":{"state":{"type":"string","enum":["complete","partial","absent","unknown","not-applicable"]},"behaviorEvidenceRefs":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["path","heading","repo","revision","url"],"properties":{"path":{"type":"string"},"heading":{"type":"string"},"repo":{"type":"string"},"revision":{"type":"string"},"url":{"type":"string"}}}},"infrastructureEvidenceRefs":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["path","heading","repo","revision","url"],"properties":{"path":{"type":"string"},"heading":{"type":"string"},"repo":{"type":"string"},"revision":{"type":"string"},"url":{"type":"string"}}}}}},"awsGuidance":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["path","heading","repo","revision","url"],"properties":{"path":{"type":"string"},"heading":{"type":"string"},"repo":{"type":"string"},"revision":{"type":"string"},"url":{"type":"string"}}}},"designAction":{"type":"string","enum":["none","reuse","validate-existing","modify","new"]},"documentationAction":{"type":"string","enum":["none","update","create"]},"implementationAction":{"type":"string","enum":["none","modify","new","replace","retire","unknown"]},"rationale":{"type":"string","minLength":1},"conflicts":{"type":"array","items":{"type":"string","minLength":1}},"kind":{"type":"string","enum":["behavior","infrastructure","documentation"]},"current":{"type":"string","minLength":1},"target":{"type":"string","minLength":1},"disposition":{"type":"string","enum":["retain","change","replace","add","retire","undetermined"],"description":"Implementation disposition from assessed current behavior to the required target; existing code is evidence, never an obligation to retain it."},"suitabilityEvidenceRefs":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["path","heading","repo","revision","url"],"properties":{"path":{"type":"string"},"heading":{"type":"string"},"repo":{"type":"string"},"revision":{"type":"string"},"url":{"type":"string"}}},"minItems":1}}}}
// ===== SHARED BLOCK architecture-baseline — END =====
const SURVEY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['subject', 'subjectReason', 'capabilities', 'baseline', 'openTargets', 'businessConflicts', 'coverage', 'summary'],
  properties: {
    subject: { type: 'string' },
    subjectReason: { type: 'string' },
    coverage: COVERAGE_SCHEMA,
    baseline: BASELINE_SCHEMA,
    capabilities: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['name', 'requirements', 'effectiveViews', 'code', 'openBeads', 'openTargets'],
        properties: {
          name: { type: 'string' },
          requirements: { type: 'array', items: { type: 'string' } },
          effectiveViews: { type: 'array', items: { type: 'string' } },
          code: { type: 'array', items: { type: 'string' } },
          openBeads: { type: 'array', items: { type: 'string' } },
          openTargets: { type: 'array', items: { type: 'string' } },
          notes: { type: 'string' },
        },
      },
    },
    openTargets: { type: 'array', items: { type: 'string' } },
    businessConflicts: CONFLICT_ITEMS,
    summary: { type: 'string' },
  },
}
// Consumed by maker, checker and decider prompts: one shared completion standard.
const DESIGN_REVIEW_STANDARD = `Use the same acceptance basis throughout: applicable PRD outcomes, settled owner decisions and section-2 constraints, the relevant MODEL obligations, existing source evidence, and the retained target/delta. The assigned writers reconcile their connected contracts in the combined design before handing it to reviewers: contracts, event publishers, ownership, security and failure behavior must agree across its views. Inspect cited implementation and tests; distinguish evidence read from behavior actually verified. Do this within the existing authoring pass, not a new agent or audit pass.
BEFORE HANDOFF, the producer checks the same concrete obligations the reviewers will check, where relevant to this change: exact contract fields and identifiers across producer/consumer boundaries; event publisher, subscriber and owner agreement; data ownership and lifecycle; authorization and trust boundaries; failure, retry and idempotency behavior; cost assumptions with unit math; and consistency of the target, delta and their diagrams. Trace these against the applicable PRD outcomes, owner constraints, source evidence and MODEL obligations. Supply sufficient detail and evidence for independent verification in the retained views, not merely in the agent summary. This is completion of the assigned design, not permission to add product requirements, unrelated redesign or hypothetical scale. When a repair crosses a retained view boundary, repair the connected contract and views together within the ledger's reconciled ownership scope; do not leave a known contradiction because an earlier task named only one file.
Review is an independent safety net against that same basis, not a source of new requirements or preferred redesigns. Each finding identifies the violated requirement/constraint/contract or concrete correctness defect, its evidence and the bounded repair. Do not reopen a settled mechanism just to offer another design. On later rounds review the changed claims/views and their affected dependencies, retaining still-valid evidence; do not demand fresh unrelated proposals. New evidence of a real defect must still be reported. Neither this shared standard nor the selection of specialists guarantees approval.`

const COORDINATOR_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['readyForDecision', 'reason', 'dispatches', 'overlaps'],
  properties: {
    readyForDecision: { type: 'boolean' },
    reason: { type: 'string' },
    dispatches: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['agentType', 'role', 'task', 'selectionReason', 'repairIds', 'files', 'answers', 'claimIds', 'claimFiles', 'coverageIds'],
        properties: {
          agentType: { type: 'string' },
          role: { type: 'string', enum: Object.keys(ROSTER) },
          task: { type: 'string' },
          selectionReason: { type: 'string', minLength: 1 },
          repairIds: { type: 'array', items: { type: 'string' } },
          files: { type: 'array', items: { type: 'string' } },
          answers: { type: 'array', items: { type: 'string' } },
          coverageIds: { type: 'array', items: { type: 'string' } },
          claimIds: { type: 'array', items: { type: 'string' } }, claimFiles: { type: 'array', items: { type: 'string' } },
        },
      },
    },
    // Consumed by: archrounds.overlap_justified, which warns about an overlap no entry names.
    // One entry per overlap: the coordinator decides it once, with one reason.
    overlaps: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['files', 'claimIds', 'agentTypes', 'reason'],
        properties: {
          files: { type: 'array', items: { type: 'string' } },
          claimIds: { type: 'array', items: { type: 'string' } },
          agentTypes: { type: 'array', items: { type: 'string' } },
          reason: { type: 'string' },
        },
      },
    },
  },
}
// ===== SHARED BLOCK architecture-artifacts — BEGIN (canonical: scripts/shared-blocks/architecture-artifacts.js; edit there, then: node scripts/shared-blocks.mjs --write) =====
// Generated from the executable artifact-handoff contract schemas.
const WRITER_SCHEMA = {"type":"object","additionalProperties":false,"required":["files","claims","answers","businessConflicts","coverage","summary"],"properties":{"repairAnswers":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["repairId","response"],"properties":{"repairId":{"type":"string"},"response":{"type":"string"}}}},"files":{"type":"array","items":{"type":"string"}},"coverage":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["id","subject","scope","obligation","sources","views","status","action","reason","evidenceRefs","disposition","dispositionReason"],"properties":{"id":{"type":"string"},"subject":{"type":"string"},"scope":{"type":"string"},"obligation":{"type":"string"},"sources":{"type":"array","items":{"type":"string"}},"views":{"type":"array","items":{"type":"string"}},"status":{"type":"string","enum":["Present and sufficient","Present but incomplete","Required and absent","Not yet applicable","Not assessed"]},"action":{"type":"string","enum":["create","update","unchanged","remove","not-applicable","unresolved"]},"reason":{"type":"string"},"evidenceRefs":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["path","heading","repo","revision","url"],"properties":{"path":{"type":"string"},"heading":{"type":"string"},"repo":{"type":"string"},"revision":{"type":"string"},"url":{"type":"string"}}}},"disposition":{"type":"string","enum":["required","unrelated-debt"]},"dispositionReason":{"type":"string"}}}},"claims":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["claimId","claim","file","citation","supersedes","evidenceRefs"],"properties":{"claimId":{"type":"string"},"claim":{"type":"string"},"file":{"type":"string"},"citation":{"type":"string"},"supersedes":{"type":"array","items":{"type":"string"}},"evidenceRefs":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["path","heading","repo","revision","url"],"properties":{"path":{"type":"string"},"heading":{"type":"string"},"repo":{"type":"string"},"revision":{"type":"string"},"url":{"type":"string"}}}}}}},"answers":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["findingId","response","evidence"],"properties":{"findingId":{"type":"string"},"response":{"type":"string","enum":["fixed","disputed"]},"evidence":{"type":"string"}}}},"businessConflicts":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["requirements","why"],"properties":{"requirements":{"type":"array","items":{"type":"string"}},"why":{"type":"string"}}}},"summary":{"type":"string"}}}
const REVIEW_SCHEMA = {"type":"object","additionalProperties":false,"required":["findings","coverageChecks","resolutions","summary"],"properties":{"repairChecks":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["repairId","verdict","evidence","files"],"properties":{"repairId":{"type":"string"},"files":{"type":"array","items":{"type":"string"}},"verdict":{"type":"string","enum":["verified","revise"]},"evidence":{"type":"string"}}}},"coverageChecks":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["id","verdict","evidence"],"properties":{"id":{"type":"string"},"verdict":{"type":"string","enum":["verified","unsupported","wrong"]},"evidence":{"type":"string"}}}},"resolutions":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["findingId","verdict","evidence"],"properties":{"findingId":{"type":"string"},"verdict":{"type":"string","enum":["accepted","rejected"]},"evidence":{"type":"string"}}}},"findings":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["claimId","claim","file","verdict","evidence","owner"],"properties":{"claimId":{"type":"string"},"claim":{"type":"string"},"file":{"type":"string"},"verdict":{"type":"string","enum":["verified","unsupported","wrong"]},"evidence":{"type":"string"},"owner":{"type":"string"}}}},"estimates":{"type":"array","items":{"type":"string"}},"summary":{"type":"string"}}}
// ===== SHARED BLOCK architecture-artifacts — END =====
const OWNER_CONCERN_KINDS = ['business-conflict', 'architecture-conflict']
const DECISION_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['round', 'verdict', 'diligence', 'choices', 'returnTo', 'ownerConcerns', 'summary'],
  properties: {
    round: { type: 'integer' },
    verdict: { type: 'string', enum: ['approve', 'return', 'owner-concern'] },
    diligence: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['check', 'present', 'where'],
        properties: { check: { type: 'string' }, present: { type: 'boolean' }, where: { type: 'string' } },
      },
    },
    returnTo: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['agentType', 'missing'],
        properties: { agentType: { type: 'string' }, missing: { type: 'string' } },
      },
    },
    choices: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['dispute', 'chosen', 'why'],
        properties: { dispute: { type: 'string' }, chosen: { type: 'string' }, why: { type: 'string' } },
      },
    },
    ownerConcerns: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['kind', 'concern', 'evidence'],
        properties: { kind: { type: 'string', enum: OWNER_CONCERN_KINDS }, concern: { type: 'string' }, evidence: { type: 'string' } },
      },
    },
    summary: { type: 'string' },
  },
}
const MAINTAIN_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['changedFiles', 'createdFiles', 'deletedFiles', 'viewsChecked', 'constraintIssues', 'contradictions', 'summary'],
  properties: {
    changedFiles: { type: 'array', items: { type: 'string' } },
    createdFiles: { type: 'array', items: { type: 'string' } },
    deletedFiles: { type: 'array', items: { type: 'string' } },
    viewsChecked: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['element', 'view', 'action'],
        properties: { element: { type: 'string' }, view: { type: 'string' }, action: { type: 'string', enum: ['updated', 'deleted', 'added', 'unaffected'] } },
      },
    },
    constraintIssues: { type: 'array', items: { type: 'string' } },
    contradictions: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
}
const CONFORMANCE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['conforms', 'reviewedFiles', 'findings', 'coverageChecks', 'summary'],
  properties: {
    conforms: { type: 'boolean' },
    coverageChecks: COVERAGE_CHECKS_SCHEMA,
    reviewedFiles: { type: 'array', items: { type: 'string' } },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['file', 'finding', 'evidence'],
        properties: { file: { type: 'string' }, finding: { type: 'string' }, evidence: { type: 'string' } },
      },
    },
    summary: { type: 'string' },
  },
}

/** Returns the section 2 fingerprint, or { error }; with `keep`, section 2 is also copied aside for a restore. */
const constraintsSnapshot = (label, phaseName, keep) => depscore(label, phaseName, `arch-constraints --arch-root ${shq(archPath)}${keep ? ' --keep' : ''}`)
const sameSnapshot = (x, y) =>
  !!x && !!y && !x.error && !y.error && x.exists === y.exists && x.digest === y.digest && JSON.stringify(x.gitStatus || []) === JSON.stringify(y.gitStatus || [])
/** Returns null when section 2 is unchanged since `before`, else puts section 2 back from the copy and returns the failure. */
async function constraintsGuard(before, label, phaseName) {
  const after = await constraintsSnapshot(label, phaseName)
  if (sameSnapshot(before, after)) return null
  const restored = after && after.error ? null : await depscore(`${label}:restore`, phaseName, `arch-constraints-restore --arch-root ${shq(archPath)} --kept ${shq(before.kept)}`)
  const restoreNote = !restored ? '' : restored.error ? `; section 2 could not be put back: ${restored.error}` : `; section 2 was put back as it was (${listed(restored.written).length} file(s) written back, ${listed(restored.deleted).length} deleted)`
  const why = after && after.error
    ? `section 2 could not be fingerprinted after ${phaseName}: ${after.error}`
    : `a session wrote under ${CONSTRAINTS} during ${phaseName}; section 2 holds the owner's constraints and the pipeline never writes there (git status now: ${JSON.stringify((after && after.gitStatus) || [])})${restoreNote}`
  log(`Section 2: ${why}`)
  return { ok: false, stage: 'constraints-written', deterministicFailure: true, reason: why, error: why, before, after, restored }
}

/**
 * Fingerprints every file of arc42/, target/ and built/ with depscore.py arch-snapshot. The per-file
 * hashes stay on disk: `save` writes them to that file, and each file in `against` (a fingerprint
 * saved earlier) yields the NUMBER of files created, changed and deleted since it, in `diffs`, in
 * that order; their names stay in the relay file (`relayFile`, under result.diffs). Returns the
 * result or { error }.
 */
async function treeSnapshot(label, phaseName, { save, against = [] } = {}) {
  const out = await depscore(label, phaseName, `arch-snapshot --arch-root ${shq(archPath)} --counts${save ? ` --save ${shq(save)}` : ''}${against.map((f) => ` --against ${shq(f)}`).join('')}`)
  return !out || out.error ? out || { error: 'no result' } : out
}
/** The number of files diff `i` of a snapshot created, changed or deleted. */
function diffCount(snap, i) {
  const d = (snap && Array.isArray(snap.diffs) && snap.diffs[i]) || {}
  return (Number(d.created) || 0) + (Number(d.changed) || 0) + (Number(d.deleted) || 0)
}

/**
 * Binds the step's saved work to the arc42 views it read or wrote with depscore.py arch-revision.
 * Saved work one of whose views changed in arc42 since it was recorded moves to a dated stale folder
 * in the Epic's artifacts directory and the step starts again from the survey; a change elsewhere in
 * arc42 (another Epic's integration) leaves it in place.
 */
const revision = await depscore('revision:check', 'Survey', `arch-revision check --arch-root ${shq(archPath)} --work-dir ${shq(WORK)} --stale-root ${shq(ART.dir)}`)
if (!revision || revision.error || revision.ok !== true || !hasText(revision.revision)) {
  const why = `the saved work in ${WORK} could not be bound to the current arc42 revision: ${(revision && revision.error) || 'no result'}`
  return { ok: false, stage: 'survey', reason: why, error: why, ...died('Survey') }
}
if (revision.status === 'stale') log(`Revision: ${revision.reason}; ${revision.moved} saved item(s) set aside to ${revision.movedTo}; the step starts again from the survey`)
else log(`Revision: arc42 ${String(revision.revision).slice(0, 12)} (${revision.status})`)
/** Records the step's own integration in the revision record: 'integrating' before it writes arc42, 'integrated' once approved. A record that could not be written is logged. */
async function markRevision(state, phaseName) {
  const out = await depscore(`revision:${state}`, phaseName, `arch-revision mark --arch-root ${shq(archPath)} --work-dir ${shq(WORK)} --state ${state}`)
  if (!out || out.error || out.ok !== true) log(`Revision: the record in ${WORK} could not be marked ${state}: ${(out && out.error) || 'no result'}; the integration continues`)
}

const before = await constraintsSnapshot('constraints:before', 'Survey', true)
if (!before || before.error || !hasText(before.kept)) {
  const why = `section 2 of the architecture could not be fingerprinted and copied before the step: ${(before && before.error) || 'no copy was named'}`
  return { ok: false, stage: 'survey', reason: why, error: why, ...died('Survey') }
}
const treeBefore = await treeSnapshot('tree:before', 'Survey', { save: TREE_START })
if (!treeBefore || treeBefore.error) {
  const why = `the architecture could not be fingerprinted before the step: ${(treeBefore && treeBefore.error) || 'no result'}`
  return { ok: false, stage: 'survey', reason: why, error: why, ...died('Survey') }
}

let facts = await readFacts('resume:read-saved', 'Survey')
if (facts.error) {
  const why = `depscore.py arch-resume failed: ${facts.error}. arch-resume sets aside a saved file it cannot read; this failure is in the script itself.`
  return {
    ok: false,
    stage: 'resume',
    headline: facts.exception ? `Architecture resume failed: ${facts.exception}` : `Architecture could not read its saved work in ${WORK}: ${facts.error}`,
    reason: why,
    error: why,
    // A Python exception is deterministic: every re-dispatch meets it again. It is the pipeline's to fix, not the owner's.
    ...(facts.exception ? { deterministicFailure: true } : {}),
    ...died('Survey'),
  }
}
const resumedFacts = facts

// ---------------------------------------------------------------- Survey
async function surveyFreshness(label, seal = false) {
  const argv = ['python3', DS.script.replace(/[^/]+$/, 'archbaseline.py'), '--survey', SURVEY_JSON,
    ...[prd.path, MODEL, MENU, CONSTRAINTS].filter(hasText).flatMap(path => ['--input', path]),
    '--context-sha', relayKit.sha256Json({ prdBody: prd.body || '', schema: SURVEY_SCHEMA }), ...(seal ? ['--seal'] : [])]
  const result = await relayKit.run(run, { label, phase: 'Survey', runner: RELAY_RUNNER, argv, file: nextRelayFile(label) })
  if (!result.ok || ![0, 2].includes(result.exitCode) || !result.json || !/^[a-f0-9]{64}$/.test(result.json.revision || '')) {
    const message = result.error || JSON.stringify(result.json || {})
    dispatchFailures.push({ label, phase: 'Survey', message }); log(`${label}: ${message}`); return null
  }
  const warnings = listed(result.json.warnings)
  if (warnings.length) log(`${label}: ${warnings.length} warning(s) about the survey's assessment and evidence, listed under warnings in ${result.relayFile}`)
  return result.json
}
phase('Survey')
const surveyFresh = await surveyFreshness('survey:freshness')
if (!surveyFresh) return { ok: false, stage: 'survey-inputs', ...died('Survey') }
const savedSurvey = surveyFresh.current === true && facts.survey && facts.survey.saved === true && hasText(facts.survey.subject) ? facts.survey : null
let survey = savedSurvey ? { subject: savedSurvey.subject, capabilities: savedSurvey.capabilities } : null
/**
 * Dispatches the survey and saves it, sealed to its inputs. With `recheck`, the Check review left
 * findings that the effective architecture lacks design or documentation: the survey reassesses the
 * affected capabilities from those findings, so they enter design scope. Updates `facts`; returns
 * the accepted survey, or { failure } with the result that stops the step.
 */
async function runSurvey(recheck = false) {
  const label = recheck ? 'survey:recheck' : 'survey:reality'
  const repos = await run(
    `List every repository of this project: its name, the absolute path of its local checkout, its role (what it is for) and its lifecycle (for example active, deprecated, archived). Answer from your records and the live repositories. Change nothing.`,
    { label: recheck ? 'survey:recheck-repositories' : 'survey:repositories', phase: 'Survey', agentType: 'agent-teams-workforce:polyrepo-steward', effort: 'low', schema: REPOS_SCHEMA }
  )
  if (!repos) return { failure: { ok: false, stage: 'survey', reason: 'the polyrepo-steward named no repositories', ...died('Survey') } }
  const fresh = recheck ? await surveyFreshness('survey:recheck-freshness') : surveyFresh
  const surveyRevision = fresh && fresh.revision
  if (!surveyRevision) return { failure: { ok: false, stage: 'survey-inputs', ...died('Survey') } }
  const surveyCandidate = `${WORK}/candidates/${recheck ? 'survey-recheck' : 'survey'}.json`
  const surveyPrior = await probeArtifact(label, 'Survey', surveyCandidate, SURVEY_JSON, SURVEY_SCHEMA, surveyRevision)
  if (!surveyPrior) return { failure: { ok: false, stage: 'survey', ...died('Survey') } }
  const recheckBlock = recheck
    ? `\nRECHECK: the Check review of your survey left open findings: the \`findings\` list of ${LEDGER_JSON}, with the coverage checks in ${ROUNDS_DIR}. Reassess the capabilities they concern. Where a finding shows that a section 2 constraint or non-effective arc42 content is not represented in the effective views, or that design or documentation is missing, set that capability's \`designAction\` or \`documentationAction\` with the cited gap, so it enters design scope. Where the evidence refutes a finding, keep the assessment and say why in \`notes\`. Keep the subject: ${subjectName}.\n`
    : ''
  const surveyed = surveyPrior.pending ? await run(
    `You are the prd-reality-reconciler, SURVEYING for the architecture step. The architecture team designs from your survey; you design nothing. If a survey exists, retain still-valid evidence and provenance; reassess affected facts, the subject and the assessment against the current inputs.
${recheckBlock}
PRD: ${prdRef}

${ARCH_WHERE}

${INPUTS_RULE}

${COVERAGE_RULE}

THE REPOSITORIES, from the polyrepo-steward (use these facts as given; do not look for repositories yourself):
${JSON.stringify(repos.repositories, null, 2)}

THE OPEN BEADS are in the central beads database (${DS.repo}). Read them with \`atw-bd\`, which reads that database wherever it runs, read-only (\`atw-bd list\`, \`atw-bd show\`, \`atw-bd search\`); write nothing to beads.

For EACH capability the PRD needs, report:
- \`effectiveViews\`: the absolute paths of the effective views (under ${ARC42}) that show it, found through the catalog;
- \`code\`: the code that implements it on \`main\`, as \`<repo>:<path>:<line>\`;
- \`openBeads\`: the ids of open Stories and Tasks of other Epics that plan work on it;
- \`openTargets\`: the paths of open targets under ${archPath}/target/ that change it;
- \`requirements\`: the PRD requirement headings it serves.
An empty list is an answer: say in \`notes\` where you looked. In \`notes\` also give the result of the architecture-baseline skill's check of what the effective architecture does not yet represent, with the documents checked.

Name the \`subject\` the target will describe: the feature, service, component or layer this PRD changes, named as the glossary and the repositories name it — never the PRD, the Epic, a bead id or a date — and say why in \`subjectReason\`. Give the name as it is written (\`Company Intelligence\` and \`company-intelligence\` are both fine): the run derives the \`target/<subject>/\` folder name from it (lower-case, every run of other characters one hyphen).
${PRD_RULE}
${BUSINESS_CONFLICT_RULE}
Write ${SURVEY_MD} as the readable survey; pass its path rather than copying it into responses.${artifactBrief(surveyCandidate, SURVEY_SCHEMA, surveyRevision)}`,
    { label, phase: 'Survey', agentType: 'prd-reality-reconciler', effort: 'medium', schema: ARTIFACT_RETURN_SCHEMA }
  ) : surveyPrior
  if (!(await acceptArtifact(label, 'Survey', surveyCandidate, SURVEY_JSON, SURVEY_SCHEMA, surveyed, surveyRevision))) {
    const why = `the survey the prd-reality-reconciler returned could not be saved to ${SURVEY_JSON}`
    return { failure: { ok: false, stage: 'survey', reason: why, error: why, ...died('Survey') } }
  }
  await recordFiles(recheck ? 'survey:recheck-record' : 'survey:record', 'Survey', [SURVEY_MD])
  const sealed = await surveyFreshness(recheck ? 'survey:recheck-seal' : 'survey:seal', true)
  if (!sealed) return { failure: { ok: false, stage: 'survey-inputs', reason: 'the accepted survey could not be sealed to its inputs', ...died('Survey') } }
  if (sealed.current !== true) {
    const why = `the accepted survey ${SURVEY_JSON} carries no assessment: ${listed(sealed.errors).join('; ') || 'its baseline list is missing'}`
    return { failure: { ok: false, stage: 'survey', reason: why, error: why, ...died('Survey') } }
  }
  const acceptedSurvey = await readFacts(recheck ? 'survey:recheck-accepted' : 'survey:accepted', 'Survey')
  if (acceptedSurvey.error) return { failure: { ok: false, stage: 'survey', reason: acceptedSurvey.error } }
  facts = acceptedSurvey
  return { survey: acceptedSurvey.survey }
}
if (survey) {
  log(`Survey: reused ${SURVEY_JSON}`)
} else {
  log(`Survey: refreshing the assessment because ${listed(surveyFresh.errors).join('; ') || 'its input binding is missing or changed'}; retained round artifacts remain available for content-scoped reuse`)
  const surveyed = await runSurvey()
  if (surveyed.failure) return surveyed.failure
  survey = surveyed.survey
}
/** Where the survey is; failures name the files, never carry the survey. */
const surveyPaths = { surveyPath: SURVEY_MD, surveyJsonPath: SURVEY_JSON }
// The subject as named; depscore.py arch-target derives the folder name every later step uses,
// taking dates and the Epic, PRD and bead names out of it. With no subject named, the PRD file's
// name stands in, and the name of the PRD itself is not taken out of it.
const surveyedSubject = hasText(a.subject) ? a.subject.trim() : hasText(survey.subject) ? survey.subject.trim() : ''
const subjectName = surveyedSubject || prdBase
const SUBJECT_FORBID = (surveyedSubject ? FORBID : FORBID.filter((t) => t !== prdBase)).join(',')
if (!surveyedSubject && subjectName) log(`Survey: no subject was named; the PRD file's name ${subjectName} names the target`)
/** Checks the draft with depscore.py arch-target --dry-run; the full report goes to TARGET_CHECK and only its summary comes back. Returns the summary or { error }. */
async function checkDraft(label, phaseName, subjectArg) {
  const out = await depscore(label, phaseName, `arch-target --draft ${shq(DRAFT)} --baseline ${shq(SURVEY_JSON)} --arch-root ${shq(archPath)} --subject ${shq(subjectArg)} --forbid ${shq(SUBJECT_FORBID)} --dry-run --out ${shq(TARGET_CHECK)}`)
  if (!out || out.error) return out || { error: 'no result' }
  return out.summary && typeof out.summary === 'object' ? out.summary : { error: 'depscore.py arch-target printed no summary' }
}
const subjectCheck = await checkDraft('target:check-subject', 'Survey', subjectName || '-')
const subjectRefusals = subjectCheck && !subjectCheck.error ? listed(subjectCheck.subjectRefusals) : []
const subject = subjectCheck && !subjectCheck.error && hasText(subjectCheck.subject) ? subjectCheck.subject.trim() : ''
if (!subjectName || subjectRefusals.length || !subjectCheck || subjectCheck.error || !subject) {
  const why = !subjectName
    ? 'the survey named no subject for the target and no PRD file name stands in for one'
    : subjectRefusals.length
      ? `the target subject cannot name a target: ${subjectRefusals.join('; ')}`
      : `the target subject could not be checked: ${(subjectCheck && subjectCheck.error) || 'no folder name returned'}`
  return { ok: false, stage: 'survey', deterministicFailure: subjectRefusals.length > 0, reason: why, error: why, ...surveyPaths }
}
if (subject !== subjectName) log(`Survey: the subject ${subjectName} names the folder target/${subject}/`)
log(`Survey: subject ${subjectName} (folder target/${subject}/); ${Number(survey.capabilities) || 0} capabilit(ies)`)

// ---------------------------------------------------------------- Rounds
// The claim and finding ledger lives on disk: depscore.py arch-resume folds every saved round result
// into ledger.json and returns only the facts below. Sessions read the ledger by its path.
let lastRound = Number(facts.rounds.last) || 0
/** Every re-dispatch after a failed or empty result, with what changed in its input. */
const retries = []
/** Each finding id handed to a writer to answer: { agentType, round, clarified }. */
const asked = new Map()
let silentLast = []
/** Authorship follows the design/documentation obligations the survey's assessment leaves unresolved, never a fixed discipline quota. */
const baselineNeedsAuthor = () => !!(listed(facts.baseline && facts.baseline.designWork).length || listed(facts.baseline && facts.baseline.docWork).length)
/** The capabilities writers may be dispatched for: those the survey marks for design or documentation work, or with unresolved evidence. */
const designScope = () => [...new Set([...listed(facts.baseline && facts.baseline.designWork), ...listed(facts.baseline && facts.baseline.docWork), ...listed(facts.baseline && facts.baseline.unknowns)])]
/** True when the effective architecture and the code already serve every capability: the target is checked and approved, not designed. */
const checkOnly = () => !!(facts.baseline && facts.baseline.valid === true && !designScope().length)
const CHECK_REVIEWER = 'architecture-boundary-guardian'
/** The fixed round plan of the Check step: one independent reviewer verifies every coverage row and the existing design of the capabilities the survey marks validate-existing. */
const checkPlan = () => {
  const review = listed(facts.baseline && facts.baseline.designReview)
  return {
    readyForDecision: true,
    overlaps: [],
    dispatches: [{
      role: 'reviewer',
      agentType: CHECK_REVIEWER,
      selectionReason: 'the survey finds every capability served by the effective architecture and the code on main, with nothing in arc42 left unrepresented; the target needs independent verification of its coverage rows and of that representation, not design',
      task: `Verify every row of the \`coverage\` list in ${LEDGER_JSON} against the effective views and the code on main, and return a coverage check for each.${review.length ? ` Verify that the existing design serves these capabilities as the survey states: ${review.join(', ')}.` : ''} Check, as the architecture-baseline skill describes, that the section 2 constraints and the non-effective arc42 content (in-review views, open targets, build records) that apply to the PRD's capabilities are represented in their effective views; report each that is not as a finding citing the constraint or document and the effective view, so the survey reassesses that capability.`,
      coverageIds: [],
      claimIds: [],
      claimFiles: [],
      repairIds: [],
      answers: [],
      files: [],
    }],
  }
}
const ledgerFacts = () => facts.rounds
const writersSoFar = () => listed(ledgerFacts().writers)
const openFindings = () => (Array.isArray(ledgerFacts().openFindings) ? ledgerFacts().openFindings : []).filter((f) => f && hasText(f.id))
/** The number of claims without a reviewer verdict, by writer. */
const unreviewedByWriter = () => Object.entries(ledgerFacts().unreviewedClaims || {}).filter(([, k]) => Number(k) > 0)
const unreviewedCount = () => unreviewedByWriter().reduce((t, [, k]) => t + Number(k), 0)
const ledgerLine = () => `${Number(ledgerFacts().claims) || 0} claim(s), ${Number(ledgerFacts().findings) || 0} finding(s), ${openFindings().length} open, ${unreviewedCount()} claim(s) without a reviewer verdict`
if (lastRound) log(`Rounds: resumed after round ${lastRound} — ${ledgerLine()}`)

/**
 * Returns what is still open in the team's work: the coordinator routes it and the decider reads it.
 * None of it stops the decider from ruling; the target write and the integration review check what
 * reaches the architecture.
 */
function decisionNotes() {
  const notes = []
  for (const id of listed(facts.repairs && facts.repairs.open)) notes.push(`repair ${id} awaits its bounded correction in ${LEDGER_JSON}`)
  for (const id of listed(facts.repairs && facts.repairs.checksNeeded)) notes.push(`repair ${id} awaits independent verification of the current artifacts in ${LEDGER_JSON}`)
  if (gapCount(facts)) notes.push(`${gapCount(facts)} coverage note(s): each is listed under result.coverage.gaps in ${facts.relayFile}, with its row in ${LEDGER_JSON}`)
  if (!facts.baseline) notes.push(`depscore.py arch-resume reported no assessment facts for the survey (the \`baseline\` list of ${SURVEY_JSON})`)
  else if (facts.baseline.valid !== true) notes.push(`the survey carries no assessment (the \`baseline\` list of ${SURVEY_JSON}): ${listed(facts.baseline.errors).join('; ') || 'no error named'}`)
  if (listed(facts.baseline && facts.baseline.warnings).length) notes.push(`${listed(facts.baseline.warnings).length} warning(s) about the survey's assessment, listed under result.baseline.warnings in ${facts.relayFile}`)
  if (listed(facts.baseline && facts.baseline.unknowns).length) notes.push(`the survey's implementation evidence is unresolved for ${facts.baseline.unknowns.join(', ')}; it is carried as implementation work`)
  if (baselineNeedsAuthor() && !writersSoFar().length) notes.push("the survey's assessment names design or documentation work that no writer has authored yet")
  for (const f of openFindings()) notes.push(`finding ${f.id} (its verdict and file are in ${LEDGER_JSON}) ${f.answered ? 'awaits independent resolution of its answer' : 'is unanswered'}; owner ${f.owner || 'not known — assign it to a writer'}`)
  for (const [w, k] of unreviewedByWriter()) notes.push(`${k} claim(s) by ${w} have no reviewer verdict (the claims by ${w} in ${LEDGER_JSON} whose \`verdicts\` list is empty)`)
  return notes
}

/**
 * Makes the draft reviewable before any review reads it. depscore.py arch-target --seed writes the
 * baseline handoff from the survey into the draft as baseline.json: the effective views each
 * capability relies on, the implementation gaps against the code on main, and the note naming the
 * case — none (future = current: this one set, no delta), new (the authored views are both future
 * and delta) or partial (target views and a delta of the change alone). It is deterministic and
 * rewritten from the current survey each time; views a writer authored sit beside it. Returns
 * { draft: true, change } when the draft exists to review, { draft: false } when it could not be
 * made (the reviewers then read the canonical views), or { error }.
 */
async function reviewTarget(label, phaseName) {
  const seeded = await depscore(`${label}:seed`, phaseName, `arch-target --seed --draft ${shq(DRAFT)} --baseline ${shq(SURVEY_JSON)} --arch-root ${shq(archPath)} --subject ${shq(subject)} --forbid ${shq(SUBJECT_FORBID)}`)
  const seedOk = !!(seeded && !seeded.error && seeded.summary && seeded.summary.ok === true)
  if (!seedOk) log(`${label}: the baseline handoff could not be seeded into the draft: ${(seeded && seeded.error) || listed(seeded && seeded.summary && seeded.summary.refusals).join('; ') || 'no result'}`)
  const check = await checkDraft(label, phaseName, subject)
  if (!check || check.error) return { error: `the draft could not be checked: ${(check && check.error) || 'no result'}` }
  return { draft: seedOk || check.draftWritten === true, authored: check.draftWritten === true, change: (seedOk && seeded.summary.architectureChange) || '' }
}
/** The design a reviewer or the decider reads, as one prompt line. */
const reviewedDesign = (draft) => draft
  ? `THE DRAFT TARGET is ${DRAFT}. Its \`baseline.json\` is the baseline handoff written from the survey: each capability with the effective views it relies on (\`entries[].documents\`, cited by path), \`implementationWork\` (the capabilities whose implementation is not built on \`main\`: the build work, which is not architecture change), and \`architectureChange\` with its \`note\`. Review the documents the note names: \`none\` — no architecture change, so the one set is the current effective views it cites (${ARC42}) and there is no delta; \`new\` — the authored views in the arc42 section layout are both the future and the delta; \`partial\` — the authored target views and \`delta/\`, the change alone; \`pending\` — the assessment names design or documentation work no writer has authored yet, so there is nothing to review but the handoff, and every missing view is a finding for its writer. Read it; write nothing in it and nothing in ${archPath}.`
  : `THE DESIGN UNDER REVIEW is the existing design: the draft could not be written, so review the canonical arc42 views in ${ARC42} (the effective version, with the owner's constraints in section 2) and the open targets in ${archPath}/target/, against the survey. Read them; write nothing in ${archPath}.`

/** The saved decision's facts: { verdict, round, returnTo: [agent], ownerConcerns: count, ownerConcernKinds, ownerOnly }. */
const savedDecision = facts.decision && typeof facts.decision === 'object' && hasText(facts.decision.verdict) ? facts.decision : null
const repairsPending = (value) => !!(listed(value.repairs && value.repairs.open).length || listed(value.repairs && value.repairs.checksNeeded).length)
// A saved approval stands unless rounds ran after it.
let decision = savedDecision && savedDecision.verdict === 'approve' && !facts.rounds.pendingPlan && (Number(savedDecision.round) || 0) >= lastRound ? savedDecision : null
const roundLimit = MAX_ROUNDS
/** Returns eligible specialists named by the decision; their bounded repairs remain in the decision artifact. */
const returnedTo = (dec) =>
  (dec && Array.isArray(dec.returnTo) ? dec.returnTo : [])
    .map((r) => (typeof r === 'string' ? r : r && r.agentType))
    .filter((r) => hasText(r) && !!roleOf(r.trim().replace(AGENT_PREFIX, '')))
    .map((r) => ({ agentType: r.trim().replace(AGENT_PREFIX, '') }))
let forced = savedDecision && savedDecision.verdict === 'return' && !(lastRound > (savedDecision.round || 0)) ? returnedTo(savedDecision) : []
let rejected = []
let pendingGaps = []

/** Returns the owner-concern result that holds the Epic for the owner. A decision read back from disk carries only the count and kinds; the owner reads the concerns in the decision file. */
function ownerConcern(dec) {
  const concerns = Array.isArray(dec.ownerConcerns) ? dec.ownerConcerns.filter((c) => c && hasText(c.concern)) : null
  const count = concerns ? concerns.length : Number(dec.ownerConcerns) || 0
  return {
    ok: false,
    stage: 'owner-concern',
    reason: `the architecture-decider raised ${count} owner concern(s) on ${subject}`,
    ...(concerns ? { ownerConcerns: concerns } : { ownerConcernKinds: listed(dec.ownerConcernKinds) }),
    requiredHumanActions: [
      ...(concerns
        ? concerns.map((c) => `${c.kind === 'architecture-conflict' ? 'CONFLICTING SECTION 2 CONSTRAINTS' : 'CONFLICTING BUSINESS REQUIREMENTS'} on ${subject}: ${c.concern} — evidence: ${c.evidence}`)
        : [`The architecture-decider raised ${count} owner concern(s) on ${subject} (${listed(dec.ownerConcernKinds).join(', ')}): read them in ${DECISION_MD}.`]),
      `Once the PRD or section 2 says which side holds, delete ${DECISION_JSON}: while it holds these concerns, every run of the architecture step holds the Epic again.`,
    ],
    decision: dec,
    decisionPath: DECISION_MD,
    subject,
    ...surveyPaths,
  }
}
/** True when the last decision escalated issues the team resolves itself; the coordinator reads them in the decision file. */
let teamNotes = false
/** True when every owner concern of a decision is one of the two cases that reach the owner: irreconcilable business requirements, or conflicting section 2 constraints. */
const businessOnly = (dec) => {
  if (typeof dec.ownerOnly === 'boolean') return dec.ownerOnly
  const concerns = (Array.isArray(dec.ownerConcerns) ? dec.ownerConcerns : []).filter((c) => c && hasText(c.concern))
  return concerns.length > 0 && concerns.every((c) => OWNER_CONCERN_KINDS.includes(c.kind))
}
if (savedDecision && savedDecision.verdict === 'owner-concern') {
  if (businessOnly(savedDecision)) {
    log('Decide: the saved decision holds conflicting business requirements; the Epic is held again')
    return ownerConcern(savedDecision)
  }
  log('Decide: the saved decision escalated what the team decides itself; it is set aside and the team resolves it')
  teamNotes = Number(savedDecision.ownerConcerns) > 0
}

/** Returns the prompt for one writer or reviewer dispatch. */
function dispatchPrompt(n, d, file, revision, research = null, reviewsDraft = false, lastWriter = false) {
  const contractKind = WRITER_ROLES.includes(d.role) ? 'writer' : 'review'
  const contractRoot = DS.script.replace(/scripts\/portfolio\/[^/]+$/, 'skills/artifact-handoff')
  const contractTool = DS.script.replace(/[^/]+$/, 'artifactcontract.py')
  const contractBinding = `--schema-file ${shq(`${contractRoot}/schemas/architecture-${contractKind}.schema.json`)} --candidate ${shq(file)} --revision ${shq(revision)} --progress-file ${shq(`${file}.progress.json`)}`
  const completionCommand = `python3 ${shq(contractTool)} submit ${contractBinding}${WRITER_ROLES.includes(d.role) ? ` --files-root ${shq(DRAFT)} --files-field files` : ''}`
  const checkpointCommand = `python3 ${shq(contractTool)} checkpoint ${contractBinding}`
  const planEntry = `the dispatch with \`seq\` ${d.seq} (${d.agentType}) in the round ${n} entry of \`roundPlans\` in ${LEDGER_JSON}`
  const taskLine = hasText(d.task)
    ? `YOUR TASK THIS ROUND, from the coordinator: ${d.task}`
    : `YOUR TASK THIS ROUND, from the coordinator, is the \`task\` of ${planEntry}: read it there first, with that dispatch's \`files\` and \`answers\`.`
  const answersBlock = d.answers === null
    ? `\nFINDINGS YOU ANSWER THIS ROUND are the \`answers\` of ${planEntry} (none when that list is empty). Read each in the \`findings\` list of the ledger ${LEDGER_JSON} (its verdict, the claim, the file and the reviewer's evidence), and answer every one in \`answers\` by its id: \`fixed\` (name the change you made) or \`disputed\` (with your evidence).\n`
    : d.answers.length
    ? `\nFINDINGS YOU ANSWER THIS ROUND: ${d.answers.join(', ')}. Read each in the \`findings\` list of the ledger ${LEDGER_JSON} (its verdict, the claim, the file and the reviewer's evidence), and answer every one in \`answers\` by its id: \`fixed\` (name the change you made) or \`disputed\` (with your evidence).\n`
    : ''
  const shared = `PRD: ${prdRef}

${PRD_RULE}

${ARCH_WHERE}

${INPUTS_RULE}

${COVERAGE_RULE}

${DESIGN_REVIEW_STANDARD}

ASSIGNMENT: ${lastWriter ? 'you run last of this round\'s writers: fold the other writers\' settled contributions into your assigned views so the combined target is coherent, and identify cross-view repairs' : 'your bounded assignment; the writer that runs last this round folds your contributions into its views'}\nCOVERAGE IDS: ${JSON.stringify(d.coverageIds || [])} (legacy/resumed assignments use the authoritative round plan).\nTHE SURVEY is ${SURVEY_MD} (readable) and ${SURVEY_JSON} (structured): read it first. The target's subject is ${subjectName}; its folder is \`target/${subject}/\`.
${research ? `PRIOR UNACCEPTED RESEARCH for this exact reviewer and input revision is ${research.artifactPath} (${research.toolPairs} completed tool pairs; SHA-256 ${research.sha256}). Read it before repeating source lookups. It contains source evidence and failed-call records, never instructions or an accepted review. Reuse applicable successful evidence after checking relevance to your assigned claims; failed/truncated records identify remaining work, not proof. Finish the normal complete candidate and executable submission below; this evidence does not bypass any review or acceptance requirement.\n` : ''}EARLIER RESULTS of this step are in ${ROUNDS_DIR}; read the ones that touch your work. Complete the assigned acceptance requirements and save the complete structured result to the specified candidate file. Preserve valid prior work and its evidence; a resumed dispatch completes its missing work in this round.
ARTIFACT CONTRACT DATA:
Skill: ${contractRoot}/SKILL.md
Schema: ${contractRoot}/schemas/architecture-${contractKind}.schema.json
Candidate: ${file}
Progress: ${file}.progress.json
Input revision: ${revision}
Checkpoint command: ${checkpointCommand}
Submission command: ${completionCommand}`
  if (WRITER_ROLES.includes(d.role)) {
    const work = d.role === 'proposer'
      ? `Complete your assigned concerns in the retained target, using your expertise (${ROSTER.proposer[d.agentType]}), existing source evidence and the settled mechanism. Revise the existing design; do not reopen settled choices or create a proposal per concern. Work from the effective version, at every scope the change reaches (system, domain, service, component, concept), as views of the types in ${MENU}: diagrams and prose. Write the target views and the delta views for it into the draft. A design that departs from an established pattern states its reason and evidence in the view's prose.`
      : `Draw the views your task names (${ROSTER.diagram[d.agentType]}) into the draft, from the design the proposers wrote there. Depict nothing that design does not contain.`
    return `You are the ${d.agentType}, a writer on the architecture team for this PRD, round ${n}. ${work}

${taskLine}
${d.files === null ? `THE DRAFT FILES YOU OWN THIS ROUND are the \`files\` of ${planEntry}, relative to ${DRAFT} (write only these; other sessions may be writing the rest). When that list is empty, change no view another writer owns, and name every file you write in \`files\`.` : d.files.length ? `THE DRAFT FILES YOU OWN THIS ROUND, relative to ${DRAFT} (write only these; other sessions may be writing the rest):\n${d.files.map((f) => `- ${f}`).join('\n')}` : 'You were named no draft files this round: change no view another writer owns, and name every file you write in `files`.'}
${answersBlock}
${shared}

${DRAFT_RULES}

Read \`repairRequests\` in ${LEDGER_JSON}. For each open repair assigned to you by the coordinator, complete its missing diligence and return \`repairAnswers\` with its exact repairId and a response identifying the changed views/evidence. Retain resolved repairs; do not redo them.

Use claimId="" for a new claim or the existing ledger id for an explicit revision. Keep unchanged ids; supersedes lists only deliberately replaced claims you own. Cite evidenceRefs and do not silently discard findings. A writer answer proposes a fix/dispute; independent resolution is still required. Return in \`files\` every draft file you wrote, relative to ${DRAFT}. Return in \`claims\` every claim your views make that a reviewer must check — about AWS (cite the documentation page you read), the code (cite repository, path and line on \`main\`), or the architecture (cite the view path and heading) — each with the draft file it is in. A design with no claims cannot be reviewed and cannot be approved: state every claim a reviewer must check. ${BUSINESS_CONFLICT_RULE}`
  }
  return `You are the ${d.agentType}, a ${d.role === 'cost' ? 'cost reviewer' : 'reviewer'} on the architecture team for this PRD, round ${n}: ${ROSTER[d.role][d.agentType]}.

${taskLine}

${reviewedDesign(reviewsDraft)}

${shared}

THE LEDGER is ${LEDGER_JSON}: every claim the writers stated (\`claims\`, each with its \`id\`, writer, draft file, citation and the \`verdicts\` given so far) and every finding. Read it; write nothing in it.
YOUR ASSIGNED CLAIMS are the \`assignedClaims\` of ${planEntry}. Check exactly these claims against their citations with independent evidence, and give each claim's id as claimId. Do not repeat unrelated verified claims. When none are assigned, answer only your coordinator's bounded domain question and affected dependencies; do not start a blanket audit.
Read \`repairRequests\` in ${LEDGER_JSON}. Independently verify answered repairs within your assigned scope against the current artifacts; return \`repairChecks\` with repairId, verified/revise, concrete evidence and files: the draft-relative or absolute evidence/contract file paths you inspected for that repair. A revise check may use an empty files list. Do not repeat resolved repair requests without identifying new evidence of a current defect.
Return verified, unsupported or wrong with evidence. Check the coverage IDs named in your task. For answered findings within your assigned scope, return resolutions with findingId, accepted/rejected and independent evidence: accept fixed only after verifying the changed evidence/view, and disputed only when evidence refutes the original finding. An unsupported assertion never resolves a finding. A new concrete uncovered problem uses an empty claimId and names its writer as owner.${d.role === 'cost' ? ' State your estimates, with the unit math, in `estimates`; a cost the design does not support is a finding like any other.' : ''}`
}

const cleanFile = (f) => String(f || '').trim().replace(/^\/+/, '')
const agentName = (x) => String(x || '').trim().replace(AGENT_PREFIX, '')
/** The plan's overlap entries that state a reason, normalized as they are saved. */
const planOverlaps = (plan) =>
  (Array.isArray(plan && plan.overlaps) ? plan.overlaps : [])
    .filter((o) => o && hasText(o.reason))
    .map((o) => ({ files: listed(o.files).map(cleanFile), claimIds: listed(o.claimIds), agentTypes: listed(o.agentTypes).map(agentName), reason: o.reason.trim() }))

/** The requirement ids a design-scope capability serves, from the survey's assessment. */
const scopeRequirements = (capability) => listed(facts.baseline && facts.baseline.requirementsOf && facts.baseline.requirementsOf[capability])
/** The writer the script adds for a capability, by the kind of obligation the assessment records for it. */
const WRITER_FOR_KIND = { behavior: 'integration-pattern-architect', infrastructure: 'cdk-infrastructure-designer', documentation: 'architecture-diagram-author' }
/**
 * Returns the plan with the writers its round needs: while the survey's assessment names design or
 * documentation work no writer has authored, and the coordinator's plan has no writer, one writer is
 * added for each capability with that work, chosen by the kind of obligation it is, ahead of the
 * reviewers, so reviewers review authored work.
 */
function withWriters(plan) {
  const dispatches = Array.isArray(plan.dispatches) ? plan.dispatches : []
  if (!baselineNeedsAuthor() || writersSoFar().length || dispatches.some((d) => WRITER_ROLES.includes(roleOf(agentName(d && d.agentType))))) return plan
  const kinds = (facts.baseline && facts.baseline.kindOf) || {}
  const work = [...new Set([...listed(facts.baseline.designWork), ...listed(facts.baseline.docWork)])]
  const added = work.map((c) => {
    const agentType = WRITER_FOR_KIND[kinds[c]] || WRITER_FOR_KIND.behavior
    const ids = scopeRequirements(c)
    return {
      agentType,
      role: roleOf(agentType),
      task: `Author the target views, and the delta views of the change, for the capability ${c}${ids.length ? ` (${ids.join(', ')})` : ''}, as the survey's assessment in ${SURVEY_JSON} describes its design and documentation work.`,
      selectionReason: `the survey's assessment names design or documentation work for ${c} that no writer has authored`,
      repairIds: [], files: [], answers: [], coverageIds: [], claimIds: [], claimFiles: [],
    }
  })
  log(`Round plan: the plan has no writer while the assessment names unauthored work; added ${[...new Set(added.map((d) => d.agentType))].join(', ')} for ${work.join(', ')}`)
  return { ...plan, readyForDecision: false, dispatches: [...added, ...dispatches] }
}

/** Validates only the coordinator's justified dispatches; returns { dispatches, rejected, stuck }. */
function settleDispatches(plan, n) {
  const out = []
  const bad = []
  for (let d of Array.isArray(plan.dispatches) ? plan.dispatches : []) {
    const name = d && hasText(d.agentType) ? d.agentType.trim().replace(AGENT_PREFIX, '') : ''
    const role = roleOf(name)
    if (!role) {
      bad.push(`${name || '(no agent)'}: not on the roster`)
      continue
    }
    if (role !== d.role) log(`Round ${n}: ${name} runs as ${role}, its roster role, not ${d.role}`)
    if (!hasText(d.selectionReason)) d = { ...d, selectionReason: 'coordinator selected' }
    const files = WRITER_ROLES.includes(role) ? listed(d.files).map(cleanFile) : []
    const badFile = files.find((f) => !f || f.split('/').includes('..') || f.split('/').includes('02-architecture-constraints'))
    if (badFile !== undefined) {
      bad.push(`${name}: draft file ${JSON.stringify(badFile)} is outside the draft or in section 2`)
      continue
    }
    const answers = WRITER_ROLES.includes(role) ? listed(d.answers) : []
    for (const id of answers) {
      const f = openFindings().find((x) => x.id === id && !x.answered)
      if (f) {
        f.owner = name
        assigned.set(id, name)
      }
    }
    const same = out.find((x) => x.agentType === name)
    if (same) {
      same.task = `${same.task}\n${d.task}`
      same.selectionReason += `; ${d.selectionReason || ''}`
      same.repairIds = [...new Set([...same.repairIds, ...listed(d.repairIds)])]
      same.files = [...new Set([...same.files, ...files])]
      same.answers = [...new Set([...same.answers, ...answers])]
      same.coverageIds = [...new Set([...same.coverageIds, ...listed(d.coverageIds)])]
      same.claimIds = [...new Set([...same.claimIds, ...listed(d.claimIds)])]
      same.claimFiles = [...new Set([...same.claimFiles, ...listed(d.claimFiles).map(cleanFile)])]
    } else {
      out.push({ agentType: name, role, task: String(d.task || ''), selectionReason: String(d.selectionReason || ''), repairIds: listed(d.repairIds), files, answers, coverageIds: listed(d.coverageIds), claimIds: listed(d.claimIds), claimFiles: listed(d.claimFiles).map(cleanFile) })
    }
  }
  // Only the coordinator selects authors. Missing assignments remain ledger gaps,
  // rather than silently creating additional writer dispatches here.
  for (const d of out) d.answers = d.answers.filter((id) => openFindings().some((f) => f.id === id && f.owner === d.agentType))
  // A finding handed back to the writer that left it unanswered is re-sent once, with that named in its
  // task; still unanswered after that, it is not sent a third time and stays open for the decider.
  const stuck = []
  for (const d of out) {
    const repeated = d.answers.filter((id) => asked.has(id) && asked.get(id).agentType === d.agentType && asked.get(id).clarified)
    if (repeated.length) {
      stuck.push(`${d.agentType}: ${repeated.join(', ')}`)
      d.answers = d.answers.filter((id) => !repeated.includes(id))
    }
    const again = d.answers.filter((id) => asked.has(id) && asked.get(id).agentType === d.agentType)
    if (!again.length) continue
    const prev = Math.max(...again.map((id) => asked.get(id).round))
    const result = silentLast.includes(d.agentType) ? 'never came back' : 'answered none of them'
    d.task = `${d.task}\nROUND ${prev} HANDED YOU finding(s) ${again.join(', ')}, and your result ${result}. Answer each one in \`answers\` this round, as \`fixed\` or \`disputed\`.`
    d.clarified = again
    retries.push({ step: `round${n}:${d.agentType}`, findings: again, whatChanged: `round ${n} tells ${d.agentType} that its round ${prev} result ${result} for finding(s) ${again.join(', ')}` })
  }
  return { dispatches: out, rejected: bad, stuck }
}

/** The result saved for a dispatch that returned nothing twice: it states nothing, so its round finishes without it. */
function noResult(d) {
  const summary = `NO RESULT: ${d.agentType} returned no result twice; the round went on without it`
  return WRITER_ROLES.includes(d.role)
    ? { files: [], claims: [], answers: [], businessConflicts: [], coverage: [], summary }
    : { findings: [], coverageChecks: [], resolutions: [], summary }
}
/** Saves the no-result of a dispatch to its result file; returns whether it was saved. */
async function recordNoResult(n, d) {
  const saved = await relayKit.ensureJson(run, { label: `round${n}:no-result:${d.agentType}`, phase: 'Rounds', runner: RELAY_RUNNER, file: d.file, value: noResult(d) })
  log(saved.ok
    ? `round${n}: ${d.agentType} returned no result twice; recorded as no result in ${d.file} and the round goes on without it`
    : `round${n}: ${d.agentType} returned no result twice, and its no-result could not be saved: ${saved.error}`)
  return saved.ok
}

/**
 * Runs writers in plan order, accepting each result before the next, then reviewers together. A
 * dispatch with no accepted result is sent once more; with none again it is recorded as no result
 * and later writers and reviewers still run. The ledger is folded again from the saved results
 * after the writers, so the reviewers read this round's claims, and after the reviewers. Returns
 * { silent } (the dispatches whose result is not saved: an interrupted run) or { error } when the
 * saved results could not be read.
 */
async function runRound(n, dispatches) {
  const writing = dispatches.filter((d) => WRITER_ROLES.includes(d.role))
  const reviewing = dispatches.filter((d) => REVIEW_ROLES.includes(d.role))
  const held = [...writing, ...reviewing].map((d, i) => ({ ...d, seq: d.seq || i + 1 }))
  let ordered = held.map((d) => ({ ...d, file: resultFile(n, d) }))
  // The writer that runs last in the round, by position in the dispatch order, reconciles the target.
  const writerSeqs = ordered.filter((d) => WRITER_ROLES.includes(d.role)).map((d) => d.seq)
  const lastWriterSeq = writerSeqs.length ? writerSeqs[writerSeqs.length - 1] : null
  // Reviewers read the draft only when the rounds have written one; set after the writers run.
  let reviewsDraft = false
  // A dispatch counts only after its referenced on-disk candidate is validated and recorded.
  const go = (d) => async () => {
    const label = `round${n}:${d.role}:${d.agentType}`
    const candidate = `${WORK}/candidates/${d.file.split('/').pop()}`
    const schema = WRITER_ROLES.includes(d.role) ? WRITER_SCHEMA : REVIEW_SCHEMA
    const reviewing = REVIEW_ROLES.includes(d.role)
    const scopedReview = reviewing && hasText(d.reviewInputRevision)
    const revision = await sourceRevision(`${label}:inputs`, 'Rounds', scopedReview ? [prd.path, MODEL, MENU, CONSTRAINTS] : [prd.path, SURVEY_JSON, ...(reviewing && reviewsDraft ? [DRAFT] : [])], scopedReview ? { round: n, agentType: d.agentType, assignedEvidence: d.reviewInputRevision, schema } : { round: n, assignment: d, schema })
    if (!revision) return null
    const prior = await probeArtifact(label, 'Rounds', candidate, d.file, schema, revision, '', REVIEW_ROLES.includes(d.role) ? d.agentType : '')
    if (!prior) return null
    const got = prior.pending ? await run(dispatchPrompt(n, d, candidate, revision, prior.research, reviewing && reviewsDraft, WRITER_ROLES.includes(d.role) && d.seq === lastWriterSeq), {
      label,
      phase: 'Rounds',
      agentType: dispatchName(d.agentType),
      architectureBaseline: true,
      effort: d.role === 'proposer' ? 'high' : 'medium',
      schema: ARTIFACT_RETURN_SCHEMA,
    }) : prior
    return await acceptArtifact(label, 'Rounds', candidate, d.file, schema, got, revision)
  }
  const results = new Map()
  /** Runs one dispatch, and once more when it has no accepted result. */
  const twice = async (d) => {
    const got = await go(d)()
    if (got || dispatchInterruption) return got
    log(`round${n}: ${d.agentType} has no accepted result; sending it once more`)
    return go(d)()
  }
  let writersAttempted = false
  for (const d of ordered.filter((d) => WRITER_ROLES.includes(d.role) && !d.complete)) {
    writersAttempted = true
    const got = await twice(d)
    results.set(d.seq, got)
    if (dispatchInterruption) return { silent: [d.agentType] }
    if (!got && !(await recordNoResult(n, d))) return { silent: [d.agentType] }
  }
  if (facts.rounds.pendingPlan) ordered = planDispatches(facts.rounds.pendingPlan)
  let reviewers = ordered.filter((d) => REVIEW_ROLES.includes(d.role) && !d.complete)
  if (reviewers.length) {
    if (writersAttempted) {
      const mid = await readFacts(`round${n}:ledger-writers`, 'Rounds')
      if (mid.error) return { error: mid.error, exception: mid.exception }
      facts = mid
      if (mid.rounds.pendingPlan && mid.rounds.pendingPlan.dispatches.some(d => WRITER_ROLES.includes(d.role) && !d.complete)) return { silent: mid.rounds.pendingPlan.dispatches.filter(d => WRITER_ROLES.includes(d.role) && !d.complete).map(d => d.agentType) }
      ordered = mid.rounds.pendingPlan ? planDispatches(mid.rounds.pendingPlan) : ordered
      reviewers = ordered.filter((d) => REVIEW_ROLES.includes(d.role) && !d.complete)
    }
    const target = await reviewTarget(`round${n}:review-target`, 'Rounds')
    if (target.error) {
      log(`round${n}: ${target.error}; reviewers remain undispatched, saved work retained`)
      return { silent: reviewers.map((d) => d.agentType) }
    }
    reviewsDraft = target.draft
    log(`round${n}: reviewers review ${reviewsDraft ? `the draft target ${DRAFT}${target.authored ? '' : ' (the baseline handoff alone: no authored views)'}` : `the existing design in ${ARC42} (the draft could not be written)`}`)
    const got = await parallel(reviewers.map((d) => () => twice(d)))
    reviewers.forEach((d, i) => results.set(d.seq, got[i]))
    if (!dispatchInterruption) for (const [i, d] of reviewers.entries()) if (!got[i]) await recordNoResult(n, d)
  }
  const after = await readFacts(`round${n}:ledger`, 'Rounds')
  if (after.error) return { error: after.error, exception: after.exception }
  facts = after
  if (facts.rounds.pendingPlan) return { silent: planDispatches(facts.rounds.pendingPlan).filter((d) => !d.complete).map((d) => d.agentType) }
  const savedKeys = listed(facts.rounds.saved)
  const unsaved = ordered.filter((d) => results.get(d.seq) && !savedKeys.includes(`r${n}-${d.seq}`))
  if (unsaved.length) log(`Round ${n}: ${unsaved.map((d) => d.agentType).join(', ')} returned a result but did not save it to its result file; it counts as no result`)
  return { silent: ordered.filter((d) => !savedKeys.includes(`r${n}-${d.seq}`)).map((d) => d.agentType) }
}

/** Runs the decider over the artifacts; returns its decision or null. */
async function decide(n, correction = '', notes = []) {
  phase('Decide')
  const target = await reviewTarget(`decide:round${n}:target`, 'Decide')
  if (target.error) { log(`decide:round${n}: ${target.error}`); return null }
  const decisionRevision = await sourceRevision(`decide:round${n}:inputs`, 'Decide', [...(target.draft ? [DRAFT] : []), LEDGER_JSON, SURVEY_JSON, prd.path], { round: n, correction, schema: DECISION_SCHEMA })
  if (!decisionRevision) return null
  const candidate = `${WORK}/candidates/${decisionRevision}.json`
  const prior = await probeArtifact(`decide:round${n}`, 'Decide', candidate, DECISION_JSON, DECISION_SCHEMA, decisionRevision)
  if (!prior) return null
  const dec = prior.pending ? await run(
    `You are the architecture-decider. Decide whether the target below is approved. You produced none of it, and you decide from the artifacts alone: read them.
${correction}

ARTIFACTS:
- the PRD: ${hasText(prd.path) ? prd.path : '(inline — see the survey)'}
- the survey: ${SURVEY_MD} and ${SURVEY_JSON}
- every result of every round: the files in ${ROUNDS_DIR}, and the claim and finding ledger folded from them: ${LEDGER_JSON}
- the target and its delta: ${reviewedDesign(target.draft)}
- the effective version, with the owner's constraints in section 2: ${ARC42}; open targets: ${archPath}/target/

${PRD_RULE}

${COVERAGE_RULE}

${DESIGN_REVIEW_STANDARD}
Read \`repairRequests\` in ${LEDGER_JSON}, including prior answers and independent checks. Do not reissue resolved repairs from an older decision; a new defect must identify current evidence and the concrete remaining violation.
Read all coverage rows and independent checks in ${LEDGER_JSON}; check completeness against the MODEL, not only existing catalog hits. Approve from the evidence for each relevant obligation, never from an aggregate boolean.
${notes.length ? `\nWHAT THE TEAM'S WORK STILL HAS OPEN, as the ledger records it (weigh each; none of it decides for you):\n${notes.map((g) => `- ${g}`).join('\n')}\n` : ''}

The team has designed, challenged and settled this target in its rounds, led by the coordinator. You are not its lead: you approve its result, and you choose only where the team left competing solutions it could not settle.

CHECK THAT THE DUE DILIGENCE IS PRESENT, item by item in \`diligence\`: every claim reviewed with evidence and every finding answered; the target shows every changed element at every scope where the effective version shows it; the delta shows the change alone (an entirely new architecture has its target views as its delta, and no architecture change has one set and no delta, as the note in \`baseline.json\` says); the owner's constraints in section 2 are honoured; the open targets that show the same elements were read and are not contradicted; a departure from an established pattern states its reason and evidence.

COMPETING SOLUTIONS: where findings stand disputed, or a reviewer's alternative was argued with evidence and not adopted, choose between them in \`choices\`: what was in dispute, the option you chose, and why, from the evidence in the artifacts and the product's priorities (the seeker's privacy and data protection first). A choice is part of an approval, not a reason to escalate.

VERDICT:
- \`approve\` when the diligence is present, with every choice you made in \`choices\`.
- \`return\` when evidence, validation or design work is missing: name each responsible specialist in \`returnTo\` (one of ${Object.values(ROSTER).flatMap((roles) => Object.keys(roles)).join(', ')}) with exactly what is missing. A technical value the PRD leaves open is not missing diligence when the team chose it with a reason.
- \`owner-concern\` is the last resort, for two cases only, each in \`ownerConcerns\` with its evidence: kind \`business-conflict\`, two BUSINESS requirements of the PRD that no design whatsoever could satisfy together, shown by the team's own analysis; or kind \`architecture-conflict\`, owner's constraints in section 2 that contradict each other or that no design can meet together with the PRD. Never escalate a "how" in the PRD, an open technical value, effective views that contradict each other, a security, privacy, cost or best-practice question, or a difference from the effective version: the team decides those as technical gaps.
Set \`round\` to ${n}.

Write ${DECISION_MD} as the readable decision; recipients read it by path.${artifactBrief(candidate, DECISION_SCHEMA, decisionRevision)}`,
    { label: `decide:round${n}`, phase: 'Decide', agentType: 'architecture-decider', effort: 'high', schema: ARTIFACT_RETURN_SCHEMA }
  ) : prior
  if (!(await acceptArtifact(`decide:round${n}`, 'Decide', candidate, DECISION_JSON, DECISION_SCHEMA, dec, decisionRevision))) return null
  if ((await recordFiles('decide:record', 'Decide', [DECISION_MD])).length) { log('decision provenance recording failed; saved work retained'); return null }
  const accepted = await readFacts(`decide:accepted-${n}`, 'Decide')
  if (accepted.error) { log(accepted.error); return null }
  return { decision: accepted.decision, facts: accepted }
}

phase('Check')
log(checkOnly()
  ? `Check: the effective architecture and the code serve every capability; ${CHECK_REVIEWER} verifies the coverage rows and the decider rules, with no design authoring`
  : `Check: design scope ${designScope().join(', ') || '(none)'}${facts.baseline && facts.baseline.valid === true ? '' : "; the survey's assessment is invalid, so the coordinator routes the rounds"}`)

phase('Rounds')
let staleDecisionCorrection = ''
let staleDecisionCorrected = false
let ready = !!(savedDecision && savedDecision.verdict === 'approve') || facts.rounds.readyForDecision === true
let rechecked = false
/** The round after which the decider last ruled. */
let decidedRound = -1
while (!decision) {
  // A finding on a review-only Check means the survey judged the effective architecture complete and the
  // review disagrees: the survey reassesses once, and the capabilities it then marks enter design scope.
  if (!rechecked && lastRound >= 1 && checkOnly() && openFindings().length) {
    rechecked = true
    phase('Survey')
    log(`Check: ${openFindings().length} open finding(s) on a review-only target; the survey reassesses the capabilities they concern`)
    const resurveyed = await runSurvey(true)
    if (resurveyed.failure) return { ...resurveyed.failure, subject }
    const renamed = resurveyed.survey && hasText(resurveyed.survey.subject) && !hasText(a.subject) && resurveyed.survey.subject.trim() !== subjectName
    if (renamed) log(`Check: the reassessed survey names the subject ${resurveyed.survey.subject.trim()}; the step keeps ${subjectName} (target/${subject}/)`)
    log(`Check: ${checkOnly() ? 'the reassessed survey still finds no design or documentation work; the findings go to the rounds' : `design scope ${designScope().join(', ')}`}`)
    phase('Rounds')
    pendingGaps = []
    ready = false
  }
  if (ready) {
    pendingGaps = decisionNotes()
    decidedRound = lastRound
    {
      const decided = await decide(lastRound, staleDecisionCorrection, pendingGaps)
      if (!decided || !decided.decision) return { ok: false, stage: 'decide', reason: 'the architecture-decider returned nothing', ...died('Decide'), subject, ...surveyPaths }
      const dec = decided.decision
      const concernCount = Array.isArray(dec.ownerConcerns) ? dec.ownerConcerns.filter((c) => c && hasText(c.concern)).length : Number(dec.ownerConcerns) || 0
      if (dec.verdict === 'owner-concern' || concernCount) {
        if (concernCount && businessOnly(dec)) return ownerConcern(dec)
        teamNotes = true
        log(concernCount ? `Decide: ${concernCount} issue(s) escalated that the team decides itself; they go back to the team` : 'Decide: the decider raised an owner concern and named none; the target goes back to the team')
        phase('Rounds')
        ready = false
        continue
      }
      facts = decided.facts
      if (dec.verdict === 'approve') {
        decision = dec
        break
      }
      forced = returnedTo(facts.decision || {})
      if (!forced.length && !repairsPending(facts)) {
        if (staleDecisionCorrected) {
          log(`Decide: the decider repeated a return with no unresolved repair (${JSON.stringify(dec.returnTo || [])}); the current target is taken as approved`)
          decision = { ...dec, verdict: 'approve' }
          break
        }
        staleDecisionCorrected = true
        staleDecisionCorrection = `YOUR LAST RETURN WAS NOT ACTIONABLE (${JSON.stringify(dec.returnTo || [])}): the saved ledger has no unresolved repair request. Read repairRequests, their answers and independent current-revision checks in ${LEDGER_JSON}. Do not repeat a resolved request. Decide again from the current artifacts: approve when the existing acceptance requirements are met, or identify a concrete new defect with current evidence. Nothing has been sent back to a writer.`
        retries.push({ step: `decide:round${lastRound}`, whatChanged: 'the decision was told its return contained no unresolved repair and directed to the saved independent resolution evidence' })
        log(`Decide: stale return suppressed; asking the decider once to consider saved resolution evidence`)
        continue
      }
      log(`Decide: ${forced.length ? `returned to ${forced.map((f) => f.agentType).join(', ')}` : 'answered repairs require independent verification; no writer redispatch'}`)
      phase('Rounds')
    }
    ready = false
  }
  // At the round limit the decider rules on the target as the team left it; past it, each return
  // gets one round and the decider rules again, up to twice the limit.
  if (!facts.rounds.pendingPlan && !facts.rounds.resumeRound && lastRound >= roundLimit) {
    if (decidedRound !== lastRound) {
      log(`Rounds: ${lastRound} round(s) ran, the limit is ${roundLimit}; the decider rules on the target as the team left it`)
      ready = true
      continue
    }
    if (lastRound >= 2 * roundLimit) {
      const why = `the architecture-decider returned the target after each of the ${lastRound - roundLimit} round(s) run past the limit of ${roundLimit}; its last return is in ${DECISION_JSON}`
      log(`Rounds: ${why}`)
      return { ok: false, stage: 'rounds', reason: why, error: why, subject, ...surveyPaths }
    }
  }
  const pendingPlan = facts.rounds.pendingPlan
  let n = pendingPlan ? pendingPlan.round : (facts.rounds.resumeRound || lastRound + 1)
  if (!pendingGaps.length && n > 1) pendingGaps = decisionNotes()
  const coordinatorBrief = `You are the architecture-decision-workflow-coordinator. Name the dispatches for round ${n} of at most ${roundLimit}; the script runs them. You read and route; you design, review and decide nothing, write only your assigned plan/checkpoint artifacts, and dispatch nothing yourself.

PRD: ${prdRef}
THE SURVEY: ${SURVEY_MD} and ${SURVEY_JSON}. The target's subject is ${subjectName}; its folder is \`target/${subject}/\`.
THE DRAFT TARGET: ${DRAFT} (arc42 section layout; \`delta/\` holds the change alone).
THE SURVEY'S ASSESSMENT (per-capability actions): ${JSON.stringify(facts.baseline)}
EARLIER RESULTS: ${ROUNDS_DIR}.
THE ARCHITECTURE: ${archPath} (\`arc42/\` effective; \`target/\` open targets).${designScope().length ? `\nDESIGN SCOPE: capabilities ${designScope().map((c) => `${c}${scopeRequirements(c).length ? ` (${scopeRequirements(c).join(', ')})` : ''}`).join('; ')}` : ''}

THE ROSTER (role: agent — what it covers):
${rosterText}

THE LEDGER is ${LEDGER_JSON}: every claim with its reviewer verdicts, and every finding with its owner and answer, folded from the saved results. Read it. So far: ${ledgerLine()}.

WHAT THE TEAM'S WORK STILL HAS OPEN (route what needs work; the decider reads the same list):
${pendingGaps.length ? pendingGaps.map((g) => `- ${g}`).join('\n') : "- inspect the survey's current assessment and coverage facts"}
${teamNotes ? `\nISSUES FOR THE TEAM TO RESOLVE IN ITS DESIGN were raised at the decision: they are the \`ownerConcerns\` in ${DECISION_JSON} (readable in ${DECISION_MD}). Read them and route each to the writers it concerns, and to reviewers.\n` : ''}${forced.length ? `\nTHE ARCHITECTURE-DECIDER RETURNED THE TARGET to: ${forced.map((f) => f.agentType).join(', ')}; what each is missing is in \`returnTo\` of ${DECISION_JSON}. Select the specialists needed for the named missing diligence; preserve completed work.` : ''}${rejected.length ? `\nDISPATCHES REFUSED LAST ROUND: ${rejected.join('; ')}` : ''}${silentLast.length ? `\nDISPATCHES THAT RETURNED NOTHING LAST ROUND: ${silentLast.join(', ')}` : ''}

${PRD_RULE}

${COVERAGE_RULE}

${DESIGN_REVIEW_STANDARD}
Set each dispatch's coverageIds to its applicable ledger row IDs; name its coverage question in task. Writers run in the order you list them, and the last one listed folds the other writers' contributions into its views and finds cross-view repairs, so list writers in the order they should run, with the integrating writer last. Coverage notes in the ledger are work to route, including absent views; do not restart unrelated completed design.

YOU LEAD THE TEAM to a consensus architecture. The architecture-decider is not part of the rounds: it sees the result only after the team has designed, challenged and settled it.

HOW TO ROUTE:
- You are the architecture lead and coordinate only; do not author design. Assess the PRD, existing code, effective architecture and relevant in-progress targets before selecting the proposer(s) needed. There is no fixed proposer count or retained lead author. For each dispatch provide selectionReason naming the applicable requirement, evidence or unresolved concern and why that specialist is needed; do not dispatch the entire roster by default. Reuse valid prior work. Distinguish unchanged architecture from missing implementation: the survey's assessment keeps design, documentation and implementation work separate.
- Keep design, review and approval separate. Diagram authors depict settled design; reviewers critique without authoring proposals. Preserve valid existing specialist results and assign only the remaining work.
- The survey's assessment is above. Select only reviewers applicable to its actual obligations and current claims, explaining the evidence/coverage scope in selectionReason. No fixed reviewer roster or discipline quota applies.
- When a competing alternative is proposed or a writer disputes a finding, route it back to the writers concerned so the team converges on one design; leave two designs standing only when the team has argued both with evidence and still disagrees.
- Give each writer dispatch the draft files it owns this round, relative to the draft folder; two writers in one round never own the same file.
- Order writers so required input decisions exist before their consumers run. Writers execute in this order, and a rejected result stops subsequent dispatches. Do not require a writer to verify a later writer's unwritten output before completing its own assignment; route that cross-view reconciliation after the necessary outputs exist, retaining their accepted work.
- Give reviewers claimIds for existing claims and claimFiles for exact draft-relative files whose NEW/revised claims they will check after writers finish. Match file responsibility to reviewer expertise. Assigning the same claimId or claimFile to two or more reviewers is an overlap, and an overlap is one decision you make: state it once in \`overlaps\`, as one entry naming the shared \`files\` and \`claimIds\`, the reviewer \`agentTypes\` that share them, and the one \`reason\`. The reviewers' dispatches carry no reason. An overlap no entry names is logged as a warning; return \`overlaps: []\` when no two reviewers share anything. Unmatched claims remain gaps for the next normal round; no assignment-only agent pass. A reviewer without a relevant claim, coverage obligation or repair is unnecessary.
- Every claim gets a reviewer verdict: dispatch reviewers for the claims not yet reviewed, and a cost reviewer for claims about cost.
- Route open \`repairRequests\` to the appropriate selected writer using repairIds, and answered repairs to an independent reviewer. Include their IDs in the bounded task. Do not redispatch resolved repairs merely because an older decision still names them.
- For answered findings, route independent resolution; do not send an unchanged accepted claim back to its maker. If a resolution rejects an answer, the next brief names the specific remaining defect and evidence from the ledger.
- Every unanswered open finding is answered by its owner: put its id in that writer's \`answers\`. A finding with no owner is yours to assign to a writer. Reassign an outstanding finding explicitly through its selected writer's answers when its concern requires a different specialist; preserve accepted answers.
- Dispatch diagram authors to draw the views the proposers describe, once the design is written.
- Writers work on the capabilities in DESIGN SCOPE, and each writer's task names the capabilities it covers; every other capability gets review only.
- While DESIGN SCOPE names work no writer has authored yet, the round dispatches the writers that author those views first: reviewers review authored work. A plan with no writer then gets one added by the script for each capability with that work.
- Writers run first and reviewers after them in the same round, so a reviewer sees this round's writing.
- Set \`readyForDecision\` true, with no dispatches, when the team has designed, challenged and settled the target; what the list above still names goes to the decider with it.`
  const checking = !pendingPlan && n === 1 && checkOnly()
  if (checking) log(`Round ${n}: Check plan — ${CHECK_REVIEWER} verifies every coverage row; no coordinator`)
  let plan = checking ? checkPlan() : pendingPlan
  if (!pendingPlan && !checking) {
    const planCandidate = `${WORK}/candidates/round${n}-plan-0.json`
    const planFile = `${WORK}/plans/round${n}-plan-0.json`
    const planLabel = `round${n}:coordinate`
    const planRevision = await sourceRevision(`${planLabel}:inputs`, 'Rounds', [LEDGER_JSON, SURVEY_JSON, prd.path], { round: n, schema: COORDINATOR_SCHEMA })
    if (!planRevision) return { ok: false, stage: 'round-plan-inputs', ...died('Rounds') }
    const planPrior = await probeArtifact(planLabel, 'Rounds', planCandidate, planFile, COORDINATOR_SCHEMA, planRevision, 'coordinator')
    if (!planPrior) return { ok: false, stage: 'round-plan', ...died('Rounds') }
    const reference = planPrior.pending ? await run(`${coordinatorBrief}${artifactBrief(planCandidate, COORDINATOR_SCHEMA, planRevision)}`, { label: planLabel, phase: 'Rounds', agentType: 'architecture-decision-workflow-coordinator', effort: 'medium', schema: ARTIFACT_RETURN_SCHEMA }) : planPrior
    const acceptedPlan = await acceptArtifact(planLabel, 'Rounds', planCandidate, planFile, COORDINATOR_SCHEMA, reference, planRevision, 'coordinator')
    plan = acceptedPlan && acceptedPlan.facts ? withWriters(acceptedPlan.facts) : null
  }
  if (!plan) return { ok: false, stage: 'rounds', reason: `the coordinator returned no plan for round ${n}`, ...died('Rounds'), subject, ...surveyPaths }
  const settled = pendingPlan ? { dispatches: planDispatches(pendingPlan), rejected: [], stuck: [] } : settleDispatches(plan, n)
  rejected = settled.rejected
  forced = []
  teamNotes = false
  if (rejected.length) log(`Round ${n}: refused ${rejected.join('; ')}`)
  if (settled.stuck.length) log(`Round ${n}: finding(s) stayed unanswered after their owner was told once; they stay open for the decider: ${settled.stuck.join('; ')}`)
  for (const r of retries.filter((x) => x.step.startsWith(`round${n}:`))) log(`Round ${n}: re-dispatch — ${r.whatChanged}`)
  if (!pendingPlan) {
    const orderedPlan = { round: n, readyForDecision: plan.readyForDecision, overlaps: planOverlaps(plan), dispatches: [...settled.dispatches.filter(d => WRITER_ROLES.includes(d.role)), ...settled.dispatches.filter(d => REVIEW_ROLES.includes(d.role))] }
    const savedPlan = await readFacts(`round${n}:save-plan`, 'Rounds', orderedPlan)
    if (savedPlan.error) return { ok: false, stage: 'rounds', reason: savedPlan.error, subject }
    facts = savedPlan
    const saved = savedPlan.rounds.pendingPlan
    if (saved && hasText(savedPlan.rounds.planKept)) {
      // A saved plan stands, and the new one is set aside: run what is pending of it.
      plan = { ...plan, readyForDecision: saved.readyForDecision }
      n = saved.round
    }
    settled.dispatches = saved ? planDispatches(saved) : orderedPlan.dispatches
  }
  if (!settled.dispatches.some((d) => !d.complete)) {
    if (plan.readyForDecision !== true) log(`Round ${n}: the coordinator dispatched nothing and did not declare the target ready (${plan.reason || 'no reason given'}); the decider rules`)
    lastRound = n
    ready = true
    continue
  }
  log(`Round ${n}: ${settled.dispatches.map((d) => `${d.role}:${d.agentType}`).join(', ')}`)
  for (const d of settled.dispatches) for (const id of listed(d.answers)) asked.set(id, { agentType: d.agentType, round: n, clarified: (d.clarified || []).includes(id) })
  const roundRun = await runRound(n, settled.dispatches)
  if (roundRun.error) {
    const why = `depscore.py arch-resume failed after round ${n}: ${roundRun.error}. The saved results in ${ROUNDS_DIR} could not be read; the step stops, and the saved results stay on disk for the next attempt.`
    log(`Round ${n}: ${why}`)
    return { ok: false, stage: 'rounds', headline: roundRun.exception ? `Architecture round ${n} failed: ${roundRun.exception}` : `Architecture could not read the saved results of round ${n}: ${roundRun.error}`, reason: why, error: why, subject, ...surveyPaths }
  }
  const silent = roundRun.silent
  silentLast = silent
  if (silent.length) return { ok: false, resumable: true, stage: 'rounds', reason: `round ${n} has unfinished dispatches: ${silent.join(', ')}; saved work retained`, ...died('Rounds'), subject, ...surveyPaths }
  lastRound = n
  pendingGaps = []
  ready = plan.readyForDecision === true || lastRound > roundLimit
}
const guardRounds = await constraintsGuard(before, 'constraints:after-rounds', 'Rounds')
if (guardRounds) return { ...guardRounds, subject }
const treeRounds = await treeSnapshot('tree:after-rounds', 'Rounds', { against: [TREE_START] })
if (!treeRounds || treeRounds.error) log(`Rounds: the architecture could not be fingerprinted after the rounds: ${(treeRounds && treeRounds.error) || 'no result'}`)
else if (diffCount(treeRounds, 0)) log(`Rounds: ${diffCount(treeRounds, 0)} file(s) changed in the architecture at ${archPath} during the rounds (listed under result.diffs in ${treeRounds.relayFile}); another Epic's work, or a session that wrote outside ${WORK}`)

// ---------------------------------------------------------------- Closure
const CLOSURE_ROOTS = `${WORK}/closure-roots.json`
const CLOSURE_DEPLOYMENTS = `${WORK}/closure-deployments.json`
const CLOSURE_JSON = `${WORK}/closure.json`
const DEPLOYMENTS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['repositories', 'summary'],
  properties: {
    repositories: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['name', 'path', 'lifecycle', 'deploys'],
        properties: {
          name: { type: 'string' },
          path: { type: 'string' },
          lifecycle: { type: 'string' },
          deploys: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              required: ['element', 'kind', 'evidence'],
              properties: { element: { type: 'string' }, kind: { type: 'string' }, evidence: { type: 'string' } },
            },
          },
        },
      },
    },
    summary: { type: 'string' },
  },
}
const CLOSURE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['prerequisites', 'rootEdges', 'satisfied', 'summary'],
  properties: {
    prerequisites: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['element', 'state', 'views', 'requiredBy', 'requires', 'evidence', 'deployedBy', 'plannedBy', 'repository', 'reason'],
        properties: {
          element: { type: 'string' },
          state: { type: 'string', enum: ['absent', 'stale', 'planned'] },
          views: { type: 'array', items: { type: 'string' } },
          requiredBy: { type: 'array', items: { type: 'string' } },
          requires: { type: 'array', items: { type: 'string' } },
          evidence: { type: 'array', items: { type: 'string' } },
          deployedBy: { type: ['string', 'null'] },
          plannedBy: { type: ['string', 'null'] },
          repository: {
            anyOf: [
              { type: 'null' },
              { type: 'object', additionalProperties: false, required: ['name', 'template', 'reason'], properties: { name: { type: 'string' }, template: { type: 'string' }, reason: { type: 'string' } } },
            ],
          },
          reason: { type: 'string' },
        },
      },
    },
    rootEdges: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['item', 'requires', 'evidence'],
        properties: { item: { type: 'string' }, requires: { type: 'array', items: { type: 'string' } }, evidence: { type: 'string' } },
      },
    },
    satisfied: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['element', 'deployedBy', 'evidence'],
        properties: { element: { type: 'string' }, deployedBy: { type: ['string', 'null'] }, evidence: { type: 'array', items: { type: 'string' } } },
      },
    },
    summary: { type: 'string' },
  },
}
/**
 * The Closure phase: walks from every build root (the delta's elements, the authored views of an
 * entirely new architecture, and the future set's implementation gaps) to the elements its work
 * rests on, and writes each one that is not built and current to target/<subject>/closure.json, which
 * depscore.py arch-delta merges as prerequisite items. Never skipped. Returns { closure } with
 * its counts, or { failure } with the result that stops the step.
 */
async function runClosure(targetDir, deltaDir) {
  phase('Closure')
  const stop = (why) => ({ failure: { ok: false, stage: 'closure', reason: why, error: why, subject, targetDir, deltaDir, ...died('Closure') } })
  const roots = await depscore('closure:roots', 'Closure', `arch-delta --delta-dir ${shq(deltaDir)} --roots-only --save ${shq(CLOSURE_ROOTS)}`)
  if (!roots || roots.error) return stop(`depscore.py arch-delta did not list the delta at ${deltaDir}: ${(roots && roots.error) || 'no result'}`)
  if (roots.ok !== true) log(`Closure: depscore.py arch-delta lists the delta with refusals, carried on: ${listed(roots.refusals).join('; ')}`)
  const depRevision = await sourceRevision('closure:deployments-inputs', 'Closure', [CLOSURE_ROOTS], { schema: DEPLOYMENTS_SCHEMA })
  if (!depRevision) return stop('the inputs of the deployment inventory could not be bound')
  const depCandidate = `${WORK}/candidates/closure-deployments.json`
  const depPrior = await probeArtifact('closure:deployments', 'Closure', depCandidate, CLOSURE_DEPLOYMENTS, DEPLOYMENTS_SCHEMA, depRevision)
  if (!depPrior) return stop('the saved deployment inventory could not be checked')
  const deployments = depPrior.pending ? await run(
    `For every repository of this project, list what its code on \`main\` deploys or publishes: each AWS resource and shared platform element (a CDK stack or construct, a database, network, event bus, queue, user pool, API, an SSM parameter it writes, a package it publishes), named as the architecture at ${ARC42} names it where you can tell, each with the file:line on \`main\` that deploys it. A repository that deploys nothing has an empty list. Answer from your records and the live repositories; change nothing.${artifactBrief(depCandidate, DEPLOYMENTS_SCHEMA, depRevision)}`,
    { label: 'closure:deployments', phase: 'Closure', agentType: 'agent-teams-workforce:polyrepo-steward', effort: 'medium', schema: ARTIFACT_RETURN_SCHEMA }
  ) : depPrior
  if (!(await acceptArtifact('closure:deployments', 'Closure', depCandidate, CLOSURE_DEPLOYMENTS, DEPLOYMENTS_SCHEMA, deployments, depRevision))) return stop(`the deployment inventory could not be saved to ${CLOSURE_DEPLOYMENTS}`)
  const revision = await sourceRevision('closure:inputs', 'Closure', [CLOSURE_ROOTS, CLOSURE_DEPLOYMENTS, ARC42, prd.path], { schema: CLOSURE_SCHEMA })
  if (!revision) return stop('the inputs of the closure could not be bound')
  const walk = async (rev, refusalsFile) => {
    const candidate = `${WORK}/candidates/closure-${rev}.json`
    const prior = await probeArtifact('closure:walk', 'Closure', candidate, CLOSURE_JSON, CLOSURE_SCHEMA, rev)
    if (!prior) return null
    const got = prior.pending ? await run(
      `You are the prd-reality-reconciler in CLOSURE mode (your charter's "The prerequisite closure" section).${refusalsFile ? ` depscore.py arch-closure refused your previous closure; its refusals are \`result.refusals\` in ${refusalsFile}. Correct each one.` : ''}

PRD: ${prdRef}

${ARCH_WHERE}

THE ROOTS are the \`items\` of ${CLOSURE_ROOTS}: the build roots of this PRD's approved target ${targetDir} (its \`architectureChange\` and \`note\` say whether a delta exists), one item per element, with its id: elements the delta (or an entirely new target) shows, and the implementation gaps between the future set and the code on \`main\`.
WHAT EACH REPOSITORY DEPLOYS on \`main\`, from the polyrepo-steward, is ${CLOSURE_DEPLOYMENTS}.
THE OPEN BEADS of every repository and Epic are in the central beads database (${DS.repo}); read them with \`atw-bd\`, read-only.${artifactBrief(candidate, CLOSURE_SCHEMA, rev)}`,
      { label: 'closure:walk', phase: 'Closure', agentType: 'prd-reality-reconciler', effort: 'medium', schema: ARTIFACT_RETURN_SCHEMA }
    ) : prior
    return acceptArtifact('closure:walk', 'Closure', candidate, CLOSURE_JSON, CLOSURE_SCHEMA, got, rev)
  }
  let checked = null
  for (let pass = 0; pass < 2; pass++) {
    const accepted = await walk(pass ? `${revision}-fix${pass}` : revision, pass ? checked.relayFile : '')
    if (!accepted) return stop(`the closure the prd-reality-reconciler returned could not be saved to ${CLOSURE_JSON}`)
    checked = await depscore(`closure:check-${pass + 1}`, 'Closure', `arch-closure --closure ${shq(CLOSURE_JSON)} --delta-dir ${shq(deltaDir)}`)
    if (!checked || checked.error) return stop(`depscore.py arch-closure did not run: ${(checked && checked.error) || 'no result'}`)
    if (checked.ok === true) break
    log(`Closure: depscore.py arch-closure refused the closure (pass ${pass + 1}): ${listed(checked.refusals).join('; ')}`)
  }
  if (checked.ok !== true) return stop(`depscore.py arch-closure refused the corrected closure: ${listed(checked.refusals).join('; ')}`)
  const count = Array.isArray(checked.prerequisites) ? checked.prerequisites.length : 0
  log(`Closure: ${count} prerequisite(s) not built and current, written to ${checked.closurePath}`)
  return { closure: { path: checked.closurePath, workPath: CLOSURE_JSON, prerequisites: count } }
}

// ---------------------------------------------------------------- Target
phase('Target')
const target = await depscore('target:write', 'Target', `arch-target --draft ${shq(DRAFT)} --baseline ${shq(SURVEY_JSON)} --arch-root ${shq(archPath)} --subject ${shq(subject)} --forbid ${shq(SUBJECT_FORBID)} --out ${shq(TARGET_JSON)}`)
const targetSummary = target && target.summary ? target.summary : null
if (!targetSummary || target.error || targetSummary.ok !== true) {
  const why = targetSummary ? `depscore.py arch-target refused the approved draft: ${listed(targetSummary.refusals).join('; ') || 'no reason given'}` : `depscore.py arch-target did not run: ${(target && target.error) || 'no result'}`
  return { ok: false, stage: 'target', reason: why, error: why, decision, subject, ...died('Target') }
}
const targetDir = targetSummary.targetDir
const deltaDir = targetSummary.deltaDir
const architectureChange = hasText(targetSummary.architectureChange) ? targetSummary.architectureChange : 'partial'
/** The delta folder when the target has one: a partial change. With none or an entirely new architecture there is no delta folder. */
const deltaFolder = architectureChange === 'partial' ? deltaDir : ''
log(`Target: ${targetSummary.files} file(s) at ${targetDir}; architecture change ${architectureChange}${deltaFolder ? `, ${targetSummary.deltaFiles} in its delta` : ', no delta folder'}`)

// Approved existing views need only lifecycle publication; no author or maintainer is
// dispatched when the validated assessment contains no design/documentation change and no
// writer wrote the draft; a written draft is integrated like any other target.
if (targetSummary.designChanged === false && targetSummary.documentationChanged === false && targetSummary.draftWritten !== true) {
  phase('Integrate')
  await markRevision('integrating', 'Integrate')
  const approvalFiles = listed(targetSummary.approvalFiles)
  const publicationFreshness = await surveyFreshness('baseline:publication-freshness')
  if (!publicationFreshness || publicationFreshness.current !== true) log("Integrate: the survey's sources changed since the decision; the approved existing views are published as approved")
  let approval = null
  let vaultCommit = null
  if (approvalFiles.length) {
    approval = await depscore('baseline:approve', 'Integrate', `arch-approve --arch-files ${shq(approvalFiles.join(','))} --reviewed-files ${shq(approvalFiles.join(','))} --arch-root ${shq(ARC42)}`)
    const counts = approval && approval.summary
    if (!approval || approval.error || !counts) return { ok: false, stage: 'approve', reason: `depscore.py arch-approve did not run: ${(approval && approval.error) || 'no result'}`, approval, subject, targetDir, deltaDir }
    if (Number(counts.refused) > 0) return { ok: false, stage: 'approve', reason: `depscore.py arch-approve refused ${counts.refused} file(s) in section 2 or outside the architecture (listed under refused in ${approval.relayFile})`, approval, subject, targetDir, deltaDir }
    const left = Number(counts.unreviewed || 0) + Number(counts.failed || 0) + Number(counts.noFrontmatter || 0)
    if (left) log(`Integrate: ${left} approved existing view(s) were not set effective and stay in review (listed in ${approval.relayFile})`)
    vaultCommit = await depscore('baseline:commit', 'Integrate', `arch-commit --arch-root ${shq(ARC42)} --files ${shq(approvalFiles.join(','))} --message ${shq(`docs(architecture): approve existing views for ${subject}`)}`)
    if (!vaultCommit || vaultCommit.error || vaultCommit.ok !== true) return { ok: false, stage: 'commit', reason: 'existing-view approval could not be committed', vaultCommit, approval, subject, targetDir, deltaDir }
  }
  const publication = {
    changedFiles: approvalFiles, createdFiles: [], deletedFiles: [],
    viewsChecked: approvalFiles.map((view) => ({ element: subject, view, action: 'updated' })),
    constraintIssues: [], contradictions: [],
    summary: approvalFiles.length ? 'Independently approved existing views set effective; no design or documentation content change.' : 'Current effective views independently approved as suitable; no architecture publication change.',
  }
  const saved = await relayKit.ensureJson(run, { label: 'baseline:publication', phase: 'Integrate', runner: RELAY_RUNNER, file: UPDATE_JSON, value: publication })
  if (!saved.ok) log(`Integrate: the publication receipt could not be saved to ${UPDATE_JSON}: ${saved.error}`)
  else await recordFiles('baseline:record', 'Integrate', [UPDATE_JSON])
  await markRevision('integrated', 'Integrate')
  const closed = await runClosure(targetDir, deltaDir)
  if (closed.failure) return closed.failure
  return {
    closure: closed.closure,
    ok: true, subject, subjectName, targetDir, deltaDir, targetPath: TARGET_JSON,
    surveyPath: SURVEY_MD, decision, decisionPath: DECISION_MD,
    architectureUpdate: { changedFiles: approvalFiles.length, createdFiles: 0, deletedFiles: 0, constraintIssues: 0, contradictions: 0 },
    conformance: null, approval, vaultCommit, rounds: lastRound, retries, openItems: [],
    noArchitectureChange: true, architectureChange, implementationWork: targetSummary.implementationWork,
    architectureUpdatePath: UPDATE_JSON, ledgerPath: LEDGER_JSON,
  }
}

// ---------------------------------------------------------------- Integrate
phase('Integrate')
await markRevision('integrating', 'Integrate')
const SECTION_2_RULE = `Write nothing under ${CONSTRAINTS}: section 2 holds the owner's constraints, and only the owner changes them; the run fails on any change there. A constraint you believe should change goes in \`constraintIssues\`, with the constraint, the conflicting content and the reason.`
const INTEGRATE_TASK = `Architecture root: ${archPath}\nMODEL: ${MODEL}\nMENU: ${MENU}\n\nIntegrate the approved target at ${targetDir} (${deltaFolder ? `the change alone is in ${deltaFolder}` : 'an entirely new architecture: its target views are also its delta, and there is no delta folder'}) into the effective version, the folder ${ARC42}, as the architecture documentation model's step 5 describes. For each element the delta (or, with no delta folder, the target) adds, changes or removes, find every effective view that shows it through the catalog (\`subject\` and \`shows\`), at every scope, and update or delete each one; add the target's new views in the section folder the model names, named for their subject. Keep every touched view's catalog frontmatter true to what it now shows. Edit in place: no changelog narrative, and no superseded content left beside the new. Leave every \`lifecycle_state\` as you find it: the run sets it after review. Leave ${targetDir} as it is: later phases read it.
${SECTION_2_RULE}
Read approved coverage rows/checks in ${LEDGER_JSON} and approval ${DECISION_JSON}. Apply every approved coverage action, including absent/new views and affected navigation; do not invent unapproved design. For independently excluded unrelated-debt rows record only the unchanged disposition; never repair their absent views. Record each row id in viewsChecked.element with its view/action, using unaffected for justified unchanged/not-applicable rows and view="" for a not-applicable or independently excluded unrelated-debt obligation without an existing path (never invent a view).

The result names every file you changed, created or deleted as an absolute path under ${ARC42}, every view the catalog listed for a changed element and what you did to it, and every contradiction with another effective view or open target.`
const integrationRevision = await sourceRevision('integrate:inputs', 'Integrate', [targetDir, deltaFolder, DECISION_JSON, SURVEY_JSON, prd.path], { schema: MAINTAIN_SCHEMA })
if (!integrationRevision) return { ok: false, stage: 'integrate-inputs', ...died('Integrate') }
const updateCandidate = `${WORK}/candidates/${integrationRevision}.json`
const updateBrief = artifactBrief(updateCandidate, MAINTAIN_SCHEMA, integrationRevision)
/** The integration's file lists, written by depscore.py arch-integration-files; the script holds only their counts. */
const FILES_JSON = `${WORK}/integration-files.json`
/** Facts the saved integration left: its report's counts (the report itself stays in UPDATE_JSON), its fingerprint, its last review. */
const savedFacts = resumedFacts.integration || {}
const savedUpdate = savedFacts.update && typeof savedFacts.update === 'object' ? savedFacts.update : null
const INTEGRATE_BEFORE = `${WORK}/integrate-before.json`
const savedTree = savedFacts.beforeSaved === true
const integrateBefore = savedTree ? { saved: INTEGRATE_BEFORE } : await treeSnapshot('tree:before-integrate', 'Integrate', { save: INTEGRATE_BEFORE })
if (!integrateBefore || integrateBefore.error) {
  const why = `the architecture could not be fingerprinted before the integration: ${(integrateBefore && integrateBefore.error) || 'no result'}`
  return { ok: false, stage: 'integrate', reason: why, error: why, decision, subject, targetDir, deltaDir, ...died('Integrate') }
}
if (savedUpdate && !savedTree) log('Integrate: no fingerprint was saved before the earlier integration pass; its files are taken from its report and this pass is measured')
/** The last saved review's facts: { n, path, conforms, findings: count }. */
const lastSavedReview = savedFacts.lastReview && typeof savedFacts.lastReview === 'object' ? savedFacts.lastReview : null

let integrationCoverageRows = coverageRowsOf(facts)
/** The integration as the script tracks it: counts from arch-integration-files; the lists are in FILES_JSON, the report in UPDATE_JSON. */
let update = null
let reviewPass = lastSavedReview ? Number(lastSavedReview.n) || 0 : 0
const reusedSaved = !!(savedUpdate && lastSavedReview && lastSavedReview.conforms === true)
if (reusedSaved) {
  log('Integrate: reused the saved integration and its conforming review')
} else {
  const prior = await probeArtifact('integrate:maintain', 'Integrate', updateCandidate, UPDATE_JSON, MAINTAIN_SCHEMA, integrationRevision)
  if (!prior) return { ok: false, stage: 'integrate', ...died('Integrate') }
  const report = prior.pending ? await run(
    savedUpdate
      ? `You are the architecture-maintainer, RESUMING an integration a previous session began and did not finish. Its report is ${UPDATE_JSON}; its edits are in the working tree (\`git status --short\` in the repository holding ${archPath}). Do not start over: finish every view the previous pass left inconsistent with the target or with the other views of the same element, then save the complete candidate report for both passes.\n\n${INTEGRATE_TASK}${updateBrief}`
      : `You are the architecture-maintainer.\n\n${INTEGRATE_TASK}${updateBrief}`,
    { label: 'integrate:maintain', phase: 'Integrate', agentType: 'architecture-maintainer', effort: 'medium', schema: ARTIFACT_RETURN_SCHEMA }
  ) : prior
  if (!(await acceptArtifact('integrate:maintain', 'Integrate', updateCandidate, UPDATE_JSON, MAINTAIN_SCHEMA, report, integrationRevision))) {
    const why = `the integration report the architecture-maintainer returned could not be saved to ${UPDATE_JSON}`
    return { ok: false, stage: 'integrate', reason: why, error: why, decision, subject, targetDir, deltaDir }
  }
}

/** What the integration report returns: counts and where the lists are. */
const updateFacts = (f) => ({
  reportPath: UPDATE_JSON,
  filesPath: FILES_JSON,
  touched: Number(f.touched) || 0,
  deleted: Number(f.deleted) || 0,
  unreported: Number(f.unreported) || 0,
  constraintIssues: Number(f.constraintIssues) || 0,
  contradictions: Number(f.contradictions) || 0,
})
/**
 * Measures what the integration wrote since INTEGRATE_BEFORE with depscore.py arch-integration-files,
 * which unions it with the saved report, writes the lists to FILES_JSON and saves the tree to
 * TREE_LAST; with `sinceLast` it also counts the files changed since the previous measurement.
 * Returns { update, changedSinceLast, relayFile } or { failure }.
 */
async function measured(label, sinceLast, accumulate) {
  const now = await depscore(label, 'Integrate', `arch-integration-files --arch-root ${shq(archPath)} --before ${shq(INTEGRATE_BEFORE)} --report ${shq(UPDATE_JSON)} --files-out ${shq(FILES_JSON)} --save-last ${shq(TREE_LAST)}${sinceLast ? ` --last ${shq(TREE_LAST)}` : ''}${accumulate ? ' --accumulate' : ''}`)
  if (!now || now.error) {
    const why = `the architecture could not be measured after the integration: ${(now && now.error) || 'no result'}`
    return { failure: { ok: false, stage: 'integrate', reason: why, error: why, architectureUpdate: update, decision, subject, targetDir, deltaDir, ...died('Integrate') } }
  }
  if (Number(now.unreported) > 0) log(`Integrate: ${now.unreported} file(s) written and not reported, added to the review (listed under unreported in ${FILES_JSON})`)
  return { update: { ...updateFacts(now), section2: Number(now.section2) || 0, outside: Number(now.outside) || 0 }, changedSinceLast: Number(now.changedSinceLast) || 0 }
}
/** Returns the failure when the integration wrote a file in section 2 (section 2 is put back), else null; files changed outside arc42 are logged. */
async function outOfBounds(u) {
  if (u.outside) log(`Integrate: ${u.outside} file(s) changed outside the effective version ${ARC42} since the integration began (listed under outside in ${FILES_JSON}); another Epic's work, or the maintainer writing outside arc42`)
  if (!u.section2) return null
  const guard = await constraintsGuard(before, 'constraints:integrate-bounds', 'Integrate')
  if (guard) return { ...guard, architectureUpdate: u, decision, subject, targetDir, deltaDir }
  const why = `the integration wrote ${u.section2} file(s) in section 2, which holds the owner's constraints (listed under section2 in ${FILES_JSON})`
  return { ok: false, stage: 'integrate', deterministicFailure: true, reason: why, error: why, architectureUpdate: u, decision, subject, targetDir, deltaDir }
}
const firstMeasure = await measured('tree:after-integrate', false, false)
if (firstMeasure.failure) return firstMeasure.failure
update = firstMeasure.update
const bounds = await outOfBounds(update)
if (bounds) return bounds

/** Names where a review's findings are: the review file, and the changed files it did not review. */
const findingsWhere = (c) =>
  `the \`findings\` in ${c.path}${Number(c.missedCount) > 0 ? `, and the ${c.missedCount} file(s) the integration changed or created that the review did not review (listed under result.missed in ${c.checkFile})` : ''}`
/** Runs one conformance review; a changed file the review does not cover is a finding. `again` names the previous review and the number of files the correction changed. */
async function review(again) {
  reviewPass += 1
  const againBlock = again
    ? `\nTHIS IS REVIEW ${reviewPass}. The previous review's findings are ${findingsWhere(again.previous)}; read them. Correction ${again.correction} changed ${again.changed} file(s) to answer them (listed under changedSinceLast in ${FILES_JSON}). Confirm each finding is resolved, and check the changed files as fully as the rest.\n`
    : ''
  const reviewFile = `${WORK}/conformance-${reviewPass}.json`
  const reviewCandidate = `${WORK}/candidates/conformance-${reviewPass}.json`
  const current = await readFacts(`integrate:coverage-${reviewPass}`, 'Integrate')
  if (current.error) { log(`Integrate: ${current.error}`); return null }
  integrationCoverageRows = coverageRowsOf(current)
  const reviewRevision = await sourceRevision(`integrate:review-${reviewPass}:inputs`, 'Integrate', [targetDir, deltaFolder, UPDATE_JSON, FILES_JSON, DECISION_JSON], { reviewPass, again, schema: CONFORMANCE_SCHEMA })
  if (!reviewRevision) return null
  const prior = await probeArtifact(`integrate:review-${reviewPass}`, 'Integrate', reviewCandidate, reviewFile, CONFORMANCE_SCHEMA, reviewRevision)
  if (!prior) return null
  const got = prior.pending ? await run(
    `You are the architecture-conformance-reviewer. Check one integration of an approved target into the effective version; report findings and fix nothing.

THE APPROVED TARGET: ${targetDir} (${deltaFolder ? `the change alone in ${deltaFolder}` : 'an entirely new architecture: its target views are also its delta, with no delta folder'}).
THE INTEGRATION REPORT: ${UPDATE_JSON}. The ${update.touched} file(s) it changed or created, every one of which you review, are the \`touched\` list in ${FILES_JSON}; the ${update.deleted} it deleted are its \`deleted\` list.
${againBlock}
${ARCH_WHERE}

Read approved coverage in ${LEDGER_JSON} and decision ${DECISION_JSON}. Independently check every approved action, including required views absent before integration, honest diagram declarations, readable rendering, cross-scope consistency and navigation. Report unrelated historical debt in summary, not blocking findings. Return coverageChecks for EVERY approved ledger row id, with verdict and evidence naming the integrated view and disposition (including unchanged/not-applicable and independently excluded unrelated-debt, whose missing views must not be repaired). Do not change the design to fill a gap.

Check that the integration applied the approved target exactly, no more and no less; that every effective view the catalog lists for each changed element was updated or deleted, at every scope; that the new views sit in the section folders the model names with catalog frontmatter true to what they show; that no superseded content remains beside the new and no view contradicts another or an open target; and that nothing under ${CONSTRAINTS} changed. Return in \`reviewedFiles\` the absolute path of every file you checked and found conforming, and one finding per problem with its file and evidence; \`conforms\` is true only when there is no finding.${artifactBrief(reviewCandidate, CONFORMANCE_SCHEMA, reviewRevision)}`,
    { label: `integrate:review-${reviewPass}`, phase: 'Integrate', agentType: 'architecture-conformance-reviewer', architectureBaseline: true, effort: 'medium', schema: ARTIFACT_RETURN_SCHEMA }
  ) : prior
  if (!(await acceptArtifact(`integrate:review-${reviewPass}`, 'Integrate', reviewCandidate, reviewFile, CONFORMANCE_SCHEMA, got, reviewRevision))) return null
  return covered({ path: reviewFile })
}
/**
 * Checks a saved review with depscore.py arch-review-check: a changed file it does not cover, or an
 * approved coverage row id without a verified check, is a finding, and the review does not conform.
 * Returns the review with missedCount and checkFile, or null when the check could not run.
 */
async function covered(c) {
  const check = await depscore(`integrate:review-check-${reviewPass}`, 'Integrate', `arch-review-check --review ${shq(c.path)} --files ${shq(FILES_JSON)} --coverage-from ${shq(integrationCoverageRows.file)}`)
  if (!check || check.error) {
    log(`Integrate: the review in ${c.path} could not be checked: ${(check && check.error) || 'no result'}`)
    return null
  }
  const findings = Array.isArray(c.findings) ? [...c.findings] : []
  if (Number(check.coverageUnverified) > 0) findings.push({ file: UPDATE_JSON, finding: `${check.coverageUnverified} approved coverage row(s) lack verified integration evidence (listed under result.coverageUnverified in ${check.relayFile})`, evidence: 'no per-obligation conformance check' })
  if (Number(check.missed) > 0) findings.push({ file: FILES_JSON, finding: `${check.missed} file(s) changed or created by the integration were not reviewed (listed under result.missed in ${check.relayFile})`, evidence: 'absent from reviewedFiles' })
  if (Number(check.findings) > 0 && !Array.isArray(c.findings)) findings.push({ file: c.path, finding: `${check.findings} reviewer finding(s); read the authoritative review artifact`, evidence: 'saved independent review' })
  const conforms = check.conforms === true && Number(check.findings) === 0 && findings.length === 0
  return { ...c, findings, conforms, missedCount: Number(check.missed) || 0, checkFile: check.relayFile }
}

let conformance = lastSavedReview && lastSavedReview.conforms === true && reusedSaved ? await covered({ ...lastSavedReview, findings: [] }) : null
if (!conformance || conformance.conforms !== true) conformance = await review()
if (!conformance) return { ok: false, stage: 'integrate', reason: 'the architecture-conformance-reviewer returned no result, or its review could not be checked', ...died('Integrate'), decision, subject, targetDir, deltaDir, architectureUpdate: update }
let corrections = 0
while (conformance.conforms !== true && corrections < MAX_CORRECTIONS) {
  corrections += 1
  const correctionRevision = `${integrationRevision}-review${reviewPass}`
  const correctionCandidate = `${WORK}/candidates/${correctionRevision}.json`
  const prior = await probeArtifact(`integrate:correct-${corrections}`, 'Integrate', correctionCandidate, UPDATE_JSON, MAINTAIN_SCHEMA, correctionRevision)
  if (!prior) return { ok: false, stage: 'integrate', ...died('Integrate') }
  const fixed = prior.pending ? await run(
    `You are the architecture-maintainer, CORRECTING your integration (correction ${corrections} of ${MAX_CORRECTIONS}). The architecture-conformance-reviewer's findings are ${findingsWhere(conformance)}: read them. Correct each one in place, then save the complete candidate report of the integration, every pass together.

${INTEGRATE_TASK}${artifactBrief(correctionCandidate, MAINTAIN_SCHEMA, correctionRevision)}`,
    { label: `integrate:correct-${corrections}`, phase: 'Integrate', agentType: 'architecture-maintainer', effort: 'medium', schema: ARTIFACT_RETURN_SCHEMA }
  ) : prior
  if (!(await acceptArtifact(`integrate:correct-${corrections}`, 'Integrate', correctionCandidate, UPDATE_JSON, MAINTAIN_SCHEMA, fixed, correctionRevision))) {
    const why = `the corrected integration report could not be saved to ${UPDATE_JSON}`
    return { ok: false, stage: 'integrate', reason: why, error: why, decision, subject, targetDir, deltaDir }
  }
  const fixMeasure = await measured(`tree:after-correct-${corrections}`, true, true)
  if (fixMeasure.failure) return fixMeasure.failure
  update = fixMeasure.update
  const fixedBounds = await outOfBounds(update)
  if (fixedBounds) return fixedBounds
  const changedNow = fixMeasure.changedSinceLast
  if (!changedNow) {
    log(`Integrate: correction ${corrections} changed no file, so a further review would judge the same integration; its findings stand as residuals and the files the review did not find conforming stay in review`)
    break
  }
  const whatChanged = `correction ${corrections} changed ${changedNow} file(s) to answer ${(conformance.findings || []).length} finding(s)`
  retries.push({ step: 'integrate:review', attempt: reviewPass + 1, whatChanged })
  log(`Integrate: review again — ${whatChanged}`)
  conformance = await review({ correction: corrections, changed: changedNow, previous: conformance })
  if (!conformance) return { ok: false, stage: 'integrate', reason: 'the architecture-conformance-reviewer returned no result, or its review could not be checked', ...died('Integrate'), decision, subject, targetDir, deltaDir, architectureUpdate: update }
}
/** The review's findings the integration leaves standing: the files they name stay in review. */
const residuals = conformance.conforms === true ? [] : (conformance.findings || []).map((f) => `${f.file}: ${f.finding}`)
if (residuals.length) log(`Integrate: the integration does not conform after ${corrections} correction pass(es); the files the review found conforming are set effective and ${residuals.length} finding(s) stand as residuals: ${residuals.join('; ')}`)
const guardIntegrate = await constraintsGuard(before, 'constraints:after-integrate', 'Integrate')
if (guardIntegrate) return { ...guardIntegrate, subject, targetDir, deltaDir, architectureUpdate: update }

let approval = null
if (update.touched) {
  approval = await depscore('integrate:approve', 'Integrate', `arch-approve --arch-files-from ${shq(FILES_JSON)} --reviewed-from ${shq(conformance.path)} --arch-root ${shq(ARC42)}`)
  const n = approval && approval.summary ? approval.summary : null
  const refused = approval && !approval.error ? (approval.refused || []).map((x) => x.path) : []
  if (!n || approval.error || refused.length) {
    const why = !n || approval.error
      ? `depscore.py arch-approve did not run: ${(approval && approval.error) || 'no result'}`
      : `depscore.py arch-approve refused these integrated files, in section 2 or outside the architecture: ${refused.join(', ')}`
    return { ok: false, stage: 'approve', reason: why, error: why, approval, conformance, architectureUpdate: update, decision, subject, targetDir, deltaDir }
  }
  const inReview = [...listed(approval.unreviewed), ...(approval.failed || []).map((x) => x.path)]
  log(`Approval: ${n.promoted || 0} file(s) set to effective, ${n.unchanged || 0} already effective${inReview.length ? `; ${inReview.length} stay in review: ${inReview.join(', ')}` : ''}`)
}

let vaultCommit = null
if (update.touched + update.deleted) {
  vaultCommit = await depscore('integrate:commit', 'Integrate', `arch-commit --arch-root ${shq(ARC42)} --files-from ${shq(FILES_JSON)} --message ${shq(`docs(architecture): integrate the approved target for ${subject}`)}`)
  if (!vaultCommit || vaultCommit.error || vaultCommit.ok === false) {
    const why = `depscore.py arch-commit did not commit and push the integrated files: ${(vaultCommit && (vaultCommit.error || listed(vaultCommit.refusals).join('; '))) || 'no result'}`
    return { ok: false, stage: 'commit', reason: why, error: why, vaultCommit, approval, conformance, architectureUpdate: update, decision, subject, targetDir, deltaDir }
  }
  log(`Commit: ${vaultCommit.commit ? `${vaultCommit.commit} on ${vaultCommit.branch}` : 'nothing new to commit'}${vaultCommit.pushed ? ', pushed' : ''}`)
}
await markRevision('integrated', 'Integrate')

const closed = await runClosure(targetDir, deltaDir)
if (closed.failure) return closed.failure

return {
  ok: true,
  subject,
  subjectName,
  targetDir,
  deltaDir,
  architectureChange,
  closure: closed.closure,
  targetPath: TARGET_JSON,
  surveyPath: SURVEY_MD,
  decision,
  decisionPath: DECISION_MD,
  architectureUpdate: update,
  conformance,
  approval,
  vaultCommit,
  rounds: lastRound,
  retries,
  openItems: [
    ...(update.constraintIssues + update.contradictions > 0 ? [`${update.constraintIssues} constraint issue(s) and ${update.contradictions} contradiction(s) recorded in ${UPDATE_JSON}`] : []),
    ...residuals.map((r) => `integration finding left standing (its file stays in review): ${r}`),
  ],
  architectureUpdatePath: UPDATE_JSON,
  ledgerPath: LEDGER_JSON,
}

})())
