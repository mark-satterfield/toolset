---
name: validation-protocol
description: Evidence-based validation protocol for verifying fixes, implementation work, refactors, and generated artifacts. Use before claiming work is complete; success means observing intended behavior, not merely seeing no errors.
user-invocable: true
---

# Validation Protocol

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

Use the accepted requirements and constraints shared with the maker to state measurable criteria before verification; do not introduce new product requirements as review criteria:

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

For a revision, apply the incremental-review and actionable-finding rules in `../subagent-contract/SKILL.md`: reuse valid evidence, review changes and affected dependencies, and explain any evidence-based reopening. A correct artifact passes; review is not a search for a reason to fail. Required safety, independence, and regression checks still apply.

### 5. Result

The result states whether every criterion is satisfied, or names each gap: a required criterion that is unmet, unclear, or unverified. Each gap identifies its evidence/location, the existing requirement or dependent behavior at risk, and the correction or missing evidence that would satisfy a verifiable pass condition. The caller's schema carries the result. Only when the caller gives no schema, state it as `VALIDATED` or `GAPS_FOUND` followed by the gaps.

## Anti-Patterns

- Claiming completion without reproducing or observing the baseline.
- Treating a successful command exit as proof of intended behavior.
- Skipping edge cases listed in the acceptance criteria.
- Saying "should work" instead of reporting observed evidence.

