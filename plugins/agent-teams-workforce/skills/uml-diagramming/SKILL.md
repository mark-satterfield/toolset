---
name: uml-diagramming
description: Authors UML diagrams — class, sequence, state, component, and deployment — as Mermaid source for GitHub and Docusaurus, and maps each diagram to the arc42 section it belongs in (component → 5, runtime sequence/state → 6, deployment → 7, domain-model class → 8). Use when the user asks to draw a UML diagram, model a domain or class structure, sketch a sequence or interaction, model a state machine, diagram components or building blocks, show deployment topology, or place a diagram into an arc42 architecture document.
triggers:
  - draw a UML diagram
  - class diagram
  - sequence diagram
  - state diagram
  - state machine
  - component diagram
  - deployment diagram
  - model the domain
  - show the interaction flow
  - diagram in mermaid
  - arc42 section
  - building block view
---

# UML Diagramming

Author UML diagrams as **Mermaid** source so they render natively in GitHub and Docusaurus, and place each diagram in the **arc42** section where readers expect it. This skill covers the five UML diagram types that carry their weight in software documentation: class, sequence, state, component, and deployment.

You produce diagram *source*, not images. Mermaid is text, so it lives in version control next to the code it describes, diffs cleanly in pull requests, and renders without a build step.

## When to use this skill

Reach for it when the user wants to model structure or behavior visually: a domain or class model, an interaction or message flow, a state machine, a component/building-block breakdown, a deployment topology, or any diagram destined for an arc42 architecture document.

## Workflow

1. **Pick the diagram type.** Match the question being answered to the right UML type. "What are the things and how do they relate?" → class. "Who calls whom, in what order?" → sequence. "What modes does this thing move between?" → state. "What are the parts of the system and their interfaces?" → component. "Where does it run?" → deployment. The decision criteria and what each type communicates are in `references/uml-diagram-types.md`.

2. **Author the Mermaid source.** Write a fenced `mermaid` block using the correct grammar for that diagram type (`classDiagram`, `sequenceDiagram`, `stateDiagram-v2`, and the flowchart-based approximations Mermaid uses for component and deployment views). Every diagram type has a worked, copy-ready example in `references/mermaid-uml-syntax.md` — that reference file is the only place mermaid code fences live. Read it, adapt the closest example, and keep the diagram focused on one question.

3. **Place it in the right arc42 section.** A UML diagram is not just a picture; it occupies a slot in the architecture narrative. Component view → section 5 (Building Block View). Runtime behavior — sequence and state diagrams — → section 6 (Runtime View). Deployment topology → section 7 (Deployment View). The domain/class model → section 8 (Crosscutting Concepts). The full mapping with rationale is in `references/arc42-section-mapping.md`.

4. **Confirm the render target.** GitHub renders Mermaid in Markdown automatically; Docusaurus needs the `@docusaurus/theme-mermaid` theme enabled. Both, plus where Mermaid is weaker than PlantUML, are covered in `references/rendering-targets.md`. Stay Mermaid-first; only note the PlantUML tradeoff when a diagram genuinely exceeds Mermaid's reach.

## Diagram-type cheat sheet

| Question being answered | UML type | Mermaid grammar | arc42 section |
|---|---|---|---|
| What are the entities and how do they relate? | Class | `classDiagram` | 8 — Crosscutting Concepts (domain model) |
| Who sends what message, in what order? | Sequence | `sequenceDiagram` | 6 — Runtime View |
| What states does an entity move through? | State | `stateDiagram-v2` | 6 — Runtime View |
| What are the parts and their interfaces? | Component | `flowchart` (component view) | 5 — Building Block View |
| What runs on which node/host? | Deployment | `flowchart` (deployment view) | 7 — Deployment View |

(This is a plain prose sketch, not a rendered diagram — all runnable Mermaid lives in the references.)

## Authoring conventions

- One diagram answers one question. If a sequence diagram needs ten participants, the boundary is probably wrong — split it.
- Name participants and classes after domain concepts, not implementation classes, in arc42 sections 5–8. Implementation detail belongs in code, not the architecture overview.
- Keep labels short. Mermaid wraps poorly; long edge labels hurt readability in both GitHub and Docusaurus.
- Prefer `stateDiagram-v2` over the legacy `stateDiagram` grammar — it is the supported, actively maintained variant.
- For component and deployment views, Mermaid has no first-class UML notation, so you approximate with `flowchart` plus `subgraph` for boundaries and nodes. The reference shows the agreed conventions so diagrams stay consistent across a repo.

## What you do NOT do

- You do not generate raster images (PNG/SVG export) — you emit Mermaid text and let the render target draw it.
- You do not author arc42 prose or the surrounding document sections — you produce the diagram and state which section it belongs in.
- You do not switch tools silently. This skill is Mermaid-first; if a diagram truly needs PlantUML, say so explicitly and explain the tradeoff (see `references/rendering-targets.md`) rather than quietly emitting PlantUML.
- You do not invent UML semantics. Class, sequence, state, component, and deployment diagrams have defined meanings; follow them.

## References

- `references/uml-diagram-types.md` — when to choose class vs sequence vs state vs component vs deployment, and what each communicates.
- `references/mermaid-uml-syntax.md` — real, copy-ready Mermaid examples for every type (the only file with mermaid code fences).
- `references/rendering-targets.md` — Mermaid rendering in GitHub and Docusaurus, and where Mermaid is weak versus PlantUML.
- `references/arc42-section-mapping.md` — which UML type maps to which arc42 section (5, 6, 7, 8).
