---
name: c4-diagramming
description: >-
  Author C4 model architecture diagrams — Level 1 System Context, Level 2 Container,
  Level 3 Component, and (sparingly) Level 4 Code — written in Mermaid C4 syntax so they
  render natively in GitHub and Docusaurus, and mapped onto the arc42 documentation
  template (L1 to section 3 Context & Scope, L2/L3 to section 5 Building Block View,
  deployment views to section 7). Use when the user asks to draw or document system
  architecture, produce a context or container diagram, model components, decide which
  C4 level fits, embed an architecture diagram in a README or doc site, or align C4
  output with arc42 sections.
triggers:
  - draw a C4 diagram
  - system context diagram
  - container diagram
  - component diagram
  - C4 model
  - architecture diagram in Mermaid
  - document the architecture
  - which C4 level
  - arc42 building block view
  - embed diagram in Docusaurus
  - render diagram in GitHub
  - deployment diagram
---

# C4 Diagramming

Author C4 model diagrams in Mermaid and slot them into an arc42 documentation set. The
C4 model (Context, Containers, Components, Code — by Simon Brown) is a hierarchy of four
zoom levels over the same system. You pick the level that answers the reader's question,
draw only what that level admits, and let the next level down absorb the detail you left
out. This skill holds the workflow and the level-selection judgment; all Mermaid syntax
lives in the reference files so it never trips the no-fenced-mermaid rule that applies to
this body.

## What this skill produces

- A diagram at the right C4 level for the audience and the question being asked.
- Mermaid source authored against the `C4Context` / `C4Container` / `C4Component`
  diagram kinds, so it renders without a plugin in GitHub Markdown and (with a small
  config change) in Docusaurus.
- A placement decision: which arc42 section the diagram belongs in, so the architecture
  documentation stays coherent rather than becoming a pile of unlabeled pictures.

## Workflow

1. **Fix the question and the audience.** A diagram exists to answer one question for one
   audience. "How does this system fit into its world?" is a Level 1 question for business
   and non-technical stakeholders. "What are the deployable/runnable units and how do they
   talk?" is Level 2 for the whole technical team. "What are the major structural building
   blocks inside one container?" is Level 3 for developers of that container. "How is this
   one component built?" is Level 4 — rarely worth drawing by hand. If you cannot name the
   question, do not draw yet.

2. **Choose the level.** Use `references/c4-levels.md` to decide what belongs at each level
   and, just as important, what must be pushed down a level or left out. Resist mixing
   levels in one diagram — a Context diagram that shows internal containers, or a Container
   diagram that names individual classes, is the most common C4 mistake.

3. **Enumerate the elements before drawing.** List the people (actors), the software
   systems (yours and external), and — at L2/L3 — the containers or components, plus every
   relationship with a verb-phrase label and, where it matters, a technology/protocol
   annotation ("Makes API calls to", "[JSON/HTTPS]"). C4 relationships are directed and
   labeled; an unlabeled arrow is incomplete.

4. **Write the Mermaid source.** Copy the matching pattern from
   `references/mermaid-c4-syntax.md` and substitute your elements. That file is the only
   place fenced Mermaid examples live; the body here points to it deliberately. As a plain
   prose sketch, a Level 1 diagram reads: `Person(customer)` and `Person(staff)` on the
   outside, your `System(yourSystem)` in the middle, `System_Ext(...)` for each third party,
   and `Rel(...)` lines connecting them with action verbs.

5. **Pick the arc42 home.** Use `references/arc42-section-mapping.md`:
   - Level 1 System Context → arc42 **section 3, Context & Scope** (business + technical
     context).
   - Level 2 Container and Level 3 Component → arc42 **section 5, Building Block View**
     (level 1 / level 2 / level 3 of decomposition, mirroring the C4 zoom).
   - Deployment-oriented views (a C4 Deployment diagram or a container-to-infrastructure
     mapping) → arc42 **section 7, Deployment View**.

6. **Verify rendering for the target.** Confirm where the diagram will live — a GitHub
   README/PR/issue, or a Docusaurus site — and apply the guidance in
   `references/github-docusaurus-rendering.md` (GitHub renders Mermaid natively in fenced
   blocks; Docusaurus needs `@docusaurus/theme-mermaid` enabled with `markdown.mermaid:
   true`). Note the known gotchas: the C4 diagram kinds are experimental and layout is
   auto-managed, so prefer `UpdateLayoutConfig` over hand-tuning, and keep element counts
   modest so the auto-layout stays legible.

## Level-to-question cheat sheet

| Question the reader is asking | C4 level | arc42 section |
|---|---|---|
| How does the system fit into the wider world? Who and what does it interact with? | L1 System Context | 3 — Context & Scope |
| What are the high-level deployable/runnable units, and how do they communicate? | L2 Container | 5 — Building Block View |
| What are the major building blocks inside one container, and their responsibilities? | L3 Component | 5 — Building Block View |
| How is one specific component implemented? (rarely drawn; often auto-generated) | L4 Code | 5 — Building Block View (lowest level) |
| What runs where — which infrastructure hosts which containers? | C4 Deployment | 7 — Deployment View |

## What you do NOT do

- You do not invent architecture. Diagram the system as the user describes it or as the
  code shows it; ask when a relationship or boundary is unclear rather than guessing.
- You do not mix C4 levels in a single diagram. One diagram answers one level's question.
- You do not draw Level 4 (Code) by hand unless explicitly asked — it ages fastest and is
  better produced from the code (IDE/UML tooling) when needed at all.
- You do not place fenced Mermaid blocks in this SKILL.md. Every runnable example lives in
  `references/mermaid-c4-syntax.md`.
- You do not produce arc42 prose for unrelated sections; this skill owns the diagrams and
  their placement, not the full document.

## References

- `references/c4-levels.md` — when to use each C4 level and exactly what belongs (and does
  not belong) at each.
- `references/mermaid-c4-syntax.md` — real, runnable Mermaid examples for `C4Context`,
  `C4Container`, and `C4Component`. The only place fenced Mermaid is allowed.
- `references/github-docusaurus-rendering.md` — how Mermaid renders natively in GitHub and
  how to enable it in Docusaurus, with the C4-specific gotchas.
- `references/arc42-section-mapping.md` — which C4 level maps to which arc42 section (3, 5, 7).
