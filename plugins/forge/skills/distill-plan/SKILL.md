---
name: "distill-plan"
description: >-
  Distill a READY implementation plan out of a multi-purpose document — one that has grown into
  a mix of decision register, target-state design, work breakdown, and open-items list. Discerns
  the actual implementation steps, asks questions to make each step deterministic (literal
  pre-condition, action, post-condition, rollback), and delivers a step-by-step plan that carries
  its own execution state so any agent, in any session, can resume at the right step. Everything
  that is not a current implementation step — decisions, history, notes, to-dos, open questions —
  stays outside the plan. Use when the user wants to turn a working document into an executable
  plan, make a plan "ready", extract the plan from a design doc, or prepare a plan for handoff
  between agents or sessions.
triggers:
  - distill a plan
  - extract the implementation plan
  - make this plan ready
  - turn this document into a plan
  - get this plan ready to execute
  - prepare this plan for handoff
  - forge a plan from
argument-hint: "[path | inline text | 'headless']"
---

# distill-plan

You turn a multi-purpose working document into a READY implementation plan — a FORGE
instruction block whose PROCESS is a Sequential set of atomic, deterministic, state-carrying
steps that any agent can execute or resume without interpretation. The source document keeps
everything it has; the plan takes only the steps.

## Read first

- `${CLAUDE_PLUGIN_ROOT}/references/implementation-plan.md` — the plan doctrine: the execution
  blueprint, the Separation Rule, execution state and handoff, the READY definition. This
  document governs your output.
- `${CLAUDE_PLUGIN_ROOT}/references/plan-template.md` — the fill-in scaffold you populate.
- `${CLAUDE_PLUGIN_ROOT}/references/framework.md` — the FORGE authoring spec the plan must
  still satisfy.
- `${CLAUDE_PLUGIN_ROOT}/references/operating-rules.md` — quiet discipline, input resolution,
  modes, the gap policy, the disclosure ledger. Obey it.
- `${CLAUDE_PLUGIN_ROOT}/references/review-rubric.md` — how you grade before delivering,
  including the plan-class defects.

## Inputs

The source material: a document path (or several), or inline text. Typically a document that
has accreted several purposes — decisions, design, work breakdown, open items — around the
skeleton of a plan. Resolve inputs per `operating-rules.md` §2.

Mode is interactive unless the prompt or an argument says `headless` / `quiet` / `batch` /
`non-interactive`.

## Process

The following steps are exhaustive.

1. **Read** the source material and the five reference files above.

2. **Classify the source.** Partition every part of the source into exactly one of:
   - **Plan material** — steps, orderings, dependencies, prerequisites, verification
     commands, rollback procedures, blast-radius statements.
   - **Decision material** — rulings and their rationale, rejected alternatives, "why we
     changed course".
   - **Design material** — target-state descriptions: templates, gates, flows, models.
   - **Open items** — questions, unknowns, unresolved choices.
   - **Residue** — notes, to-dos, history, audit narrative, anything else.
   Only plan material enters the plan. Record the rest for the distillation report (step 8).
   Do not modify the source document.

3. **Draft the plan's ANCHOR.** One objective, a specific target, a measurable success
   criterion for the whole plan. If the source's objective is plural — the document is trying
   to achieve several independent end states — say so and split: one plan per objective,
   chained per the framework's Gate.After → Gate.Before mechanism.

4. **Build the hierarchy.** Derive phases from the source's large objectives or workstreams,
   ordered by their dependencies. Decompose each phase into atomic steps — smallest viable
   unit, single verifiable outcome. Number steps `{phase}.{step}`. Where the source offers a
   work breakdown ("the skeleton of a plan, not a plan"), the workstreams seed the phases; the
   steps still have to be made deterministic in step 5.

5. **Make each step deterministic.** Every step gets `Status: pending` plus the four blueprint
   elements — literal Pre-condition, exact Action, literal Post-condition, specific Rollback.
   An objective masquerading as a step ("Update the DNS records") is a gap: the execution
   method is missing. For every missing or non-literal element, apply the gap policy
   (`operating-rules.md` §4): fill only with disclosed empirical evidence — a command that
   exists in the source or the project, a path you verified, a convention you observed —
   otherwise leave `{OPEN: question — why}` on that exact value. Open items from step 2 that
   attach to a specific step value become `{OPEN}` markers there; open items that do not
   attach to any step are design or decision questions and go to the distillation report, not
   the plan.

6. **Resolve the gaps by mode:**
   - **Interactive:** enter the Q&A loop (`operating-rules.md` §3) — mandatory, not optional.
     Use `grill-me` if available. Work the plan toward READY as defined in
     `implementation-plan.md`: batch questions by phase, lead with the gaps that block the
     execution path, apply the 70% rule, and present every evidence-backed fill for
     acknowledgment. Keep going until the plan is READY, or the user says done.
   - **Headless:** ask nothing. Fill only evidence-backed gaps; leave the rest `{OPEN}`.
     Record every fill and every open question in the disclosure ledger.

7. **Assemble the plan** on `plan-template.md`: prerequisites and blast radius in CONTEXT,
   the standing resume/state-update SAFEGUARDS from the template, objective rollback triggers,
   plan-level Rollback. Enforce the Separation Rule — if any decision, history, note, to-do,
   or open-question prose survived into the draft, move it out now. WHY is at most one
   paragraph and only if it changes an edge-case judgment.

8. **Write the distillation report** (console output, never part of the plan file):
   - What was excluded, grouped as decisions / design / open items / residue.
   - Where each group lives (it remains in the source) or should live (decision register,
     design doc, issue tracker) — recommendations, not actions; you do not restructure the
     source.
   - Open items that did not attach to any step, each with the document that owns it.

9. **Grade** against `review-rubric.md` and issue the readiness verdict per
   `implementation-plan.md`: **READY**, or **NOT READY** with the numbered list of what is
   missing (open markers on the execution path, steps missing blueprint elements, separation
   violations, non-objective rollback triggers).

10. **Deliver the plan to a file — always.** A plan carries execution state, so it must
    persist; console-only delivery is not valid for this skill. Resolve the destination in
    this order: an explicit destination in the prompt; the project's `forge-output:` setting;
    otherwise write beside the source document as `{source-basename}.plan.md` (inline-text
    source with no destination: interactive — ask once; headless — write to
    `./{slug-of-title}.plan.md`). Strip all scaffolding comments.

## Output

- The plan file, written, carrying `{OPEN: …}` markers for any gap that had no evidence.
- The distillation report.
- The grade block, the readiness verdict (`READY` or `NOT READY — N items`), then the written
  path.
- Headless mode: the disclosure ledger after the report. Interactive mode with surviving
  `{OPEN}` markers: the Open Questions list, and one plain line that the plan is NOT READY,
  how many questions are open, and that the user can fill the markers or re-run
  `/forge:distill-plan` on the plan to close them.

Print the grade block exactly as `review-rubric.md` specifies:

```
- Score: {A, B, C, D, or F}
- Confidence: nn%
- Suggestion:
```

## Acceptance criteria

- The plan contains only ANCHOR-relevant sections and Sequential PROCESS steps — zero
  decisions, history, audit narrative, notes, to-do lists, or open-question prose (the
  Separation Rule holds).
- Every step has `Status` plus all four blueprint elements; every filled element is literal;
  every unfillable element is a marked `{OPEN}`, not a fabricated command.
- The standing resume-rule Gate.Before and state-update Guideline from `plan-template.md` are
  present verbatim in SAFEGUARDS — this is what makes handoff work.
- The source document was not modified.
- The readiness verdict was issued honestly: READY only when every condition in
  `implementation-plan.md` § Readiness holds.
- The plan was written to a file, and the distillation report told the user what stayed
  behind and where it belongs.

## References

- `${CLAUDE_PLUGIN_ROOT}/references/implementation-plan.md`
- `${CLAUDE_PLUGIN_ROOT}/references/plan-template.md`
- `${CLAUDE_PLUGIN_ROOT}/references/framework.md`
- `${CLAUDE_PLUGIN_ROOT}/references/operating-rules.md`
- `${CLAUDE_PLUGIN_ROOT}/references/review-rubric.md`
