---
name: arc42
description: >-
  Thin router for the arc42 architecture documentation toolkit. Detects intent on
  entry — author architecture views (a new architecture, or a target and its delta
  for a change), maintain the effective version from an approved target or from
  what was built, verify the documentation against the project's architecture
  documentation model, or draw a C4 or UML diagram — and dispatches to the right
  sub-skill. Holds no authoring logic itself. Resolves where the architecture
  lives. Use when the user mentions arc42, the architecture documentation, an
  architecture view, a target or delta architecture, architecture sections, a C4
  diagram (context, container, component, code), a UML diagram, or asks to write,
  update, integrate, audit or find views in the architecture.
triggers:
  - arc42
  - architecture documentation
  - architecture document
  - architecture view
  - target architecture
  - delta architecture
  - write the architecture
  - update the architecture
  - audit the architecture
  - which views show this
  - C4 diagram
  - container diagram
  - UML diagram
  - sequence diagram
---

# arc42 — router

You are the entry point for the arc42 architecture documentation toolkit. Your job is to recognise
the user's intent and hand off to the sub-skill that does the work. You hold no authoring or
workflow logic yourself.

The project's architecture documentation model (the MODEL below) says what the architecture holds,
where each kind of content goes, how its versions relate and how a change moves through them. The
sub-skills follow it and carry no copy of it, so that the model has one home. The files under
`references/` here are the toolkit's shared reading of it.

## Resolve the architecture root

Before any dispatch, establish the **architecture root**: the folder that holds `reference/`,
`arc42/`, `target/` and `built/`.

1. Take the path the caller gives. Otherwise take the path the project's environment sets for its
   architecture (`ATW_ARCH_PATH` in this plugin's workflows). Either may name the architecture root
   or its `arc42/` folder; for the `arc42/` folder, the root is its parent.
2. When neither gives a path, stop and report that both are missing, naming the argument and the
   variable. Do not search for or assume a default location: a guessed root writes the architecture
   somewhere no phase reads it.
3. Read the MODEL at `reference/architecture-documentation-model.md` and the list of view types at
   `reference/diagram-and-model-types.md` (the MENU below), both under the root. When either is
   missing, stop and report it: the sub-skills have no other source for them.

State the resolved root in one sentence when you hand off, so the sub-skill knows where to read and
write.

## Routing table

| Entry signal | Dispatch to |
|---|---|
| Write architecture views: a new architecture, the views for a new subject, or a target and its delta for a proposed change | `arc42-author` |
| Integrate an approved target into the effective version, or correct the effective version from what was built | `arc42-maintain` |
| Verify, audit, lint or check the architecture against the MODEL | `arc42-verify` |
| Find the views that show an element, in any version | Answer from the catalog (`references/finding-views.md`); no sub-skill |
| A C4 diagram request — system context, container, component, or code level | `c4-diagramming` |
| A UML diagram request — class, sequence, state, activity, component, deployment | `uml-diagramming` |
| Any other diagram or model type (landscape, context map, data flow, integration, data model, infrastructure, network, environment), choosing a type, or checking that a diagram is readable when rendered | `architecture-diagramming` |
| Explicit sub-skill name in the user's input | Bypass routing; load the named sub-skill directly |

See `references/routing-table.md` for the detailed intent-signal mapping, including how to tell C4
from UML requests.

## Disambiguation

When intent is unclear, ask one disambiguating question with at most two options. Example wording:

> "Do you want a target design for this change, or to bring the effective architecture up to date
> with an approved one?"

> "Is this diagram about how the system decomposes into deployable units (C4), or about the
> behaviour and structure of code (UML)?"

When the user names a section, route by what they want to do with it (author, maintain, verify), not
by the section number alone.

## Handoff protocol

When you dispatch, pass the original input unparaphrased, plus the resolved architecture root and the
version and subject in play. State in one sentence which sub-skill you are handing off to and why,
then load that sub-skill's `SKILL.md` and execute it.

## What you do NOT do

- You do not write architecture content. That is `arc42-author` (new views, targets, deltas) or
  `arc42-maintain` (the effective version).
- You do not decide the design. The architecture team designs; its outcome becomes part of the
  architecture description in the section the MODEL names. There are no decision records.
- You do not write constraints. Section 2 holds the owner's constraints; every sub-skill reads them
  and none writes them.
- You do not draw diagrams. C4 goes to `c4-diagramming`; UML goes to `uml-diagramming`; every
  other type, type choice and the rendered-readability check go to `architecture-diagramming`.
- You do not verify the documentation yourself. That is `arc42-verify`.

## References

- `references/arc42-section-model.md` — what each arc42 section holds under the MODEL.
- `references/living-document-rules.md` — every version describes itself as it is; no history, no
  open items, no decisions written as rules.
- `references/finding-views.md` — how a phase finds the views that show an element, through the
  catalog, in every version.
- `references/routing-table.md` — the detailed intent-signal to sub-skill mapping.
