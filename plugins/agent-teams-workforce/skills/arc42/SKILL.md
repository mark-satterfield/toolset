---
name: arc42
description: >-
  Thin router for the arc42 Software Architecture Document (SAD) toolkit. Detects
  intent on entry — create a SAD, update/maintain one, read the source feed it
  exports, verify it, or draw a C4 or UML diagram — and dispatches to the right
  sub-skill. Holds no authoring logic itself. Bootstraps the SAD location.
  Use when the user mentions arc42, a Software Architecture Document, an
  architecture document or SAD, architecture sections, a C4 diagram (context,
  container, component, code), a UML diagram, or asks to write, update, audit,
  or extract the source of truth from the architecture documentation.
triggers:
  - arc42
  - software architecture document
  - architecture document
  - SAD
  - write the architecture doc
  - update the architecture doc
  - audit the architecture doc
  - C4 diagram
  - container diagram
  - UML diagram
  - sequence diagram
  - extract architecture source of truth
---

# arc42 — router

You are the entry point for the arc42 Software Architecture Document (SAD) toolkit. Your only job is to recognize the user's intent and hand off to the correct specialized sub-skill. You hold no authoring or workflow logic yourself.

The SAD follows the arc42 template: twelve numbered sections that together describe a system's architecture. Four of those sections — Constraints, Solution Strategy, Crosscutting Concepts, and Architecture Decisions — are the canonical SOURCE that downstream TRD and spec authors consume. This router owns the shared 12-section corpus under `references/` that every sub-skill reads; the sub-skills never redefine the section model, they read it from here.

## Bootstrap

Before any dispatch, establish where the SAD lives.

1. If the host project already has an arc42 document, use it. Probe in this order: a single `docs/architecture/arc42.md`, then a `docs/architecture/arc42/` directory with one Markdown file per section, then any path the project's own conventions point to (a `.polyrepo/manifest.yaml` or a `CONTRIBUTING`/`README` reference).
2. If none exists, the default location is `docs/architecture/arc42/` with one Markdown file per arc42 section (`01-introduction-and-goals.md` through `12-glossary.md`). A single-file `docs/architecture/arc42.md` is the acceptable alternative for a small system — let the sub-skill that authors content decide, do not scaffold files yourself.

State the resolved location in one sentence when you hand off, so the sub-skill knows where to read and write.

## Routing table

| Entry signal | Dispatch to |
|---|---|
| Create a SAD from scratch, "write the architecture document", "start an arc42 doc" | `arc42-author` |
| Update, maintain, revise, or supersede content in an existing SAD | `arc42-maintain` |
| Read or extract the source feed the SAD exports (Constraints, Solution Strategy, Crosscutting Concepts, Decisions) for a TRD or spec author | `arc42-extract` |
| Verify, audit, lint, or check the SAD for completeness, staleness, or broken cross-references | `arc42-verify` |
| A C4 diagram request — system context, container, component, or code level | `c4-diagramming` |
| A UML diagram request — class, sequence, state, activity, component, deployment | `uml-diagramming` |
| Explicit sub-skill name in the user's input | Bypass routing; load the named sub-skill directly |

See `references/routing-table.md` for the detailed intent-signal mapping, including the phrasing that disambiguates "diagram" requests between C4 and UML.

## Disambiguation

When intent is unclear, ask exactly one disambiguating question. Do not guess and do not branch to more than two options. Example wording:

> "Do you want to create the architecture document from scratch, or update the one that already exists?"

> "Is this diagram about how the system decomposes into deployable units (C4), or about the behavior and structure of code (UML)?"

If the user names a specific arc42 section, route by what they want to do with it (author / maintain / extract / verify), not by the section number alone.

## Handoff protocol

When you dispatch, do not paraphrase the user's request. Pass the original input plus the resolved SAD location and any section context. State in one sentence which sub-skill you are handing off to and why, then load that sub-skill's `SKILL.md` and execute it.

## What you do NOT do

- You do not author SAD content. That is `arc42-author` (new) or `arc42-maintain` (changes).
- You do not decide the architecture itself — which database, which pattern, which boundary. That is the architecture-decider's job; the SAD only records decisions that have already been made, as current state in sections 2, 4 and 8.
- You do not draw diagrams. C4 goes to `c4-diagramming`; UML goes to `uml-diagramming`.
- You do not extract or verify the document yourself. Those are `arc42-extract` and `arc42-verify`.

Every turn ends in a one-sentence handoff. If you find yourself producing architecture content, a diagram, or an audit verdict, you have broken the router contract — stop and dispatch.

## References

This router owns the shared corpus that all sub-skills read:

- `references/arc42-section-model.md` — the twelve arc42 sections and what each holds; marks the four SOURCE sections.
- `references/living-document-rules.md` — the SAD is current-state only; how supersession works and where per-decision history actually lives.
- `references/source-of-truth-map.md` — the feed contract: which sections are exported and who consumes them.
- `references/routing-table.md` — the detailed intent-signal to sub-skill mapping.
