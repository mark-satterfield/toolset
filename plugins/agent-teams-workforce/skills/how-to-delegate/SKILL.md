---
name: how-to-delegate
description: On-demand preparation worksheet for authorized delegation. Use when explicitly asked to prepare a delegation brief, keeping the caller task, role limits, acceptance criteria, and output schema intact.
user-invocable: true
---

# Delegation Preparation

This worksheet is an on-demand aid, not a prerequisite to every routing decision. The passive authority is [Agent Orchestration](../agent-orchestration/SKILL.md).

A task in the caller prompt is sufficient input, including when no command arguments exist. Do not wait for `$ARGUMENTS`, restart task discovery, or ask for confirmation of already-authorized work. If explicitly invoked without any task in the conversation, ask for the missing outcome; continue independent assigned work.

Consumed by: an authorized dispatching orchestrator — uses the answers to compose the existing task brief. No separate worksheet artifact is required.

1. Identify the assigned role and outcome: selection, investigation, review, implementation, or approval. A selector returns its selection; only an authorized dispatcher sends work.
2. Include relevant observations already available, their source, known paths and uncertainties. Do not gather the agent's evidence in advance.
3. State scope, the reason for the work, caller constraints, acceptance criteria and required checks. Explicit broader authority from the caller remains in scope.
4. Choose the fewest suitable specialists from the available roster. Explain the distinct need before material optional fanout; preserve workflow caps and required independent review.
5. Pass existing artifacts, actionable findings, pass conditions and valid evidence for incremental repair. Investigate affected dependencies when evidence warrants it.
6. Preserve the exact consumer output schema and role's tool restrictions. Use [the prompt template](../delegate/SKILL.md) only when useful; do not add fields or substitute a report path.

Use `agent-teams-workforce:validation-protocol` when validation is assigned. Domain skills and host tools are optional resources only when actually available and useful; no undeclared external command or skill is mandatory. Completion means satisfying the caller's criteria with evidence, not invoking a separate completion command.
