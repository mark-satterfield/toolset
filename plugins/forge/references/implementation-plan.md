# Implementation Plan

How the PROCESS portion of a FORGE instruction block is written when that block is an
**implementation plan** — a Sequential PROCESS meant to drive real system change, executed by
one agent or handed across several sessions. This discipline attaches to the **kind of work**,
not to the skill that authored the block: `compose-instructions` writing implementation work
from rough intent, `revise-instructions` modifying it, `review-instructions` grading it, and
`distill-plan` extracting it from a multi-purpose document all produce and enforce the same
PROCESS shape whenever the Applicability test below says the block is a plan.

An implementation plan contains **current implementation steps and nothing else**. Everything
else a working document accumulates — decisions, history, audit trails, notes, to-do lists,
open questions — lives outside the plan. That separation is not cosmetic: an executing agent
reads everything in its instructions as instruction. A "Why we changed course" section in the
middle of a plan is noise at best and a misread directive at worst.

---

## Applicability — when a block is an implementation plan

A FORGE instruction block is an implementation plan, and its PROCESS must follow this
document, when **any** of these holds:

1. **State change:** any PROCESS step changes state outside the conversation — files, repos,
   infrastructure, databases, configuration, external services.
2. **Session span:** execution could outlive one session, or the plan may be handed from one
   agent to another.
3. **Recovery cost:** a failed or half-completed run requires deliberate recovery — the work
   cannot simply be re-asked from scratch.

When **none** holds — read-only analysis, a report, a single-session task whose failure costs
nothing but the retry — the block is not a plan. Write PROCESS as ordinary framework steps;
the blueprint would be dead weight there. Do not apply this document to make a three-step
read-only task carry Status fields and rollback procedures.

The test is evaluated by whichever skill is authoring, revising, or reviewing the block. It
is a property of the work, not of the entry point.

---

## Core Characteristics

* **Deterministic Execution:** Eliminates ambiguity. Two different engineers following the same playbook must arrive at the exact same system state.
* **Idempotency:** Steps can be safely repeated without causing unintended side effects or compounding failures.
* **State-Awareness:** Explicitly defines the required system state before execution (pre-conditions) and the expected state after execution (post-conditions).
* **Failure Tolerance:** Anticipates failure modes. Includes predefined rollback procedures and failure thresholds rather than relying on on-the-fly troubleshooting.
* **Auditable:** Leaves a clear trace of actions taken, making post-incident reviews factual rather than speculative.

## Best Practices

* **Define Prerequisites Explicitly:** List required permissions, tooling versions, credentials, and environmental invariants before the first execution step.
* **Atomic Steps:** Break complex operations into the smallest viable units of work. Each step must have a single, verifiable outcome.
* **Verification at Boundaries:** Insert hard tollgates. Require empirical verification of Step N's output before permitting the initiation of Step N+1.
* **Explicit Blast Radius:** Document exactly what systems, services, or data are impacted. State what is strictly out of scope to prevent scope creep during execution.
* **Executable as Code:** Translate playbook steps into automated, version-controlled scripts wherever possible. Treat manual documentation as a transitional state toward automation.
* **Mandate Rollback Triggers:** Define the exact metrics, log outputs, or time-bounds that mandate an abort and rollback sequence. Remove subjective judgment from mid-deployment crisis management.
* **Continuous Decay Testing:** Execute the playbook against isolated staging environments periodically. Documentation rots if not executed; validate instructions against current infrastructure configurations.

In an implementation plan, large objectives provide the structural framework; step-by-step details provide the execution mechanism.
The plan must contain both levels to be effective.

## The Hierarchy

### 1. The Phase (Large Objective)

Defines the *what* and the *why*. This level is for orchestration, stakeholder communication, and understanding the blast radius.

* **Purpose:** Establishes context and intent. If a step-by-step action fails, the objective tells the engineer what the system *should* have achieved, allowing them to formulate a safe recovery path.
* **Example:** "Phase 3: Failover primary database traffic to the secondary region."

### 2. The Execution (Step-by-Step Detail)

Defines the *how*. This level must be deterministic, exhaustive, and atomic.

* **Purpose:** Eliminates localized knowledge and ambiguity. The executor should not need to guess the correct flag, path, or sequence.
* **The Anti-Pattern:** Writing objectives masquerading as steps (e.g., "Step 4: Update the DNS records"). This forces the engineer to invent the execution method in real-time.
* **Example:** "Run `aws route53 change-resource-record-sets --hosted-zone-id Z1234567 --change-batch file://failover-batch.json`."

## The Execution Blueprint

Every objective should be decomposed into a sequence containing these four detailed elements:

1. **Pre-condition:** The literal command or query used to verify the system is ready for the action.
2. **Action:** The exact script, command, or UI click-path to execute.
3. **Post-condition:** The literal command or query used to verify the action succeeded.
4. **Rollback:** The specific action to take if the post-condition fails or times out.

---

## How the blueprint maps onto FORGE

A plan is still a FORGE instruction block. Nothing here adds a section to the framework's
closed set — the plan discipline lives *inside* the existing sections:

| Plan concern | FORGE home |
| --- | --- |
| Prerequisites (permissions, tooling versions, credentials, invariants) | `CONTEXT` — `Setup:` and `Fact:` entries; verified again by `Gate.Before` |
| Blast radius — what is impacted, what is strictly out of scope | `CONTEXT` — `Scope: In / Out` |
| The plan's overall objective and its measurable end state | `ANCHOR` |
| Phases and steps (the hierarchy, the four-element blueprint, execution state) | `PROCESS` — always `Sequential` |
| Resume rule, state-update rule, rollback triggers, failure thresholds | `SAFEGUARDS` |
| The one paragraph of rationale that governs edge-case judgment | `WHY` — and no more than that |

`PROCESS` in a plan is **always Sequential**. A plan that offers the executor a choice of
approaches is a design document that has not finished deciding. Phases are the top level of
the Sequential block; steps are the numbered items within a phase; every step carries the
four blueprint elements plus a `Status` field.

---

## The Separation Rule

The plan contains **only** what an executor needs to run the next step. Each of these has a
home, and that home is not the plan:

| Content | Belongs in | Allowed trace inside the plan |
| --- | --- | --- |
| Decisions and rationale ("what you ruled and why") | A decision register | One-line reference to the register entry, only where a step depends on it |
| Target-state design (templates, gates, flows, communication model) | A design document | The plan may cite the design doc by path; it never restates it |
| History, "why we changed course", superseded approaches | The decision register or the document's own history | None |
| Audit trail of execution (who ran what, when, output) | An execution log kept beside the plan | Per-step `Status` only |
| Open questions | `{OPEN: …}` markers on the exact value that needs the answer | The marker itself — never a prose "Open Questions" section |
| To-do lists, future work, nice-to-haves | The issue tracker or a backlog document | None |
| Notes, observations, working commentary | Anywhere else | None |

Two consequences worth stating plainly:

- **A plan never has an "Open Questions" section.** An open question in a plan is an
  `{OPEN: question — why}` marker sitting on the specific pre-condition, action,
  post-condition, or rollback value that needs the answer. If the question does not attach to
  a specific step value, it is not a plan question — it is a design or decision question, and
  it goes to the document that owns it.
- **Distillation is non-destructive.** When a plan is distilled out of a multi-purpose
  document, the source document keeps everything it had. The plan takes only the steps.
  Nothing is deleted on the plan's account; the distillation report says what was excluded
  and where it lives or should live.

---

## Execution State and Handoff

The plan file is the **single source of execution state**. Any agent, in any session, must be
able to open the plan cold and know exactly where execution stands — because all state lives
in the plan, not in the memory of the session that ran it.

### Status

Every step carries a `Status` field with exactly one of four values:

- `pending` — not started.
- `in-progress` — the step's Action has begun and its Post-condition has not yet verified.
- `done` — the step's Post-condition verified. Only a verified post-condition makes a step
  done; a clean-looking run does not.
- `blocked` — the step cannot proceed. A blocked status always names its reason and what
  unblocks it, in one line on the Status field.

### The state-update rule

The executor updates the plan file as it works — this is not optional and is never batched:

1. Set `Status: in-progress` immediately before running the step's Action.
2. Run the Action.
3. Run the Post-condition. If it verifies, set `Status: done` and proceed to the next step.
4. If the Post-condition fails or times out, execute the step's Rollback, set
   `Status: blocked — <reason>`, and follow SAFEGUARDS.

### The resume rule

On opening a plan — first session or fiftieth — the executor:

1. Reads every step's `Status` before acting.
2. Locates the first step whose Status is not `done`. That is the resume point.
3. Verifies the invariant: every step **before** the resume point is `done`. If any is not,
   the plan's state is corrupt — halt and report; do not repair by guessing.
4. If the resume-point step is `in-progress` (a prior session died mid-step), run that step's
   Post-condition first: if it verifies, mark the step `done` and move on; if it does not,
   execute the step's Rollback, reset the step to `pending`, and re-execute it. This is why
   steps must be idempotent.
5. If the resume-point step is `blocked`, report the recorded reason and halt unless the
   blocker is resolved.
6. Execute from the resume point, in order, under the state-update rule.

Handoff between agents needs no ceremony beyond this: the outgoing session leaves the plan
file current under the state-update rule; the incoming session applies the resume rule. Both
are following the same plan, and the plan itself says where to pick up.

---

## Readiness

A plan is **READY** when all of the following hold:

1. Every step carries all four blueprint elements — Pre-condition, Action, Post-condition,
   Rollback — and a `Status` field. On steps whose Action is genuinely non-destructive,
   read-only, and re-runnable, Rollback may read `Rollback: none required — read-only`;
   it may never be silently absent.
2. Every Pre-condition, Action, and Post-condition is literal — a command, query, script, or
   exact click-path — not an objective the executor must translate into an execution method.
3. No `{OPEN: …}` marker remains anywhere on the execution path.
4. No content violates the Separation Rule — no decisions, history, notes, to-do lists, or
   open-question prose inside the plan.
5. Prerequisites and blast radius are explicit in `CONTEXT`, and rollback triggers in
   `SAFEGUARDS` are objective (metrics, log outputs, time-bounds — not judgment calls).
6. The plan grades **B or better** under `review-rubric.md`, with zero plan-class defects.

A plan that misses any of these is **NOT READY**, and the readiness verdict names what is
missing. NOT READY is an honest, deliverable state — a NOT READY plan with marked `{OPEN}`
gaps is worth more than a READY-looking plan with fabricated commands.
