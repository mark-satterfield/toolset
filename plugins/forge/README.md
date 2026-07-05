# forge

Tooling for **FORGE — Framework for Objective-Rooted, Gated Execution**: a methodology for writing instructions an AI agent can execute without interpretation. The framework's whole premise is that an agent does not infer intent — it executes. Every gap you leave is a judgment call you hand to the agent. `forge` is the tooling that helps you close those gaps before you hand them off.

The framework itself lives in `references/framework.md`. The fill-in scaffold lives in `references/template.md`. The plugin wraps both with three skills.

## What "instructions" means here

A single unit of work written to the framework is a set of **instructions** (the framework's own template titles it an *instruction block*). Instructions may be delivered to an agent as a stand-alone prompt, or embedded in — or referenced by — a larger prompt. The only required part is `ANCHOR` (the objective); every other section is included only when it carries information the agent would not otherwise have or correctly assume.

The goal of every skill here is the same: produce instructions that are **self-contained, clear, concise, and complete**, so the executing agent has as little as possible to infer — even when its context is full. Hallucination is worst when the agent has to fill a gap from a conversation it half-remembers. A self-contained instruction removes the gap.

## Skills

Three standalone skills. None of them calls another — the review *mechanics* live in `references/review-rubric.md`, which all three share.

| Skill | Slash command | What it does |
| --- | --- | --- |
| `compose-instructions` | `/forge:compose-instructions` | Write new instructions from a rough prompt, a form, a file, or an inline description. |
| `revise-instructions` | `/forge:revise-instructions` | Modify existing instructions, preserving what the change doesn't touch and re-checking ripple effects. |
| `review-instructions` | `/forge:review-instructions` | Grade instructions against the framework. Returns only Score / Confidence / Suggestion. Asks nothing. |

All three accept instructions in any form — an inline string, a file path, several file paths, or a rough form to transform. They resolve obvious typos in a path rather than failing on them; if a named input genuinely cannot be found in the obvious place, they stop and say so immediately rather than searching the file system.

## The grade

`review-instructions` returns, and `compose`/`revise` print after they write, exactly this block:

```
- Score: {A, B, C, D, or F}
- Confidence: nn%
- Suggestion:
```

The grade does **not** measure form-completeness (a short instruction can earn an A). It measures **how well the executing agent will understand the instructions, and the risk that execution diverges from what the human intended.** The grade is dominated by the single highest-risk gap, not by an average. **Confidence** is the reviewer's confidence in that risk assessment — high when the instructions are self-contained and every referent was validated against reality, lower when the grade rests on things the reviewer could not check. **Suggestion** appears only when there is a concrete change worth making; otherwise it reads `none`.

The full rubric — defect catalog, severity, anchored A–F bands, confidence bands — is in `references/review-rubric.md`. It grades against the **Common Failure Modes** section of `references/framework.md`, so the linter and the framework can never drift apart.

## Modes

- **Interactive (default).** The skill closes gaps with you. It runs a Q&A loop — using the `grill-me` skill when that skill is installed, otherwise a built-in loop — and keeps asking until the risk is low and everything fillable is filled, or until you say you are done. The loop is mandatory: the skill will not skip it and hand you a draft full of silent guesses. Every question batch includes an explicit "I'm done / show me the draft" exit. For anything it infers, it validates against reality where it can and gets your acknowledgment before relying on it.
- **Headless / quiet.** Set by passing `headless` (or `quiet` / `batch` / `non-interactive`) in the prompt or as a skill argument. The skill asks nothing and best-efforts the result, but headless is **not** permission to guess — it only removes the option to ask. It still validates against reality where it can, and it emits a **disclosure ledger** so nothing it filled or left open is hidden.

**The gap rule (both modes).** A gap is filled only with **disclosed empirical evidence** — something observed in reality (the source, an existing file, a project convention), not the skill's own hunch — and the evidence is shown to you. A gap it cannot ground stays a gap: it is marked inline as `{OPEN: <question> — <why>}` rather than guessed. When a human can't answer — headless, or you stepped away and the wait timed out — the skill **still does not guess**; it leaves the `{OPEN}` markers and tells you the output is incomplete. Incomplete-but-honest output is a valid deliverable; a complete-looking fabrication is not. You can fill the `{OPEN}` markers yourself, or run the instructions back through `/forge:compose-instructions` and answer the Q&A to close them.

Validation is bounded: read the named file, check the named value, look at how sibling cases are handled — the obvious referent in the obvious place. The skills do not crawl the file system.

## Output

By default, composed and revised instructions print to the **console**.

You can change the default for a project the way you would set an environment variable — by putting a line in your project's `CLAUDE.md` (or any file Claude loads as project memory):

```
forge-output: docs/instructions/
```

When `forge-output:` names a directory, written instructions go there under a filename derived from the instruction title. When it names a file, they go to that file. An explicit destination in your prompt always wins over both the `forge-output:` setting and the console default. `review-instructions` never writes a file and ignores this setting.

Output is clean: the template's scaffolding comments are deleted, and no provenance or "generated by" markers are added unless you ask for them.

## Layout

```
plugins/forge/
├── .claude-plugin/plugin.json
├── plugin.json
├── README.md
├── CLAUDE.md
├── commands/
│   ├── compose-instructions.md
│   ├── revise-instructions.md
│   └── review-instructions.md
├── references/
│   ├── framework.md        — the FORGE framework (the authoring spec and the defect catalog)
│   ├── template.md         — the fill-in instruction-block scaffold
│   ├── operating-rules.md  — shared behavioral contract: quiet discipline, modes, validation, output
│   └── review-rubric.md    — shared grading mechanics: defects, severity, A–F bands, confidence
└── skills/
    ├── compose-instructions/SKILL.md
    ├── revise-instructions/SKILL.md
    └── review-instructions/SKILL.md
```

## Scope

**Does:** turn rough material into precise instructions; modify existing instructions safely; grade instructions for interpretability and intent-fidelity risk; close gaps interactively or best-effort them headlessly.

**Does NOT:** execute the instructions it writes. `forge` produces the prompt; running it is a separate act.
