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

## Inputs

Two things: the **existing instructions** (a file path or inline text) and the **change request** (what to alter, add, remove, or fix). Resolve inputs per `operating-rules.md` §2: fix obvious path typos; if the named instructions are not findable in the obvious place, stop and say so — do not crawl the file system.

Mode is interactive unless the prompt or an argument says `headless` / `quiet` / `batch` / `non-interactive`.

## Process

The following steps are exhaustive.

1. **Read** the existing instructions, the change request, and the four reference files above.
2. **Locate the change.** Identify exactly which sections, steps, or sub-keywords the request touches. Preserve everything else verbatim — do not rewrite untouched content for style. Respect the human's existing wording.
3. **Apply the change.** Make the requested modification. If it adds a section, populate it from the template; if it removes one, delete it cleanly.
4. **Trace the ripple.** Re-check the whole block for defects the change may have introduced, using the `review-rubric.md` defect scan, with attention to:
   - **Vocabulary drift** — does the change use a different word for a concept named elsewhere?
   - **Branch/loop completeness** — did a new `IF` arrive without an `OTHERWISE`, or a new `LOOP` without termination?
   - **Scope overlap** — does the change now contradict or subsume another instruction?
   - **Gate consistency** — if these are chained blocks, does a changed `Gate.After` still match the next block's `Gate.Before`?
   - **Approach-type mixing** — did the change drop an `Option` into a `Sequential` block?
   - **Decomposition** — did the change extend the block across a phase boundary (a new human decision, or a step needing input that will not exist until an earlier step finishes) so it should become a `PAUSE` or a split into chained blocks? Conversely, did the change remove the boundary that justified a split, so two blocks should merge? Apply the `review-rubric.md` Decomposition check.
5. **Validate inferences** against reality per `operating-rules.md` §4 — including any new file, value, or path the change introduces.
6. **Resolve ambiguity by mode:**
   - **Interactive:** if the change request itself is unclear, or the ripple exposes a gap, enter the Q&A loop (`operating-rules.md` §3). Apply the 70% rule. Acknowledge inferences. Keep going until the result grades B or better and the change is fully specified, or the user says done.
   - **Headless:** do not ask. Best-effort the ambiguity, validate where you can, and record unvalidated inferences and 70%-rule risks in the Assumptions & Risks ledger.
7. **Grade** the revised result against `review-rubric.md`.
8. **Deliver** per `operating-rules.md` §6 — console by default, the `forge-output:` location if set, or an explicit destination if given. If the source was a file and no other destination applies, the revised instructions replace the file's content. Strip any scaffolding.

## Output

- The revised instructions, clean and whole (not a diff, unless the user asks for a diff).
- Interactive mode, after a file write: the grade block, then the written path.
- Headless mode: the instructions followed by the Assumptions & Risks ledger.

Print the grade block exactly as `review-rubric.md` specifies:

```
- Score: {A, B, C, D, or F}
- Confidence: nn%
- Suggestion:
```

## Acceptance criteria

- The requested change is applied, and no content outside its scope was altered.
- The ripple trace found no new Blocking or Major defect, or any it found was resolved before delivery.
- Every new inference was validated against reality where a bounded check was possible.
- Interactive: ambiguities and 70%-rule risks were acknowledged. Headless: they appear in the ledger.
- The revised instructions grade no lower than the original, or the regression is stated and (interactive) acknowledged.

## References

- `${CLAUDE_PLUGIN_ROOT}/references/framework.md`
- `${CLAUDE_PLUGIN_ROOT}/references/template.md`
- `${CLAUDE_PLUGIN_ROOT}/references/operating-rules.md`
- `${CLAUDE_PLUGIN_ROOT}/references/review-rubric.md`
