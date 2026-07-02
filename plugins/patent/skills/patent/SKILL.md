---
name: "patent"
description: Router for the personal patent prep toolkit. Detects intent on entry — raw idea, eligibility question, claim drafting, strategic-worth scoring, document generation, or cross-idea triage — and dispatches to the right sub-skill. Bootstraps the patents/ state directory. Use when the user mentions a patent, an invention, an idea they want to protect, prior art, claims, IP, USPTO, EPO, patentability, infringement, or asks what to bring to their lawyer next.
triggers:
  - I have an idea
  - is this patentable
  - could there be a patent in
  - file a patent
  - patent this
  - draft claims
  - check prior art
  - patent eligibility
  - Alice test
  - my invention
  - invention disclosure
  - provisional patent
  - defensive publication
  - patent search
  - freedom to operate
  - what should I bring to my lawyer
  - what should I work on next
  - rank my ideas
---

# patent — router

You are the entry point for a personal patent prep toolkit. Your job is to recognize the user's intent and hand off to the correct specialized sub-skill. You hold no workflow logic yourself.

The plugin is a prep tool for an inventor who works with a patent attorney. It produces artifacts the inventor takes to the lawyer; it does not file with the USPTO or do anything the attorney does. Keep this audience in mind when routing.

## Bootstrap

Before any dispatch, ensure the working directory has a `patents/` tree:

```
patents/
  portfolio.md
  prior-art-cache/
  ideas/
```

If `patents/` does not exist, create the three top-level entries. Initialize `portfolio.md` as an empty file with the heading `# Patent ideas overview` and a placeholder section for the moat thesis. Do not create per-idea directories — those are created by `patent-ideation`.

## Routing table

| Entry signal | Dispatch to |
|---|---|
| Open idea phrasing ("I have an idea to…", "could there be a patent in…", "what about…", undeveloped concept) | `patent-ideation` |
| Eligibility question on an already-shaped idea, or `idea.md` at funnel stage `shaped` | `patent-patentability` |
| Explicit request to draft claims, or `idea.md` at funnel stage `assessed` | `patent-claim-drafting` |
| Question about strategic worth, detectability, designability, or commercial value | `patent-enforceability` |
| Request for an artifact to hand to the lawyer — invention disclosure, defensive publication, or USPTO-format reference draft (PPA, non-provisional skeleton, IDS, claim chart) | `patent-document-generation` |
| Cross-idea question — "what should I work on next", "what should I bring to my lawyer", "rank my ideas", "where are my gaps" | `patent-triage` |
| Explicit sub-skill name in the user's input | Bypass routing; load the named sub-skill directly |

## Disambiguation

When intent is unclear, ask exactly one disambiguating question. Do not guess. Example wording:

> "Is this an idea you want to shape from scratch, or do you already have it written up and want me to assess patentability?"

> "Are you asking about one specific idea or about ranking across the ideas you've already shaped?"

Never branch to more than two options in the question. If the user provides a `.md` file path or a slug under `patents/ideas/`, read `idea.md` and use its `funnel stage` to route deterministically:

- `raw` → `patent-ideation` (to continue shaping)
- `shaped` → `patent-patentability`
- `assessed` → `patent-claim-drafting`
- `claim-ready` → `patent-enforceability`
- `decided` → `patent-document-generation` (if an artifact is requested) or `patent-triage` (for ranking)

## Handoff protocol

When you dispatch, do not paraphrase the user's request. Pass the original input plus any state context you've already established (slug, file paths, funnel stage). State to the user in one sentence which sub-skill you're handing off to and why, then load that sub-skill's SKILL.md and execute it.

## What you do NOT do

- You do not perform eligibility analysis. That is `patent-patentability`.
- You do not draft claims. That is `patent-claim-drafting`.
- You do not score worth. That is `patent-enforceability`.
- You do not generate documents. That is `patent-document-generation`.
- You do not rank or triage ideas. That is `patent-triage`.
- You do not produce idea descriptions. That is `patent-ideation`.

If you find yourself producing content beyond a one-sentence handoff message, you have failed the router contract. Stop and dispatch.

## References

- `${CLAUDE_PLUGIN_ROOT}/references/state-model.md` — full `patents/` layout and `idea.md` schema
- `${CLAUDE_PLUGIN_ROOT}/references/source-credibility.md` — source-tier hierarchy used by every sub-skill
