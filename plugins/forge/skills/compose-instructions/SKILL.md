---
name: "compose-instructions"
description: >-
  Compose new FORGE-structured instructions an AI agent can execute without interpretation, from a
  rough prompt, a form, a file, or an inline description. Closes the gaps the executing agent would
  otherwise have to guess at: in interactive mode it runs a Q&A loop (using the grill-me skill when
  available) until risk is low or the user says done; in headless mode it best-efforts the result and
  reports its assumptions. Use when the user wants to write, draft, author, or generate agent
  instructions, a prompt, a runbook, or an instruction block, or asks to turn a vague request into a
  precise, self-contained prompt.
triggers:
  - compose instructions
  - write instructions
  - draft a prompt
  - author an instruction block
  - turn this into instructions
  - make this prompt precise
  - write a runbook for the agent
  - forge instructions from
argument-hint: "[inline text | path | 'headless']"
---

# compose-instructions

You turn rough material into a precise, self-contained set of instructions written to the FORGE framework — instructions an executing agent can run without interpretation, even with a full context. Your output is the perfect prompt for the job: clear, concise, complete, and gap-free.

## Read first

- `${CLAUDE_PLUGIN_ROOT}/references/framework.md` — the authoring spec. Section structure, sub-keywords, and the rules instructions must satisfy.
- `${CLAUDE_PLUGIN_ROOT}/references/template.md` — the fill-in scaffold you populate.
- `${CLAUDE_PLUGIN_ROOT}/references/operating-rules.md` — quiet discipline, input resolution, modes, the reality-validation rule, output destination. Obey it.
- `${CLAUDE_PLUGIN_ROOT}/references/review-rubric.md` — how you grade your own output before delivering.

## Inputs

Source material in any form — an inline string, a file path, several paths, or a rough form to transform. Resolve inputs per `operating-rules.md` §2: fix obvious path typos; if a named input is not findable in the obvious place, stop and say so — do not crawl the file system.

Mode is interactive unless the prompt or an argument says `headless` / `quiet` / `batch` / `non-interactive`.

## Process

The following steps are exhaustive.

1. **Read** the source material and the four reference files above.
2. **Draft the ANCHOR first.** `[ANCHOR]` is the only required section. State `Objective`, `Target`, and a measurable `Success Criteria`. If you cannot state a measurable success criterion from the source, that is the first gap to close (interactive) or log (headless).
3. **Map the rest.** Add only the sections that carry information the agent would not reliably have or correctly assume: `[CONTEXT]`, `[WHEN]`, `[PROCESS]`, `[SAFEGUARDS]`, `[WHY]`. An empty section is noise; a needed-but-absent section is a defect. Delete every section you do not use, and delete the template's scaffolding comments.
4. **Infer what is reasonable**, then validate each inference against reality per `operating-rules.md` §4. Read the referenced files, check the named values, confirm the paths.
5. **Find the gaps** — anything missing, unclear, ambiguous, conflicting, or inferred. You are the only party who can judge how an AI agent will read a gap. Run the defect scan from `review-rubric.md` against the draft to surface them.
6. **Close the gaps by mode:**
   - **Interactive:** enter the Q&A loop (`operating-rules.md` §3). Use `grill-me` if available. Apply the 70% rule. Get acknowledgment for every inference. Keep going until the draft grades B or better and everything fillable is filled, or the user says they are done.
   - **Headless:** do not ask. Best-effort each gap, validate where you can, and record every unvalidated inference and every 70%-rule risk in the Assumptions & Risks ledger.
7. **Handle phases (decomposition).** Produce one instruction block by default. When the work spans more than one phase across a boundary — a human decision, or a step needing input that cannot exist until an earlier phase completes — follow the framework's PAUSE-vs-split rule: one block with a `PAUSE` when you can write the branch table now; chained blocks (linking `Gate.After` → `Gate.Before`) when a later phase cannot be written yet. Do not cram a phase boundary into a single block — that forces the agent to fabricate input that does not yet exist. This is the `review-rubric.md` Decomposition check.
8. **Grade** the result against `review-rubric.md`.
9. **Deliver** per `operating-rules.md` §6 — console by default, the `forge-output:` location if the project sets one, or an explicit destination if the user gave one. Strip scaffolding. Emit a fragment instead of a full block if the instructions are meant to be embedded in a larger prompt.

## Output

- The composed instructions, clean.
- Interactive mode, after a file write: the grade block, then the written path.
- Headless mode: the instructions followed by the Assumptions & Risks ledger.

Print the grade block exactly as `review-rubric.md` specifies:

```
- Score: {A, B, C, D, or F}
- Confidence: nn%
- Suggestion:
```

## Acceptance criteria

- The output contains a complete, measurable `[ANCHOR]` and no template scaffolding comments.
- Every `IF` has an `OTHERWISE`; every `LOOP` has a termination condition and a never-reached behavior.
- Every inference was validated against reality where a bounded check was possible.
- Interactive: every inference and every 70%-rule risk was acknowledged by the human before delivery. Headless: every one appears in the ledger.
- The delivered instructions grade B or better, OR the residual risk is stated (interactive: acknowledged; headless: laddered in the ledger).

## References

- `${CLAUDE_PLUGIN_ROOT}/references/framework.md`
- `${CLAUDE_PLUGIN_ROOT}/references/template.md`
- `${CLAUDE_PLUGIN_ROOT}/references/operating-rules.md`
- `${CLAUDE_PLUGIN_ROOT}/references/review-rubric.md`
