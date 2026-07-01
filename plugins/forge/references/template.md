# Instruction Block: [Title]

<!--
  TEMPLATE INSTRUCTIONS
  =====================
  The agent is the default actor. Do not annotate agent steps.
  Only annotate steps where a human or external system acts: [Human: Name] or [System: Name].
  Delete any section or sub-keyword you are not using. Empty sections add noise.
  The only required section is [ANCHOR].

  BEFORE YOU WRITE:
  - Replace broad nouns ("the system", "the codebase") with specific identifiers.
  - Every IF must have an OTHERWISE.
  - Every LOOP must have a termination condition and a defined behavior if never reached.
  - Use the same word for the same concept throughout. Pick one: test, check, verification.
  - Avoid: "as needed", "where appropriate", "if necessary", "successfully completed".
  - Avoid passive voice. Not "the file should be written" — "Write the file to /path/."
  - If a list of steps is exhaustive, say so: "The following steps are exhaustive."
-->

---

## [CONTEXT]

<!--
  Use when the agent needs facts, defined terms, scope boundaries, or starting state.
  Omit if the agent would correctly assume everything in this section.
-->

**Fact:**
<!-- A fixed, non-arguable truth relevant to this task. -->

**Fact:**
<!-- Add or remove Fact entries as needed. -->

**Define:**
<!-- term = specific meaning for this block only. Overrides common usage everywhere in this block. -->

**Define:**
<!-- Add or remove Define entries as needed. -->

**Scope:**
- In:  <!-- What is explicitly included. -->
- Out: <!-- What is explicitly excluded. -->

**Setup:**
<!-- The starting state or configuration when execution begins. -->

---

## [WHEN]

<!--
  Use when this block should not execute immediately on receipt.
  Omit if the block executes immediately.
  WHEN answers: Should I run this?
  Gate.Before answers: Am I ready to run this? (Those are different questions.)
-->

**Trigger:**
<!-- A specific event or state change that activates this block. -->

**Schedule:**
<!-- Time-based or recurring activation. Example: Every day at 02:00 UTC. -->

**Condition:**
<!-- A boolean state that must become true. Example: Queue depth exceeds 500. -->

---

## [ANCHOR]

<!-- Required. State what must be achieved. Do not describe how. -->

**Objective:**
<!-- One sentence. The high-level action to take. -->

**Target:**
<!-- The exact subject, dataset, system, or materials being acted upon. Be specific. -->

**Success Criteria:**
<!--
  A measurable, observable outcome. Must be evaluable without human interpretation.
  Avoid: "successfully completed", "properly handled", "fully verified".
  Write: the specific state that must be observable when the job is done.
-->

---

## [PROCESS]

<!--
  Choose exactly one approach type. Delete the other two.
  Do not mix approach types at the same level. Use nesting if branching requires it.

  APPROACH TYPES:
    Sequential   — Strict ordered steps. No deviation.
    White-Listed — Multiple valid options. Agent chooses one.
    Black-Listed — Total freedom except named exclusions.

  CONDITIONAL SUB-KEYWORDS (valid inside any approach type):
    IF [condition] THEN: / OTHERWISE:
    LOOP [target] UNTIL [termination condition]:

  ACTOR ANNOTATION (use only when a non-agent entity acts):
    [Human: Name]
    [System: Name]

  PAUSE BLOCK (use when execution must stop for human input and then resume):
    PAUSE:
      [Human: Name]  What the human does.
      RESUME IF:     The condition or input that allows execution to continue.
      BRANCH:
        "Response A" → What happens next.
        "Response B" → What happens next.
-->

### Approach: Sequential

1. <!-- Step one. -->
2. <!-- Step two. -->
3. <!-- Step three. -->

---

### Approach: White-Listed

Choose one of the following options:

**Option 1 (label):**
1. <!-- Step. -->
2. <!-- Step. -->

**Option 2 (label):**
1. <!-- Step. -->
2. <!-- Step. -->

---

### Approach: Black-Listed

- **Restriction:** <!-- Do not use this approach or method. -->
- **Exclude:** <!-- These approaches are not permitted. -->

<!-- Describe the execution approach here, within the above exclusions. -->

---

## [SAFEGUARDS]

<!--
  Execution controls. Behavioral rules, gates, error handling, rollback.
  All sub-keywords are independent. Delete what you are not using.

  Guideline types are mutually exclusive for the same class of error:
    Stop If     — Halt immediately. Report state. Do not proceed.
    Keep Going  — Override normal stop behavior. Proceed despite minor errors.
    No Deviation — PROCESS is strict. Do not improvise or substitute.
    Best Effort  — Partial completion is acceptable.
-->

**Gate.Before:**
<!-- Precondition. Must be true before execution starts. If not met, halt and report. -->

**Gate.After:**
<!-- Postcondition. Must be verified true after execution before declaring success. -->

**Guideline — [Stop If / Keep Going / No Deviation / Best Effort]:**
<!-- Delete the labels that do not apply. Write the condition or scope of this rule. -->

**On Error:**
<!-- What to do when something unexpected occurs that no other rule covers. Be specific. -->

**Rollback:**
- Trigger: <!-- The condition that initiates rollback. -->
- Steps:
  1. <!-- Step to undo work. -->
  2. <!-- Step to undo work. -->
- Verify: <!-- How to confirm rollback succeeded. -->

---

## [WHY]

<!--
  One paragraph. Write only when the rationale would change how the agent handles
  an edge case not covered by PROCESS or SAFEGUARDS.
  If WHY would not change any decision, delete this section.
-->
