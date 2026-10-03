---
name: delegate
description: Role-aware prompt template for authorized delegation to bounded specialists. Use when composing a task brief; preserves caller acceptance criteria, tool limits, and exact output schemas.
user-invocable: true
---

# Delegation Template

Use this on demand when authorized to dispatch. The passive authority is [Agent Orchestration](../agent-orchestration/SKILL.md). Loading this template does not authorize a selector or reviewer to dispatch or implement.

Consumed by: the assigned specialist — uses this brief to establish its role, scope, acceptance criteria and response format.

```text
ROLE AND TASK:
[Assigned role: select, investigate, review, implement, or approve; requested outcome and why it matters.]

OBSERVATIONS:
[Relevant facts already in context, attributed to their source; distinguish hypotheses.]

SCOPE AND CONSTRAINTS:
[Known paths, boundaries, user/caller restrictions, permitted tools, and affected dependencies.]

ACCEPTANCE AND VERIFICATION:
[Consumer's existing criteria, required checks, and evidence needed to satisfy them.]

EXISTING WORK:
[Artifact paths, actionable findings, pass conditions, and valid prior evidence to retain.]

RETURN FORMAT:
[Exact caller schema; otherwise a concise status, deliverables, verification and blockers.]
```

Gather current evidence relevant to the assignment. Implement only when implementation is the assigned role. When validation is required, use `agent-teams-workforce:validation-protocol` against the caller's criteria. Report unperformed checks honestly.

Do not pre-gather source or diagnostic output for the specialist. Supply required constraints without inventing a method or expanding scope. Investigate wider impact only when evidence connects it to the task or the caller expressly assigns broader repair. Do not require a report file based on response length: create artifacts only when the consumer requires them, and never replace a machine-consumed result with a path.
