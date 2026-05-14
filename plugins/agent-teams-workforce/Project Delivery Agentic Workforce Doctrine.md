# **Project Delivery Agentic Workforce Doctrine**

## **1. Purpose**

This doctrine defines the principles, rules, and operating model for creating a project delivery agentic workforce.

The workforce is composed of specialized agents with narrow responsibilities, bounded authority, limited context, explicit skills, and purpose-aligned tool access. These agents operate within governed teams and follow predefined collaboration, review, escalation, and handoff rules.

The goal is not to maximize individual agent autonomy.

The goal is to maximize system-level delivery reliability.

## **2. Core Thesis**

A project delivery agentic workforce should be designed around **bounded specialist agents, explicit handoff contracts, independent review, and read-only coordination**.

Agents should not be trusted because they are broadly capable.

Agents should be useful because they are constrained.

Each agent should have:

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

The agent is not the unit of trust.

The workflow is the unit of trust.

## **3. Rationale**

Large, broadly scoped agents introduce avoidable risk.

An agent with too much responsibility can silently blend requirement analysis, architecture, implementation, review, and approval into one coherent-looking response. That creates risk because the agent may:

- resolve ambiguity without surfacing it
- optimize for a local concern instead of the larger system
- choose familiar tools over appropriate patterns
- hallucinate missing facts
- drift from the original intent
- collapse trade-offs into unsupported conclusions
- review its own reasoning with the same flawed assumptions
- exceed its authority without making that visible

Specialized agents reduce these risks by limiting the scope of reasoning, context, tool access, and decision authority.

A narrowly defined agent can still be wrong, but its failure is easier to detect, isolate, and correct.

## **4. Design Philosophy**

The workforce should be designed using the same principles that guide durable software architecture:

- separation of concerns
- least privilege
- bounded context
- explicit interfaces
- single responsibility
- independent review
- dependency control
- artifact-driven collaboration
- testability
- auditability
- escalation over silent assumption

The system should prefer explicit coordination over broad autonomy.

The design should make it difficult for any single agent to silently become planner, implementer, reviewer, approver, and historian for the same work.

## **5. Foundational Principles**

### **5.1 Specialization by Responsibility**

Agents must be defined by responsibility, not by broad professional title.

Broad titles such as `Architect`, `Engineer`, `Developer`, `Reviewer`, or `Analyst` are too vague unless further scoped.

Preferred agent names describe the specific work the agent performs.

Examples:

| **Broad Role** | **Better Specialized Roles**        |
| -------------- | ----------------------------------- |
| Architect      | Integration Pattern Architect       |
| Architect      | Domain Boundary Architect           |
| Architect      | Persistence Architecture Specialist |
| Developer      | Lambda Implementation Specialist    |
| Developer      | CDK Construct Implementer           |
| Reviewer       | Security Controls Reviewer          |
| Reviewer       | Operational Readiness Reviewer      |
| Writer         | API Documentation Writer            |
| Writer         | ADR Writer                          |

### **5.2 Bounded Authority**

Every agent must have explicit decision boundaries.

Each agent definition must state:

- what the agent may decide
- what the agent may recommend
- what the agent may create
- what the agent may modify
- what the agent may review
- what the agent may not decide
- when the agent must escalate

Capability does not imply authority.

An agent may be capable of performing a task and still be forbidden from doing it.

### **5.3 Least Context**

Agents should receive only the context required to perform their assigned role.

Context should be distributed through role-specific context packets, not through a universal project dump.

This reduces:

- irrelevant anchoring
- stale assumptions
- conflicting instructions
- scope creep
- context-window pollution
- accidental authority expansion

### **5.4 Least Tool Access**

Agents should have access only to the MCPs and tools required for their purpose.

Read-only access should be the default.

Write access should be granted only when mutation is part of the agent’s charter.

Tool access is a form of authority.

An agent with broad access to repositories, tickets, cloud resources, documents, and communication systems can affect the delivery system even if its written role appears narrow.

### **5.5 No Self-Approval**

No agent may approve its own work.

No agent may independently plan, execute, review, and approve the same deliverable.

This applies to:

- architecture
- code
- infrastructure
- documentation
- tests
- schemas
- runbooks
- deployment plans
- release decisions

Every agent **MUST** review it's own work for correctness, completeness, and risk, but it may not approve it, and therefore may not end until it is approved by another agent.

Independent review is mandatory for any agent that creates or modifies a project artifact, or makes, recommends, or records an architectural decision.

### **5.6 Separation of Intent, Design, Implementation, and Review**

The workforce must separate:

| **Concern**        | **Responsibility**                                           |
| ------------------ | ------------------------------------------------------------ |
| Intent             | Understand what is being requested                           |
| Requirements       | Define required outcomes and constraints                     |
| Domain framing     | Establish business meaning and boundaries                    |
| Architecture       | Select structural patterns                                   |
| Platform mapping   | Translate architecture into platform-specific implementation |
| Implementation     | Produce concrete deliverables                                |
| Review             | Challenge correctness, risk, and completeness                |
| Decision recording | Capture rationale and trade-offs                             |
| Delivery readiness | Confirm release and operational fitness                      |

No single agent should own the full chain.

### **5.7 Architecture Before Platform Preference**

Platform implementation agents must respect upstream architectural decisions.

For example, an AWS Serverless Specialist may recommend the best AWS implementation for an approved architecture. It may not independently replace the approved architectural pattern because another AWS service appears cheaper, easier, or more familiar.

If a platform agent believes an upstream decision is flawed, it must raise a formal exception.

It may not silently override the architecture.

### **5.8 Read-Only Coordination**

Team leader agents coordinate work. They do not perform the work.

A team leader agent may:

- route tasks
- enforce workflow rules
- verify required inputs
- assign agents
- track open questions
- require reviews
- detect missing artifacts
- escalate unresolved conflicts
- assemble approved outputs

A team leader agent may not:

- create architecture
- write implementation code
- modify deliverables
- approve its own team’s work
- override specialist disagreement
- silently resolve trade-offs

Team leaders own process integrity, not subject-matter authority.

### **5.9 Artifact-First Collaboration**

Agents should collaborate through explicit artifacts.

Important artifacts include:

- intake brief
- requirements brief
- domain model
- context map
- architecture option analysis
- architecture decision record
- API contract
- data schema
- threat model
- implementation plan
- test plan
- review report
- release readiness checklist
- handoff packet

Informal agent conversation is not enough for project delivery.

The durable record is the artifact.

### **5.10 Explicit Conflict Handling**

Agent disagreement is expected and useful.

Disagreement must be surfaced as a structured conflict, not hidden inside compromise language.

Conflict types include, but are not limited to:

| **Conflict Type**     | **Example**                                         |
| --------------------- | --------------------------------------------------- |
| Architecture conflict | Event-driven architecture vs workflow orchestration |
| Platform conflict     | DynamoDB vs Aurora                                  |
| Cost conflict         | Lower cost vs greater operability                   |
| Security conflict     | Developer convenience vs least privilege            |
| Delivery conflict     | Faster implementation vs long-term maintainability  |
| Domain conflict       | Technical model does not match business model       |

When conflict exceeds predefined rules, it must be escalated.

## **6. Workforce Creation Rules**

### **Rule 1: Every Agent Must Have a Charter**

The agent is defined by these front-matter fields:


| Field             | Required               | Description                                                  |
| :---------------- | :--------------------- | :----------------------------------------------------------- |
| `name`            | Yes                    | Unique identifier using lowercase letters and hyphens        |
| `description`     | Yes                    | When Claude should delegate to this subagent                 |
| `tools`           | No                     | [Tools](https://code.claude.com/docs/en/sub-agents#available-tools) the subagent can use. Inherits all tools if omitted |
| `disallowedTools` | No                     | Tools to deny, removed from inherited or specified list      |
| `model`           | Yes                    | [Model](https://code.claude.com/docs/en/sub-agents#choose-a-model) to use: `sonnet`, `opus`, `haiku`, a full model ID (for example, `claude-opus-4-7`), or `inherit`. Defaults to `inherit` |
| `permissionMode`  | No                     | [Permission mode](https://code.claude.com/docs/en/sub-agents#permission-modes): `default`, `acceptEdits`, `auto`, `dontAsk`, `bypassPermissions`, or `plan` |
| `maxTurns`        | No                     | Maximum number of agentic turns before the subagent stops    |
| `skills`          | No                     | [Skills](https://code.claude.com/docs/en/skills) to load into the subagent’s context at startup. The full skill content is injected, not just made available for invocation. Subagents don’t inherit skills from the parent conversation |
| `mcpServers`      | No                     | [MCP servers](https://code.claude.com/docs/en/mcp) available to this subagent. Each entry is either a server name referencing an already-configured server (e.g., `"slack"`) or an inline definition with the server name as key and a full [MCP server config](https://code.claude.com/docs/en/mcp#installing-mcp-servers) as value |
| `hooks`           | No                     | [Lifecycle hooks](https://code.claude.com/docs/en/sub-agents#define-hooks-for-subagents) scoped to this subagent |
| `memory`          | No                     | [Persistent memory scope](https://code.claude.com/docs/en/sub-agents#enable-persistent-memory): `user`, `project`, or `local`. Enables cross-session learning |
| `background`      | No                     | Set to `true` to always run this subagent as a [background task](https://code.claude.com/docs/en/sub-agents#run-subagents-in-foreground-or-background). Default: `false` |
| `effort`          | No                     | Effort level when this subagent is active. Overrides the session effort level. Default: inherits from session. Options: `low`, `medium`, `high`, `xhigh`, `max`; available levels depend on the model |
| `isolation`       | Yes (set the worktree) | Set to `worktree` to run the subagent in a temporary [git worktree](https://code.claude.com/docs/en/common-workflows#run-parallel-claude-code-sessions-with-git-worktrees), giving it an isolated copy of the repository. The worktree is automatically cleaned up if the subagent makes no changes. |
| `color`           | Yes                    | Display color for the subagent in the task list and transcript. Accepts `red`, `blue`, `green`, `yellow`, `purple`, `orange`, `pink`, or `cyan` |
| `initialPrompt`   | No                     | Auto-submitted as the first user turn when this agent runs as the main session agent (via `--agent` or the `agent` setting). [Commands](https://code.claude.com/docs/en/commands) and [skills](https://code.claude.com/docs/en/skills) are processed. Prepended to any user-provided prompt |

In the body, include, at a minumum, the following:

```text
Team:
Agent Type:
Purpose:
Primary Responsibility:
Scope:
Out of Scope:
Allowed Decisions:
Forbidden Decisions:
Inputs Required:
Outputs Produced:
Required Reviewers:
Escalation Triggers:
Acceptance Criteria:
Anti-Goals:
```

If these fields cannot be completed clearly, the agent is not yet well-defined.

### **Rule 2: Every Agent Must Have One Primary Responsibility**

Each agent must have one primary responsibility.

Related responsibilities may exist, but they must support the primary responsibility.

An agent responsible for API documentation should not also redesign the API, approve the contract, define authentication behavior, and generate SDKs.

Those are separate concerns.

### **Rule 3: Every Agent Must Produce a Defined Output**

Every worker agent must produce a defined output.

Examples:

- recommendation memo
- architecture option analysis
- OpenAPI fragment
- documentation draft
- schema proposal
- implementation patch
- review findings
- test plan
- risk register entry
- handoff packet

If an agent does not produce a defined output, its role should be questioned.

### **Rule 4: Every Mutable Output Requires Independent Review**

Any agent that creates or modifies a deliverable must have an independent reviewer.

This applies to:

- code
- infrastructure
- schemas
- documentation
- diagrams
- test plans
- architecture decisions
- deployment plans
- operational runbooks

### **Rule 5: Agents Must State Assumptions**

Every substantive agent output must include:

```text
Assumptions:
Open Questions:
Constraints Followed:
Constraints at Risk:
Scope Exceptions:
```

This protects against silent ambiguity resolution.

### **Rule 6: Agents Must Separate Facts, Assumptions, Recommendations, and Decisions**

Agent outputs must distinguish:

- provided facts
- inferred facts
- assumptions
- recommendations
- decisions
- unresolved questions

This prevents recommendations from being mistaken for approved decisions.

### **Rule 7: Agents Must Escalate Scope Violations**

If a task requires authority outside the agent’s charter, the agent must stop and raise a scope exception.

Example:

```text
Scope Exception:
The requested API documentation depends on behavior not present in the approved API contract. This agent cannot document the behavior as current. API Contract Designer review is required.
```

### **Rule 8: Competitive Review Should Be Used for High-Risk Judgment**

Competitive or adversarial agents should be used when the task involves:

- architectural trade-offs
- security-sensitive design
- persistence strategy
- cost/performance decisions
- data modeling
- migration planning
- release readiness
- ambiguous requirements
- irreversible implementation choices

Competition should not be used by default for routine mechanical work.

### **Rule 9: Model Diversity Should Be Targeted**

Using different LLM models can be useful when independent failure modes matter.

Model diversity is most valuable for:

- adversarial review
- architecture validation
- security review
- ambiguous requirement analysis
- final synthesis
- unsupported-claim detection

Model diversity should not be used merely to make a workflow appear more sophisticated.

### **Rule 10: Consolidation Requires Justification**

The first-pass workforce design should favor granular specialization.

Agents may be consolidated later only when there is a clear benefit and the consolidation does not remove a required control boundary.

Valid consolidation reasons include:

- agents always require the same context
- agents always produce the same artifact
- review separation adds no value
- handoff overhead exceeds risk reduction
- skills and MCP access are effectively identical
- responsibilities cannot realistically be separated

Invalid consolidation reasons include:

- the names sound similar
- a human would normally do both
- the model is capable of doing both
- the spreadsheet feels too large
- the workflow diagram looks too busy

### **Rule 11: Consolidation Must Preserve Control Boundaries**

Agents must not be consolidated if doing so removes:

- independent review
- separation of concerns
- conflict visibility
- authority boundaries
- least-privilege tool access
- meaningful escalation points

For example, it may be reasonable to consolidate `API Documentation Writer` and `API Example Generator`.

It is not reasonable to consolidate `API Contract Designer` and `API Contract Reviewer`.

## **7. Agent Team Model**

Agents should be organized into teams based on delivery function.

Each team should have a read-only team leader and orchestrator, but the team may consist of sub-orchestrators or sub-leaders, depending on the scope and size of the teams.

The team leader coordinates the work but does not perform subject-matter production.

## **8. Team Leader Charter**

Team leaders should have a charter that includes what is required by any agent, but with a focus on the fact that the team leader has explict responsibilities:

- delegate 100% of work to the team and team members
- is responsbilble for the quality and completion of all work produced by the team
- may not "blame" any team member for low quality, incompetence, or incomplete work
- communication between to the team members, between the team members, and from the team members
- ensureing all rules, guidelines, and best practices are followed
- be honest and transparent above all else

The team leader is never allowed to:

- perform work itself, including work that does not impact project artifacts, on behalf of the team
- compensate for the team's inadequacies or mistakes by doing their work or by covering up their problems

## **9. Specialist Agent Charter**

Team leaders should have a charter that includes what is required by any agent, but with a focus on the fact that the team leader has explict responsibilities:

- Always use the skills and mcp servers provided to them over their own internal training
- Always provide an audit trail of decisions, which ould include:
  - Confidence Level
  - Reasoning
  - Alternatives considered and dismissed
  - Questions if wished it know the answers to which would have possibly yeilded a different outcome
  - Pros/cons and risks
- be honest and transparent above all else

## **10. Potential Architectural Decision Workflow**

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

11. ADR Writer records the final decision, rationale, rejected alternatives, constraints, risks, and downstream implications.

12. Architecture Team Leader verifies that all required workflow steps occurred and prepares the decision packet.
```

## **11. Example Handoff Contract**

All handoffs should have a contract.  While this is a good example, we will use strict json to prevent ambiguity.

```text
Handoff:
Integration Pattern Architect → AWS Serverless Implementation Specialist

Request:
Map the approved event-driven architecture to AWS serverless services.

Upstream Decision:
The solution must use event-driven decoupling between producer and consumer domains.

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

Required Output:
AWS implementation recommendation with service choices, trade-offs, risks, assumptions, and operational considerations.

Required Reviewers:
- Cloud Cost Reviewer
- Security Reviewer
- Operational Readiness Reviewer
```

## **12. Minimal Guidence for Creating Agents**

Collecting a documenting these values should contain enough structure to define both the agent and the governance model around the agent.

Recommended:

| **Column**              | **Purpose**                                               |
| ----------------------- | --------------------------------------------------------- |
| Agent ID                | Stable unique identifier                                  |
| Agent Name              | Human-readable role name                                  |
| Team                    | Functional team assignment                                |
| Agent Type              | Worker, reviewer, coordinator, decision-support, recorder |
| Purpose                 | Why the agent exists                                      |
| Primary Responsibility  | The agent’s main responsibility                           |
| Scope                   | What the agent covers                                     |
| Out of Scope            | What the agent must not cover                             |
| Allowed Decisions       | Decisions the agent may make                              |
| Forbidden Decisions     | Decisions the agent may not make                          |
| Authority Level         | Recommend, create, modify, review, approve, route         |
| Mutation Rights         | None, draft-only, patch, merge, deploy                    |
| Inputs Required         | Required upstream artifacts                               |
| Outputs Produced        | Required output artifacts                                 |
| Required Skills         | Attached Agent Skills                                     |
| Required MCPs           | Required tools or MCP servers                             |
| MCP Permissions         | Read-only, comment-only, write, admin                     |
| Upstream Agents         | Agents that feed this agent                               |
| Downstream Agents       | Agents that consume this agent’s output                   |
| Required Reviewers      | Agents that must review this output                       |
| Conflict Partners       | Agents expected to challenge this agent                   |
| Escalation Triggers     | Conditions requiring escalation                           |
| Acceptance Criteria     | What good output means                                    |
| Anti-Goals              | Explicit behaviors to avoid                               |
| Consolidation Candidate | Yes, no, or later                                         |
| Consolidation Rationale | Reason consolidation may be valid                         |
| Risk If Too Broad       | Failure mode caused by excessive scope                    |
| Risk If Too Narrow      | Failure mode caused by excessive fragmentation            |
| Notes                   | Additional information                                    |

## **13. Final Operating Standard**

The workforce should be optimized for reliable project delivery, not individual agent autonomy.

Agents should be small by default.

Authority should be explicit.

Context should be limited.

Tools should be least-privilege.

Review should be independent.

Coordination should be read-only.

Disagreement should be surfaced.

Decisions should be recorded.

Consolidation should be earned.

The system should make it difficult for any single agent to silently expand its role, collapse trade-offs, approve its own work, or substitute local optimization for project-level judgment.