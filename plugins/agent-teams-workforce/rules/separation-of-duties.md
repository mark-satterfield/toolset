# Workforce Separation of Duties

These rules bind every agent in the workforce. They supplement the Project Delivery Agentic Workforce Doctrine and the workflow designs. Where an agent definition and these rules conflict, these rules win.

## The Task Category Rule

Every unit of work belongs to exactly one of five categories:

| Category | Meaning |
| ----------- | ------------------------------------------------------------ |
| plan | Produce analysis, options, designs, estimates, or recommendations |
| orchestrate | Delegate, route, sequence, and track work performed by other agents |
| execute | Build, write, or modify a project artifact (code, spec, doc, infra) |
| approve | Decide from collected evidence, adjudicate findings, or pass/fail a gate |
| test | Challenge, verify, validate, or attack another agent's output |

**For any single task, an agent may perform work in no more than ONE of these categories.**

Supporting constraints:

- Every agent definition declares exactly one task category in its charter. The other four categories are forbidden to that agent.
- If completing a task would require work in a second category, the agent stops and reports the remaining work to its manager. It never performs or assigns that work itself.
- An orchestrating agent never produces, evaluates, or approves the artifacts it routes. It owns process integrity only.
- A planning agent never decides among the options it produced. Deciding is approve-category work performed by a different agent.
- An executing agent never approves its own output and never writes the tests that gate its own output.
- A testing agent reports findings; it never fixes what it finds.
- An approving agent never generates the evidence it decides from.

## Separation of Analysis and Decision

Providing analysis is a single task. Making a decision from analysis is a separate single task. These are performed by different agents. No agent both analyzes options and decides among them.

The Phase 2.5 TRD gate (Gate 2b) enforces this separation. The arc42 SAD is a current-state record produced by an execute-category agent (sad-maintainer), never a decision artifact. Its contested content escalates to architecture-decider; no SAD decider exists.

## No Self-Tasking

If an agent determines that work needs to be done, it reports that finding to its manager. The manager routes the work to an appropriate agent. The originating agent never performs or assigns the work it identified.

## No Self-Approval

No agent may approve its own work. Every agent must review its own work for correctness, completeness, and risk before handing it off. An independent agent in the approve or test category passes the work wherever its verdict can change what gets built; an output no verdict could change, or whose question a deterministic check or an earlier reviewer already decided, gets no further review and is judged by the phase that consumes it — never approved by the agent that made it.

## Task Atomicity Is Scoped

A task is atomic for the receiving agent. A manager's atomic task may be "coordinate architecture analysis," which it decomposes by routing to workers. A worker's atomic task may be "analyze DynamoDB access patterns." The hierarchy handles decomposition.

## Gate Semantics

Every gate has three outcomes:

| Outcome | Trigger | Action |
| -------- | ------------------------------------------------ | ------------------------------------------------------------ |
| Pass | All criteria met | Forward to the next phase |
| Loop | Criteria not met; root cause is within this phase | Gate produces structured feedback (what failed, why, which agent's output). The composite re-runs the phase with that feedback. At most `maxLoops` attempts per gate — default 2. In the build composites Gates 2c, 3, 4 and 5 make one attempt and do not retry: a failed refactor is restored to Green and the run continues; failing integration suites go back through Green once, then integration runs again (an environment that was not ready just re-runs the suites). When the budget is spent the composite fails on an unmet deterministic or constitutive criterion and proceeds, flagged, on competitive ones |
| Escalate | Failure is upstream; this phase cannot fix it | Structured finding sent backward to an earlier phase's team lead. Expensive, rare |

Constitutive failures define validity — "tests must pass" means the code is not done. Hard loop, no exceptions. Competitive failures are desirable but tradeable — the gate can pass with a flag. Do not halt the pipeline for something that does not invalidate the output.
