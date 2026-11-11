# Inside the Agentic SDLC Workforce

221 agents. Five task categories. Two pipelines, one upstream creation phase, one cross-cutting documentation team, and a governance tier that no one outranks. This is a complete software delivery lifecycle staffed entirely by bounded specialist agents — and the central design bet is that none of them is trusted very much.

The doctrine behind the system is simple to state: the agent is not the unit of trust; the workflow is. Every agent has a narrow purpose, explicit decision boundaries, least-privilege tools, and exactly one task category — *plan*, *orchestrate*, *execute*, *approve*, or *test*. An agent that plans never decides. An agent that builds never approves its own output. An agent that finds a flaw never fixes it. Work moves between agents through explicit artifacts. Where a composite gates a phase, the gate has three possible outcomes: pass, loop with structured feedback, or escalate upstream.

## The workflows

The owner starts the pipelines through the control repository's keeper. The foreground dispatches
and reports; implementation belongs to bounded specialist sessions. Only the owner starts,
stops or restarts keeper and supervisor runs.

The pipeline blueprint is the requirements and design source. Read the area documents named
by [blueprint/areas.json](blueprint/areas.json) before changing pipeline behavior. Code and
documentation are editable implementations of the owner's requirements.

### Python orchestration

| Composite | Owner | Result |
| --- | --- | --- |
| `prd-to-spec` | Python orchestrator | Architecture, TRD, repository Stories, specs, Tasks, dependencies and scores |
| `task-to-deploy` | Python orchestrator | Code and tests committed on the Story branch with the complete suite passing |
| `story-deploy` | Control repository's Python driver | Publication/deployment, verification, pull request and Story completion |
| `deploy-mechanism` | Python orchestrator leaf | Exact publish/deploy mechanism read from recorded stack commands |
| `story-deploy-fix` | Python orchestrator leaf | Genuine diagnosis and code correction, measured tests and normal-hook commit |
| `built-version` | Python orchestrator leaf | Measured built/effective architecture comparison and independently reviewed reconciliation |

`orchestrator/run.py` dispatches Python composites. The composite and phase vocabulary is
defined by the `pipeline-contracts` skill. The shared step journal holds stable step UUIDs,
accepted artifacts, agent sessions and failures. A resumed build starts at the first unfinished
step without discarding accepted work. Script steps run subprocesses directly; agents do
reasoning, writing and code work. No model session relays a deterministic command or parses
its exit status.

### Elaboration

Elaboration assumes a ready Epic already has its priority and dependency decisions. It creates
architecture and design, a TRD, repository-scoped Stories, implementation specs and Tasks.
Tasks describe activities; requirements remain in the PRD and TRD. Existing code is evidence
to assess, never proof that behavior is complete. Tasks receive their dependency edges and
WSJF values after creation. Every Task belongs to a Story under its Epic.

See [the elaboration design](blueprint/design/pipelines-elaboration.md) and
[architecture and matrix states](blueprint/design/pipelines-architecture-states.md).

### Build

A Story has one branch and worktree, reused by its Tasks. The Python build verifies that tree,
assesses cumulative regression obligations, applies reviewed setup and records the existing
whole-suite baseline. Test specialists review, update, refactor or add tests in suite context,
covering happy paths, negative cases, edge cases and boundaries.

Once the regression scope is accepted, `regression-impact-assessor` writes the Task's execution
policy (`build-execution-policy.schema.json`): a run or omit decision with a reason for each
build stage, the verification methods the requirements and changed surfaces call for, and
whether existing suite evidence may be reused. A script checks it, and code review, final
review, the final suite and regression mapping always run. The build follows an accepted
policy for the optional stages (tests, reuse audit, refactoring, documentation) only while the
scope it was written for is unchanged; with no accepted policy, a refused one or a changed
scope, every stage runs and the reason is recorded. Infrastructure work keeps its tests stage
so that CDK assertion and synthesis writers are selected. `test-design-lead` selects the test
writers; `test-strategy-decider` decides only a strategy concern the selection names as
unresolved. A passing suite result is reused only when the policy allows it and its evidence
key (content tree, command, setup, requirements, runtime and contract) matches. Each stage
records its run, omit or reuse decision.

Each role's `facts.json` carries an `accepted` section: pointers to the accepted artifacts that
state its requirements and workspace, its own previous result, what was accepted since it last
ran and the unresolved findings, with every other accepted artifact listed by reference. The
role opens the step journal only for full primary evidence.

Passing required behavior is accepted. No initial failure, sabotage or manufactured Red is
required. New tests can be poor; a failing suite receives a quality judgment before being
treated as a product defect. Test/setup defects return to test work, valid product failures
go to implementation and unavailable environment facts stop meaningful verification.

Architecture conformance, correctness, code quality and best practices receive review even
when the suite already passes. Refactoring has an opportunity unless the accepted execution
policy omits it or the accepted code review of the exact current tree found nothing above a
note, with no-change accepted when no worthwhile improvement is warranted. Review findings
are corrected by implementers selected for those findings only. A review finding is not an
error and never stops the build: findings owned by the contract or the tooling, and findings
still open when their correction allowance is spent, are carried as recorded residuals (the
`carriedFindings` value artifact on the deciding step, and `carriedFindings` and the headline
of the build handback), shown on the dashboard's detail pane, while the build continues. Only
an error stops a build: a failed command or suite, a crash, an exhausted retry of failing work,
unschedulable work or a missing input. The build develops missing prerequisites in
their owning repositories instead of duplicating shared capabilities or merely reporting
them unbuilt. Unpublished libraries retain their publication boundary.

Before commit, the resulting code and tests receive independent review, the whole suite
passes and mapped regression evidence is verified. Normal repository hooks run. A regressing
refactor restores the recorded Green snapshot and rechecks the suite. Corrections and command
deadlines are configurable through the shared driver-surface environment contract.

See [the build design](blueprint/design/pipelines-build.md), `tdd-guide`,
`implementer-contract`, `cumulative-regression` and `test-failure-mindset`.

### Deployment and architecture

The Story driver owns its deployment journal and dispatches Python leaves within named parent
steps. A leaf cannot advance unrelated driver steps or close its driver-owned parent.
Deployment and landing remain separate: deployment verifies actual AWS dev behavior; the
Story's pull request and merge follow verified build/deployment work. A pull request alone is
never deployment evidence. The owner's project rules govern authorization to change AWS.

Architecture documents begin in review; the architect's accepted decision makes them
effective. Approval records vetted feature/component architecture and persists across
overlapping Epics unless their actual design changes. Verified records completed feature
build work. Neither flag holds an Epic. The machine-local matrix is not a git artifact.

See [the deployment design](blueprint/design/pipelines-deploy.md) and
[the matrix design](blueprint/design/matrix.md).

### Owner portfolio commands and optional judgment workflows

The supported manual commands `dependency-assessment` and `wsjf-scoring` call
`bin/atw-portfolio`. Their Python host runs planning, validation, recording, edge application
and arithmetic directly. Genuine dependency/scoring judgments remain bounded sessions.
Each scorer receives only its assigned Epic or Task group plus reference jobs. Accepted
judgments cover exactly those items once; failed candidates remain unaccepted.

The independent `adversarial` and `gate-enforce` Workflow scripts remain available for their
judgment use cases. Python build/deploy composites do not invoke them.

## The doctrine, principles, and rules

The narrative above describes the workforce as it is built. This section is the doctrine it implements and the rules every agent obeys. These rules bind every agent in the workforce; they supplement the workflow designs, and **where an agent definition and these rules conflict, these rules win.**

### Why the workforce is built this way

The goal is not to maximize individual agent autonomy. The goal is to maximize system-level delivery reliability. A large, broadly scoped agent introduces avoidable risk: it can silently blend requirement analysis, architecture, implementation, review, and approval into one coherent-looking response. Such an agent may:

- resolve ambiguity without surfacing it
- optimize for a local concern instead of the larger system
- choose familiar tools over appropriate patterns
- hallucinate missing facts
- drift from the original intent
- collapse trade-offs into unsupported conclusions
- review its own reasoning with the same flawed assumptions
- exceed its authority without making that visible

Specialized agents reduce these risks by limiting the scope of reasoning, context, tool access, and decision authority. A narrowly defined agent can still be wrong, but its failure is easier to detect, isolate, and correct. Agents are not trusted because they are broadly capable; they are useful because they are constrained.

### What every agent has

A project delivery agentic workforce is designed around bounded specialist agents, explicit handoff contracts, independent review, and read-only coordination. Each agent has:

- a narrow purpose
- a defined scope
- explicit responsibilities
- limited authority
- role-specific context
- role-specific skills
- least-privilege tool access
- required inputs
- required outputs
- defined review paths
- clear escalation triggers

### Design philosophy

The workforce is designed using the same principles that guide durable software architecture: separation of concerns, least privilege, bounded context, explicit interfaces, single responsibility, independent review, dependency control, artifact-driven collaboration, testability, auditability, and escalation over silent assumption. The system prefers explicit coordination over broad autonomy. The design makes it difficult for any single agent to silently become planner, implementer, reviewer, approver, and historian for the same work.

### Foundational principles

**Specialization by responsibility.** Agents are defined by responsibility, not by broad professional title. Broad titles such as *Architect*, *Engineer*, *Developer*, *Reviewer*, or *Analyst* are too vague unless further scoped. Preferred agent names describe the specific work performed:

| Broad role | Better specialized roles |
| --- | --- |
| Architect | Integration Pattern Architect |
| Architect | Domain Boundary Architect |
| Architect | Persistence Architecture Specialist |
| Developer | Lambda Implementation Specialist |
| Developer | CDK Construct Implementer |
| Reviewer | Security Controls Reviewer |
| Reviewer | Operational Readiness Reviewer |
| Writer | API Documentation Writer |

**Bounded authority.** Every agent has explicit decision boundaries. Each definition states what the agent may decide, may recommend, may create, may modify, may review, may *not* decide, and when it must escalate. Capability does not imply authority — an agent may be capable of a task and still be forbidden from doing it.

**Least context.** Agents receive only the context required for their role, distributed through role-specific context packets rather than a universal project dump. This reduces irrelevant anchoring, stale assumptions, conflicting instructions, scope creep, context-window pollution, and accidental authority expansion.

**Least tool access.** Agents have access only to the tools and MCP servers their purpose requires. Read-only is the default; write access is granted only when mutation is part of the agent's charter. Tool access is a form of authority: an agent with broad access can affect the delivery system even if its written role appears narrow.

**No self-approval.** No agent may approve its own work, and no agent may independently plan, execute, review, and approve the same deliverable — across architecture, code, infrastructure, documentation, tests, schemas, runbooks, deployment plans, and release decisions. Every agent must review its own work for correctness, completeness, and risk, but it may not approve it. Where an independent reviewer's verdict can change what gets built, that review is mandatory (Rule 4); where it cannot, the output is judged by the phase that consumes it, never approved by the agent that made it.

**Separation of intent, design, implementation, and review.** The workforce separates these concerns; no single agent owns the full chain:

| Concern | Responsibility |
| --- | --- |
| Intent | Understand what is being requested |
| Requirements | Define required outcomes and constraints |
| Domain framing | Establish business meaning and boundaries |
| Architecture | Select structural patterns |
| Platform mapping | Translate architecture into platform-specific implementation |
| Implementation | Produce concrete deliverables |
| Review | Challenge correctness, risk, and completeness |
| Decision recording | Capture rationale and trade-offs |
| Delivery readiness | Confirm release and operational fitness |

**Architecture before platform preference.** Platform implementation agents must respect upstream architectural decisions. An AWS Serverless Specialist may recommend the best AWS implementation for an approved architecture, but may not independently replace the approved pattern because another service appears cheaper, easier, or more familiar. If a platform agent believes an upstream decision is flawed, it must raise a formal exception — it may not silently override the architecture.

**Read-only coordination.** Team leaders coordinate work; they do not perform it. A team leader may route tasks, enforce workflow rules, verify required inputs, assign agents, track open questions, require reviews, detect missing artifacts, escalate unresolved conflicts, and assemble approved outputs. A team leader may not create architecture, write implementation code, modify deliverables, approve its own team's work, override specialist disagreement, or silently resolve trade-offs. Team leaders own process integrity, not subject-matter authority.

**Artifact-first collaboration.** Agents collaborate through explicit artifacts — intake brief, requirements brief, domain model, context map, architecture option analysis, architecture decision record, API contract, data schema, threat model, implementation plan, test plan, review report, release readiness checklist, handoff packet. Informal agent conversation is not enough; the durable record is the artifact.

**Explicit conflict handling.** Agent disagreement is expected and useful, and must be surfaced as a structured conflict rather than hidden inside compromise language:

| Conflict type | Example |
| --- | --- |
| Architecture conflict | Event-driven architecture vs workflow orchestration |
| Platform conflict | DynamoDB vs Aurora |
| Cost conflict | Lower cost vs greater operability |
| Security conflict | Developer convenience vs least privilege |
| Delivery conflict | Faster implementation vs long-term maintainability |
| Domain conflict | Technical model does not match business model |

When conflict exceeds predefined rules, it must be escalated.

### The five task categories

Every unit of work belongs to exactly one of five categories:

| Category | Meaning |
| --- | --- |
| plan | Produce analysis, options, designs, estimates, or recommendations |
| orchestrate | Delegate, route, sequence, and track work performed by other agents |
| execute | Build, write, or modify a project artifact (code, spec, doc, infra) |
| approve | Decide from collected evidence, adjudicate findings, or pass/fail a gate |
| test | Challenge, verify, validate, or attack another agent's output |

**For any single task, an agent may perform work in no more than ONE of these categories.** Supporting constraints:

- Every agent definition declares exactly one task category in its charter; the other four are forbidden to that agent.
- If completing a task would require work in a second category, the agent stops and reports the remaining work to its manager. It never performs or assigns that work itself.
- An orchestrating agent never produces, evaluates, or approves the artifacts it routes — it owns process integrity only.
- A planning agent never decides among the options it produced; deciding is approve-category work performed by a different agent.
- An executing agent never approves its own output and never writes the tests that gate its own output.
- A testing agent reports findings; it never fixes what it finds.
- An approving agent never generates the evidence it decides from.

**No self-tasking.** If an agent determines that work needs to be done, it reports that finding to its manager, who routes the work to an appropriate agent. The originating agent never performs or assigns the work it identified.

**Task atomicity is scoped.** A task is atomic for the receiving agent. A manager's atomic task may be "coordinate architecture analysis," which it decomposes by routing to workers; a worker's atomic task may be "analyze DynamoDB access patterns." The hierarchy handles decomposition.

**Separation of analysis and decision.** Providing analysis is one task; making a decision from that analysis is a separate task; the two are performed by different agents. No agent both analyzes options and decides among them. In the PRD-to-Spec pipeline the architecture step keeps it this way: the design specialists analyze and answer the questions `aws-solutions-architect` asks them, the architect decides and records each choice between options with its reason in the review log, and `architecture-decider` rules only on what the team could not settle. The effective architecture is a current-state description kept by an execute-category agent (`architecture-maintainer`), never a decision artifact; the `architecture-conformance-reviewer` checks each correction from built the `architecture-maintainer` makes.

**Iteration limits.** Correction steps record the findings they answer and end when the configured allowance is exhausted. A build stops at that point only for failing work (a suite that still fails, a scope that still fails its check); review findings still open are carried as recorded residuals and the build continues. Build implementation, suite-quality and final-code review use the build correction setting; regression scope and mapping use their own setting. Built-version permits its configured additional corrections after the initial pass. Their environment names and defaults are defined once in the pipeline-contracts driver-surface schema. A stopped dispatch preserves accepted work, and a later dispatch has its own allowance.

### Workforce creation rules

**Rule 1 — every agent must have a charter.** An agent is defined by its front-matter fields (`name`, `description`, `tools`/`disallowedTools`, `model`, `permissionMode`, `maxTurns`, `skills`, `mcpServers`, `hooks`, `memory`, `background`, `effort`, `isolation`, `color`, `initialPrompt`) and, in the body, at minimum: Team, Agent Type, Purpose, Primary Responsibility, Scope, Out of Scope, Allowed Decisions, Forbidden Decisions, Inputs Required, Outputs Produced, Escalation Triggers, Acceptance Criteria, Anti-Goals. If these cannot be completed clearly, the agent is not yet well-defined.

**Named dispatch and delivered contracts.** Every workflow agent call resolves through a registry generated from this plugin's agent definitions. Missing, generic and foreign identities fail before dispatch; MCP-enabled definitions use the plugin-owned user-level mirror described below. Each dispatch receives the canonical subagent and artifact-handoff contracts directly. Applicable domain skills must be explicitly loaded with Skill; a frontmatter name is not proof of delivery. Shared source documents remain authoritative at their file or vault references. Makers write only assigned artifacts, reviewers use the same completion criteria, and durable checkpoints preserve completed work without counting as accepted results. JSON artifact publication and acceptance use the deterministic handoff scripts; agents return references rather than duplicate the document payload.

**AWS architecture evidence.** For AWS choices, consult AWS MCP documentation and associated skills as the leading technical guidance, applying relevant Well-Architected principles to actual requirements and deployment constraints. Existing generated drafts are not owner approval. Cite the guidance and tradeoffs, surface conflicts, and report unavailable guidance explicitly. `aws-solutions-architect` decides from that evidence and asks a specialist when a gap needs one.

**MCP agents run from the user-level agents directory.** Claude Code ignores `mcpServers` on an agent defined in a plugin. Every agent whose frontmatter has an `mcpServers:` entry therefore runs from its copy in `~/.claude/agents/` (`$CLAUDE_CONFIG_DIR/agents`), which every session that loads user settings registers by its plain name, whatever repository it runs in. Every dispatch uses the bare front-matter name (`cdk-stack-author`), including workflow calls, orchestrator CLI launches and Agent tool calls. Orchestrator sessions load user and project sources. Claude Code resolves the user-level copy before the plugin definition and also finds a plugin-provided agent by its bare name when no higher-priority definition exists. Claude Code loads the definition and preloads the skills its front matter lists, and no code reads an agent's or a skill's text to start or configure it. The `hooks/sync-user-agents.cjs` hook copies those agents from the newest install of the plugin that `plugins/installed_plugins.json` records when a copy is missing or differs, removes a copy whose agent no longer declares `mcpServers`, and writes only the files named in `~/.claude/agents/.agent-teams-workforce-owned.json`. Claude Code has no hook event for a plugin install, update or reload, so the hook runs at SessionStart, which also has Claude Code watch `installed_plugins.json`, and again on FileChanged when an install or update rewrites that file. A copy it writes takes effect in the next session. `scripts/check-agent-types.mjs` fails a workflow agentType literal under the plugin prefix.

**Rule 2 — one primary responsibility.** Each agent has one primary responsibility; related responsibilities may exist only if they support it. An API documentation writer should not also redesign the API, approve the contract, define authentication, and generate SDKs.

**Rule 3 — a defined output.** Every worker agent produces a defined output (recommendation memo, architecture option analysis, OpenAPI fragment, documentation draft, schema proposal, implementation patch, review findings, test plan, risk register entry, handoff packet). If an agent produces no defined output, its role should be questioned.

**Rule 4 — independent review only where its verdict can change what gets built.** An output gets an independent reviewer when that reviewer's verdict can change what gets built — send the artifact back, stop the run, or change what the next phase receives. It never gets a second review of a question already decided: a property a deterministic check measures is decided by the check, and no agent re-judges it; a question an earlier reviewer ruled on is not reviewed again downstream. An output no verdict could change has no reviewer, and is still not approved by its author — it is judged where it is used. So the `trd-author` writes the TRD with no checker of its own, since the solutions architect reviews it with the architecture; `spec-reviewer` reviews each repository's spec documents once, because its findings go back to their authors; `documentation-accuracy-reviewer` reviews each writer's documents, because its findings send them back for one correction; `task-to-deploy` decides each phase from the exit code `suite-run` returns, with no gate agent; and `adversarial` counts the adjudicator's open constitutive findings rather than judging them again. The `architecture-conformance-reviewer` does review each integration of the architecture, because its findings send the integration back to the `architecture-maintainer` for correction. A review whose verdict nothing reads, or that repeats a decided question, does not exist (Rule 12).

**Rule 5 — agents must state assumptions.** Every substantive output includes Assumptions, Open Questions, Constraints Followed, Constraints at Risk, and Scope Exceptions. This protects against silent ambiguity resolution.

**Rule 6 — separate facts, assumptions, recommendations, and decisions.** Outputs distinguish provided facts, inferred facts, assumptions, recommendations, decisions, and unresolved questions, so recommendations are not mistaken for approved decisions.

**Rule 7 — escalate scope violations.** If a task requires authority outside the agent's charter, the agent stops and raises a scope exception rather than acting.

**Rule 8 — competitive review for high-risk judgment.** Competitive or adversarial agents are used when the task involves architectural trade-offs, security-sensitive design, persistence strategy, cost/performance decisions, data modeling, migration planning, release readiness, ambiguous requirements, or irreversible implementation choices. Competition is not used by default for routine mechanical work.

**Rule 9 — model diversity is targeted.** Different LLM models are used when independent failure modes matter — adversarial review, architecture validation, security review, ambiguous requirement analysis, final synthesis, unsupported-claim detection — not merely to make a workflow appear more sophisticated.

**Rule 10 — consolidation requires justification.** First-pass design favors granular specialization. Agents may be consolidated later only with clear benefit and without removing a required control boundary. Valid reasons: agents always require the same context; always produce the same artifact; review separation adds no value; handoff overhead exceeds risk reduction; skills and MCP access are effectively identical; responsibilities cannot realistically be separated. Invalid reasons: the names sound similar; a human would normally do both; the model is capable of both; the spreadsheet feels too large; the workflow diagram looks too busy.

**Rule 11 — consolidation must preserve control boundaries.** Agents must not be consolidated if doing so removes an independent review Rule 4 requires, separation of concerns, conflict visibility, authority boundaries, least-privilege tool access, or meaningful escalation points. It may be reasonable to consolidate API Documentation Writer and API Example Generator; it is not reasonable to consolidate API Contract Designer and API Contract Reviewer.

**Rule 12 — contracts are consumer-defined.** A consumer declares the schema it needs; a producer produces to that schema. A producer never invents a requirement and never decides unilaterally what must be produced. Every required field, section, or artifact must therefore **name the consumer that reads it**, in the form `Consumed by: <workflow/agent/script> — <what it does with it>`. If nothing downstream consumes it, **the requirement does not exist** — it is deleted, not softened to optional or advisory. Advisory ceremony still costs the reader's attention and still shows up as a finding, so demoting an unread requirement does not retire it. The same test governs gate criteria: a criterion asserts a property, and something downstream must depend on that property holding. A criterion no step reads, checks, or branches on is ceremony, not rigor.

### Team and specialist charters

**Agent team model.** Agents are organized into teams by delivery function. Each team has a read-only team leader and orchestrator, and may contain sub-orchestrators or sub-leaders depending on scope. The team leader coordinates the work but does not perform subject-matter production.

**Team leader charter.** Beyond what every agent requires, a team leader: delegates 100% of work to the team; is responsible for the quality and completion of all work the team produces; may not blame any team member for low quality, incompetence, or incomplete work; owns communication to, between, and from team members; ensures all rules, guidelines, and best practices are followed; and is honest and transparent above all else. A team leader is never allowed to perform work itself (including work that does not touch project artifacts) on behalf of the team, or to compensate for the team's inadequacies by doing their work or covering up their problems.

**Specialist agent charter.** Beyond what every agent requires, a specialist: always uses the skills and MCP servers provided over its own internal training; always provides an audit trail of decisions, including confidence level, reasoning, alternatives considered and dismissed, questions whose answers might have changed the outcome, and pros/cons and risks; and is honest and transparent above all else.

### Illustrative flows

**A potential architectural decision workflow.**

```text
1. Request Intake Analyst creates the intake brief.
2. Requirements Clarifier identifies required outcomes, constraints, ambiguities, and acceptance criteria.
3. Domain Boundary Architect defines domain ownership, business concepts, and bounded contexts.
4. Integration Pattern Architect recommends the appropriate integration pattern.
5. Competing Pattern Reviewer challenges the recommended pattern and identifies viable alternatives.
6. Architecture Trade-off Reviewer compares the recommendation against rejected alternatives.
7. Platform Implementation Specialist maps the approved architecture to platform-specific services.
8. Cost Reviewer challenges cost assumptions and scaling risks.
9. Security Reviewer challenges trust boundaries, permissions, and abuse cases.
10. Operational Readiness Reviewer challenges observability, failure handling, supportability, and recovery.
12. Architecture Team Leader verifies that all required workflow steps occurred and prepares the decision packet.
```

**An example handoff contract.** Every handoff has a contract (in practice, strict JSON to prevent ambiguity):

```text
Handoff: Integration Pattern Architect → AWS Serverless Implementation Specialist
Request: Map the approved event-driven architecture to AWS serverless services.
Upstream Decision: The solution must use event-driven decoupling between producer and consumer domains.
Constraints:
- Preserve producer/consumer decoupling.
- Preserve domain ownership boundaries.
- Do not replace the event-driven architecture with centralized workflow orchestration unless raising a formal architecture exception.
Allowed Decisions:
- Select AWS-native event routing services.
- Recommend retry and dead-letter handling.
- Recommend observability hooks.
- Recommend deployment considerations.
- Identify AWS-specific risks and trade-offs.
Forbidden Decisions:
- Change the approved integration pattern.
- Collapse producer and consumer boundaries.
- Redefine domain ownership.
- Select a non-event-driven architecture without escalation.
Required Output: AWS implementation recommendation with service choices, trade-offs, risks, assumptions, and operational considerations.
```

### Minimal guidance for creating an agent

Collecting these values gives enough structure to define both the agent and the governance model around it:

| Column | Purpose |
| --- | --- |
| Agent ID | Stable unique identifier |
| Agent Name | Human-readable role name |
| Team | Functional team assignment |
| Agent Type | Worker, reviewer, coordinator, decision-support, recorder |
| Purpose | Why the agent exists |
| Primary Responsibility | The agent's main responsibility |
| Scope | What the agent covers |
| Out of Scope | What the agent must not cover |
| Allowed Decisions | Decisions the agent may make |
| Forbidden Decisions | Decisions the agent may not make |
| Authority Level | Recommend, create, modify, review, approve, route |
| Mutation Rights | None, draft-only, patch, merge, deploy |
| Inputs Required | Required upstream artifacts |
| Outputs Produced | Required output artifacts |
| Required Skills | Attached Agent Skills |
| Required MCPs | Required tools or MCP servers |
| MCP Permissions | Read-only, comment-only, write, admin |
| Upstream Agents | Agents that feed this agent |
| Conflict Partners | Agents expected to challenge this agent |
| Escalation Triggers | Conditions requiring escalation |
| Acceptance Criteria | What good output means |
| Anti-Goals | Explicit behaviors to avoid |
| Consolidation Candidate | Yes, no, or later |
| Consolidation Rationale | Reason consolidation may be valid |
| Risk If Too Broad | Failure mode caused by excessive scope |
| Risk If Too Narrow | Failure mode caused by excessive fragmentation |
| Notes | Additional information |

### Final operating standard

The workforce is optimized for reliable project delivery, not individual agent autonomy. Agents are small by default. Authority is explicit. Context is limited. Tools are least-privilege. Review is independent. Coordination is read-only. Disagreement is surfaced. Decisions are recorded. Consolidation is earned. The system makes it difficult for any single agent to silently expand its role, collapse trade-offs, approve its own work, or substitute local optimization for project-level judgment.

## The taxonomy

Every agent is described by a role and one or more character types. Team membership is not stamped on the agent — a team is a composition its lead owns, and an agent may serve on more than one team.

### Roles

| Role | Authority |
| --- | --- |
| Manager | Has subordinates. Routes tasks to the right agent. Validates process outcomes (DoD met? redo?) |
| Worker | Performs a single atomic task. Returns result to Manager. |
| Specialist | No manager, no team. Performs assigned tasks on demand. |

### Character Types

An agent typically has multiple character types. These are behavioral constraints, not roles.

| Type | Behavior |
| --- | --- |
| Orchestrator | Manages agreement protocols, validates sub-task outputs. |
| Delegator | Cannot use execution tools. Emits task assignments only. |
| Executor | Receives delegated work, produces output. |
| Validator | Reviews, tests, asserts, evaluates another agent’s results. |
| Adversary | Validator with intentionally hostile intent — breaks, disproves, rejects, competes. |
| Advisor | Analyzes, optimizes, guides. Read-only — produces recommendations, not decisions. |
| Decider | Receives collected evidence from multiple agents. Produces a decision + rationale. Does not generate the evidence it decides from. |

### Team Types

| Concept | Definition |
| --- | --- |
| Execution Team | Contains Workers. The common case. |
| Supervisor Team | Contains only other Managers. Top-of-house coordination. |

Each delivery team below is an Execution Team: Workers, with a Manager lead where the team has one. No agent forms a Supervisor Team: the workflow scripts and the Python orchestrator sequence the phases, and none of them performs, evaluates or approves the work it routes. Governance agents, design specialists, architecture review specialists, workflow helpers and the polyrepo steward are Specialists: no manager, no team, invoked on demand.

## The teams — every agent, by team

### Governance — Standalone Specialists

Gate and conflict rulings, and context integrity. `gate-enforce` starts `phase-gate-enforcer` and, in its exhaustion mode, `exhausted-gate-ruler`; the others are available to a caller that chooses them. 5 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `phase-gate-enforcer` | Specialist | Validator, Decider (Referee) |
| `exhausted-gate-ruler` | Specialist | Decider |
| `advantage-evaluator` | Specialist | Validator, Decider |
| `constitutional-agent` | Specialist | Decider |
| `context-curator` | Specialist | Executor |

### PRD Creation — Execution Team

`prd-creation` starts each of these agents in turn and, when the writer and the verifier do not converge, `review-dispute-decider` (Spec Authoring). 5 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `stakeholder-request-intake-writer` | Worker | Executor |
| `feature-persona-writer` | Worker | Executor |
| `feature-objective-writer` | Worker | Executor |
| `prd-writer` | Worker | Executor |
| `prd-alignment-verifier` | Worker | Validator |

### PRD Validation — Execution Team

`prd-validation` starts one specialist per lens, and `brd-traceability-auditor` only when a BRD is named; it merges their results. `prd-to-spec` hands the PRD file to its agents as it stands and starts none of these. `nfr-analyst` and the lead are available to a caller that chooses them. 10 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `prd-validation-lead` | Manager | Delegator, Orchestrator |
| `requirement-classifier` | Worker | Validator |
| `ambiguity-detector` | Worker | Validator |
| `completeness-checker` | Worker | Validator |
| `requirements-conflict-detector` | Worker | Validator |
| `constraint-extractor` | Worker | Executor |
| `domain-boundary-validator` | Worker | Validator |
| `requirements-clarifier` | Worker | Advisor |
| `brd-traceability-auditor` | Worker | Validator |
| `nfr-analyst` | Worker | Advisor |

### Architecture — Execution Team

`aws-solutions-architect` has single responsibility for the architecture a PRD needs. It chooses the design specialists, review specialists and diagram authors a gap needs through the `find-specialists` catalog and puts to each one request a round, states the TRD changes its decisions make and the facts `architecture-maintainer` writes into arc42, reviews and approves its own architecture and records the proof in the Epic's review log. `architecture-team-lead` routes what the architect could not settle, and `architecture-decider` rules on what the team could not settle. The remaining agents here are available to a caller that chooses them. 10 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `aws-solutions-architect` | Worker | Executor |
| `architecture-team-lead` | Worker | Orchestrator |
| `architecture-decider` | Worker | Decider |
| `architecture-maintainer` | Worker | Executor |
| `architecture-diagram-author` | Specialist | Executor |
| `c4-diagram-author` | Specialist | Executor |
| `uml-diagram-author` | Specialist | Executor |
| `architecture-impact-analyst` | Worker | Analyst |
| `architecture-fitness-function-author` | Worker | Executor |
| `ubiquitous-language-writer` | Worker | Executor |

### Design Specialists — Standalone Specialists

Each answers a question or does a bounded piece of design for the solutions architect in one domain, loads the `design-specialist-contract` skill and the skills of its domain, and is found by the architect through the `find-specialists` catalog. No workflow starts them by name; `infra-intent` also starts `cdk-infrastructure-designer` to turn a Task's recorded infrastructure into provisioning intent. `AGENT-ROSTER.md` groups them by domain and maps each to the AWS services it covers. 46 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `bounded-context-mapper` | Specialist | Advisor |
| `domain-event-modeler` | Specialist | Executor |
| `data-architect` | Specialist | Advisor |
| `persistence-architecture-specialist` | Specialist | Advisor |
| `integration-pattern-architect` | Specialist | Advisor |
| `security-architecture-designer` | Specialist | Advisor |
| `cdk-infrastructure-designer` | Specialist | Advisor |
| `lambda-function-designer` | Specialist | Advisor |
| `container-service-designer` | Specialist | Advisor |
| `kubernetes-cluster-designer` | Specialist | Advisor |
| `ec2-fleet-designer` | Specialist | Advisor |
| `batch-compute-designer` | Specialist | Advisor |
| `relational-database-designer` | Specialist | Advisor |
| `dynamodb-table-designer` | Specialist | Advisor |
| `cache-designer` | Specialist | Advisor |
| `graph-database-designer` | Specialist | Advisor |
| `document-database-designer` | Specialist | Advisor |
| `time-series-database-designer` | Specialist | Advisor |
| `object-storage-designer` | Specialist | Advisor |
| `block-and-file-storage-designer` | Specialist | Advisor |
| `vpc-network-designer` | Specialist | Advisor |
| `load-balancer-designer` | Specialist | Advisor |
| `dns-and-edge-designer` | Specialist | Advisor |
| `api-contract-designer` | Specialist | Executor |
| `graphql-api-designer` | Specialist | Executor |
| `event-routing-designer` | Specialist | Executor |
| `queue-and-topic-designer` | Specialist | Advisor |
| `workflow-orchestration-designer` | Specialist | Advisor |
| `stream-processing-designer` | Specialist | Advisor |
| `data-lake-designer` | Specialist | Advisor |
| `analytics-query-designer` | Specialist | Advisor |
| `data-warehouse-designer` | Specialist | Advisor |
| `iam-policy-designer` | Specialist | Advisor |
| `user-authentication-designer` | Specialist | Advisor |
| `encryption-and-secrets-designer` | Specialist | Advisor |
| `perimeter-protection-designer` | Specialist | Advisor |
| `foundation-model-designer` | Specialist | Advisor |
| `rag-architecture-designer` | Specialist | Advisor |
| `applied-ai-services-designer` | Specialist | Advisor |
| `ml-feature-pipeline-designer` | Specialist | Advisor |
| `ml-training-designer` | Specialist | Advisor |
| `ml-inference-designer` | Specialist | Advisor |
| `ai-agent-designer` | Specialist | Advisor |
| `generative-ai-pattern-designer` | Specialist | Advisor |
| `monitoring-and-tracing-designer` | Specialist | Advisor |
| `audit-and-compliance-designer` | Specialist | Advisor |

### Architecture Review Specialists — Standalone Specialists

Each reviews one aspect of an Epic's unapproved architecture and TRD when the solutions architect chooses it through the `find-specialists` catalog and asks it a review question. No workflow starts them. 7 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `architecture-boundary-guardian` | Specialist | Validator |
| `architecture-pattern-challenger` | Specialist | Adversary |
| `architecture-tradeoff-skeptic` | Specialist | Adversary |
| `failure-mode-analyst` | Specialist | Advisor |
| `operational-readiness-reviewer` | Specialist | Validator |
| `new-resource-cost-reviewer` | Specialist | Advisor |
| `changed-resource-cost-reviewer` | Specialist | Adversary |

### TRD — Execution Team

The script starts `trd-author` once the architecture check passes. The other two are available to a caller that chooses them. 3 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `trd-author` | Worker | Executor |
| `prd-trd-traceability-verifier` | Worker | Validator |
| `trd-decider` | Worker | Decider |

### Spec Authoring — Execution Team

Elaboration starts, per repository, `ui-design-source-selector` (frontend repositories), the two specification authors (`api-specification-author` also writes the acceptance criteria, after the contracts, in the same session), `dynamodb-schema-access-pattern-reviewer` when a stack the Story builds in holds a DynamoDB store, `spec-reviewer`, and `review-dispute-decider` for each finding an author disputes. The other agents here are available to a caller that chooses them. 12 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `spec-authoring-lead` | Manager | Delegator, Orchestrator |
| `ui-design-source-selector` | Worker | Advisor |
| `api-specification-author` | Worker | Executor |
| `data-model-specification-author` | Worker | Executor |
| `acceptance-criteria-writer` | Worker | Executor |
| `definition-of-done-writer` | Worker | Executor |
| `dynamodb-schema-access-pattern-reviewer` | Worker | Validator |
| `spec-reviewer` | Worker | Validator |
| `acceptance-criteria-reviewer` | Worker | Validator |
| `event-schema-reviewer` | Worker | Validator |
| `graphql-schema-reviewer` | Worker | Validator |
| `review-dispute-decider` | Worker | Decider |

### Planning and Scoring — Execution Team

Elaboration starts `task-decomposer` and `task-dependency-mapper`; `task-dependency-assessment` also starts the mapper for a Task created outside elaboration, `dependency-assessment` starts `epic-dependency-assessor`, and `wsjf-scoring` starts `wsjf-scorer`. Elaboration writes Stories by script, so `story-bead-writer` serves a Story written outside it. The reviewers are available to a caller that chooses them. 8 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `task-decomposer` | Worker | Executor |
| `task-dependency-mapper` | Worker | Executor |
| `epic-dependency-assessor` | Worker | Advisor |
| `wsjf-scorer` | Worker | Executor |
| `wsjf-scoring-reviewer` | Worker | Validator |
| `story-bead-writer` | Worker | Executor |
| `user-story-reviewer` | Worker | Validator |
| `beads-format-validator` | Worker | Validator |

### Built Version — Execution Team

`built-version` starts the comparer and, when it records a difference, `architecture-maintainer` and the conformance reviewer, after a Story's deploy to AWS dev is verified. 2 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `built-architecture-comparer` | Worker | Validator |
| `architecture-conformance-reviewer` | Worker | Validator |

### Spec Freshness — Execution Team

No workflow starts these agents; they remain for a spec written well before its build. 3 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `spec-freshness-lead` | Manager | Delegator, Orchestrator |
| `spec-currency-validator` | Worker | Validator |
| `dependency-change-detector` | Worker | Validator |

### Test Design — Execution Team

`task-to-deploy` has `test-design-lead` select the test writers the accepted execution policy and the Task's surfaces call for, and starts `test-strategy-decider` only for a strategy concern that selection names as unresolved. The other agents here are available to a caller that chooses them. 16 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `test-design-lead` | Manager | Delegator, Orchestrator |
| `tdd-unit-test-generator` | Worker | Executor (test author) |
| `consumer-driven-contract-test-writer` | Worker | Executor (test author) |
| `security-test-case-designer` | Worker | Executor (test author) |
| `aws-integration-test-writer` | Worker | Executor (test author) |
| `playwright-e2e-web-test-writer` | Worker | Executor (test author) |
| `performance-benchmark-writer` | Worker | Executor (test author) |
| `xcuitest-writer` | Worker | Executor (test author) |
| `espresso-test-writer` | Worker | Executor (test author) |
| `mobile-e2e-test-writer` | Worker | Executor (test author) |
| `ml-evaluation-tester` | Worker | Executor (test author) |
| `data-pipeline-test-writer` | Worker | Executor (test author) |
| `acceptance-criteria-coverage-assessor` | Worker | Validator |
| `test-plan-strategy-reviewer` | Worker | Validator |
| `test-isolation-specialist` | Worker | Validator |
| `test-strategy-decider` | Worker | Decider |

### Implementation — Execution Team

`tdd-green` starts `implementation-lead` to select the implementers, then each selected implementer in turn. Every implementer loads the `implementer-contract` skill. `task-to-deploy` also starts `cdk-stack-author` for an infrastructure Task. 35 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `implementation-lead` | Manager | Delegator, Orchestrator |
| `chassis-extension-implementer` | Worker | Executor |
| `api-gateway-cdk-implementer` | Worker | Executor |
| `cdk-stack-author` | Worker | Executor |
| `event-api-client-implementer` | Worker | Executor |
| `event-driven-consumer-implementer` | Worker | Executor |
| `dynamodb-access-layer-implementer` | Worker | Executor |
| `postgresql-access-layer-implementer` | Worker | Executor |
| `power-tools-configuration-implementer` | Worker | Executor |
| `cognito-lambda-trigger-implementer` | Worker | Executor |
| `webauthn-implementer` | Worker | Executor |
| `cds-ui-implementer` | Worker | Executor |
| `nextjs-component-implementer` | Worker | Executor |
| `appsync-cdk-implementer` | Worker | Executor |
| `appsync-client-subscription-implementer` | Worker | Executor |
| `ios-swiftui-implementer` | Worker | Executor |
| `android-compose-implementer` | Worker | Executor |
| `react-native-implementer` | Worker | Executor |
| `bedrock-integration-implementer` | Worker | Executor |
| `llm-observability-implementer` | Worker | Executor |
| `sagemaker-implementer` | Worker | Executor |
| `applied-ai-services-implementer` | Worker | Executor |
| `agentcore-agent-implementer` | Worker | Executor |
| `vector-search-embeddings-implementer` | Worker | Executor |
| `matching-algorithm-implementer` | Worker | Executor |
| `recommendation-engine-implementer` | Worker | Executor |
| `behavioral-signals-implementer` | Worker | Executor |
| `mcp-server-implementer` | Worker | Executor |
| `glue-etl-implementer` | Worker | Executor |
| `kinesis-stream-implementer` | Worker | Executor |
| `dynamodb-streams-cdc-implementer` | Worker | Executor |
| `s3-data-lake-implementer` | Worker | Executor |
| `athena-redshift-analytics-implementer` | Worker | Executor |
| `payments-integration-implementer` | Worker | Executor |
| `email-notification-implementer` | Worker | Executor |

### Code Quality — Execution Team

`task-to-deploy` starts `code-refactoring-specialist` for the refactoring opportunity the accepted execution policy keeps, and it decides which refactorings the changed files need. The other agents here are available to a caller that chooses them. 9 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `code-quality-lead` | Manager | Delegator, Orchestrator |
| `complexity-analyzer` | Worker | Advisor |
| `code-refactoring-specialist` | Worker | Executor |
| `lint-finding-fixer` | Worker | Executor |
| `lambda-performance-optimizer` | Worker | Executor |
| `dynamodb-cost-optimizer` | Worker | Executor |
| `frontend-performance-optimizer` | Worker | Executor |
| `code-correctness-reviewer` | Worker | Validator |
| `accessibility-validator` | Worker | Validator |

### Integration Testing — Execution Team

No workflow starts these agents; each is available to a caller that chooses it. 9 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `integration-testing-lead` | Manager | Delegator, Orchestrator |
| `cross-repo-integration-test-coordinator` | Worker | Orchestrator |
| `test-environment-provisioner` | Worker | Executor |
| `aws-integration-test-runner` | Worker | Validator |
| `event-flow-tester` | Worker | Validator |
| `data-consistency-checker` | Worker | Validator |
| `cross-service-contract-tester` | Worker | Validator |
| `flaky-test-detector` | Worker | Validator |
| `root-cause-analyst` | Worker | Advisor |

### Adversarial Validation — Execution Team

`adversarial` starts the attackers its lanes call for against the designated test environment and test identities the caller names, then `adversarial-critique-adjudicator`. No build or deploy step runs it. 11 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `adversarial-review-loop-supervisor` | Manager | Delegator, Orchestrator |
| `injection-attack-tester` | Worker | Adversary |
| `auth-bypass-tester` | Worker | Adversary |
| `permission-escalation-tester` | Worker | Adversary |
| `race-condition-tester` | Worker | Adversary |
| `contract-violation-tester` | Worker | Adversary |
| `dependency-cve-auditor` | Worker | Validator |
| `dos-resilience-tester` | Worker | Adversary |
| `data-exposure-scanner` | Worker | Validator |
| `infrastructure-security-scanner` | Worker | Validator |
| `adversarial-critique-adjudicator` | Worker | Decider (Referee) |

### Deployment and Landing — Execution Team

The Story's Python driver publishes, synthesizes, deploys and verifies directly. A failed deployment starts the genuine deploy-failure-fixer through the Python story-deploy-fix leaf. Normal git operations run directly; worktree-lander remains available for assignments that require actual hook-code remediation or landing judgment.

| Agent | Role | Character Types |
| --- | --- | --- |
| `deployment-lead` | Manager | Delegator, Orchestrator |
| `smoke-test-author` | Worker | Executor (test author) |
| `dev-deployer` | Worker | Executor |
| `deploy-failure-fixer` | Worker | Executor |
| `worktree-lander` | Worker | Executor |
| `github-actions-pipeline-implementer` | Worker | Executor |
| `cdk-infrastructure-drift-detector` | Worker | Validator |
| `slo-error-budget-designer` | Worker | Advisor |
| `finops-analyst` | Worker | Advisor |
| `incident-response-runbook-designer` | Worker | Executor |
| `production-readiness-review-facilitator` | Worker | Orchestrator |
| `deployment-strategy-decider` | Worker | Decider |

### Documentation — Execution Team

`documentation` starts `documentation-currency-auditor`, then each writer it assigns stale documents to, each followed by `documentation-accuracy-reviewer`. `filing-clerk` files a fact in the documentation vault when a person or the steward asks. 9 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `documentation-lead` | Manager | Delegator, Orchestrator |
| `documentation-currency-auditor` | Worker | Validator |
| `api-documentation-writer` | Worker | Executor |
| `readme-writer` | Worker | Executor |
| `changelog-writer` | Worker | Executor |
| `user-guide-writer` | Worker | Executor |
| `developer-documentation-writer` | Worker | Executor |
| `documentation-accuracy-reviewer` | Worker | Validator |
| `filing-clerk` | Specialist | Executor |

### Cumulative Regression Assurance — Execution Team

`task-to-deploy` starts the assessor to write the regression scope, then the Task's execution policy, and, after Green, the mapping of tests to requirements; the reviewer reviews the scope and the mapping, and a script checks the policy. 2 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `regression-impact-assessor` | Worker | Advisor |
| `regression-coverage-reviewer` | Worker | Validator |

### Workflow Helpers — Standalone Specialists

Specialists for genuine configuration, design-system and shared-capability judgment. 4 agents.

| Agent | Role | Character Types |
| --- | --- | --- |
| `test-command-resolver` | Specialist | Advisor |
| `cds-live-auditor` | Specialist | Validator |
| `cds-finding-reviewer` | Specialist | Validator |
| `shared-capability-reviewer` | Specialist | Validator |

### Standalone — Standalone Specialists

Reached through the `polyrepo-router` skill or the `/polyrepo-steward` command; `deploy-mechanism` also asks it what a repository publishes and deploys. 1 agent.

| Agent | Role | Character Types |
| --- | --- | --- |
| `polyrepo-steward` | Specialist | Executor |

## The full roster, in detail

Every agent, with the team it is rostered under, its role, character types, task category, responsibility, and the skills and tools it is granted (MCP tools are not listed).

| Agent | Team | Team Type | Role | Character Types | Category | Responsibility | Skills | Tools |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `phase-gate-enforcer` | Governance | Standalone Specialists | Specialist | Validator, Decider (Referee) | approve | Rules pass, loop or escalate on the constitutive criteria of one phase gate, from the criteria and the artifact the gate-enforce workflow quotes: loop when the cause of an unmet criterion is inside the phase, escalate when it is upstream, naming where it goes back to. Deterministic checks and competitive criteria are settled by the gate script and never reach it. | subagent-contract, validation-protocol | Read, Glob, Grep, Agent |
| `exhausted-gate-ruler` | Governance | Standalone Specialists | Specialist | Decider | approve | Rules how a run continues from a phase gate whose loops are spent: proceed, with the latest output standing and every unmet criterion carried on as a named residual with its mitigation, or one directed revision under a concrete, changed instruction. Started by the gate-enforce workflow in its exhaustion mode. | subagent-contract, validation-protocol | Read, Glob, Grep, Agent |
| `advantage-evaluator` | Governance | Standalone Specialists | Specialist | Validator, Decider | approve | Rules commit or revert on a competitive (non-constitutive) finding that work was allowed to proceed under: before the outcome exists it states the observation window and the evidence that will decide, then judges the observed outcome against it. Speculative execution with rollback, so a tradeable finding never halts a run. Use when a caller proceeded past a competitive gate flag or a non-blocking concern and needs it closed on evidence. | subagent-contract, validation-protocol | Read, Glob, Grep, Write, Agent |
| `constitutional-agent` | Governance | Standalone Specialists | Specialist | Decider | approve | Rules on a conflict between two constitutive constraints that no gate can settle: establishes the constitutional layer the conflict falls under (the owner's section 2 constraints and settled decisions recorded in the matrix, the business outcomes of the PRD the work serves, and the review standard's acceptance basis), names which constraint prevails and under what conditions, and writes the ruling as a precedent record a later conflict can cite. Use when two constraints that each define validity cannot both be met. | subagent-contract, validation-protocol, effective-architecture, matrix | Read, Glob, Grep, Write, Bash, Agent |
| `context-curator` | Governance | Standalone Specialists | Specialist | Executor | execute | Assembles a context index for one receiving agent and task: a file of pointers (paths, headings, matrix ids and atw-matrix commands) to exactly what the role needs, with every constitutive constraint that binds it carried by pointer to its one home, never copied or summarized, and keeps the constraint manifest those pointers come from current. Use when starting a session by hand that needs its context assembled under least context; the orchestrator's own briefs already carry paths only. | subagent-contract, validation-protocol, matrix | Read, Write, Edit, Glob, Grep, Agent |
| `stakeholder-request-intake-writer` | PRD Creation | Execution Team | Worker | Executor | execute | Turns one raw stakeholder request into the structured intake of a feature: the scope the request frames (what it asks for and what it leaves out), the problem, the audience, the desired outcome, the constraints it states and the open questions it leaves, WHAT the users need and never HOW to build it. Use as the intake step of PRD creation. | subagent-contract, validation-protocol, product-discovery | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `feature-persona-writer` | PRD Creation | Execution Team | Worker | Executor | execute | Writes the one target persona a feature serves, grounded in the audience, problem and outcome of the feature's intake: a proto-persona whose goals, frustrations and context are each stated, inferred or marked as an assumption, behavior over demographics. Use as the persona step of PRD creation. | subagent-contract, validation-protocol, persona-research | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `feature-objective-writer` | PRD Creation | Execution Team | Worker | Executor | execute | Writes the one objective a feature must move and the key results that prove it was met, grounded in the feature's intake: a qualitative, user-centered objective and measurable key results, each with its metric and target. Use as the objective step of PRD creation. | subagent-contract, validation-protocol, product-analytics | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `prd-writer` | PRD Creation | Execution Team | Worker | Executor | execute | Writes a template-conformant PRD, WHAT and never HOW, from a feature's intake, persona and objective, with acceptance criteria for its P0 requirements, and the one-paragraph scope of the Epic that pairs with it; on a revision, applies the alignment verdict on its previous draft. Use as the drafting step of PRD creation. | subagent-contract, validation-protocol, prd-writer, matrix, acceptance-criteria | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `prd-alignment-verifier` | PRD Creation | Execution Team | Worker | Validator | test | Independently judges whether a draft PRD aligns with the intake brief, persona and objective it was written from, and is template-conformant and WHAT-not-HOW, on four dimensions (intake, persona, objective, template). Use as the checker of the PRD draft in PRD creation. | subagent-contract, validation-protocol, prd-writer | Read, Glob, Grep, Bash, Write, Agent |
| `prd-validation-lead` | PRD Validation | Execution Team | Manager | Delegator, Orchestrator | orchestrate | Manual-only coordinator for explicitly assigned PRD validation work. Selects bounded analysts and routes their findings without making solution or approval decisions. The active prd-validation mini dispatches its lens specialists itself and does not dispatch this lead. | subagent-contract, agent-orchestration, prd-writer | Read, Glob, Grep, Agent, SendMessage |
| `requirement-classifier` | PRD Validation | Execution Team | Worker | Validator | test | Classifies every requirement a PRD states as business or technical and, for each technical rule, asks the matrix whether the architecture already states it; never rewrites the PRD. Use for the requirement-class lens of PRD validation. | subagent-contract, validation-protocol, artifact-handoff, prd-writer | Read, Glob, Grep, Bash, Write, Agent |
| `ambiguity-detector` | PRD Validation | Execution Team | Worker | Validator | test | Finds the requirements of a PRD whose user-observable behavior is unclear, contradictory within itself or open to two incompatible readings (vague quantifiers, missing user-observable boundary conditions, unstated assumptions); reports each with a concrete clarification, never fixes. Use for the ambiguity lens of PRD validation. | subagent-contract, validation-protocol, artifact-handoff, prd-writer | Read, Glob, Grep, Bash, Write, Agent |
| `completeness-checker` | PRD Validation | Execution Team | Worker | Validator | test | Checks that each requirement of a PRD has an actor, a trigger or action, an observable user outcome and a behavioral acceptance criterion, and reports each missing or defective element; never supplies one. Use for the completeness lens of PRD validation. | subagent-contract, validation-protocol, artifact-handoff, prd-writer | Read, Glob, Grep, Bash, Write, Agent |
| `requirements-conflict-detector` | PRD Validation | Execution Team | Worker | Validator | test | Finds sets of requirements in a PRD whose WHAT cannot all hold, citing the requirements in tension; never resolves them. Use for the conflict lens of PRD validation. | subagent-contract, validation-protocol, artifact-handoff, prd-writer, acceptance-criteria | Read, Glob, Grep, Bash, Write, Agent |
| `constraint-extractor` | PRD Validation | Execution Team | Worker | Executor | execute | Extracts the explicit and implied constraints a PRD imposes (regulatory, business, platform, policy), each with its kind and where the PRD states or implies it; invents none. Use for the constraints lens of PRD validation. | subagent-contract, validation-protocol, artifact-handoff, prd-writer | Read, Glob, Grep, Bash, Write, Agent |
| `domain-boundary-validator` | PRD Validation | Execution Team | Worker | Validator | test | Checks that a PRD's requirements stay inside one bounded context, and reports each requirement that makes the feature own behavior another feature or service owns or that sits in more than one context. Use for the domain-boundary lens of PRD validation. | subagent-contract, validation-protocol, artifact-handoff, prd-writer | Read, Glob, Grep, Bash, Write, Agent |
| `requirements-clarifier` | PRD Validation | Execution Team | Worker | Advisor | plan | Raises the open BUSINESS questions a PRD's author must answer before it can be specified, each tied to its requirement and unresolved; never answers them and never raises a technical gap. Use for the clarification lens of PRD validation. | subagent-contract, validation-protocol, artifact-handoff, prd-writer | Read, Glob, Grep, Bash, Write, Agent |
| `brd-traceability-auditor` | PRD Validation | Execution Team | Worker | Validator | test | Maps each PRD requirement to the objectives of a BRD the run names, for information only: a correspondence, never a verdict on the PRD. Use for the informational BRD traceability lens of PRD validation. | subagent-contract, validation-protocol, artifact-handoff, prd-writer | Read, Glob, Grep, Bash, Write, Agent |
| `nfr-analyst` | PRD Validation | Execution Team | Worker | Advisor | plan | Lists the non-functional quality intents a PRD states or implies (performance, availability, security, privacy, accessibility, operability and the rest), each tied to the requirements that state or imply it, as input to a TRD; never quantifies them and never reports them as defects of the PRD. Available to a caller that chooses it; no workflow dispatches it. | subagent-contract, prd-writer | Read, Glob, Grep, Write, Agent |
| `aws-solutions-architect` | Architecture | Execution Team | Worker | Executor | execute | Hold single responsibility for the architecture a PRD needs, from the first read of the PRD until the architecture and the TRD are designed, reviewed and approved, with the review log that proves how. | effective-architecture, subagent-contract, find-specialists, senior-architect, aws-solution-architect, python-lambda-packaging, aws-serverless-eda, senior-security, graphrag-lookup, aws-core:aws-serverless, aws-core:aws-well-architected-review, aws-core:aws-security, aws-core:aws-billing-and-cost-management, log-architecture-review, aws-core:aws-database, matrix | Read, Glob, Grep, Bash, Write |
| `architecture-team-lead` | Architecture | Execution Team | Worker | Orchestrator | orchestrate | Route what the solutions architect could not settle, so that the team settles it with the least further work. | effective-architecture, subagent-contract, find-specialists | Read, Glob, Grep, Bash, Write |
| `architecture-decider` | Architecture | Execution Team | Worker | Decider | approve | Rule between the positions on an architecture matter the solutions architect and the architecture team lead could not settle, from the evidence each position carries, and record the ruling in the matrix as the settlement of the disagreement. | effective-architecture, subagent-contract, validation-protocol, senior-architect, aws-solution-architect, python-lambda-packaging, matrix | Read, Glob, Grep, Write, Bash |
| `architecture-maintainer` | Architecture | Execution Team | Worker | Executor | execute | Write the solutions architect's decisions into the architecture documents (arc42 and detailed/), each fact in its one home with links from every other document, and correct the effective documents to match what a Story built. | effective-architecture, subagent-contract, arc42-maintain | Read, Write, Edit, Glob, Grep, Bash |
| `architecture-diagram-author` | Architecture | Execution Team | Specialist | Executor | execute | Draw one architecture diagram of a design the solutions architect has settled, of any view type the documentation model lists (C4, UML, context map, data flow, deployment and the others), and return it with its home, view type and the elements it shows. | subagent-contract, design-specialist-contract, architecture-diagramming, c4-diagramming, uml-diagramming, effective-architecture | Read, Write, Edit, Glob, Grep, Bash |
| `c4-diagram-author` | Architecture | Execution Team | Specialist | Executor | execute | Draw one C4 diagram (system context, container, component or deployment) of a design the solutions architect has settled, and return it with its home, view type and the elements it shows. | subagent-contract, design-specialist-contract, architecture-diagramming, c4-diagramming, effective-architecture | Read, Write, Edit, Glob, Grep, Bash |
| `uml-diagram-author` | Architecture | Execution Team | Specialist | Executor | execute | Draw one UML diagram (sequence, state, activity, class, component or deployment) of a design the solutions architect has settled, and return it with its home, view type and the elements it shows. | subagent-contract, design-specialist-contract, architecture-diagramming, uml-diagramming, effective-architecture | Read, Write, Edit, Glob, Grep, Bash |
| `architecture-impact-analyst` | Architecture | Execution Team | Worker | Analyst | test | Judges what an architecture change reaches. Given the architecture views an integration changed, created or deleted, it takes from the matrix every Epic, open Task and entry those views reach (`atw-matrix impact`, `affected`), and rules on each one: unaffected, not yet elaborated, elaborated but unbuilt, or already built, with a knock-on Task proposed for each built item. It changes no bead and writes no code or document; it writes only its result file. Use after an architecture change created, changed or retired architecture views. | artifact-handoff, subagent-contract, beads-contract, validation-protocol, senior-architect, graphrag-lookup, matrix | Read, Glob, Grep, Bash, Write, Agent |
| `architecture-fitness-function-author` | Architecture | Execution Team | Worker | Executor | execute | Defines testable assertions from the owner's constraints and the architecture decisions, e.g. "every Lambda uses the configured logging library", "no service reads another service's table". Use for Architecture Analysis work requiring fitness function authoring, constraint formalization, and conformance criteria. | artifact-handoff, subagent-contract, validation-protocol, senior-architect, python-coding, software-engineering, graphrag-lookup, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `ubiquitous-language-writer` | Architecture | Execution Team | Worker | Executor | execute | Captures each bounded context's ubiquitous language — terms, definitions, usage rules — as a maintained glossary. Use for Architecture Analysis work requiring domain glossary authoring, terminology consistency, and language-to-code alignment. | subagent-contract, validation-protocol, senior-architect | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `bounded-context-mapper` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on bounded contexts: their boundaries, domain responsibilities, which service owns each, the relationships between contexts and the published language each exposes. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, senior-architect | Read, Write, Glob, Grep, Bash |
| `domain-event-modeler` | Design Specialists | Standalone Specialists | Specialist | Executor | plan | Answer a question or do a bounded piece of design for the solutions architect on domain events as facts: which fact each event states, the bounded context and aggregate that owns it, what triggers it, the causal flow it belongs to and the business meaning of the data it carries. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, senior-architect | Read, Write, Glob, Grep, Bash |
| `data-architect` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on pure data architecture independent of any engine — conceptual and logical data models, entities and relationships, which domain owns each entity and its system of record, data flows and lineage, reference and master data, data classification and retention classes, operational versus analytical data, and data contracts between domains. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, data-architecture | Read, Write, Glob, Grep, Bash |
| `persistence-architecture-specialist` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on which store holds each data set (DynamoDB, Aurora or RDS, ElastiCache or MemoryDB, Neptune, DocumentDB, Timestream, S3, EBS, EFS or FSx), which block owns each store, the consistency each scenario needs, and the data lifecycle across stores. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, data-architecture, aws-core:aws-database, aws-core:aws-storage | Read, Write, Glob, Grep, Bash |
| `integration-pattern-architect` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on how building blocks interact: which interactions are synchronous calls and which are events, the delivery path each takes (direct call, EventBridge rule, SNS fan-out, SQS buffer, Step Functions), and its end- to-end delivery guarantee, ordering, idempotency and failure behaviour. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-serverless-eda, senior-architect, aws-core:aws-messaging-and-streaming | Read, Write, Glob, Grep, Bash |
| `security-architecture-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on trust boundaries, the threat model of a design and the mitigation of each threat across those boundaries: who may cross each boundary and what each runtime may reach. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, senior-security | Read, Write, Glob, Grep, Bash |
| `cdk-infrastructure-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on which repository and which CDK stack hold each resource and building block, how stacks share values, which shared infrastructure must exist first, and construct and parameter names; and express the infrastructure the architecture records for a build Task as CDK provisioning intent. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-cdk-development, aws-core:aws-cdk, cdk-coding, resource-naming, matrix, python-lambda-packaging | Read, Write, Glob, Grep, Bash |
| `lambda-function-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on AWS Lambda functions: runtime and architecture, memory, timeout and ephemeral storage, concurrency (reserved and provisioned), SnapStart, layers, invocation model and event source mappings, asynchronous invocation destinations, VPC attachment and cold-start behaviour. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, lambda, aws-core:aws-serverless, python-lambda-packaging | Read, Write, Glob, Grep, Bash |
| `container-service-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on containers on Amazon ECS: Fargate or ECS Managed Instances or EC2 capacity, task definitions (CPU, memory, containers, health checks), services and their deployment and scaling, Amazon ECR repositories and image lifecycle. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-containers | Read, Write, Glob, Grep, Bash |
| `kubernetes-cluster-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on Amazon EKS: cluster version and access, compute (managed node groups, Karpenter, Fargate profiles, EKS Auto Mode), pod networking, workload identity, add-ons and pod scaling. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-containers | Read, Write, Glob, Grep, Bash |
| `ec2-fleet-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on Amazon EC2 fleets: instance type selection, AMIs, launch templates, Auto Scaling groups and their scaling policies, Spot and mixed instances, IMDSv2 and fleet operations through Systems Manager. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-compute | Read, Write, Glob, Grep, Bash |
| `batch-compute-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on AWS Batch: compute environments (Fargate, EC2, Spot), job queues and their priorities, job definitions, array and multi-node jobs, retries and timeouts, and scheduling policies. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-compute | Read, Write, Glob, Grep, Bash |
| `relational-database-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on relational databases on Amazon Aurora, Amazon RDS, Aurora DSQL and RDS Proxy — engine and cluster shape, capacity, access path, replicas, backups, and the relational schema (tables, keys, constraints, indexes, partitioning, migrations). | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aurora-postgresql, rds, design-postgres-tables, database-schema-designer, aws-core:aws-database | Read, Write, Glob, Grep, Bash |
| `dynamodb-table-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on Amazon DynamoDB and DAX — access-pattern-first single-table or multi-table design, partition and sort keys, GSIs and LSIs, capacity mode, TTL, streams, transactions, global tables, backups and cost. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, dynamodb, aws-core:aws-database | Read, Write, Glob, Grep, Bash |
| `cache-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on in-memory caching and in-memory data stores on Amazon ElastiCache (Valkey, Redis OSS, Memcached; serverless or node-based) and Amazon MemoryDB — caching pattern, key and TTL design, invalidation, eviction, topology, durability and multi-Region replication. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-database | Read, Write, Glob, Grep, Bash |
| `graph-database-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on graph data on Amazon Neptune Database and Neptune Analytics — engine and capacity choice, property graph or RDF, node and edge model, query language (openCypher, Gremlin, SPARQL), traversal and supernode design, loading, graph algorithms and vector search. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, amazon-neptune, aws-core:aws-database | Read, Write, Glob, Grep, Bash |
| `document-database-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on document data on Amazon DocumentDB (MongoDB compatible) — cluster type and capacity, document model (embedding or referencing), indexes, MongoDB API compatibility, change streams, transactions and read scaling. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-database | Read, Write, Glob, Grep, Bash |
| `time-series-database-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on time-series data on Amazon Timestream (Timestream for InfluxDB, and Timestream for LiveAnalytics for existing accounts) — engine choice, measurement, tag and field model, cardinality, retention and downsampling, ingestion and query. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-database | Read, Write, Glob, Grep, Bash |
| `object-storage-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on object storage on Amazon S3 and the S3 Glacier storage classes — buckets, key layout, storage classes and lifecycle, versioning and Object Lock, replication, access control and Block Public Access, presigned URLs, multipart upload and event notifications. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, s3, aws-core:aws-storage | Read, Write, Glob, Grep, Bash |
| `block-and-file-storage-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on block and file storage for EC2, containers and Lambda on Amazon EBS, Amazon EFS and Amazon FSx (Lustre, NetApp ONTAP, OpenZFS, Windows File Server) — volume and file system type, performance and throughput mode, availability, snapshots and backups, lifecycle tiering and access. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-storage | Read, Write, Glob, Grep, Bash |
| `vpc-network-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on Amazon VPC networking: CIDR plan, subnets and route tables, internet and NAT gateways, VPC endpoints (gateway and interface) and PrivateLink, security groups and network ACLs, Transit Gateway and peering, and VPC flow logs. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-networking | Read, Write, Glob, Grep, Bash |
| `load-balancer-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on Elastic Load Balancing: choosing an Application, Network or Gateway Load Balancer, listeners and TLS, routing rules, target groups and health checks, stickiness, deregistration and cross-zone behaviour. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup | Read, Write, Glob, Grep, Bash |
| `dns-and-edge-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on Amazon Route 53 and Amazon CloudFront: hosted zones, records and routing policies, health checks and failover, CloudFront distributions, origins and origin access control, cache and origin request policies, edge functions, and custom domains. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-networking | Read, Write, Glob, Grep, Bash |
| `api-contract-designer` | Design Specialists | Standalone Specialists | Specialist | Executor | plan | Answer a question or do a bounded piece of design for the solutions architect on REST APIs on Amazon API Gateway (REST API): which building block exposes each interface, its resources and methods, who may call it and how the caller is authorized, request validation, throttling and usage plans, errors, and how it stays compatible. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, api-gateway, api-design-reviewer, aws-core:aws-auth | Read, Write, Glob, Grep, Bash |
| `graphql-api-designer` | Design Specialists | Standalone Specialists | Specialist | Executor | plan | Answer a question or do a bounded piece of design for the solutions architect on GraphQL APIs on AWS AppSync: schema, operations and types, which block resolves each field from which owned data, resolvers and data sources, authorization modes, subscriptions, caching and compatibility. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, appsync-graphql, aws-core:aws-auth | Read, Write, Glob, Grep, Bash |
| `event-routing-designer` | Design Specialists | Standalone Specialists | Specialist | Executor | plan | Answer a question or do a bounded piece of design for the solutions architect on Amazon EventBridge: event type names and their registry entries, the payload schema of a new event type, buses, routing rules (event pattern, targets, owning stack), each rule target's retry policy and dead-letter queue, and EventBridge Scheduler schedules. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, eventbridge, aws-core:aws-serverless | Read, Write, Glob, Grep, Bash |
| `queue-and-topic-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on Amazon SQS queues and Amazon SNS topics: standard or FIFO, visibility timeout, retention, redrive policies and dead- letter queues, SNS subscriptions, filter policies and delivery retry, fan-out, and Amazon MQ where a broker protocol is required. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, sqs, sns, aws-core:aws-messaging-and-streaming | Read, Write, Glob, Grep, Bash |
| `workflow-orchestration-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on AWS Step Functions: Standard or Express workflows, state machine structure in Amazon States Language, service integration patterns, retries and catches, sagas and compensation, Map and Parallel states, callbacks, and execution logging. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, step-functions, aws-core:aws-serverless | Read, Write, Glob, Grep, Bash |
| `stream-processing-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on real-time data streams on Amazon Kinesis Data Streams, Amazon Data Firehose, Amazon MSK and Amazon Managed Service for Apache Flink — stream and capacity mode, partition keys and ordering, retention, consumers and fan-out, delivery buffering, transformation and processing windows. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-messaging-and-streaming, senior-data-engineer | Read, Write, Glob, Grep, Bash |
| `data-lake-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on the data lake on AWS Glue, AWS Lake Formation and Amazon S3 Tables — zones and table layout, open table format (Apache Iceberg), partitioning, the Glue Data Catalog, ingestion and ETL jobs, connections to sources, data quality and Lake Formation permissions. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-data-analytics:creating-data-lake-table, aws-data-analytics:ingesting-into-data-lake, aws-data-analytics:exploring-data-catalog, aws-data-analytics:connecting-to-data-source, senior-data-engineer | Read, Write, Glob, Grep, Bash |
| `analytics-query-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on serverless SQL analytics with Amazon Athena over the data lake — workgroups and their limits, query result handling, data layout for scan cost, partition projection, federated and Iceberg queries, CTAS and UNLOAD, and capacity. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-data-analytics:querying-data-lake, aws-data-analytics:finding-data-lake-assets | Read, Write, Glob, Grep, Bash |
| `data-warehouse-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on data warehousing on Amazon Redshift (Serverless or provisioned RA3) — workgroup or cluster shape, table design (distribution, sort keys, encoding), loading with COPY and zero-ETL, materialized views, data sharing, Spectrum and workload management. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-data-analytics:redshift-guide | Read, Write, Glob, Grep, Bash |
| `iam-policy-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on AWS IAM: roles and their trust policies, identity and resource policies with least privilege, condition keys and confused-deputy protection, permission boundaries, cross-account access, service-linked and service roles, and IAM Identity Center for human access. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, iam, aws-core:aws-iam | Read, Write, Glob, Grep, Bash |
| `user-authentication-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on end-user authentication with Amazon Cognito: user pools and app clients, sign-up and sign-in flows, MFA and passkeys, OAuth 2.0 and OIDC flows, social and SAML federation, tokens and their lifetimes, Lambda triggers, and identity pools. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, cognito, aws-core:aws-auth | Read, Write, Glob, Grep, Bash |
| `encryption-and-secrets-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on AWS KMS keys and key policies, envelope encryption and key rotation, AWS Secrets Manager secrets and their rotation, and AWS Certificate Manager certificates. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, secrets-manager, aws-core:aws-secrets-manager | Read, Write, Glob, Grep, Bash |
| `perimeter-protection-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on AWS WAF web ACLs and rules (managed rule groups, rate-based rules, bot control), AWS Shield Standard and Advanced for DDoS protection, Route 53 Resolver DNS Firewall, and Amazon GuardDuty threat detection. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-networking, aws-core:aws-security | Read, Write, Glob, Grep, Bash |
| `foundation-model-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on Amazon Bedrock foundation models - model and inference profile choice per task, Converse API calls, maxTokens and timeouts, quotas and throughput, prompt caching, attaching guardrails to a model call, and inference cost. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, bedrock, aws-core:amazon-bedrock | Read, Write, Glob, Grep, Bash |
| `rag-architecture-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on retrieval-augmented generation and semantic search - Bedrock Knowledge Bases, chunking, embeddings models, vector stores (Aurora pgvector, S3 Vectors, OpenSearch, Neptune Analytics), hybrid retrieval, re-ranking, metadata filtering and retrieval evaluation. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, rag-architect, pgvector-semantic-search, aurora-postgresql, recommendation-ranking, aws-data-analytics:storing-and-querying-vectors, aws-data-analytics:amazon-opensearch-service, aws-core:amazon-bedrock | Read, Write, Glob, Grep, Bash |
| `applied-ai-services-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on the AWS pre-trained AI services - Amazon Textract document extraction, Amazon Rekognition image and video analysis, and Amazon Comprehend text analysis and PII detection - their operations, synchronous or asynchronous paths, limits, confidence handling and cost. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup | Read, Write, Glob, Grep, Bash |
| `ml-feature-pipeline-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on machine learning features - feature definitions and engineering, batch or streaming computation, SageMaker Feature Store online and offline stores, SageMaker Data Wrangler data preparation, training-serving consistency and feature drift. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, senior-data-scientist, senior-ml-engineer, senior-data-engineer | Read, Write, Glob, Grep, Bash |
| `ml-training-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on training and fine-tuning models on Amazon SageMaker AI - base model and technique (SFT, DPO, RLVR, RLAIF), training data, training jobs, managed Spot and checkpointing, hyperparameter tuning, evaluation and acceptance, experiment tracking and retraining. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-ai-ml, senior-data-scientist, senior-ml-engineer | Read, Write, Glob, Grep, Bash |
| `ml-inference-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on serving trained models on Amazon SageMaker AI - real-time, serverless and asynchronous endpoints, batch transform, multi-model and multi-container endpoints, scaling, deployment guardrails and shadow tests, and Model Monitor. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-ai-ml, senior-ml-engineer | Read, Write, Glob, Grep, Bash |
| `ai-agent-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on custom AI agents - Amazon Bedrock AgentCore Runtime and Harness, agent frameworks such as Strands, AgentCore Memory, tools through AgentCore Gateway and MCP, multi-agent and A2A, AgentCore Identity and Cedar policies, and agent bounds. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-agentic-ai, aws-agents:agents-get-started, aws-agents:agents-build, aws-agents:agents-connect, aws-agents:agents-harden, mcp-server-builder, aws-core:amazon-bedrock | Read, Write, Glob, Grep, Bash |
| `generative-ai-pattern-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on generative AI flow patterns - prompt chaining, routing, parallelisation, orchestrator and workers, evaluator-optimiser loops, prompt structure, structured output, chain of verification, LLM-as-judge evaluation, human in the loop and applying guardrails to a flow. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, senior-prompt-engineer, cove-prompt-design, aws-core:amazon-bedrock | Read, Write, Glob, Grep, Bash |
| `monitoring-and-tracing-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on Amazon CloudWatch and AWS X-Ray: metrics and embedded metric format, log groups and retention, Logs Insights queries, alarms (metric, composite, anomaly detection) and their actions, dashboards, distributed tracing with X-Ray and ADOT, Application Signals, synthetics and SLO alarms. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-observability, cloudwatch, observability-designer | Read, Write, Glob, Grep, Bash |
| `audit-and-compliance-designer` | Design Specialists | Standalone Specialists | Specialist | Advisor | plan | Answer a question or do a bounded piece of design for the solutions architect on AWS CloudTrail (trails, management and data events, CloudTrail Lake, log integrity and retention) and AWS Config (recording, managed and custom rules, conformance packs, remediation), and the Security Hub controls they feed. | subagent-contract, design-specialist-contract, effective-architecture, graphrag-lookup, aws-core:aws-observability, aws-core:aws-security | Read, Write, Glob, Grep, Bash |
| `architecture-boundary-guardian` | Architecture Review Specialists | Standalone Specialists | Specialist | Validator | test | Review, for the solutions architect, the boundaries of a design: whether each building block's responsibilities and owned data stay inside its bounded context, whether every interface that crosses a boundary is explicit about who exposes it and who may call it, whether shared behaviour is taken from its shared home, and whether the design breaks a section 2 constraint or departs from an established pattern without a stated reason. | subagent-contract, design-specialist-contract, effective-architecture, senior-architect, graphrag-lookup, matrix | Read, Glob, Grep, Bash, Write |
| `architecture-pattern-challenger` | Architecture Review Specialists | Standalone Specialists | Specialist | Adversary | test | Review, for the solutions architect, the structure of a design for concrete weaknesses: a mechanism that does not do what the requirement needs, a structure more complex than the requirement, or an AWS pattern used against its documented best practice, each reported with the simpler sufficient repair. | subagent-contract, design-specialist-contract, effective-architecture, senior-architect, aws-solution-architect, python-lambda-packaging, aws-serverless-eda, aws-core:aws-well-architected-review | Read, Glob, Grep, Bash, Write |
| `architecture-tradeoff-skeptic` | Architecture Review Specialists | Standalone Specialists | Specialist | Adversary | test | Review, for the solutions architect, the trade-off claims of a design: whether each choice between options states the options and a reason the evidence supports, and whether the assumptions and estimates it rests on (latency, throughput, limits, effort) hold against the stated constraints and AWS documentation. | subagent-contract, design-specialist-contract, effective-architecture, senior-architect, aws-solution-architect, python-lambda-packaging, aws-core:aws-well-architected-review | Read, Glob, Grep, Bash, Write |
| `failure-mode-analyst` | Architecture Review Specialists | Standalone Specialists | Specialist | Advisor | test | Review, for the solutions architect, how a design fails and recovers: throttling, duplicate and out-of-order delivery, poison messages, downstream outages, timeouts, retries, dead-letter queues, idempotency and recovery paths across Lambda, SQS, SNS, EventBridge and the event path, as the runtime views and the TRD state them. | subagent-contract, design-specialist-contract, effective-architecture, aws-serverless-eda, lambda, sqs, eventbridge | Read, Glob, Grep, Bash, Write |
| `operational-readiness-reviewer` | Architecture Review Specialists | Standalone Specialists | Specialist | Validator | test | Review, for the solutions architect, whether a design can be operated: the logs, metrics, alarms and dashboards each block needs, the TRD's observability, availability and recovery obligations, how each failure is detected and who is told, and the operational burden at the stated usage. | subagent-contract, design-specialist-contract, effective-architecture, observability-designer, cloudwatch, aws-core:aws-observability | Read, Glob, Grep, Bash, Write |
| `new-resource-cost-reviewer` | Architecture Review Specialists | Standalone Specialists | Specialist | Advisor | test | Review, for the solutions architect, the cost of each billable AWS resource a design adds: its unit prices from the AWS Price List, the monthly unit math at the stated usage computed by script, its fixed monthly floor separated from its usage cost, and the total against the stated cost ceilings. | subagent-contract, design-specialist-contract, effective-architecture, aws-core:aws-billing-and-cost-management | Read, Glob, Grep, Bash, Write |
| `changed-resource-cost-reviewer` | Architecture Review Specialists | Standalone Specialists | Specialist | Adversary | test | Review, for the solutions architect, the cost effect of a design's changes to existing resources: changed billable limits, capacity modes, retention or usage, the cost assumptions each change rests on, a monthly floor it adds or moves, and any cost cliff (a pricing tier, free-tier limit, quota or capacity-mode boundary) the stated usage reaches. | subagent-contract, design-specialist-contract, effective-architecture, aws-core:aws-billing-and-cost-management, matrix | Read, Glob, Grep, Bash, Write |
| `trd-author` | TRD | Execution Team | Worker | Executor | execute | Complete the Epic's TRD once the architecture is decided, from the seed a script wrote from the constraints that bind the Epic, the requirements the PRD implies and the solutions architect's changes, and correct it where its confirmation finds it does not resolve. | subagent-contract, effective-architecture, matrix, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash |
| `prd-trd-traceability-verifier` | TRD | Execution Team | Worker | Validator | test | Builds and checks the TRD's SOURCE traceability matrix: every TRD requirement anchored to a PRD requirement OR to an architecture view, every PRD requirement needing technical elaboration answered, and genuine scope drift flagged. The relation is not 1:1 and an architecture-sourced requirement is not an orphan. Use for TRD Authoring work requiring requirement-to-technical-requirement tracing, architecture anchoring, and scope-drift detection. | subagent-contract, validation-protocol, effective-architecture | Read, Glob, Grep, Bash, Write, Agent |
| `trd-decider` | TRD | Execution Team | Worker | Decider | approve | Rules on a dispute over a TRD from the evidence the sides wrote: a TRD maker-checker deadlock, competing TRD approaches, or checkers that contradict each other on one TRD section; generates no TRD content or analysis. For a caller that runs a TRD review loop; in elaboration TRD disputes go to architecture-decider through the architecture team. | subagent-contract, validation-protocol, effective-architecture | Read, Glob, Grep, Write, Agent |
| `spec-authoring-lead` | Spec Authoring | Execution Team | Manager | Delegator, Orchestrator | orchestrate | Routes maker output to checkers and findings back to makers until checkers pass, then reports the spec packet; never evaluates spec quality, only pass/rework signals. Use for Spec Authoring work requiring maker-checker loop coordination, delegation, and read-only orchestration. | subagent-contract, agent-orchestration | Read, Glob, Grep, Agent, SendMessage |
| `ui-design-source-selector` | Spec Authoring | Execution Team | Worker | Advisor | plan | Owns the design source of each UI item, which is where UI and front-end screen design goes in this plugin - a screen's visual design, states, layout, components and accessibility come through the CDS route, never from the solutions architect or a front-end designer agent. Chooses, for each UI item a frontend repository's Story builds, the owner's cds bundle (mocks and stylesheets) where one packages it, otherwise the live Configurable Design System (cds), or no design change; cds-ui-implementer builds from the choice. Designs nothing itself. | subagent-contract, artifact-handoff, cds:apply-design-system, cds:audit-against-system | Read, Write, Glob, Grep, Bash |
| `api-specification-author` | Spec Authoring | Execution Team | Worker | Executor | execute | Write the spec of the API, event, error and UI contracts one repository's Story builds, from the recorded architecture and design, then the acceptance criteria and Definition of Done of that Story from the TRD, the contracts and the data model; designs nothing. | subagent-contract, validation-protocol, api-design-reviewer, artifact-handoff, effective-architecture, graphrag-lookup, matrix | Read, Write, Edit, Glob, Grep, Bash |
| `data-model-specification-author` | Spec Authoring | Execution Team | Worker | Executor | execute | Write the spec of the data one repository's Story builds, from the recorded architecture and design; designs nothing. | subagent-contract, validation-protocol, dynamodb, database-schema-designer, artifact-handoff, effective-architecture, aurora-postgresql, design-postgres-tables, pgvector-semantic-search, graphrag-lookup, matrix | Read, Write, Edit, Glob, Grep, Bash |
| `acceptance-criteria-writer` | Spec Authoring | Execution Team | Worker | Executor | execute | Derive traceable criteria and Definition of Done from the finished specification set. | subagent-contract, validation-protocol, artifact-handoff, effective-architecture, acceptance-criteria | Read, Write, Edit, Glob, Grep, Bash |
| `definition-of-done-writer` | Spec Authoring | Execution Team | Worker | Executor | execute | Writes the Definition of Done of a given scope of work as independently verifiable true-or-false statements about the finished work, never checklist steps, each traced to the requirement or design decision it comes from. For a caller that needs a Definition of Done on its own; in elaboration the api-specification-author writes it with the criteria. | subagent-contract, validation-protocol, effective-architecture, acceptance-criteria | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `dynamodb-schema-access-pattern-reviewer` | Spec Authoring | Execution Team | Worker | Validator | test | Reviews the DynamoDB stores of one repository's data-model spec: whether each access pattern it states can be served by the keys and indexes it states, at the stated capacity, without a scan or client-side filtering, and whether each store has the key attributes, indexes, access patterns and expiry attribute the detailed design records. Returns findings the data-model author can correct without interpretation; changes nothing. | subagent-contract, artifact-handoff, effective-architecture, dynamodb | Read, Glob, Grep, Bash, Write |
| `spec-reviewer` | Spec Authoring | Execution Team | Worker | Validator | test | Reviews one repository's three specification documents (the API, event and error contracts, the data model, and the acceptance criteria) against the specs-and-Tasks criteria I1 to I7 of the review standard, once, and returns findings a document's author can correct without interpretation; changes nothing. | subagent-contract, validation-protocol, api-design-reviewer, artifact-handoff, effective-architecture, acceptance-criteria, dynamodb, aurora-postgresql, design-postgres-tables, python-lambda-packaging | Read, Glob, Grep, Write |
| `acceptance-criteria-reviewer` | Spec Authoring | Execution Team | Worker | Validator | test | Reviews acceptance criteria and Definition of Done statements for testability, completeness and ambiguity: whether a test can be derived from each without interpretation, with boundary and failure cases covered; reports findings, never fixes. For a caller that wants criteria checked on their own; in elaboration spec-reviewer reviews the criteria document with the specs. | subagent-contract, validation-protocol, effective-architecture, acceptance-criteria | Read, Glob, Grep, Write, Agent |
| `event-schema-reviewer` | Spec Authoring | Execution Team | Worker | Validator | test | Validates event contracts against the project's standard event and each event's payload schema — event type names, passed values, publishing conditions, consumer obligations, retry/DLQ behavior. Use for Spec Authoring work requiring standard-event conformance, event contract validation, and failure-semantics checks. | subagent-contract, validation-protocol, eventbridge, sqs | Read, Glob, Grep, Bash, Write, Agent |
| `graphql-schema-reviewer` | Spec Authoring | Execution Team | Worker | Validator | test | Reviews the GraphQL contracts of a specification against the architecture and detailed design that record the API and against AppSync patterns: types, operations, resolver and data-source mappings, authorization modes and directives, error shapes, pagination and naming; reports findings, never fixes. For a caller that wants a spec's GraphQL contracts checked. | subagent-contract, validation-protocol, api-design-reviewer, effective-architecture, appsync-graphql | Read, Glob, Grep, Bash, Write, Agent |
| `review-dispute-decider` | Spec Authoring | Execution Team | Worker | Decider | approve | Rules on a review dispute between a maker and its reviewer, from the evidence the two sides wrote: each spec review finding a specification document's author disputes (the finding stands, with the directive the author applies, or the document stands), and a PRD draft the prd-writer and the prd-alignment-verifier could not converge on (accept or reject); writes no document content and no analysis of its own. | subagent-contract, validation-protocol, artifact-handoff, effective-architecture, prd-writer | Read, Glob, Grep, Write, Bash |
| `task-decomposer` | Planning and Scoring | Execution Team | Worker | Executor | execute | Decompose what one Story builds into coherent, sized build Tasks in one repository. | subagent-contract, validation-protocol, beads-contract, graphrag-lookup, artifact-handoff, wsjf, matrix | Read, Write, Edit, Glob, Grep, Bash |
| `task-dependency-mapper` | Planning and Scoring | Execution Team | Worker | Executor | execute | Maps the build dependencies between Tasks: an edge wherever one Task cannot be built until another is, because it consumes something the other provides. Proposes the cross-Story edges among the Tasks of one Epic's Stories, or every edge to or from one Task created outside elaboration; writes no edge itself. | subagent-contract, validation-protocol, beads-contract, artifact-handoff, graphrag-lookup, matrix | Read, Write, Edit, Glob, Grep, Bash |
| `epic-dependency-assessor` | Planning and Scoring | Execution Team | Worker | Advisor | plan | Proposes and validates the Epic-to-Epic edges to and from ONE Epic, by the shared-item rule of the epic-sequencing skill, and accounts for every owned edge standing on it; scores nothing and applies nothing. | subagent-contract, epic-sequencing, artifact-handoff, matrix | Read, Write, Bash, Glob, Grep, Agent |
| `wsjf-scorer` | Planning and Scoring | Execution Team | Worker | Executor | execute | Judges the WSJF inputs of work items under the wsjf skill's rubric: for an Epic its user-business value, time criticality and their confidence from its PRD, and its job size estimate while it is not sized from its Tasks; for the Tasks of an Epic their job sizes. Writes the judgments; computes no RR-OE and no WSJF, and writes nothing to a bead. | subagent-contract, validation-protocol, wsjf, beads-contract, artifact-handoff, matrix | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `wsjf-scoring-reviewer` | Planning and Scoring | Execution Team | Worker | Validator | test | Reviews the job sizes in a set of Task WSJF judgments for consistency, evidence and defensibility against the wsjf skill's rubric and recomputes the arithmetic; reports findings, never fixes. For a caller that wants a scoring run checked. | subagent-contract, validation-protocol, wsjf | Read, Glob, Grep, Bash, Write, Agent |
| `story-bead-writer` | Planning and Scoring | Execution Team | Worker | Executor | execute | Writes the title and description of ONE Story bead, a single-repository container paired with a spec set, and names the work outside the Story's repository that the Epic's closure in the matrix holds. For a caller that needs a Story written outside elaboration; elaboration writes its Stories by script. | subagent-contract, validation-protocol, matrix | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `user-story-reviewer` | Planning and Scoring | Execution Team | Worker | Validator | test | Reviews user stories (persona, goal, benefit and acceptance criteria) for completeness, testability and scope against the work each story covers and the spec it cites; reports findings, never fixes. For a caller that holds user stories, such as a PRD's or a person's backlog. | subagent-contract, validation-protocol, beads-contract | Read, Glob, Grep, Bash, Write, Agent |
| `beads-format-validator` | Planning and Scoring | Execution Team | Worker | Validator | test | Validates that Beads issues are structurally complete (title, acceptance criteria found where the beads contract looks, dependencies that resolve, spec links that resolve) and obey the hierarchy rule; reports defects, never fixes. For a caller that wants a set of issues checked before work starts. | subagent-contract, validation-protocol, beads-contract | Read, Glob, Grep, Bash, Write, Agent |
| `built-architecture-comparer` | Built Version | Execution Team | Worker | Validator | test | Compare the code one Story built with the approved architecture and design headings that describe the stacks and entries it built, and record each difference as an in-review view under built/<element>/, citing the code by file and line. | subagent-contract, effective-architecture, architecture-diagramming, graphrag-lookup, matrix | Read, Glob, Grep, Bash, Write, Agent |
| `architecture-conformance-reviewer` | Built Version | Execution Team | Worker | Validator | test | Check, without modifying anything, that a correction of the effective architecture documents describes each element exactly as the built views of a Story record it, at every scope, with conforming front matter and placement and section 2 untouched. | artifact-handoff, subagent-contract, validation-protocol, arc42, architecture-diagramming, graphrag-lookup, effective-architecture, matrix, python-lambda-packaging | Read, Glob, Grep, Bash, Write, Agent |
| `spec-freshness-lead` | Spec Freshness | Execution Team | Manager | Delegator, Orchestrator | orchestrate | Routes spec freshness checks to validators and aggregates findings into one freshness packet. Use for Spec Freshness phase work requiring delegation, validation routing, and packet assembly. No workflow currently dispatches it. | subagent-contract, agent-orchestration | Read, Glob, Grep, Agent, SendMessage |
| `spec-currency-validator` | Spec Freshness | Execution Team | Worker | Validator | test | Checks, before implementation begins, that a specification still matches the project: every module, interface, contract, data model, file path and convention it references still exists and still matches, each claim classed current, drifted or unverifiable with evidence. For a caller that holds a spec written some time before its build. | subagent-contract, validation-protocol, graphrag-lookup | Read, Glob, Grep, Bash, Write, Agent |
| `dependency-change-detector` | Spec Freshness | Execution Team | Worker | Validator | test | Detects dependency version and contract changes since a specification was written, by diffing manifests and lockfiles against the spec-time reference and checking changed contracts, classing each as unchanged, reconciled in the spec, or needing reconciliation. For a caller that holds a spec written some time before its build. | subagent-contract, validation-protocol, dependency-auditor, graphrag-lookup, python-lambda-packaging | Read, Glob, Grep, Bash, Write, Agent |
| `test-design-lead` | Test Design | Execution Team | Manager | Delegator, Orchestrator | orchestrate | Routes requirements and design to test writers working in the existing suite, and assembles trustworthy coverage evidence. Use for Test Design work requiring delegation and criterion-to-test routing. | subagent-contract, agent-orchestration, python-lambda-packaging | Read, Glob, Grep, Write, Agent, SendMessage |
| `tdd-unit-test-generator` | Test Design | Execution Team | Worker | Executor (test author) | test | Reviews, writes and refactors unit tests, including CDK assertion tests, within the existing suite against the full requirements and design; in update mode, rules on every existing test of any kind an implementer names (update, delete or keep, citing the contract) and applies the ruling. Python and TypeScript, back end, front end and CDK. | subagent-contract, validation-protocol, tdd-guide, cumulative-regression, python-coding, typescript-coding, web-frontend-coding, cdk-coding, software-engineering, graphrag-lookup, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `consumer-driven-contract-test-writer` | Test Design | Execution Team | Worker | Executor (test author) | test | Writes and improves consumer-driven contract tests from the spec's API and event contracts. Use for Test Design work requiring contract test authoring, consumer expectation modeling, and provider verification setup. | subagent-contract, validation-protocol, contract-testing, cumulative-regression, python-coding, software-engineering, graphrag-lookup, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `security-test-case-designer` | Test Design | Execution Team | Worker | Executor (test author) | test | Designs and improves security test cases from the threat model: abuse cases, negative paths, authorization matrices. Use for Test Design work requiring threat-model-driven test design, abuse case coverage, and authorization matrix verification. | subagent-contract, validation-protocol, senior-security, cumulative-regression, python-coding, software-engineering, graphrag-lookup, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `aws-integration-test-writer` | Test Design | Execution Team | Worker | Executor (test author) | test | Writes and improves integration tests covering the event delivery path the effective architecture describes, hop by hop. Use for Test Design work requiring AWS integration test authoring, event-driven flow assertions, and test harness design. | subagent-contract, validation-protocol, aws-serverless-eda, cumulative-regression, python-coding, software-engineering, aws-core:aws-sdk-python-usage, aws-core:aws-serverless, graphrag-lookup, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `playwright-e2e-web-test-writer` | Test Design | Execution Team | Worker | Executor (test author) | test | Writes and improves Playwright E2E web tests for UI and API flows from spec acceptance criteria. Use for Test Design work requiring E2E test authoring, user journey coverage, and suite outcome analysis. | subagent-contract, validation-protocol, senior-qa, cumulative-regression, graphrag-lookup, software-engineering, typescript-coding, web-frontend-coding | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `performance-benchmark-writer` | Test Design | Execution Team | Worker | Executor (test author) | test | Writes and improves performance benchmarks with budgets from the spec's non-functional requirements. Use for Test Design work requiring benchmark authoring, NFR-to-budget translation, and suite outcome analysis. | subagent-contract, validation-protocol, senior-qa, load-testing, cumulative-regression, python-coding, software-engineering, graphrag-lookup, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `xcuitest-writer` | Test Design | Execution Team | Worker | Executor (test author) | test | Writes and improves XCUITest suites for iOS features from spec acceptance criteria in existing-suite context, recording each observed reason. Use for Test Design work requiring XCUITest authoring, iOS UI flow coverage, accessibility-identifier queries, and Red confirmation. | subagent-contract, validation-protocol, ios-swiftui, tdd-guide, cumulative-regression, graphrag-lookup, software-engineering | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `espresso-test-writer` | Test Design | Execution Team | Worker | Executor (test author) | test | Writes and improves Espresso suites for Android features from spec acceptance criteria, recording actual outcomes against required behavior. Use for Test Design work requiring Espresso authoring, Android UI coverage, Compose semantics matchers, and suite outcome analysis. | subagent-contract, validation-protocol, android-compose, tdd-guide, cumulative-regression, graphrag-lookup, software-engineering | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `mobile-e2e-test-writer` | Test Design | Execution Team | Worker | Executor (test author) | test | Writes and improves Detox and Maestro E2E tests for React Native and cross-platform mobile flows in existing-suite context, recording each outcome for the intended reason. Use for Test Design work requiring mobile E2E authoring, Detox and Maestro scripting, and suite outcome analysis. | subagent-contract, validation-protocol, cumulative-regression, graphrag-lookup, software-engineering, typescript-coding, web-frontend-coding | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `ml-evaluation-tester` | Test Design | Execution Team | Worker | Executor (test author) | test | Writes and runs ML evaluation suites — matching quality, recommendation relevance, embedding drift — reviewing existing coverage and recording actual outcomes. Use for Test Design work requiring ML evaluation design, metric/threshold encoding, dataset construction, and drift detection. | subagent-contract, validation-protocol, senior-ml-engineer, senior-data-scientist, recommendation-ranking, cumulative-regression, python-coding, software-engineering, graphrag-lookup, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `data-pipeline-test-writer` | Test Design | Execution Team | Worker | Executor (test author) | test | Writes and improves data pipeline tests — ETL correctness, CDC ordering, data quality, replay safety — recording actual outcomes against the required behavior. Use for Test Design work requiring pipeline test authoring, data quality assertions, and replay-safety checks. | subagent-contract, validation-protocol, senior-data-engineer, cumulative-regression, python-coding, software-engineering, graphrag-lookup, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `acceptance-criteria-coverage-assessor` | Test Design | Execution Team | Worker | Validator | test | Reviews existing and newly authored suite coverage, including happy, negative, edge and boundary cases. Distinguishes poor tests and setup from product defects and environment failures using actual execution evidence. Reports findings without repairing tests or product code. | subagent-contract, validation-protocol, senior-qa, cumulative-regression, graphrag-lookup | Read, Glob, Grep, Bash, Write, Agent |
| `test-plan-strategy-reviewer` | Test Design | Execution Team | Worker | Validator | test | Reviews a feature's test plan and authored suites at the strategy level — balance across unit, contract, integration, E2E, security and performance layers, test investment in the spec's highest risks, feasibility of the environments the tests need, duplication and contradiction between suites — and reports findings only. Use when a caller wants the shape of a test strategy challenged. | subagent-contract, validation-protocol, senior-qa, cumulative-regression | Read, Glob, Grep, Bash, Write, Agent |
| `test-isolation-specialist` | Test Design | Execution Team | Worker | Validator | test | Validates that tests are independent — no shared mutable state, no order dependence, self-cleaning fixtures — by static inspection and by running the suites in shuffled order and repeatedly, and reports each isolation defect with a reproduction; never fixes. Use when a caller wants a suite's isolation checked before its results are trusted. | subagent-contract, validation-protocol, tdd-guide, graphrag-lookup | Read, Glob, Grep, Bash, Write, Agent |
| `test-strategy-decider` | Test Design | Execution Team | Worker | Decider | approve | Decides a feature's test strategy — pyramid shape across test layers, environment matrix per platform, coverage thresholds — from strategy analyses and reviewer findings others produced, with a recorded rationale and rejected alternatives; generates no analysis of its own. Use when a caller has strategy evidence that needs one accountable decision. | subagent-contract, validation-protocol, senior-qa | Read, Glob, Grep, Write, Agent |
| `implementation-lead` | Implementation | Execution Team | Manager | Delegator, Orchestrator | orchestrate | Selects the implementer(s) whose specialties cover a Task, in build order, from the Task's build contract — its spec documents and the architecture views it was designed against. Use for Implementation work requiring implementer selection. | subagent-contract, agent-orchestration, graphrag-lookup, python-lambda-packaging | Read, Glob, Grep, Agent |
| `chassis-extension-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements Lambda handlers as chassis superclass extensions for API endpoints and event consumers; writes minimum code to pass failing unit tests. Use for Implementation work requiring Lambda handlers, chassis extension, and endpoint/consumer business logic. | subagent-contract, implementer-contract, validation-protocol, aws-serverless-eda, graphrag-lookup, python-coding, software-engineering, aws-core:aws-serverless, aws-core:aws-sdk-python-usage, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `api-gateway-cdk-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements API Gateway resources, methods, and authorizers in CDK; writes minimum code to pass failing unit tests. Use for Implementation work requiring API Gateway constructs, CDK infrastructure, and authorizer wiring. | subagent-contract, implementer-contract, validation-protocol, api-gateway, aws-cdk-development, graphrag-lookup, python-coding, software-engineering, aws-core:aws-cdk, aws-core:aws-serverless, aws-core:aws-auth, cdk-coding, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `cdk-stack-author` | Implementation | Execution Team | Worker | Executor | execute | Writes AWS CDK stacks, constructs and app wiring in Python for an infrastructure Task, as the Task, its spec, the provisioning intent and the architecture give them, with the minimum change that makes the failing synth assertion tests pass. Never deploys. | subagent-contract, validation-protocol, aws-cdk-development, cloudformation, python-coding, software-engineering, aws-core:aws-cdk, graphrag-lookup, cdk-coding, implementer-contract, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `event-api-client-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements the calls a service makes to the project's central event API to publish the project's events. Use for Implementation work requiring event publishing calls, mapping of domain values to the API request, and event contract conformance. | subagent-contract, implementer-contract, validation-protocol, aws-serverless-eda, graphrag-lookup, python-coding, software-engineering, aws-core:aws-sdk-python-usage, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `event-driven-consumer-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements the handler code of a routing rule's target, for whatever target type the target's owner chose. Use for Implementation work requiring event handler logic, batch processing where the target delivers batches, and reading of the project's standard event. | subagent-contract, implementer-contract, validation-protocol, sqs, aws-serverless-eda, sns, graphrag-lookup, python-coding, software-engineering, aws-core:aws-serverless, aws-core:aws-sdk-python-usage, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `dynamodb-access-layer-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements DynamoDB access patterns from the data model spec; writes minimum code to pass failing tests. Use for Implementation work requiring single-table design, GSI query construction, and conditional write semantics. | subagent-contract, implementer-contract, validation-protocol, dynamodb, graphrag-lookup, python-coding, software-engineering, aws-core:aws-sdk-python-usage, aws-core:aws-database, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `postgresql-access-layer-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements Aurora PostgreSQL access patterns through the RDS Data API from the data model spec, and the schema migrations they need; writes minimum code to pass failing tests. Use for Implementation work requiring relational queries, transactions, migrations, and pgvector or recursive graph queries over a PostgreSQL store. | subagent-contract, implementer-contract, validation-protocol, aurora-postgresql, design-postgres-tables, graphrag-lookup, python-coding, software-engineering, aws-core:aws-sdk-python-usage, aws-core:aws-database, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `power-tools-configuration-implementer` | Implementation | Execution Team | Worker | Executor | execute | Configures Lambda Power Tools — structured logging, tracing, metrics, idempotency — on Lambdas built on the chassis; configures, never rebuilds. Use for Implementation work requiring Power Tools configuration, idempotency setup, and observability wiring. | subagent-contract, implementer-contract, validation-protocol, lambda, secrets-manager, graphrag-lookup, python-coding, software-engineering, aws-core:aws-serverless, aws-core:aws-observability, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `cognito-lambda-trigger-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements Cognito Lambda triggers — sign-up, confirmation, token customization, custom auth challenges — on the chassis the architecture describes. Use for Implementation work requiring Cognito trigger logic, auth flows, and user pool event processing. | subagent-contract, implementer-contract, validation-protocol, cognito, lambda, graphrag-lookup, python-coding, software-engineering, aws-core:aws-auth, aws-core:aws-serverless, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `webauthn-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements WebAuthn passkey flows across web clients and the Cognito-backed auth stack: registration and authentication ceremonies with client-side handling. Use for Implementation work requiring WebAuthn ceremony wiring, passkey credential lifecycle, and Cognito integration. | subagent-contract, implementer-contract, validation-protocol, graphrag-lookup, software-engineering, aws-core:aws-auth, typescript-coding, web-frontend-coding, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `cds-ui-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements a Task's web UI components and pages in the application repository with the Configurable Design System (cds) applied by construction, from the supplied cds bundle or the live design system, and audits the changed UI against it before reporting; writes the minimum code that makes the failing tests pass. | subagent-contract, implementer-contract, cds:apply-design-system, cds:audit-against-system, graphrag-lookup, software-engineering, typescript-coding, web-frontend-coding, python-lambda-packaging | Read, Write, Edit, Bash, Glob, Grep, Agent |
| `nextjs-component-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements the non-visual React/Next.js work — component state, data fetching, Next.js routing — writing minimum code to pass failing unit tests. Visual component and page work goes to cds-ui-implementer, which builds with the cds design system. | subagent-contract, implementer-contract, cds:apply-design-system, validation-protocol, graphrag-lookup, software-engineering, typescript-coding, web-frontend-coding, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `appsync-cdk-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements AppSync GraphQL APIs in CDK: schema wiring, resolvers, data sources, authorization. Use for Implementation work requiring AppSync API construction, resolver and data source wiring, and authorization setup. | subagent-contract, implementer-contract, validation-protocol, aws-cdk-development, graphrag-lookup, python-coding, software-engineering, aws-core:aws-cdk, cdk-coding, appsync-graphql, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `appsync-client-subscription-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements AppSync client subscriptions for real-time web features. Use for Implementation work requiring GraphQL subscription wiring, connection lifecycle handling, real-time state updates, and reconnection handling. | subagent-contract, implementer-contract, validation-protocol, senior-frontend, graphrag-lookup, software-engineering, typescript-coding, web-frontend-coding, appsync-graphql, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `ios-swiftui-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements iOS features in SwiftUI; writes minimum code to pass failing XCUITest suites. Use for Implementation work requiring SwiftUI views, StoreKit purchase flows, on-device CoreML integration, and passkey/WebAuthn client wiring. | subagent-contract, implementer-contract, ios-swiftui, validation-protocol, graphrag-lookup, software-engineering, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `android-compose-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements Android features in Kotlin and Jetpack Compose; writes minimum code to pass failing Espresso suites. Use for Implementation work requiring Compose UI, Kotlin state and navigation wiring, and on-device ML Kit integration. | subagent-contract, implementer-contract, android-compose, validation-protocol, graphrag-lookup, software-engineering, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `react-native-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements React Native cross-platform mobile features; writes minimum code to pass failing Detox and Maestro tests. Use for Implementation work requiring React Native components, navigation and state wiring, and native module integration. | subagent-contract, implementer-contract, validation-protocol, senior-frontend, graphrag-lookup, software-engineering, typescript-coding, web-frontend-coding, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `bedrock-integration-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements the code that calls Amazon Bedrock foundation models - Converse and ConverseStream calls, prompt assembly from specified templates, guardrail and prompt-cache settings on the call, structured-output parsing, and inference error handling - writing minimum code to pass failing tests. Embeddings calls belong to vector-search-embeddings-implementer. | subagent-contract, validation-protocol, bedrock, graphrag-lookup, python-coding, software-engineering, aws-core:amazon-bedrock, aws-core:aws-sdk-python-usage, implementer-contract, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `llm-observability-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements LLM observability — prompt/response logging, token and cost metrics, drift alerts — writing minimum code to pass failing tests. Use for Implementation work requiring LLM telemetry instrumentation, quality-signal capture, and drift alerting. | subagent-contract, validation-protocol, senior-ml-engineer, graphrag-lookup, python-coding, software-engineering, aws-core:aws-observability, aws-core:amazon-bedrock, implementer-contract, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `sagemaker-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements the code that runs models on Amazon SageMaker AI as the ml-training-designer and ml-inference-designer designs record them - training job launch and training entry scripts, model registration, inference handler scripts, and the calls that invoke real-time, serverless and asynchronous endpoints or start batch transform - writing minimum code to pass failing tests. Endpoint and other resource provisioning in CDK belongs to cdk-stack-author. | subagent-contract, validation-protocol, graphrag-lookup, python-coding, software-engineering, aws-core:aws-ai-ml, aws-core:aws-sdk-python-usage, senior-ml-engineer, implementer-contract, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `applied-ai-services-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements the code that calls the AWS pre-trained AI services as the applied-ai-services-designer design records it - Amazon Textract document extraction, Amazon Rekognition image and video analysis, and Amazon Comprehend text analysis and PII detection - with their synchronous and asynchronous paths, result paging, confidence thresholds and error handling, writing minimum code to pass failing tests. Foundation-model extraction belongs to bedrock-integration-implementer. | subagent-contract, validation-protocol, graphrag-lookup, python-coding, software-engineering, aws-core:aws-sdk-python-usage, aws-core:aws-serverless, implementer-contract, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `agentcore-agent-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements custom AI agent code on Amazon Bedrock AgentCore as the ai-agent-designer design records it - the Strands (or other specified framework) agent and its AgentCore Runtime entrypoint, AgentCore Memory sessions, tool wiring through AgentCore Gateway and MCP, and outbound credentials through AgentCore Identity - writing minimum code to pass failing tests. MCP servers and Gateway targets belong to mcp-server-implementer; direct model calls to bedrock-integration-implementer. | subagent-contract, validation-protocol, aws-agentic-ai, graphrag-lookup, python-coding, software-engineering, aws-agents:agents-build, aws-agents:agents-connect, aws-agents:agents-harden, aws-core:amazon-bedrock, aws-core:aws-sdk-python-usage, implementer-contract, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `vector-search-embeddings-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements vector search and embeddings for ML features — embedding generation, index read/write, similarity queries. Use for Implementation work requiring embedding pipelines, vector index access, and similarity queries. | subagent-contract, validation-protocol, graphrag-lookup, python-coding, software-engineering, aws-core:amazon-bedrock, aws-core:aws-sdk-python-usage, aurora-postgresql, pgvector-semantic-search, implementer-contract, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `matching-algorithm-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements matching algorithms - scoring functions, ranking and tie-breaking, candidate filtering, score normalisation and the composition of these stages into the specified matcher - writing minimum code to pass failing tests. Use for Implementation work requiring matching logic and scoring and ranking functions. | subagent-contract, validation-protocol, recommendation-ranking, graphrag-lookup, python-coding, software-engineering, implementer-contract, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `recommendation-engine-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements recommendation engine components for ML features; writes minimum code to pass failing unit tests. Use for Implementation work requiring recommendation pipeline assembly, candidate sourcing, re-ranking, and serving-layer composition. | subagent-contract, validation-protocol, recommendation-ranking, graphrag-lookup, python-coding, software-engineering, aws-core:aws-sdk-python-usage, implementer-contract, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `behavioral-signals-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements behavioral signal capture and feature pipelines feeding matching and recommendation models; minimum code to pass failing tests. Use for Implementation work requiring event signal capture, feature engineering, and ML feature delivery. | subagent-contract, validation-protocol, senior-data-engineer, graphrag-lookup, python-coding, software-engineering, aws-core:aws-sdk-python-usage, implementer-contract, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `mcp-server-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements MCP servers on AWS, including AgentCore Gateway-fronted deployments — tool definitions and schemas, authorization, transport config, CDK deployment wiring. Use for Implementation work requiring MCP tool definitions, gateway-fronted deployments, and CDK wiring. | subagent-contract, validation-protocol, mcp-server-builder, aws-agentic-ai, graphrag-lookup, python-coding, software-engineering, aws-core:amazon-bedrock, aws-core:aws-cdk, implementer-contract, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `glue-etl-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements Glue ETL jobs for batch data processing; writes minimum code to pass failing data-pipeline suites. Use for Implementation work requiring Glue job authoring, PySpark transformations, and batch pipeline construction. | subagent-contract, implementer-contract, validation-protocol, senior-data-engineer, graphrag-lookup, python-coding, software-engineering, aws-data-analytics:ingesting-into-data-lake, aws-data-analytics:connecting-to-data-source, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `kinesis-stream-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements Kinesis stream producers and consumers — record serialization, partition keys, checkpointing — writing minimum code to pass failing data-pipeline tests. Use for Implementation work requiring stream producer authoring, consumer logic, and event contract adherence. | subagent-contract, implementer-contract, validation-protocol, senior-data-engineer, aws-serverless-eda, graphrag-lookup, python-coding, software-engineering, aws-core:aws-messaging-and-streaming, aws-core:aws-sdk-python-usage, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `dynamodb-streams-cdc-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements change data capture from DynamoDB Streams; writes minimum code to pass failing data-pipeline test suites. Use for Implementation work requiring stream record processing, change event transformation, and exactly-once-effect handling. | subagent-contract, implementer-contract, validation-protocol, senior-data-engineer, dynamodb, graphrag-lookup, python-coding, software-engineering, aws-core:aws-serverless, aws-core:aws-sdk-python-usage, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `s3-data-lake-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements S3 data lake layout, partitioning, and lifecycle policies; writes minimum code to pass failing data-pipeline tests. Use for Implementation work requiring lake layout, partition key construction, and lifecycle policy definition. | subagent-contract, implementer-contract, validation-protocol, senior-data-engineer, s3, graphrag-lookup, python-coding, software-engineering, aws-core:aws-storage, aws-core:aws-sdk-python-usage, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `athena-redshift-analytics-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements Athena queries and Redshift analytics models over the data lake — tables, views, SQL — writing minimum code to pass failing data-pipeline tests. Use for Implementation work requiring analytics SQL authoring, external table definition, and warehouse modeling. | subagent-contract, implementer-contract, validation-protocol, senior-data-engineer, graphrag-lookup, python-coding, software-engineering, aws-data-analytics:redshift-guide, aws-data-analytics:querying-data-lake, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `payments-integration-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements Stripe payment features: checkout sessions, webhook handlers built on the chassis, subscription lifecycle, refunds, and idempotent operations, with secrets in Secrets Manager. Use for Implementation work requiring Stripe integration, payment webhook handling, and subscription lifecycle management. | subagent-contract, implementer-contract, validation-protocol, stripe-integration-expert, secrets-manager, graphrag-lookup, python-coding, software-engineering, aws-core:aws-serverless, aws-core:aws-secrets-manager, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `email-notification-implementer` | Implementation | Execution Team | Worker | Executor | execute | Implements transactional and notification email features: responsive templates, rendering pipelines, delivery through Amazon SES, and bounce/complaint handling. Use for Implementation work requiring email template construction and delivery wiring. | subagent-contract, implementer-contract, validation-protocol, email-template-builder, graphrag-lookup, python-coding, typescript-coding, software-engineering, aws-core:aws-sdk-python-usage, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `code-quality-lead` | Code Quality | Execution Team | Manager | Delegator, Orchestrator | orchestrate | Routes refactor work to specialists, verifies tests stay green after every change, and assembles the refactor evidence packet. Use for Code Quality work requiring delegation, refactor sequencing and green-test verification. | subagent-contract, agent-orchestration, python-lambda-packaging | Read, Glob, Grep, Agent, SendMessage |
| `complexity-analyzer` | Code Quality | Execution Team | Worker | Advisor | plan | Analyzes complexity and duplication in a green-tested change set and returns a prioritized refactor recommendation memo, with the optimizer specialties (Lambda, DynamoDB cost, front-end performance, lint fixing) the change calls for; performs no refactoring. Use when a caller wants refactoring targeted by evidence before it assigns the work. | subagent-contract, tech-debt-tracker, python-coding, graphrag-lookup, python-lambda-packaging | Read, Glob, Grep, Write, Agent |
| `code-refactoring-specialist` | Code Quality | Execution Team | Worker | Executor | execute | Refactors the code a change touched for clarity, cohesion, less complexity and less duplication without changing behavior: decides which refactorings the changed files need (none is a valid answer), applies them through GitNexus (impact before each symbol, rename for every rename, detect_changes before finishing), and keeps the test suite green or gives up so the caller restores the tree. | subagent-contract, validation-protocol, code-reviewer, graphrag-lookup, python-coding, software-engineering, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `lint-finding-fixer` | Code Quality | Execution Team | Worker | Executor | execute | Fixes the lint, format and type-check findings of a check report on a change set with the smallest style-level change, keeping tests green; never suppresses or reconfigures a rule. Use when a caller has a check report (a check runner's output or a hook's findings) whose findings must be fixed. | subagent-contract, validation-protocol, code-reviewer, python-coding, software-engineering, graphrag-lookup, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `lambda-performance-optimizer` | Code Quality | Execution Team | Worker | Executor | execute | Applies measured Lambda performance optimizations — cold start (init work, imports, bundle size), client and connection reuse, hot paths — to Lambda code whose tests are green, and recommends memory and timeout values with evidence, without changing behavior. Use when a caller assigns Lambda performance items. | subagent-contract, validation-protocol, lambda, python-coding, software-engineering, aws-core:aws-serverless, graphrag-lookup, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `dynamodb-cost-optimizer` | Code Quality | Execution Team | Worker | Executor | execute | Reduces the DynamoDB cost of code whose tests are green within the approved data model — scans replaced by keyed queries, batching, projections, pagination, fewer round trips — and recommends capacity-mode and index changes with a stated cost basis, without changing behavior or data semantics. Use when a caller assigns DynamoDB cost items. | subagent-contract, validation-protocol, dynamodb, aws-cost-operations, python-coding, software-engineering, aws-core:aws-database, graphrag-lookup, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `frontend-performance-optimizer` | Code Quality | Execution Team | Worker | Executor | execute | Applies measured frontend performance optimizations — bundle trimming, code splitting and lazy loading, render-path fixes, Core Web Vitals (LCP, INP, CLS) — to React and Next.js code whose tests are green, without changing behavior, accessibility or visual output. Use when a caller assigns frontend performance items. | subagent-contract, validation-protocol, senior-frontend, graphrag-lookup, software-engineering, typescript-coding, web-frontend-coding, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `code-correctness-reviewer` | Code Quality | Execution Team | Worker | Validator | test | Independently reviews a refactor or optimisation change set for correctness regressions and behavioral drift: re-runs the test suite itself, compares contracts, error and data semantics and side effects before and after, and flags modified, weakened or skipped tests and suppressed lint rules; reports findings, never fixes. Use when a caller wants an independent behaviour-preservation check of a change set. | subagent-contract, validation-protocol, code-reviewer, python-coding, graphrag-lookup, python-lambda-packaging | Read, Glob, Grep, Bash, Write, Agent |
| `accessibility-validator` | Code Quality | Execution Team | Worker | Validator | test | Validates UI changes against WCAG 2.2 A/AA — contrast, keyboard navigation, ARIA, focus management, screen-reader flows — reporting violations with locations and remediations; never fixes. Use for Code Quality work requiring WCAG validation, accessibility regression detection, and focus-order review. | subagent-contract, validation-protocol, a11y-audit, senior-frontend, graphrag-lookup | Read, Glob, Grep, Bash, Write, Agent |
| `integration-testing-lead` | Integration Testing | Execution Team | Manager | Delegator, Orchestrator | orchestrate | Read-only selector a caller invokes to choose the integration suites for a change when it cannot derive them from declared contract surfaces. Chooses the fewest applicable suites and whether provisioning must precede them, returning suites, provisionEnv and rationale. Does not dispatch workers, run tests, aggregate results, classify failures or judge gates. | subagent-contract, agent-orchestration | Read, Glob, Grep, Agent |
| `cross-repo-integration-test-coordinator` | Integration Testing | Execution Team | Worker | Orchestrator | orchestrate | Sequences cross-repo integration test runs over the event chain, aligns environment state between repos, and routes consolidated results to its caller. Coordinates only — runs no tests. Use for Integration Testing work requiring cross-repo sequencing, environment alignment, and result routing. | subagent-contract, agent-orchestration | Read, Glob, Grep, SendMessage, Agent |
| `test-environment-provisioner` | Integration Testing | Execution Team | Worker | Executor | execute | Provisions and resets integration test environments — the event path, functions and data stores the suites depend on — confirming readiness. Use for Integration Testing work requiring environment provisioning, state reset, fixture seeding, and readiness confirmation. | subagent-contract, validation-protocol, senior-devops, aws-mcp-setup, aws-core:aws-cdk, aurora-postgresql, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `aws-integration-test-runner` | Integration Testing | Execution Team | Worker | Validator | test | Runs AWS integration test suites against the provisioned test environment, reporting structured pass/fail, coverage, and flakiness results. Use for Integration Testing work requiring suite execution, coverage measurement, and flakiness detection. | subagent-contract, validation-protocol, cumulative-regression, graphrag-lookup | Read, Glob, Grep, Bash, Write, Agent |
| `event-flow-tester` | Integration Testing | Execution Team | Worker | Validator | test | Tests event flows end-to-end through the EventBridge-SQS-Lambda chain, verifying delivery, routing, retry, and dead-letter behavior per hop. Use for Integration Testing work requiring event-driven flow validation, EventBridge rule verification, and queue/consumer checks. | subagent-contract, validation-protocol, aws-serverless-eda, python-coding, software-engineering, aws-core:aws-messaging-and-streaming, aws-core:aws-sdk-python-usage, graphrag-lookup, python-lambda-packaging | Read, Glob, Grep, Bash, Write, Agent |
| `data-consistency-checker` | Integration Testing | Execution Team | Worker | Validator | test | Verifies data consistency across services and stores after integration and event-flow runs — partial writes, orphaned records, divergent state. Use for Integration Testing work requiring cross-store verification, DynamoDB assertions, and eventual-consistency validation. | subagent-contract, validation-protocol, dynamodb, aurora-postgresql, graphrag-lookup | Read, Glob, Grep, Bash, Write, Agent |
| `cross-service-contract-tester` | Integration Testing | Execution Team | Worker | Validator | test | Runs contract tests across service and repo boundaries, verifying providers and consumers honor approved API and event contracts. Use for Integration Testing work requiring consumer-driven contract verification, schema compatibility checks, and cross-repo boundary testing. | subagent-contract, validation-protocol, api-test-suite-builder, graphrag-lookup, contract-testing | Read, Glob, Grep, Bash, Write, Agent |
| `flaky-test-detector` | Integration Testing | Execution Team | Worker | Validator | test | Verifies intermittent test failures via repeated controlled reruns; reports verified-flaky tests as findings only — never edits or disables tests. Use for Integration Testing work requiring flakiness verification, rerun-based reproduction, and root-cause findings. | subagent-contract, validation-protocol, find-cause, graphrag-lookup | Read, Glob, Grep, Bash, Write, Agent |
| `root-cause-analyst` | Integration Testing | Execution Team | Worker | Advisor | plan | Diagnoses a bug bead read-only: the reproduction, the root cause, the distinct defects behind it, the files a fix must change, the blast radius, the surfaces the fix touches, and the repository it lives in; never fixes. Use for bug diagnosis requiring evidence-chain analysis. | subagent-contract, find-cause, test-failure-mindset, graphrag-lookup, artifact-handoff, matrix | Read, Glob, Grep, Write, Agent |
| `adversarial-review-loop-supervisor` | Adversarial Validation | Execution Team | Manager | Delegator, Orchestrator | orchestrate | Sequences the adversarial validation loop: testers attack project code in designated test environments only; the Adversarial Critique Adjudicator rules on findings, which route back until pass or loop-limit escalation. Use for Adversarial Validation phase work requiring attack-wave orchestration, finding routing, and loop-limit enforcement. | subagent-contract, agent-orchestration | Read, Glob, Grep, Agent, SendMessage |
| `injection-attack-tester` | Adversarial Validation | Execution Team | Worker | Adversary | test | Probes this project's endpoints in designated test environments only for SQL, NoSQL, command, and template injection; reports each confirmed path with a minimal reproduction. Use for Adversarial Validation phase work requiring injection probing and input-boundary attack. | subagent-contract, validation-protocol, senior-secops, aurora-postgresql, graphrag-lookup | Read, Glob, Grep, Bash, Write, Agent |
| `auth-bypass-tester` | Adversarial Validation | Execution Team | Worker | Adversary | test | Attempts auth bypass — token forgery, session fixation, flow skipping — against the project's auth flows in designated test environments only, reporting each confirmed bypass. Use for Adversarial Validation phase work requiring auth-flow attack, Cognito probing, and minimal-reproduction reporting. | subagent-contract, validation-protocol, senior-secops, cognito, aws-core:aws-auth, graphrag-lookup | Read, Glob, Grep, Bash, Write, Agent |
| `permission-escalation-tester` | Adversarial Validation | Execution Team | Worker | Adversary | test | Attempts horizontal and vertical privilege escalation against this project's own IAM and authorization model in designated test environments only, reporting each confirmed escalation with a minimal reproduction. Use for Adversarial Validation phase work requiring authorization attack and IAM-model probing. | subagent-contract, validation-protocol, senior-secops, iam, aws-core:aws-iam, graphrag-lookup | Read, Glob, Grep, Bash, Write, Agent |
| `race-condition-tester` | Adversarial Validation | Execution Team | Worker | Adversary | test | Probes this project's concurrent flows in designated test environments only for race conditions and idempotency gaps — TOCTOU, double-spend, lost updates, replay duplication — reporting each defect with a minimal reproduction. Use for Adversarial Validation phase work requiring concurrency attack and idempotency probing. | subagent-contract, validation-protocol, senior-secops, aws-serverless-eda, graphrag-lookup, python-lambda-packaging | Read, Glob, Grep, Bash, Write, Agent |
| `contract-violation-tester` | Adversarial Validation | Execution Team | Worker | Adversary | test | Sends contract-violating inputs — malformed payloads, type/range violations, schema mismatches — across the project's service boundaries in designated test environments only. Use for Adversarial Validation phase work requiring contract-boundary attack, API/event schema probing, and minimal-reproduction reporting. | subagent-contract, validation-protocol, api-test-suite-builder, graphrag-lookup | Read, Glob, Grep, Bash, Write, Agent |
| `dependency-cve-auditor` | Adversarial Validation | Execution Team | Worker | Validator | test | Audits the project's Python and Node dependencies for known CVEs, scoring severity and exploitable transitive paths. Use for Adversarial Validation phase work requiring CVE scanning, severity scoring, and supply-chain risk reporting. | subagent-contract, validation-protocol, dependency-auditor, python-lambda-packaging | Read, Glob, Grep, Bash, Write, Agent |
| `dos-resilience-tester` | Adversarial Validation | Execution Team | Worker | Adversary | test | Probes load and resource-exhaustion resilience in designated test environments only, reporting where throttling, backpressure, or quotas fail; findings are competitive, not gate-stopping. Use for Adversarial Validation phase work requiring exhaustion probing, resilience evaluation, and competitive-finding reporting. | subagent-contract, validation-protocol, senior-secops, graphrag-lookup, load-testing | Read, Glob, Grep, Bash, Write, Agent |
| `data-exposure-scanner` | Adversarial Validation | Execution Team | Worker | Validator | test | Scans the project's responses, logs, and storage in designated test environments only for data exposure — leaked secrets, PII, over-returned fields, unencrypted storage — reporting each confirmed exposure. Use for Adversarial Validation phase work requiring data-leak scanning, secret/PII detection, and minimal-reproduction reporting. | subagent-contract, validation-protocol, senior-secops, graphrag-lookup | Read, Glob, Grep, Bash, Write, Agent |
| `infrastructure-security-scanner` | Adversarial Validation | Execution Team | Worker | Validator | test | Scans project IaC and deployed test infrastructure, designated test environments only, for public exposure, over-broad IAM, missing encryption, and open security groups, reporting each with a minimal reproduction. Use for Adversarial Validation phase work requiring IaC security scanning, CDK and cloud-config review, and misconfiguration reporting. | subagent-contract, validation-protocol, senior-secops, aws-cdk-development, aws-core:aws-iam, graphrag-lookup, python-lambda-packaging | Read, Glob, Grep, Bash, Write, Agent |
| `adversarial-critique-adjudicator` | Adversarial Validation | Execution Team | Worker | Decider (Referee) | approve | Rules on each adversarial finding whether it is real, its severity, and whether it is constitutive (a hard stop) or competitive (a tradeable concern), with a rationale per finding; the referee whose rulings implementers cannot downgrade. Use for Adversarial Validation phase work requiring finding adjudication and constitutive-vs-competitive classification. | subagent-contract, validation-protocol, senior-security | Read, Glob, Grep, Write, Agent |
| `deployment-lead` | Deployment and Landing | Execution Team | Manager | Delegator, Orchestrator | orchestrate | Routes the feature deployment sequence, validates preconditions per step, and assembles the deployment evidence packet. Use for Deployment team work requiring delegation, sequencing discipline, and evidence assembly. | subagent-contract, agent-orchestration, python-lambda-packaging | Read, Glob, Grep, Agent, SendMessage |
| `smoke-test-author` | Deployment and Landing | Execution Team | Worker | Executor (test author) | test | Writes, before the deploy, the smoke tests that verify a change's critical paths against the endpoints of a deployment, parameterized by environment variables so the deploy session can run them against AWS dev once it has deployed. Never deploys and never runs them against a deployment. | subagent-contract, validation-protocol, api-test-suite-builder, python-coding, typescript-coding, software-engineering, graphrag-lookup, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `dev-deployer` | Deployment and Landing | Execution Team | Worker | Executor | execute | Deploys one repository to AWS dev by the mechanism the repository deploys by (cdk deploy of the affected stacks, or the repository's own deploy path such as a static-site build, S3 sync and CloudFront invalidation), then runs its smoke tests or names the one command that runs them. Never deploys to any other environment and never writes code. | subagent-contract, validation-protocol, senior-devops, aws-cdk-development, aws-core:aws-cdk, cdk-coding, python-coding, python-lambda-packaging | Read, Glob, Grep, Bash, Agent |
| `deploy-failure-fixer` | Deployment and Landing | Execution Team | Worker | Executor | execute | Diagnoses a failed package publish, cdk synth, cdk deploy to AWS dev or stack verification from its output and the CloudFormation stack events, fixes the CDK (or whatever else the deploy needs) in the Story's worktree, runs the repository's synth assertion tests, corrects a test the fix proves wrong, and names the command that runs them. Never deploys, commits or publishes. | subagent-contract, validation-protocol, cdk-coding, aws-cdk-development, aws-core:aws-cdk, aws-core:aws-cloudformation, cloudformation, python-coding, software-engineering, test-failure-mindset, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `worktree-lander` | Deployment and Landing | Execution Team | Worker | Executor | execute | Lands the work in a git worktree: commits every change through the repository's hooks (fixing every finding they report, never bypassing them), and when asked pushes the branch and opens its pull request with the project's PR command. Never pushes to the default branch and never merges. | subagent-contract, validation-protocol, software-engineering, python-coding, typescript-coding, shell-coding, python-lambda-packaging | Read, Edit, Write, Glob, Grep, Bash, Agent |
| `github-actions-pipeline-implementer` | Deployment and Landing | Execution Team | Worker | Executor | execute | Writes and changes a repository's GitHub Actions workflows: OIDC authentication to AWS with no stored credentials, dependency and build caching, and the build, test, lint and deploy jobs the repository's own commands define. A specialist a caller chooses when a repository's CI/CD workflows must be created or changed. | subagent-contract, validation-protocol, senior-devops, software-engineering, shell-coding, python-lambda-packaging | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `cdk-infrastructure-drift-detector` | Deployment and Landing | Execution Team | Worker | Validator | test | Detects drift between a repository's deployed CloudFormation stacks and its CDK app (cdk diff, CloudFormation drift detection, template comparison) and reports each divergence with evidence; read-only, never remediates. A specialist a caller chooses to check deployed infrastructure against its code. | subagent-contract, validation-protocol, aws-cdk-development, cloudformation, aws-core:aws-cdk, aws-core:aws-cloudformation, python-lambda-packaging | Read, Glob, Grep, Bash, Write, Agent |
| `slo-error-budget-designer` | Deployment and Landing | Execution Team | Worker | Advisor | plan | Designs a deployed service's SLOs and error budgets: SLIs from the CloudWatch metrics it emits, targets and windows traced to its NFRs, error budget policy and multi-window burn-rate CloudWatch alarms; recommends, never adopts. A specialist a caller chooses when a service needs SLOs. | subagent-contract, observability-designer, cloudwatch, aws-core:aws-observability | Read, Glob, Grep, Write, Agent |
| `finops-analyst` | Deployment and Landing | Execution Team | Worker | Advisor | plan | Models what a feature costs to run on AWS before it ships — unit economics, scaling cost curves across load scenarios, budget impact, cost cliffs — and ranks cost recommendations; decides nothing. A specialist a caller chooses for a pre-deployment cost analysis. | subagent-contract, aws-core:aws-billing-and-cost-management | Read, Glob, Grep, Write, Agent |
| `incident-response-runbook-designer` | Deployment and Landing | Execution Team | Worker | Executor | execute | Writes a deployed feature's operational runbooks — incident response keyed to its alarms and SLIs, rollback steps that match its deployment strategy, and disaster recovery (backup, restore, failover) for its AWS resources — with every referenced command and resource verified. A specialist a caller chooses when a feature needs runbooks. | subagent-contract, validation-protocol, senior-devops, observability-designer, aws-core:aws-observability | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `production-readiness-review-facilitator` | Deployment and Landing | Execution Team | Worker | Orchestrator | orchestrate | Coordinates a production readiness review: checks the required artifacts exist (rollout result, smoke test results, drift report, SLO design, runbooks), routes each to the reviewer charged with it, and assembles the readiness packet with the reviewers' findings verbatim; never decides readiness. A coordinator a caller chooses before a production deployment. | subagent-contract, agent-orchestration | Read, Glob, Grep, SendMessage, Agent |
| `deployment-strategy-decider` | Deployment and Landing | Execution Team | Worker | Decider | approve | Decides one repository's deployment strategy (rollout mechanism such as Lambda alias traffic shifting, canary, blue-green or all-at-once; canary health criteria; rollback triggers) from analyses others produced (rollout options and risk, FinOps, SLO design, drift), with a recorded rationale; produces no analysis. A specialist a caller chooses when a rollout must be decided. | subagent-contract, validation-protocol, senior-devops, aws-core:aws-serverless, python-lambda-packaging | Read, Glob, Grep, Write, Agent |
| `documentation-lead` | Documentation | Execution Team | Manager | Delegator, Orchestrator | orchestrate | Routes documentation work for shipped changes, tracks artifacts lacking current docs, and reports documentation currency. Use for cross-cutting Documentation team work requiring delegation, currency tracking, and currency reporting. | subagent-contract, agent-orchestration | Read, Glob, Grep, Agent, SendMessage |
| `documentation-currency-auditor` | Documentation | Execution Team | Worker | Validator | test | Audits which documents a change leaves stale or missing, with cited evidence, and assigns each stale document to the documentation writer whose kind covers it (API reference, README, changelog, user guide, or internal and technical documents); names the specification files the change contradicts. Read-only. | subagent-contract, validation-protocol | Read, Glob, Grep, Bash, Write, Agent |
| `api-documentation-writer` | Documentation | Execution Team | Worker | Executor | execute | Updates the human-readable API reference documents of shipped APIs from their OpenAPI and GraphQL specifications: endpoint and operation guides, request, response and error examples, SDK snippets. Never edits a specification file. | subagent-contract, validation-protocol | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `readme-writer` | Documentation | Execution Team | Worker | Executor | execute | Writes and maintains README files — setup, usage, onboarding — derived from shipped code and pipelines. Use for cross-cutting Documentation team work requiring README authoring, setup documentation, and onboarding flow writing. | subagent-contract, validation-protocol | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `changelog-writer` | Documentation | Execution Team | Worker | Executor | execute | Writes the changelog entries for a change before it merges, from the change and the conventional commits on its branch, in the project's changelog format, flagging breaking changes and recommending the semantic version increment. Never decides, sets or bumps a version. | subagent-contract, validation-protocol, changelog-generator | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `user-guide-writer` | Documentation | Execution Team | Worker | Executor | execute | Updates user-facing feature guides and walkthroughs, for the people who use the product, from the spec and the shipped behaviour. Not internal or technical documents, READMEs, changelogs or API reference documents. | subagent-contract, validation-protocol | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `developer-documentation-writer` | Documentation | Execution Team | Worker | Executor | execute | Updates a repository's internal and technical documents so they match the shipped code: developer guides, design and implementation notes, module and service documentation, configuration references and contributing guides. Not READMEs, changelogs, API reference documents, user guides or specification files. | subagent-contract, validation-protocol, software-engineering | Read, Write, Edit, Glob, Grep, Bash, Agent |
| `documentation-accuracy-reviewer` | Documentation | Execution Team | Worker | Validator | test | Reviews the documents a documentation writer updated for a change against the behaviour the change ships, claim by claim, and reports each inaccurate claim and each uncovered behaviour with cited evidence. Read-only; never fixes. | subagent-contract, validation-protocol | Read, Glob, Grep, Bash, Write, Agent |
| `filing-clerk` | Documentation | Execution Team | Specialist | Executor | execute | The documentation filing clerk for the project's documentation vault. Hand it a fact, decision, definition, or note and it (1) searches the project's Obsidian vault — fast, from several angles — to see whether it is already documented, (2) hunts for any single-source-of-truth violation (an unmarked duplicate of something canonical), (3) if the fact is genuinely new, decides the one correct home and files it there with proper classification frontmatter, and (4) reports what it did and any conflicts for the owner to adjudicate. Use PROACTIVELY whenever the owner says things like "if we don't have it already, note that…", "file this", "document that…", "make sure it's written down somewhere", "capture this", "record that we decided…", "add … to arc42 / the glossary / the docs", or offloads a fact so the owner won't forget it. Examples: "note in arc42 somewhere that we use Amazon Bedrock AgentCore and the Strands Agents SDK for our agent" → clerk checks the SAD, files under §4 Solution Strategy if absent; "define 'aging authority' in the glossary if it isn't there" → clerk searches, adds a glossary term; "record that student verification uses SheerID" → clerk finds the right tech/spec doc and files it. | subagent-contract, obsidian:obsidian-cli, obsidian:obsidian-markdown, arc42 | Read, Write, Edit, Bash, Grep, Glob, Agent |
| `regression-impact-assessor` | Cumulative Regression Assurance | Execution Team | Worker | Advisor | plan | Maps the components a Task changes to every current requirement they can affect, across all PRDs and the repositories that consume them, and to the unit, contract, integration and nonfunctional test layers each requires — before Red as the regression scope, after Red as the final mapping to actual test IDs and to the repository's test and check commands, each with its setup — retaining earlier requirements unless an accepted source supersedes them. | subagent-contract, artifact-handoff, cumulative-regression, graphrag-lookup | Read, Glob, Grep, Bash, Write, Agent |
| `regression-coverage-reviewer` | Cumulative Regression Assurance | Execution Team | Worker | Validator | test | Independently reviews a regression scope or final regression mapping against the actual requirement sources across PRDs, the changed code and the test assertions — completeness of discovered requirements and test layers, preservation of earlier requirements and tests, source-backed supersession, and, for a mapping, that the mapped tests exist, assert the obligations and are collected by the declared commands — and approves it or returns concrete findings. | subagent-contract, artifact-handoff, cumulative-regression, graphrag-lookup | Read, Glob, Grep, Bash, Write, Agent |
| `test-command-resolver` | Workflow Helpers | Standalone Specialists | Specialist | Advisor | execute | Finds the command a repository itself declares for running its whole test suite — from its AGENTS.md or CLAUDE.md, else the test task of its Taskfile — and returns it exactly as declared, or a resolution error naming the files read. Runs nothing and changes nothing. | subagent-contract | Read, Glob, Grep, Agent |
| `cds-live-auditor` | Workflow Helpers | Standalone Specialists | Specialist | Validator | test | Audits the UI files a Task changed against the live Configurable Design System (cds) when no mockup or cds bundle was supplied, and rules each finding. | subagent-contract, validation-protocol, cds:apply-design-system, cds:audit-against-system, graphrag-lookup | Read, Glob, Grep, Bash, Agent |
| `cds-finding-reviewer` | Workflow Helpers | Standalone Specialists | Specialist | Validator | test | Rules on the findings a deterministic cds audit of a Task's changed UI could not rule on - each class name the supplied cds bundle's stylesheets do not name - as a violation, allowed, or a cds gap, against the bundle and the configured design system; changes no file. | subagent-contract, validation-protocol, cds:apply-design-system, cds:audit-against-system, graphrag-lookup | Read, Glob, Grep, Bash, Agent |
| `shared-capability-reviewer` | Workflow Helpers | Standalone Specialists | Specialist | Validator | test | Rules, for each definition a deterministic reuse check could not rule on, whether a function a Task added duplicates a behaviour a shared capability (a shared library, layer, chassis or service) provides to its consumers — duplicate or not-duplicate, with one sentence of reason. Reads only the named function and the provides entry; changes nothing. | subagent-contract, python-lambda-packaging | Read, Grep, Agent |
| `polyrepo-steward` | Standalone | Standalone Specialists | Specialist | Executor | execute | The fleet's caretaker and the place to ask about this project's repositories. It learns about the fleet as it answers, and keeps what it learns for the next question. Ask it first whenever your work involves more than one repository. It also carries out the routine management of the fleet and keeps its records true to the fleet. That management can write into a repository, but the steward never authors or edits a repository's content. It owns the repository templates, the shared master copies and its own tool: it keeps them current and says when they need to change. The specialist agents built for that work write the changes. | subagent-contract, graphrag-lookup, polyrepo-repo, polyrepo-info, polyrepo-governance, polyrepo-beads, matrix | Bash, Read, Write, Edit, Glob, Grep, Agent |

## References

- [Agents directory](./AGENT-ROSTER.md)
