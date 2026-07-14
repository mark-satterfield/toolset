# Operating rules — shared behavioral contract

Every forge skill obeys these rules. They are written once here so the three skills cannot drift apart. Where a skill needs a rule, it cites this file; it does not restate it.

The point of forge is to produce instructions an agent executes without interpretation. A tool that enforces that standard must meet it. Follow these rules literally.

---

## 1. Quiet discipline

Value the human's time and tokens.

- Do not narrate. Do not write "Now reading the file", "Let me check…", "I will now…". Do the thing.
- Do not summarize what you are about to do or what you just did, beyond what a rule below explicitly requires you to print.
- Do not editorialize about the instructions, the framework, or your own process.
- The only console output you produce is: the questions a Q&A loop asks (interactive mode only), the instructions themselves (when output goes to console), the grade block, the written path (after a file write), the disclosure ledger (headless mode, or interactive when `{OPEN}` markers remain), and — when the output is incomplete — one plain line telling the human so. Nothing else.

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
- **The loop is not optional.** You must surface every gap and every inference to the human before delivering. Delivering output that contains a fill the human never saw, or an unmarked gap, is a failure of the skill — not a shortcut. What you may fill and what must stay open is governed by §4.
- **If the human goes quiet.** If a question is not answered — the human stepped away and the wait times out — do **not** fill the open gap with a guess. Apply §4: keep the high-confidence, evidence-backed fills, leave every other gap as an `{OPEN: …}` marker, and tell the human the output is incomplete.

### Headless / quiet — opt in

Set by `headless`, `quiet`, `batch`, or `non-interactive` in the prompt or as a skill argument.

- Ask **no** questions.
- Best-effort the instructions from what you have — under §4. Headless is not permission to guess: it only removes the option to *ask*. Evidence-gated fills still apply, and a gap with no evidence still stays open.
- Apply §4 in full — reality-validation, the confidence gate, and the `{OPEN: …}` markers for gaps you cannot ground.
- Emit the **disclosure ledger** (§5): every evidence-backed fill and every open question. Nothing you inferred or left open is hidden.

---

## 4. The gap policy — evidence, confidence, and when to stop

A gap is anything the instruction needs that the source did not give you: a missing fact, an unnamed path, an ambiguous term, a value you would otherwise just assume. How you handle a gap is the core of forge. Follow this literally in **both** modes.

**Never fill a gap from plausibility.** Your own sense that an answer is "probably right" is not a basis to fill anything. A fill needs **empirical evidence** — something you observed in reality:

- the source material itself,
- an existing file, value, or pattern in the project that you checked,
- a convention visible in the surrounding code, tree, or docs.

**Validate against reality — the bounded check.** For any gap you intend to fill, first try to ground it: read the file the instruction references, check the value it names, look at how sibling cases are handled, confirm the path exists. The attempt is **bounded** — the obvious referent in the obvious place. Do not crawl the file system, and do not chase a referent through more than the one or two places it would obviously be. The rule is that you *tried*.

**Then rate the fill by the evidence, not by your confidence:**

- **High — the evidence points to one answer.** Fill it, then **disclose the evidence**: state what you observed and why it decided the fill. Example: *"The source never says where `progress_tools.py` should be written, but four sibling scripts live in `scripts/mcp/`, so I place the new one there."* Interactive: present it for acknowledgment. Headless: record it in the ledger. A confirmed inference is relied upon; a contradicted one is corrected.
- **Not high — no evidence, thin evidence, or evidence pointing more than one way.** **Do not fill it.** It becomes an **open question** (below). Filling here is the exact failure forge exists to prevent.

**Disclosure is never optional.** No gap is ever filled silently. If the human cannot see what you decided and the evidence you decided it on, you have broken this rule.

### When a human cannot answer

Two situations put a gap beyond a human's reach in the moment: **headless mode** (you were told not to ask), and **interactive mode where the human does not answer** — they stepped away and the wait times out. Treat both the same:

- A **high-confidence, evidence-backed** fill may stand — disclosed.
- A **not-high-confidence** gap **stays open. You do not close it with a guess.** An unanswered question is not permission to invent; it is the absence of an answer. Leave it open.

### Incomplete output is acceptable. Fabricated output is not.

Instructions delivered with clearly-marked open questions are a valid, honest deliverable. Instructions that *look* complete because you filled the holes with guesses are a failure — the worst outcome forge can produce, because the human cannot tell the guess from the fact.

- Mark every unresolved gap inline, where it belongs: `{OPEN: <the question the human must answer> — <why it is open: no evidence / conflicting evidence / unanswered>}`.
- Collect them all in the **Open Questions** part of the disclosure ledger (§5).
- Tell the human plainly: the output is incomplete, N questions are open, and they can either fill the `{OPEN: …}` markers themselves or run the instructions back through `/forge:compose-instructions` and answer the Q&A to close them.

Never imply a clean, complete instruction set when any gap was filled by assumption or left open.

---

## 5. The disclosure ledger

Every gap you touched is disclosed here, in two parts:

```
## Disclosure
Assumptions — gaps filled, with the evidence for each:
- Assumed: <the fill> — Evidence: <what you observed> — <validated against X | could not validate>
- Risk: <what the executing agent may still struggle with> — <why>

Open Questions — gaps left unfilled, each still marked {OPEN: …} in the instructions:
- Open: <the question the human must answer> — <why it is open: no evidence / conflicting evidence / unanswered>
```

**Headless mode** always appends the full ledger after the instructions. **Interactive mode** appends the **Open Questions** list whenever any `{OPEN: …}` marker survives to delivery — the human stepped away, the wait timed out, or they declined to answer. If a part is empty, write its header and `- none`. Never imply a clean, complete instruction set when you filled a gap by assumption or left one open.

---

## 6. Where output goes

**Input documents are read-only.** No skill ever overwrites a file it read as input. The one exception: the user's prompt explicitly names that exact input path as the destination (rule 1). If any other rule resolves to an input path, fall through to rule 3's naming instead.

Resolve the destination in this order. The first that applies wins.

1. **Explicit destination in the prompt** — the user named a path or said "write it to X". Use it.
2. **Project setting `forge-output:`** — the active project context (its `CLAUDE.md` or other loaded memory) defines a line `forge-output: <path>`. This is the project's default, set like an environment variable.
   - If `<path>` is a directory, write a file there named from a slug of the instruction title (`# Instruction Block: {Title}`); if there is no title, slug the `Objective`.
   - If `<path>` is a file, write there.
3. **New file beside the source** — the source was a file and nothing above applies. Write a new file next to it, named `{source-basename}.{artifact}.md` where `{artifact}` says what the file is: `instructions` (compose-instructions), `revised` (revise-instructions), `plan` (distill-plan).
4. **Console** — the source was inline text and nothing above applies. Print the instructions to the console.

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
