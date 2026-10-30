---
name: acceptance-criteria
description: How to write acceptance criteria and Definition of Done statements a test can be derived from without interpretation, and how to judge them - one observable outcome per criterion, concrete inputs and values, Given/When/Then or a boolean assertion, the boundary and failure cases each requirement needs, criteria of one requirement that cannot contradict each other, measurable non-functional criteria, Definition of Done as true-or-false statements about the finished work, and the falsifiability test a reviewer applies. Use when writing, revising or reviewing acceptance criteria or a Definition of Done, in a PRD or in a specification's criteria document.
user-invocable: false
---

# Testable acceptance criteria

An acceptance criterion is testable when a test author can build one passing case and one failing
case from its text alone, without asking what was meant. Everything below serves that test. Where
the criteria sit in a document, and what that document's contract adds (a PRD's P0 rule and its
WHAT-not-HOW boundary in the `prd-writer` skill; a criteria document's sources and schema in the
brief and the artifact-handoff contract), is the document's own rule. The structure a
specification's criteria document is checked against is stated once, below, under "A criteria
document's structure".

## One criterion

1. **One observable outcome.** A criterion states one result a test can observe: a response, a
   stored value, a message shown, an event published, a state reached. Two outcomes joined by
   "and" are two criteria unless they cannot occur apart.
2. **A precondition, a trigger, an outcome.** Write `Given <state> When <action> Then <outcome>`,
   or a boolean assertion ("A request without a session token receives 401") when the trigger is
   obvious. The `Given` names the state the outcome depends on; a criterion with no state assumes
   none.
3. **Concrete values.** Name the input, the limit and the expected result as values or as a value
   the referenced source defines ("more than the 20 items the page size defines", not "too many
   items"). A number the sources do not give is not invented: the criterion cites where the value
   comes from, or the gap is reported.
4. **No judgement words.** "Fast", "user-friendly", "appropriate", "correctly", "gracefully",
   "as expected", "etc." and "should" make a criterion untestable. Replace each with the
   observable fact it stands for, or report the requirement as ambiguous.
5. **Observable from outside.** The outcome is something the system under test exposes at the
   boundary the criterion is written for; a PRD criterion names user-observable behaviour, a
   specification criterion may name the API response, the stored item or the published event the
   specification defines. Never an internal step ("the handler calls the validator").
6. **Traceable.** Each criterion names the requirement or specification section it proves. A
   criterion that proves no stated requirement adds scope and is removed.

## The set for one requirement

- **The success case, every boundary, every failure.** For each requirement: the main success
  case; each boundary the sources define (the limit, one under, one over; empty; the first and
  last allowed value); each rejection or failure the sources define (invalid input, missing
  permission, missing or duplicate resource, downstream failure the requirement names), with the
  outcome the user or caller observes. A failure the sources do not define is reported, not
  invented.
- **Mutually consistent.** No two criteria of one requirement may both apply to the same input
  and demand opposite outcomes. The usual cause is a success criterion whose `Given` names only
  some of the conditions its sibling criteria treat as decisive, so a rejected input also
  satisfies the success case. **Every success criterion's `Given` restates every condition a
  sibling criterion treats as grounds for rejection.** One such pair halted a pipeline for a day:
  one criterion rejected an out-of-range value, and another said "Given a settings write
  containing no unknown fields … then the write succeeds"; a write with a known field holding an
  out-of-range value satisfied both. The repair closed the second `Given`: "… no unknown fields
  **and no field value outside its defined type or range** …". Close an under-specified `Given`;
  never reword it into vagueness or delete the criterion that exposed the conflict.
- **Independent.** Each criterion is checkable on its own, in any order, without the state another
  criterion's test leaves behind.
- **Non-functional criteria are measured.** A performance, availability, capacity or security
  criterion names the metric, the threshold, the load or condition it holds under and how it is
  measured ("p95 latency under 300 ms at 50 requests per second, measured at the API Gateway
  stage"). Without them it is a quality intent, not a criterion.
- **Assigned when a unit test cannot check it.** A criterion only an integration, end-to-end,
  load or human test can check says so; it is not dropped for being hard to unit test.

## A criteria document's structure

A specification's criteria document (`spec-<slug>.criteria.md`) is checked by
`spec_authoring.criteria_document` before Tasks cite it, against exactly these rules:

1. **Each item is a list item that opens with its id.** An acceptance criterion opens with
   `AC-<n>`, a Definition of Done statement with `DOD-<n>` (`- AC-3: Given …`). The document
   holds at least one of each.
2. **An item runs to the next item or heading.** Every line after the id line, up to the next list
   item that opens with an `AC-` or `DOD-` id or the next heading, belongs to the item, so a
   statement may wrap over as many lines as it needs.
3. **Every id once, every id followed by its statement.**
4. **A criterion that opens with `Given` states its `When` and `Then`.** The keywords are matched
   as words anywhere in the whole item, wrapped lines included, in any letter case. A criterion
   that does not open with `Given` (a boolean assertion) needs neither.

Each problem the check reports names the lines of the item, its id and what it lacks.

## Definition of Done

A Definition of Done statement is a true-or-false statement about the finished work ("Every route
in the API specification returns the error body the error contract defines"), never a checklist
step ("Write the error handling") and never a process activity ("Code reviewed"). Each one is
independently verifiable and traces to the requirement or design decision it comes from.

## Reviewing criteria

Apply the falsifiability test to each criterion on its own: could a test author build a failing
and a passing case from this text alone? A criterion fails, with the reason, when it is
untestable (no observable outcome, a judgement word, a value nobody defines), incomplete (a
boundary or failure case the sources define has no criterion) or ambiguous (two incompatible
readings, or a conflict with a sibling criterion). A set passes only when every criterion was
judged individually. Wording that does not affect testability is not a finding.
