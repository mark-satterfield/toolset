---
name: arc42-author
description: >-
  Authors a brand-new arc42 Software Architecture Document (SAD) from supplied
  inputs — scaffolds all 12 arc42 sections as a single living current-state
  document and explicitly marks sections 2 (Constraints), 4 (Solution Strategy),
  8 (Crosscutting Concepts), and 9 (Architecture Decisions) as the downstream
  source feeds other tools extract from. Use when the user asks to create,
  scaffold, bootstrap, write, or start an arc42 SAD, an architecture document,
  an architecture description, or a system design document, or when an
  architecture needs to be captured in the arc42 template for the first time.
triggers:
  - create an arc42 document
  - scaffold a SAD
  - write an architecture document
  - bootstrap arc42
  - start an architecture description
  - new software architecture document
  - author arc42 sections
  - document the system architecture
  - fill in the arc42 template
  - capture our architecture in arc42
  - draft solution strategy and constraints
  - write crosscutting concepts
---

# arc42 Author — create a new SAD

Single task: take the inputs you are given (a system brief, quality goals, known
constraints, a tech-stack sketch, stakeholder list) and produce a complete,
**current-state** arc42 Software Architecture Document scaffolded across all 12
sections. You author one document. You do not assess, audit, diff, or maintain
an existing SAD — that is a different job.

The arc42 template is fixed: 12 numbered sections in a fixed order. You fill
every one. A section with no content yet still gets its heading plus an explicit
`> TODO:` line naming what input is still missing — never a silent gap, never a
deleted section.

## Living current-state document

The SAD describes the architecture **as it is now**, in present tense. It is not
a changelog and not a history. Never write revision-timestamp lines,
version-bump notes, or dated edit markers inside the body — that metadata
belongs in version control, not in the prose. When the architecture changes, you
change the affected section in place so the document always reads as the truth of
the current system.

## The shared arc42 corpus

The canonical per-section definitions, the arc42 section glossary, and the
quality-scenario vocabulary live in the shared corpus at `../arc42/references/`.
Read that corpus first for the authoritative meaning of each section. The four
reference files in **this** skill's `references/` are the authoring playbook
layered on top of that corpus — they tell you how to write, and how to know when
a section is done.

## The four downstream-source sections

Four sections are not just documentation — other tools extract structured feeds
from them, so they must be written to be machine-extractable, not just readable:

| Section | Role | Why it is a source |
|---|---|---|
| **2 — Constraints** | Technical / organizational / political limits | Drift detectors and compliance checks read constraints as rules to enforce |
| **4 — Solution Strategy** | Fundamental decisions and how quality goals are met | The decision log and tech-radar feeds are seeded here |
| **8 — Crosscutting Concepts** | Domain model, persistence, security, error handling, observability, idempotency | Code-generation and review tooling reads concepts as the canonical pattern set |
| **9 — Architecture Decisions** | The ADR index | The ADR tracker reads this as the authoritative decision list |

When authoring 2, 4, and 8, follow the extraction-shape rules in the matching
reference file so each item parses as a discrete, IDed, atomic statement. Mark
these sections in the document with the agreed `<!-- source-feed -->` comment so
downstream tooling can locate them.

## The 12 sections

1. **Introduction and Goals** — what the system does, top 3–5 quality goals (each
   tied to a measurable scenario), key stakeholders and their concerns.
2. **Constraints** — technical, organizational, and political constraints. *Source feed.*
3. **Context and Scope** — business context (who/what the system talks to) and
   technical context (protocols, interfaces, data formats at the boundary).
4. **Solution Strategy** — the fundamental decisions: technology choices,
   top-level decomposition, and how each quality goal is achieved. *Source feed.*
5. **Building Block View** — static decomposition. Level 1 (whitebox of the whole
   system) and zoom into the blackboxes that need it. This is the C4 Container /
   Component layer in arc42 terms.
6. **Runtime View** — important runtime scenarios shown as interaction sequences:
   how building blocks collaborate to satisfy a use case.
7. **Deployment View** — the infrastructure: nodes, channels, and the mapping of
   building blocks onto execution environments.
8. **Crosscutting Concepts** — domain model, persistence, security,
   error-handling, logging/observability, idempotency, and other concerns that
   cut across building blocks. *Source feed.*
9. **Architecture Decisions** — an index of ADRs (context → decision → status →
   consequences). *Source feed.*
10. **Quality Requirements** — the quality tree and a table of concrete,
    measurable quality scenarios (stimulus → response → measure).
11. **Risks and Technical Debt** — known risks and accepted debt, each with an
    owner and a mitigation or pay-down note.
12. **Glossary** — domain and technical terms with single agreed definitions.

## Authoring procedure

1. **Read the corpus** at `../arc42/references/` and this skill's
   `references/section-templates.md` for the per-section prompt and acceptance bar.
2. **Inventory the inputs.** Map each supplied artifact (brief, quality goals,
   constraints, stack sketch, stakeholder list) onto the sections it feeds.
3. **Author in dependency order, not numeric order.** Practically: 1 → 2 → 3 →
   10 (quality scenarios) → 4 → 5 → 8 → 6 → 7 → 9 → 11 → 12. Quality goals (1)
   and scenarios (10) must exist before Solution Strategy (4) can state how they
   are met; the building block view (5) must exist before runtime (6) and
   deployment (7) can reference its blocks.
4. **Apply the source-feed shaping** to sections 2, 4, and 8 using
   `references/constraints-guide.md`, `references/solution-strategy-guide.md`, and
   `references/crosscutting-concepts-guide.md`.
5. **Place all diagrams in `references/` files, never in this SKILL.md body.**
   Diagram code (C4 levels in a Mermaid `C4Context`/`C4Container` block, UML
   sequence and component diagrams) goes in the reference files. The body of the
   SAD you generate may embed diagrams; this skill's own SKILL.md may not contain
   a mermaid fence — point to the reference files by path instead.
6. **Check each section against its acceptance bar.** A section is done only when
   it meets the bar in `references/section-templates.md`. If it cannot meet the
   bar yet, leave the explicit `> TODO:` naming the missing input.

## Diagram conventions

arc42 prescribes sections, not a diagram notation, so this skill pins one:
**C4 for structure, UML for behavior.**

- Section 3 (Context) → C4 System Context diagram.
- Section 5 (Building Blocks) → C4 Container then C4 Component diagrams.
- Section 6 (Runtime) → UML sequence diagrams.
- Section 7 (Deployment) → C4 Deployment / UML deployment diagram.

The accurate C4 and UML notation rules and ready-to-fill diagram skeletons are in
`references/section-templates.md`. A plain-text sketch of the C4 layering, with
no diagram fence, is: `Person -> System` at context level; `System -> [Container
-> Container]` at container level; `Container -> [Component -> Component]` at
component level — each level zooms one box from the level above.

## Acceptance bar for the whole SAD

The document is done when: all 12 headings exist; every quality goal in section 1
has a matching measurable scenario in section 10; sections 2/4/8 are shaped as
source feeds and marked; every building block named in 5 appears in at least one
of 6 or 7; every ADR referenced in 4 has an entry in 9; and every remaining gap
is an explicit `> TODO:` and not a missing section.

## What you do NOT do

- You do **not** assess or audit an existing SAD for drift or quality.
- You do **not** diff the document against the running system.
- You do **not** produce the downstream feeds yourself — you only shape sections
  2/4/8 so the feed-extraction tools can read them.
- You do **not** write ADR bodies — section 9 is an *index*; full ADRs live with
  the ADR tooling. You author the index entry (context, decision, status).
- You do **not** add revision history, edit-timestamp lines, or changelogs to the
  body. The SAD is a living current-state document.

## References

- `references/section-templates.md` — per-section authoring prompt and a concrete
  acceptance bar for each of the 12 sections, plus C4/UML diagram skeletons.
- `references/constraints-guide.md` — how to author section 2 as an extractable
  source feed.
- `references/solution-strategy-guide.md` — how to author section 4.
- `references/crosscutting-concepts-guide.md` — how to author section 8.
- `../arc42/references/` — the shared arc42 corpus (authoritative section
  definitions and quality-scenario vocabulary).
