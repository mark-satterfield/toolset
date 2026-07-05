# Instruction Block: {Title}

<!--
  TEMPLATE INSTRUCTIONS
  =====================
  The agent is the default actor. Do not annotate agent steps.
  Only annotate steps where a human or external system acts: [Human: {Name}] or [System: {Name}].
  Delete any section or sub-keyword you are not using. Empty sections add noise.
  The only required section is ANCHOR.

  NOTATION (three delimiters, one meaning each):
  - Bare keyword heading (## ANCHOR) — a FORGE section. The heading level marks it; no brackets.
  - [square] — an OPTIONAL element. Used here only for the actor annotation, which appears
    only when a non-agent acts: [Human: {Name}], [System: {Name}].
  - {curly} — a VALUE TO FILL IN. Replace the whole token, braces included, with a real value.
  - {OPEN: question — why} — a REQUIRED value you could not answer with evidence. Leave the
    marker in place, and disclose it. Incomplete-but-honest output is acceptable; a guess is not.

  BEFORE YOU WRITE:
  - Replace broad nouns ("the system", "the codebase") with specific identifiers.
  - Every IF must have an OTHERWISE.
  - Every LOOP must have a termination condition and a defined behavior if never reached.
  - Use the same word for the same concept throughout. Pick one: test, check, verification.
  - Avoid: "as needed", "where appropriate", "if necessary", "successfully completed".
  - Avoid passive voice. Not "the file should be written" — "Write the file to /path/."
  - If a list of steps is exhaustive, say so: "The following steps are exhaustive."
  - Fill a gap only with disclosed empirical evidence. If you cannot, leave {OPEN: …}.
-->

---

## CONTEXT

<!--
  Use when the agent needs facts, defined terms, scope boundaries, or starting state.
  Omit if the agent would correctly assume everything in this section.
  Entries render as list items so each stays on its own line.
-->

<!--
  Sub-keyword entries are bullets so each stays on its own line. Adjacent bold-label lines with
  only a single newline between them collapse into one paragraph when rendered — bullets do not.
-->

- **Fact:** {a fixed, non-arguable truth relevant to this task}
- **Fact:** {add or remove Fact entries as needed}
- **Define:** {term} = {specific meaning for this block only — overrides common usage everywhere in this block}
- **Define:** {add or remove Define entries as needed}

**Scope:**
- In:  {what is explicitly included}
- Out: {what is explicitly excluded}

**Setup:** {the starting state or configuration when execution begins}

---

## WHEN

<!--
  Use when this block should not execute immediately on receipt.
  Omit if the block executes immediately.
  WHEN answers: Should I run this?
  Gate.Before answers: Am I ready to run this? (Those are different questions.)
-->

**Trigger:** {a specific event or state change that activates this block}

**Schedule:** {time-based or recurring activation, e.g. Every day at 02:00 UTC}

**Condition:** {a boolean state that must become true, e.g. Queue depth exceeds 500}

---

## ANCHOR

<!-- Required. State what must be achieved. Do not describe how. -->

**Objective:** {one sentence — the high-level action to take}

**Target:** {the exact subject, dataset, system, or materials being acted upon — be specific}

**Success Criteria:** {a measurable, observable outcome, evaluable without human interpretation}
<!--
  Avoid: "successfully completed", "properly handled", "fully verified".
  Write the specific state that must be observable when the job is done.
-->

---

## PROCESS

<!--
  Choose exactly one approach type. Delete the other two.
  Do not mix approach types at the same level. Use nesting if branching requires it.

  APPROACH TYPES:
    Sequential   — Strict ordered steps. No deviation.
    White-Listed — Multiple valid options. Agent chooses one.
    Black-Listed — Total freedom except named exclusions.

  CONDITIONAL SUB-KEYWORDS (valid inside any approach type):
    IF {condition} THEN: / OTHERWISE:
    LOOP {target} UNTIL {termination condition}:

  ACTOR ANNOTATION (use only when a non-agent entity acts):
    [Human: {Name}]
    [System: {Name}]

  PAUSE BLOCK (use when execution must stop for human input and then resume):
    PAUSE:
      [Human: {Name}]  What the human does.
      RESUME IF:       The condition or input that allows execution to continue.
      BRANCH:
        "Response A" → What happens next.
        "Response B" → What happens next.
-->

### Approach: Sequential

1. {step one}
2. {step two}
3. {step three}

---

### Approach: White-Listed

Choose one of the following options:

**Option 1 ({label}):**
1. {step}
2. {step}

**Option 2 ({label}):**
1. {step}
2. {step}

---

### Approach: Black-Listed

- **Restriction:** {do not use this approach or method}
- **Exclude:** {these approaches are not permitted}

<!-- Describe the execution approach here, within the above exclusions. -->

---

## SAFEGUARDS

<!--
  Execution controls. Behavioral rules, gates, error handling, rollback.
  All sub-keywords are independent. Delete what you are not using.

  Guideline types are mutually exclusive for the same class of error:
    Stop If     — Halt immediately. Report state. Do not proceed.
    Keep Going  — Override normal stop behavior. Proceed despite minor errors.
    No Deviation — PROCESS is strict. Do not improvise or substitute.
    Best Effort  — Partial completion is acceptable.
-->

**Gate.Before:** {precondition — must be true before execution starts; if not met, halt and report}

**Gate.After:** {postcondition — must be verified true after execution before declaring success}

**Guideline — {Stop If | Keep Going | No Deviation | Best Effort}:** {the condition or scope of this rule}

**On Error:** {what to do when something unexpected occurs that no other rule covers — be specific}

**Rollback:**
- Trigger: {the condition that initiates rollback}
- Steps:
  1. {step to undo work}
  2. {step to undo work}
- Verify: {how to confirm rollback succeeded}

---

## WHY

<!--
  One paragraph. Write only when the rationale would change how the agent handles
  an edge case not covered by PROCESS or SAFEGUARDS.
  If WHY would not change any decision, delete this section.
-->

{rationale}
