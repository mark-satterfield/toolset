---
name: validation-protocol
description: Evidence-based validation protocol for verifying fixes, implementation work, refactors, and generated artifacts. Use before claiming work is complete; success means observing intended behavior, not merely seeing no errors.
user-invocable: true
---

# Validation Protocol

SOURCE: Adapted from `/Users/msat1971/projects/miscellaneous/3rd-party/Jamie-BitFlight/claude_skills/plugins/development-harness/skills/validation-protocol/SKILL.md`.

Use this protocol whenever an agent is about to claim that a change, document, plan, or investigation is complete.

## Core Principle

Success means observing the intended outcome. "No errors" is not enough.

## Protocol

### 1. Establish Baseline

Before changing or accepting anything, identify the current state:

- For bugs: reproduce or observe the failing state.
- For feature work: identify the expected user-visible or system-visible behavior.
- For docs/specs: identify the source of truth the artifact must match.
- For analysis: identify the question that must be answered and what evidence will settle it.

### 2. Define Success Criteria

State measurable criteria before verification:

- What output, behavior, file, or decision proves success?
- What checks or observations will be used?
- What would count as partial success or failure?

### 3. Apply or Assess the Work

Perform the implementation, review, or artifact generation inside the assigned scope. Capture material observations while working.

### 4. Verify Against Criteria

Re-run the baseline check or inspect the resulting artifact against the success criteria:

- Compare expected vs. observed behavior.
- Cite file paths, commands, reports, or artifacts used as evidence.
- Distinguish verified facts from inferences.

### 5. Report Result

Return one of:

```text
VALIDATED
```

when all criteria are satisfied, or:

```text
GAPS_FOUND
```

when any criterion is unmet, unclear, or unverified.

## Anti-Patterns

- Claiming completion without reproducing or observing the baseline.
- Treating a successful command exit as proof of intended behavior.
- Skipping edge cases listed in the acceptance criteria.
- Saying "should work" instead of reporting observed evidence.

