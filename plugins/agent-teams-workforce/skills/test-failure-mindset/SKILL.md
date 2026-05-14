---
name: test-failure-mindset
description: Balanced investigation protocol for failing tests. Use when diagnosing test failures, deciding whether implementation or test expectations are wrong, or preventing superficial test updates.
user-invocable: true
---

# Test Failure Mindset

SOURCE: Adapted from `/Users/msat1971/projects/miscellaneous/3rd-party/Jamie-BitFlight/claude_skills/plugins/development-harness/skills/test-failure-mindset/SKILL.md`.

Tests are executable specifications. A failing test is a diagnostic signal, not an automatic instruction to change either code or test.

## Dual Hypothesis

Always consider both possibilities:

| Hypothesis A | Hypothesis B |
| --- | --- |
| The test expectation is wrong or stale. | The implementation has a bug or regression. |
| The test encodes an obsolete assumption. | The test found an edge case. |
| The fixture or mock is unrealistic. | The system contract was violated. |

## Investigation Steps

1. Read the test name, setup, assertions, and comments.
2. Identify the behavior the test is trying to specify.
3. Trace the implementation path related to the failing assertion.
4. Check whether the expected behavior is documented in requirements, specs, ADRs, or accepted criteria.
5. Decide whether to fix implementation, fix the test, or return `STATUS: BLOCKED` for clarification.

## Red Flags

- Updating assertions to match current output without explaining why.
- Deleting inconvenient cases.
- Adding broad mocks that bypass the behavior under test.
- Bulk-changing snapshots without inspecting meaningful differences.
- Treating "make tests pass" as the goal instead of "make behavior correct."

## Reporting

When reporting a test failure investigation, include:

- Failing test or suite.
- What behavior the test specifies.
- Observed implementation behavior.
- Decision: implementation bug, test bug, ambiguous, or environmental issue.
- Evidence and recommended next action.

