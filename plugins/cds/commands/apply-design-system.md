---
description: Surface the design system's vocabulary — class names, token names, event hooks, ARIA contracts, reference pointers — for non-UI code (handlers, fetchers, business logic) that interacts with plugin-generated UI. Emits no code.
argument-hint: "[what is being built or changed; which generated surface the code interacts with]"
allowed-tools: Read, Glob, Grep
---

# /cds:apply-design-system

Invoke the `apply-design-system` skill in this plugin. Load and execute `skills/apply-design-system/SKILL.md` and follow its discovery checklist, pipeline, and halt conditions exactly.

## Process

1. Load `skills/apply-design-system/SKILL.md`.
2. Treat `$ARGUMENTS` as the caller's one-sentence problem statement. If empty, ask: "What are you building or changing, and which generated surface does it interact with?"
3. Run the discovery checklist (one-sentence summary → which surface → rendering context → UI category → motion/interaction).
4. Apply the pipeline: confirm rendering context, identify the Page context (`libraries/pages/`), load the library set for the category, surface the structured markdown response with named sections (Class names / Token names / Event hooks / ARIA contracts / Reference pointers / Halt conditions).

## Notes

- This command emits NO code. It surfaces reference content into the conversation as a structured markdown response.
- The author writes the non-UI code (handlers, data fetching, state, glue) using the surfaced vocabulary; this command provides the contract their code must bind against.
- Every value surfaced cites a reference file — no class name, token, event hook, or ARIA contract is invented.
- Halt code: `MISSING_SPEC` if the reference does not cover the author's category; surfaces the gap explicitly.
