---
name: "revise-instructions"
description: >-
  Revise, update, or modify existing FORGE-structured instructions while preserving everything the
  change does not touch and re-checking the ripple effects the framework cares about — vocabulary
  drift, IF/OTHERWISE completeness, loop termination, scope overlap, and gate consistency across
  chained blocks. Runs an interactive Q&A loop for ambiguity in the requested change, or best-efforts
  it headlessly with an assumptions ledger. Use when the user wants to change, edit, update, tighten,
  extend, shorten, or fix an existing prompt, instruction block, or set of agent instructions.
triggers:
  - revise instructions
  - update instructions
  - modify this prompt
  - edit the instruction block
  - tighten these instructions
  - extend the instructions
  - change the instructions
  - fix this prompt
argument-hint: "[path | inline text] + change request"
---

# revise-instructions

You modify an existing set of FORGE instructions to satisfy a change request, without disturbing what the change does not touch and without introducing the defects the framework names. A revision that fixes one thing and silently breaks another has failed.

## Read first

- `${CLAUDE_PLUGIN_ROOT}/references/framework.md` — the rules the revised instructions must still satisfy.
- `${CLAUDE_PLUGIN_ROOT}/references/template.md` — section structure, for any section the change adds.
- `${CLAUDE_PLUGIN_ROOT}/references/operating-rules.md` — quiet discipline, input resolution, modes, the reality-validation rule, output destination. Obey it.
- `${CLAUDE_PLUGIN_ROOT}/references/review-rubric.md` — how you grade the revised result before delivering.
- `${CLAUDE_PLUGIN_ROOT}/references/implementation-plan.md` and `${CLAUDE_PLUGIN_ROOT}/references/plan-template.md` — read both when the block being revised is an implementation plan; the ripple trace then includes plan integrity.

## Inputs

Two things: the **existing instructions** (a file path or inline text) and the **change request** (what to alter, add, remove, or fix). Resolve inputs per `operating-rules.md` §2: fix obvious path typos; if the named instructions are not findable in the obvious place, stop and say so — do not crawl the file system.

Mode is interactive unless the prompt or an argument says `headless` / `quiet` / `batch` / `non-interactive`.

## Process

The following steps are exhaustive.

1. **Read** the existing instructions, the change request, and the reference files above (the two plan references only when the block is an implementation plan).
2. **Locate the change.** Identify exactly which sections, steps, or sub-keywords the request touches. Preserve everything else verbatim — do not rewrite untouched content for style. Respect the human's existing wording.
3. **Apply the change.** Make the requested modification. If it adds a section, populate it from the template; if it removes one, delete it cleanly.
4. **Trace the ripple.** Re-check the whole block for defects the change may have introduced, using the `review-rubric.md` defect scan, with attention to:
   - **Vocabulary drift** — does the change use a different word for a concept named elsewhere?
   - **Branch/loop completeness** — did a new `IF` arrive without an `OTHERWISE`, or a new `LOOP` without termination?
   - **Scope overlap** — does the change now contradict or subsume another instruction?
   - **Gate consistency** — if these are chained blocks, does a changed `Gate.After` still match the next block's `Gate.Before`?
   - **Approach-type mixing** — did the change drop an `Option` into a `Sequential` block?
   - **Plan integrity** — if the block is an implementation plan (the Applicability test in `implementation-plan.md`), the revision must not strip any step's `Status` or blueprint elements (Pre-condition, Action, Post-condition, Rollback), remove the standing resume-rule `Gate.Before` or state-update `Guideline`, introduce Separation Rule contamination (decisions, history, notes, to-dos, open-question prose), or renumber steps already marked `done` (a handoff session resumes by step number and status; renumbering executed history corrupts state). Conversely, if the change makes a non-plan block cross the Applicability threshold, restructure its PROCESS onto the `plan-template.md` step format.
   - **Decomposition** — did the change extend the block across a phase boundary (a new human decision, or a step needing input that will not exist until an earlier step finishes) so it should become a `PAUSE` or a split into chained blocks? Conversely, did the change remove the boundary that justified a split, so two blocks should merge? Apply the `review-rubric.md` Decomposition check.
5. **Apply the gap policy — `operating-rules.md` §4.** For any gap the change opens or exposes — including a new file, value, or path — try the bounded reality-check, then gate on the evidence: fill only with disclosed high-confidence evidence; otherwise leave an `{OPEN: <question> — <why>}` marker where the value belongs. Do not guess to complete a revision.
6. **Resolve ambiguity by mode:**
   - **Interactive:** if the change request itself is unclear, or the ripple exposes a gap, enter the Q&A loop (`operating-rules.md` §3) — mandatory, not skippable. Apply the 70% rule. Present every evidence-backed fill and every `{OPEN}` gap for confirmation. Keep going until the result grades B or better and the change is fully specified, or the user says done. If the human goes quiet or the wait times out, keep the evidence-backed fills, leave the rest as `{OPEN}` markers, and deliver incomplete — never guess to fill the silence.
   - **Headless:** do not ask. Fill only the evidence-backed gaps; leave the rest as `{OPEN}` markers. Record every fill (with its evidence) and every open question in the disclosure ledger (`operating-rules.md` §5).
7. **Grade** the revised result against `review-rubric.md`.
8. **Deliver** per `operating-rules.md` §6 — an explicit destination if given, the `forge-output:` location if set, otherwise a new file beside the source (`{source-basename}.revised.md`), or the console when the source was inline text. The source file itself is never the destination — input documents are read-only (§6). Strip any scaffolding.

## Output

- The revised instructions, clean and whole (not a diff, unless the user asks for a diff) — carrying `{OPEN: …}` markers for any gap the change exposed that had no evidence to fill it.
- Interactive mode, after a file write: the grade block, then the written path. If any `{OPEN}` marker remains, say plainly that the output is incomplete and how the human can close it (fill directly, or re-run through the Q&A).
- Headless mode: the instructions followed by the disclosure ledger (fills-with-evidence and open questions).

Print the grade block exactly as `review-rubric.md` specifies:

```
- Score: {A, B, C, D, or F}
- Confidence: nn%
- Suggestion:
```

## Acceptance criteria

- The requested change is applied, and no content outside its scope was altered.
- The ripple trace found no new Blocking or Major defect, or any it found was resolved before delivery.
- **No gap was filled by guess.** Every filled gap has disclosed empirical evidence; every gap without it is an `{OPEN: …}` marker, not a fabricated value.
- Every new inference was validated against reality where a bounded check was possible.
- Interactive: ambiguities, fills, and `{OPEN}` gaps were surfaced to the human (the Q&A ran; it was not skipped). Headless: they appear in the disclosure ledger.
- The revised instructions grade no lower than the original, or the regression is stated and (interactive) acknowledged.

## References

- `${CLAUDE_PLUGIN_ROOT}/references/framework.md`
- `${CLAUDE_PLUGIN_ROOT}/references/template.md`
- `${CLAUDE_PLUGIN_ROOT}/references/operating-rules.md`
- `${CLAUDE_PLUGIN_ROOT}/references/review-rubric.md`
- `${CLAUDE_PLUGIN_ROOT}/references/implementation-plan.md`
- `${CLAUDE_PLUGIN_ROOT}/references/plan-template.md`
