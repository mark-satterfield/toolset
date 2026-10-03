---
name: agent-orchestration
description: Passive delegation contract for workflow selectors and dispatching orchestrators. Use when routing assigned work, choosing bounded specialists, or composing delegation briefs while preserving caller schemas and role boundaries.
---

# Agent Orchestration

Consumed by: workflow-selected leads and dispatching orchestrators — bounds routing, delegation, and returned results without adding a preparation artifact.

The caller's prompt is already your task. Loading this skill does not start an interactive worksheet, require arguments, or authorize dispatch. Follow your charter and allowed tools.

## Role and response

- A selector returns only the selection the caller requests. The workflow dispatches the selected agents; the selector does not dispatch, implement, run checks, or create files.
- A reviewer examines assigned evidence and returns findings; it does not implement repairs. A maker changes only its assigned deliverable. Keep maker, independent checker, and approver authority separate.
- A dispatching orchestrator assigns work only when its charter and caller authorize dispatch. Choose the fewest suitable roster specialists; do not substitute a generic role for required expertise.
- Return the caller's exact schema. Do not prepend DONE/BLOCKED text, append a worksheet, or replace a structured response with a file path when the consumer expects JSON. Otherwise use the shared subagent contract's status presentation.

## Bounded delegation

Apply the preloaded `agent-teams-workforce:subagent-contract`: preserve required checks, workflow caps, existing artifacts, and valid evidence. Difficulty alone does not justify more agents, proposals, or reviews. Before material optional expansion, identify the unresolved need and expected benefit in the existing brief or update.

Pass the outcome and its reason, scope and known paths, relevant observations already available, accepted criteria, restrictions, and the consumer's response schema. Distinguish observations from hypotheses. Do not pre-read the specialist's source or collect diagnostics merely to prepare its brief. Agents verify current evidence themselves. Preserve explicit user or caller constraints, including authorized repository-wide repair; scope guidance does not override them.

Investigate affected dependencies when evidence connects them to the assigned problem. A single code smell does not authorize an entire-pattern cleanup. For repairs, carry forward the original artifact, actionable findings, verifiable pass conditions and still-valid evidence. Rereview changed scope and affected dependencies; explain new evidence before reopening settled work. Required independent, safety, and regression checks remain required.

Parallelize only distinct assignments with a concrete benefit; serialize shared mutations. Reuse a suitable existing owner and completed results before adding another context. Escalate missing policy or uncovered specialty in the caller's format rather than inventing authority, a default specialist, or a new deliverable.

## On-demand references

Read only the reference needed for the current assignment:

- [Delegation prompt template](../delegate/SKILL.md) when authorized to dispatch.
- [Preparation worksheet](../how-to-delegate/SKILL.md) when explicitly requested; it is not startup work.
- [Orchestrator guard reference](../orchestrator-discipline/SKILL.md) for hook scope or guard troubleshooting. Top-level mode guards do not turn a selector into a dispatcher.
- [Polyrepo router](../polyrepo-router/SKILL.md) for repository governance questions, not routine workflow selection.
- `agent-teams-workforce:validation-protocol` for evidence standards when validation is assigned. Completion is measured against the caller's acceptance criteria; no external completion command is required.
