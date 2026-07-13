# Implementation Plan: {Title}

<!--
  TEMPLATE INSTRUCTIONS
  =====================
  This is the fill-in scaffold for an implementation plan — a FORGE instruction block whose
  PROCESS obeys references/implementation-plan.md. Read that document first; this template
  does not restate its rules.

  The agent is the default actor. Annotate only steps where a human or external system acts:
  [Human: {Name}] or [System: {Name}].

  Delete any optional entry you are not using. Delete every scaffolding comment before
  delivery. {curly} tokens are values to fill in — replace the whole token, braces included.
  {OPEN: question — why} marks a required value you could not answer with evidence; leave it
  in place rather than guessing.

  WHAT NEVER GOES IN THIS FILE (the Separation Rule, implementation-plan.md):
  decisions and rationale, target-state design, history, audit narrative, notes, to-do lists,
  or an "Open Questions" section. Open questions exist only as {OPEN: …} markers on the exact
  step value that needs the answer.
-->

---

## CONTEXT

<!-- Prerequisites and blast radius. Both are mandatory in a plan. -->

- **Fact:** {environmental invariant that must hold throughout execution}
- **Define:** {term} = {specific meaning within this plan}

**Setup (prerequisites):**
- Permissions: {required roles/credentials, named exactly}
- Tooling: {tool and version, e.g. terraform >= 1.9.0}
- Environment: {invariants that must be true when execution begins}

**Scope (blast radius):**
- In:  {systems, services, and data this plan touches}
- Out: {what is strictly out of scope — named to prevent scope creep during execution}

**References:**
- Design: {path to the design document this plan implements — cite, never restate}
- Decisions: {path to the decision register — cite, never restate}

---

## ANCHOR

**Objective:** {one sentence — what this plan achieves}

**Target:** {the exact systems, files, or resources being changed — specific identifiers}

**Success Criteria:** {the measurable, observable end state — evaluable without human interpretation}

---

## PROCESS

<!--
  Always Sequential. Phases are the large objectives; steps are atomic execution units.
  Every step carries Status + the four blueprint elements. Steps must be idempotent.
  Number steps {phase}.{step} so a step reference is unambiguous across sessions.
-->

Sequential. The following phases and steps are exhaustive. Do not add, skip, or reorder steps.

### Phase 1: {Large objective — the what and the why of this phase}

#### Step 1.1: {imperative, single-outcome title}
- **Status:** pending
- **Pre-condition:** {literal command or query verifying the system is ready for this action}
- **Action:** {the exact script, command, or UI click-path to execute}
- **Post-condition:** {literal command or query verifying the action succeeded}
- **Rollback:** {the specific action if the post-condition fails or times out}

#### Step 1.2: {imperative, single-outcome title}
- **Status:** pending
- **Pre-condition:** {…}
- **Action:** {…}
- **Post-condition:** {…}
- **Rollback:** {… | none required — read-only}

### Phase 2: {Large objective}

#### Step 2.1: {imperative, single-outcome title}
- **Status:** pending
- **Pre-condition:** {…}
- **Action:** {…}
- **Post-condition:** {…}
- **Rollback:** {…}

<!--
  PAUSE is available where a human decision gates the next step:
  PAUSE:
    [Human: {Name}]  {what the human decides or provides}
    RESUME IF:       {the condition or input that allows execution to continue}
    BRANCH:
      "{Response A}" → {what happens next}
      "{Response B}" → {what happens next}
-->

---

## SAFEGUARDS

**Gate.Before:** This plan file is the single source of execution state. Apply the resume
rule from `implementation-plan.md`: read every step's Status; locate the first non-`done`
step; verify every step before it is `done` (halt and report if not); recover an
`in-progress` step via its Post-condition, and a failed one via its Rollback. Additionally:
{plan-specific precondition, e.g. the literal check that prerequisites in CONTEXT hold}.

**Gate.After:** {literal verification of the ANCHOR Success Criteria — run it; do not assume success from a clean run}

**Guideline — No Deviation:** Execute steps strictly in the written order. Update this plan
file's Status fields per the state-update rule in `implementation-plan.md` — `in-progress`
before each Action, `done` only after the Post-condition verifies, never batched.

**Guideline — Stop If:** {objective rollback trigger — the exact metric, log output, or time-bound that mandates abort; no judgment calls}

**On Error:** Execute the current step's Rollback, set its Status to `blocked — <reason>`,
preserve all state, and report the exact condition encountered. Do not continue past a
blocked step.

**Rollback:**
- Trigger: {the condition that abandons the plan, as opposed to a single step}
- Steps:
  1. {ordered instructions to unwind completed phases, most recent first}
- Verify: {how to confirm the system is back to its pre-plan state}

---

## WHY

<!-- One paragraph, only if it would change an edge-case judgment. Not history. Not a decision log. -->

{rationale}
