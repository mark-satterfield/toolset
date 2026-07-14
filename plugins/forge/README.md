# forge

Tooling for **FORGE — Framework for Objective-Rooted, Gated Execution**: a methodology for writing instructions an AI agent can execute without interpretation. The framework's whole premise is that an agent does not infer intent — it executes. Every gap you leave is a judgment call you hand to the agent. `forge` is the tooling that helps you close those gaps before you hand them off.

The framework itself lives in `references/framework.md`. The fill-in scaffold lives in `references/template.md`. The plugin wraps both with three skills.

## What "instructions" means here

A single unit of work written to the framework is a set of **instructions** (the framework's own template titles it an *instruction block*). Instructions may be delivered to an agent as a stand-alone prompt, or embedded in — or referenced by — a larger prompt. The only required part is `ANCHOR` (the objective); every other section is included only when it carries information the agent would not otherwise have or correctly assume.

The goal of every skill here is the same: produce instructions that are **self-contained, clear, concise, and complete**, so the executing agent has as little as possible to infer — even when its context is full. Hallucination is worst when the agent has to fill a gap from a conversation it half-remembers. A self-contained instruction removes the gap.

## Skills

Four standalone skills. None of them calls another — the review *mechanics* live in `references/review-rubric.md`, which all four share.

| Skill | Slash command | What it does |
| --- | --- | --- |
| `compose-instructions` | `/forge:compose-instructions` | Write new instructions from a rough prompt, a form, a file, or an inline description. |
| `revise-instructions` | `/forge:revise-instructions` | Modify existing instructions, preserving what the change doesn't touch and re-checking ripple effects. |
| `review-instructions` | `/forge:review-instructions` | Grade instructions against the framework. Returns only Score / Confidence / Suggestion. Asks nothing. |
| `distill-plan` | `/forge:distill-plan` | Distill a READY implementation plan out of a multi-purpose document. Steps in; everything else stays out. |

All four accept instructions in any form — an inline string, a file path, several file paths, or a rough form to transform. They resolve obvious typos in a path rather than failing on them; if a named input genuinely cannot be found in the obvious place, they stop and say so immediately rather than searching the file system.

## Implementation plans

The plan discipline attaches to the **kind of work, not the skill that authored the block**. Whenever a block passes the Applicability test in `references/implementation-plan.md` — a step changes state outside the conversation, execution could span sessions or hands, or failure requires recovery — its PROCESS follows the plan rules, no matter which skill wrote it. `compose-instructions` authoring implementation work from rough notes emits exactly the same PROCESS shape as `distill-plan`; `revise-instructions` preserves it through changes; `review-instructions` grades it with the plan-class defects. Blocks that fail the test (read-only analysis, trivial single-session tasks) stay ordinary — no Status fields on a three-step lookup.

**When to use which skill** — the output shape is the same, so choose by the input problem:

| Your starting point | Use | Why |
| --- | --- | --- |
| Intent — rough notes, a request, a description of what should happen | `/forge:compose-instructions` | The work is **authoring**. If it classifies as a plan, PROCESS comes out in plan form automatically. |
| An existing multi-purpose document with a plan buried in it | `/forge:distill-plan` | The work is **extraction**: classify the content, take only the steps, report where the decisions, design, history, and open items belong. |

One-line heuristic: *is there a document the plan has to be pulled out of?* `distill-plan`. Otherwise `compose-instructions`. If you can't tell, the cost of guessing wrong is near zero — distill is compose plus the separation pass.

Agent-generated working documents accrete purposes: a decision register, a target-state design, a work breakdown, an open-items list — all in one file. Executing that file directly hands the agent noise as instruction. `distill-plan` separates the plan from everything else:

- **The plan takes only current implementation steps.** Decisions, history, audit narrative, notes, to-do lists, and open-question prose stay outside — the **Separation Rule** in `references/implementation-plan.md`. The source document is never modified; a distillation report says what was excluded and where it belongs.
- **Every step is deterministic.** Phase → Step hierarchy, each step carrying the four-element execution blueprint: a literal **Pre-condition**, the exact **Action**, a literal **Post-condition**, and a specific **Rollback**. An objective masquerading as a step ("Update the DNS records") is treated as a gap, not a step.
- **The plan carries its own execution state.** Every step has a `Status` (`pending` / `in-progress` / `done` / `blocked`), executors update it as they work, and the standing resume rule means any session — including one picking up after another ran out of context — opens the plan cold and knows exactly which step is next, because all preceding steps are marked `done`.
- **The plan is graded for readiness.** The skill runs the interactive Q&A until the plan is **READY** (every step complete and literal, no `{OPEN}` markers on the execution path, no separation violations, grade B or better) or delivers it honestly marked **NOT READY** with what remains.

The doctrine lives in `references/implementation-plan.md`; the scaffold in `references/plan-template.md`. The `review-instructions` rubric includes plan-class defects, so grading a plan through `/forge:review-instructions` checks the same rules.

## Agent

`plan-distiller` — a subagent that runs `distill-plan` headlessly in its own context, for large documents you don't want loaded into the main session or for pipeline use. It never guesses: gaps without evidence come back as `{OPEN: …}` markers with the disclosure ledger. Interactive gap-closing stays in the main session via `/forge:distill-plan` — a subagent cannot interrogate you.

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

**Input documents are never overwritten.** A file a skill read as input is read-only; the only way output lands on an input file is naming that exact path as the destination in your prompt.

When no destination is indicated and the source was a file, output goes to a new sibling file whose name says what it is — `{source-basename}.instructions.md` (compose), `{source-basename}.revised.md` (revise), `{source-basename}.plan.md` (distill). When the source was inline text, composed and revised instructions print to the **console**.

You can set a project-wide destination the way you would set an environment variable — by putting a line in your project's `CLAUDE.md` (or any file Claude loads as project memory):

```
forge-output: docs/instructions/
```

When `forge-output:` names a directory, written instructions go there under a filename derived from the instruction title. When it names a file, they go to that file. An explicit destination in your prompt always wins over the `forge-output:` setting. `review-instructions` never writes a file and ignores this setting.

Output is clean: the template's scaffolding comments are deleted, and no provenance or "generated by" markers are added unless you ask for them.

## Layout

```
plugins/forge/
├── .claude-plugin/plugin.json
├── plugin.json
├── README.md
├── CLAUDE.md
├── agents/
│   └── plan-distiller.md   — headless subagent wrapper around distill-plan
├── commands/
│   ├── compose-instructions.md
│   ├── revise-instructions.md
│   ├── review-instructions.md
│   └── distill-plan.md
├── references/
│   ├── framework.md            — the FORGE framework (the authoring spec and the defect catalog)
│   ├── template.md             — the fill-in instruction-block scaffold
│   ├── implementation-plan.md  — the plan doctrine: blueprint, Separation Rule, execution state, readiness
│   ├── plan-template.md        — the fill-in implementation-plan scaffold
│   ├── operating-rules.md      — shared behavioral contract: quiet discipline, modes, validation, output
│   └── review-rubric.md        — shared grading mechanics: defects, severity, A–F bands, confidence
└── skills/
    ├── compose-instructions/SKILL.md
    ├── revise-instructions/SKILL.md
    ├── review-instructions/SKILL.md
    └── distill-plan/SKILL.md
```

## Scope

**Does:** turn rough material into precise instructions; distill implementation plans out of multi-purpose documents; modify existing instructions safely; grade instructions for interpretability and intent-fidelity risk; close gaps interactively or best-effort them headlessly.

**Does NOT:** execute the instructions or plans it writes. `forge` produces the prompt; running it is a separate act. The plan format tells the *executor* how to track state and resume — the executing session, not forge, does the executing.
