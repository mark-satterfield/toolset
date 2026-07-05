# Review rubric — shared grading mechanics

The single source of truth for how forge grades instructions. `review-instructions` runs this end to end. `compose-instructions` and `revise-instructions` run it on their own output before delivering, and print the result. No skill restates these rules — they cite this file.

Grade against `framework.md`. Its **Common Failure Modes** section is the defect catalog. Its section definitions are the structural checklist. Because the rubric points at the framework rather than copying it, the two cannot drift apart.

---

## What the grade measures

The grade does **not** measure form-completeness. A three-line instruction with only an `ANCHOR` can earn an **A** if that anchor leaves the agent nothing to guess. A fully-populated instruction with every section present can earn an **F** if one of those sections hands the agent a dangerous, unbounded choice.

The grade measures two coupled things, both about the **executing agent**, not about the document:

1. **Interpretability** — will the agent understand exactly what to do, with no gap it must fill by guessing?
2. **Intent-fidelity risk** — where a gap exists, how likely is the agent's fill to diverge from what the human meant, and how costly is that divergence?

**The grade is dominated by the single highest-risk gap, not by an average.** One blocking ambiguity caps the grade low no matter how clean the rest is. Averaging would let a dangerous void hide behind good prose. Do not average.

---

## The defect scan

Check the instructions against every item below. Each maps to the framework. For each defect found, assign a severity (next section).

**Anchor integrity**
- `ANCHOR` present with `Objective`, `Target`, and `Success Criteria`.
- `Success Criteria` is observable and measurable, not a qualitative judgment ("successfully completed", "properly handled", "fully verified").
- `Target` names a specific subject, not a broad spatial noun ("the system", "the codebase", "the data").

**Branch and loop completeness**
- Every `IF` has an explicit `OTHERWISE` (even if `OTHERWISE: Continue.`).
- Every `LOOP` has an explicit termination condition AND a defined behavior if termination is never reached.
- Unlisted state handling: if execution can produce a state that is neither success nor failure (UNKNOWN, TIMEOUT, PARTIAL), the instructions define what the agent does in it.
- Missing prerequisite behavior: if a prerequisite can be absent, the instructions say whether to halt, fix, skip, or report.

**Language precision**
- No qualitative modifiers that force a subjective call: "as needed", "where appropriate", "if necessary", "where possible".
- No softened commands: a strict command followed by a clause that quietly reintroduces an exception. Exceptions must be their own conditional.
- No in-line "unless" / "except" appended to a primary instruction.
- No passive voice that hides the actor ("the file should be written" — by whom?).
- Vocabulary is consistent: one concept, one word, throughout (a "test" is not later a "check" or "verification script").

**Structure**
- Approach types are not mixed at the same level (a `Sequential` block with a mid-stream `Option` is really `White-Listed` — it must be restructured or nested).
- Scope does not overlap: specific instructions and broad generic ones do not contradict or subsume each other.
- Exhaustiveness is stated where it matters: if a list is closed, it says so ("The following steps are exhaustive").
- Illustrative examples are not embedded where the agent could mistake them for binding rules.

**Actors and gates**
- Agent steps are not annotated; only human/external steps carry `[Human: …]` or `[System: …]`.
- `Stop If` and `Keep Going` are not both set for the same class of error.
- In a chained set, each block's `Gate.Before` matches the prior block's `Gate.After`.

**Decomposition** (framework: "When to use PAUSE vs. splitting…" and "Chaining Instruction Blocks")
- A block that spans more than one phase across a boundary — a human decision, or a step needing input that cannot exist until an earlier step completes — uses the framework's mechanism for that boundary: a `PAUSE` when the branch table is writable now, or a split into chained blocks (`Gate.After` → `Gate.Before`) when the next phase cannot be written yet. A monolith that crams such a boundary is a defect. It is **Blocking** when it forces the agent to act on input that does not yet exist (the agent will fabricate it); otherwise **Major**.
- The inverse — two or more blocks that share one objective with no real phase boundary — should be a single block. Needless fragmentation is a **Minor** defect.

**Open-question markers**
- A gap the author left as `{OPEN: … — why}` (per `framework.md` Notation) is **disclosed incompleteness, not a hidden defect.** Grade it by its impact if executed unfilled — a load-bearing `{OPEN}` on a destructive or irreversible path is still **Blocking**; an `{OPEN}` on a cosmetic choice is **Minor**. Never treat a properly-marked, disclosed open question as a trap; the trap is the *undisclosed guess*, which reads as a normal value and which this rubric cannot catch by inspection — the composing process (`operating-rules.md` §4) exists to prevent it.
- While any `{OPEN}` marker remains, the instructions are incomplete by definition: they cannot grade **A**, and the Suggestion must name closing the open questions as the path to a higher grade.

---

## Severity

Assign each defect one severity. Severity is about the executing agent's likely behavior, not about tidiness.

- **Blocking** — the agent cannot proceed correctly, or is as likely to take a wrong, costly action as a right one. Examples: no measurable `Success Criteria`; a destructive or irreversible action over an undefined boundary; an `IF` guarding a destructive branch with no `OTHERWISE`.
- **Major** — a real ambiguity that will plausibly change the outcome, but not catastrophically. The agent will probably guess right; the human is carrying real risk.
- **Minor** — low-divergence or cosmetic. Passive voice that is still unambiguous, mild vocabulary drift, a missing exhaustiveness statement on a list the agent would treat as closed anyway.

---

## Grade bands

Map the defect set to a letter. Find the lowest band whose condition the instructions meet.

- **F** — `ANCHOR` missing or non-actionable (no measurable `Success Criteria`); OR a destructive/irreversible action over an undefined boundary; OR two or more Blocking defects. The agent cannot safely execute this.
- **D** — exactly one Blocking defect; OR a cluster of Major defects that together make a wrong material outcome as likely as a right one.
- **C** — no Blocking defects, but one or more Major defects that could plausibly change the outcome. The agent will probably comply, but the human is carrying risk they should see.
- **B** — no Blocking and no outcome-changing Major defects. At most one or two low-impact Majors, or several Minors. Intent will almost certainly survive execution.
- **A** — no Blocking, no Major. At most cosmetic Minors. An agent with a full context or an empty one executes it the same way the human intended; `Success Criteria` is objectively verifiable.

---

## Confidence

Confidence is a percentage expressing how much you trust your own grade — not how good the instructions are.

It rises when the instructions are self-contained and every referent named in them was validated against reality (the files exist, the values check out, the paths resolve). It falls when the grade rests on something you could not check: a referenced file you cannot see, an external system's behavior, a term whose real-world meaning you had to assume.

Bands:

- **90–100%** — instructions are self-contained, or every referent was validated. The grade stands on facts.
- **70–89%** — minor unvalidated assumptions remain, none load-bearing for the grade.
- **50–69%** — the grade depends on an external or a referent you could not verify.
- **below 50%** — you could not validate the load-bearing parts. The grade is provisional; say so in the suggestion.

`review-instructions` does **not** ask questions to raise its confidence. It reports the confidence it has. `compose` and `revise`, in interactive mode, will already have validated and asked before they grade — so their confidence is normally high.

---

## Suggestion

Optional. Include a suggestion only when there is a concrete change that would raise the grade or cut risk — the one or two highest-value fixes, stated as actionable edits, not observations. If the grade is already A with high confidence, or if no change is worth making, write `none`.

A review may still suggest even when it is not lowering the grade — if you would strongly recommend an addition, name it here.

---

## Output contract

The grade is reported as exactly this block, and for `review-instructions` it is the **entire** output — no preamble, no questions, no narration:

```
- Score: {A, B, C, D, or F}
- Confidence: nn%
- Suggestion:
```

`nn` is the integer confidence. After `Suggestion:` put the concrete recommendation, or `none`.
