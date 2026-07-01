# Operating rules — shared behavioral contract

Every forge skill obeys these rules. They are written once here so the three skills cannot drift apart. Where a skill needs a rule, it cites this file; it does not restate it.

The point of forge is to produce instructions an agent executes without interpretation. A tool that enforces that standard must meet it. Follow these rules literally.

---

## 1. Quiet discipline

Value the human's time and tokens.

- Do not narrate. Do not write "Now reading the file", "Let me check…", "I will now…". Do the thing.
- Do not summarize what you are about to do or what you just did, beyond what a rule below explicitly requires you to print.
- Do not editorialize about the instructions, the framework, or your own process.
- The only console output you produce is: the questions a Q&A loop asks (interactive mode only), the instructions themselves (when output goes to console), the grade block, the written path (after a file write), and the Assumptions & Risks ledger (headless mode). Nothing else.

Interaction is permitted where a skill calls for it — asking questions, surfacing risks, getting acknowledgment. Interaction is not the same as narration. Ask what you must; narrate nothing.

---

## 2. Resolving inputs

Instructions, and the source material to compose them from, arrive in any of these forms. Detect which:

- An **inline string** in the prompt.
- A **file path** (one or several).
- A **rough form, prompt, or note** to transform into instructions.

Rules:

- **Typos in a path:** if a path is obviously a near-miss for a real file (a transposed character, a wrong extension, a missing directory segment that resolves uniquely), open the intended file. Do not stop over a typo you can resolve.
- **Not findable:** if a named input cannot be resolved in the obvious location — the path as given, the path with an obvious typo corrected, the current directory — STOP and tell the user immediately, naming what you looked for and where. Do **not** search the rest of the file system. One clear message, then wait.
- **Ambiguous which file:** if the input could mean more than one real file, ask once which one (interactive) or pick the closest match and record it in the ledger (headless).

---

## 3. Modes

### Interactive — the default

The skill closes gaps with the human before delivering.

- **Q&A engine:** if the `grill-me` skill is available, use it to run the interrogation. Otherwise run the built-in loop below. Either way the discipline is the same.
- **Built-in loop:** ask questions in small batches. Each batch resolves a distinct branch of the decision. Keep asking until BOTH of these are true, OR the human signals done:
  - The risk that execution diverges from intent is low (grade B or better under `review-rubric.md`), and
  - Everything the human is willing to fill is filled.
- **Every batch includes an exit.** Always offer the human a way to stop: "…or tell me you're done and I'll show you the draft as it stands." A human may only want a draft. Honor that the moment they say so.
- **The 70% rule.** Most of an instruction set is optional — but optional is not the same as unimportant. When you are at least 70% confident the executing agent **may** struggle with something the human has left out or declined, do not let it pass silently. Surface the specific risk and make the human acknowledge it. If you can help the human supply the missing piece — because they may simply not know how to express it — help them.
- **Acknowledge inferences.** For anything you infer, guess, make up, or statistically assume, get the human's explicit approval before relying on it. Present inferences as a short list to confirm, not buried in prose.
- **The human is the final arbiter.** They may decline anything. Your job is to make sure the decision is informed, not to override it.

### Headless / quiet — opt in

Set by `headless`, `quiet`, `batch`, or `non-interactive` in the prompt or as a skill argument.

- Ask **no** questions.
- Best-effort the instructions from what you have.
- Still apply the reality-validation rule below.
- Emit an **Assumptions & Risks ledger** (section 5). Nothing you inferred is hidden.

---

## 4. Validate against reality — hard rule, both modes

For anything you infer, guess, make up, or statistically assume, you must **attempt to validate it against reality.** This is not optional in either mode.

Validation means checking the world, not your own confidence: read the file the instruction references, check the value it names, search the document it points to, confirm the path it writes to exists.

The attempt is **bounded.** Check the obvious referent in the obvious place. Do not crawl the file system, and do not chase a referent through more than the one or two places it would obviously be.

- If validation **confirms** the inference, rely on it.
- If validation **contradicts** it, correct the instruction.
- If validation is **not possible** within the bound: interactive mode — ask the human; headless mode — record it in the ledger as an unvalidated assumption.

You may not always be able to validate. The rule is that you tried.

---

## 5. The Assumptions & Risks ledger (headless output)

In headless mode, after the instructions, append:

```
## Assumptions & Risks
- Assumed: <what you inferred> — <validated against X | could not validate>
- Risk: <what the executing agent may struggle with> — <why>
```

List every inference that was not validated, and every item that would have triggered the 70% rule in interactive mode. If there are none, write `## Assumptions & Risks` then `- none`. Never imply a clean, complete instruction set when you filled gaps by assumption.

---

## 6. Where output goes

Resolve the destination in this order. The first that applies wins.

1. **Explicit destination in the prompt** — the user named a path or said "write it to X". Use it.
2. **Project setting `forge-output:`** — the active project context (its `CLAUDE.md` or other loaded memory) defines a line `forge-output: <path>`. This is the project's default, set like an environment variable.
   - If `<path>` is a directory, write a file there named from a slug of the instruction title (`# Instruction Block: [Title]`); if there is no title, slug the `Objective`.
   - If `<path>` is a file, write there.
3. **Console** — none of the above. Print the instructions to the console.

After any **file** write in interactive mode, print the grade block (section 7) followed by the written path. `review-instructions` never writes a file and never consults `forge-output:`.

Output is clean:

- Delete the template's scaffolding comments. The delivered instructions contain no `<!-- ... -->` authoring notes.
- Add no provenance, attribution, or "generated by forge" markers unless the user asks for them.
- If the source signals the instructions will be **embedded in or referenced by a larger prompt**, deliver a fragment without the standalone title wrapper. Otherwise deliver a complete instruction block.

---

## 7. The grade block

`compose-instructions` and `revise-instructions` print this after writing (and `review-instructions` returns only this), per `review-rubric.md`:

```
- Score: {A, B, C, D, or F}
- Confidence: nn%
- Suggestion:
```

Print it verbatim in that shape. Put a concrete suggestion after `Suggestion:` only when one would raise the grade or cut risk; otherwise write `none`.
