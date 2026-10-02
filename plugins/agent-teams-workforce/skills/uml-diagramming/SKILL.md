---
name: uml-diagramming
description: Authors UML diagrams — class, sequence, state, component, and deployment — as Mermaid source for GitHub and Docusaurus, and places each one as a view in the arc42 section its scope and view type name (structure of a domain, service or component → 5, runtime flows → 6, deployment → 7, a pattern used across services → 8), with the catalog frontmatter every view carries. Use when the user asks to draw a UML diagram, model a domain or class structure, sketch a sequence or interaction, model a state machine, diagram components or building blocks, show deployment topology, or place a diagram into an arc42 architecture document.
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

Author UML diagrams as **Mermaid** source so they render natively in GitHub and Docusaurus, and place each diagram in the **arc42** section where readers expect it. This skill covers the six UML diagram types that carry their weight in software documentation: class, sequence, state, activity, component, and deployment.

You produce diagram *source*, not images. Mermaid is text, so it lives in version control next to the code it describes, diffs cleanly in pull requests, and renders without a build step.

## When to use this skill

Reach for it when the user wants to model structure or behavior visually: a domain or class model, an interaction or message flow, a state machine, a component/building-block breakdown, a deployment topology, or any diagram destined for an arc42 architecture document.

## Project coverage and validation

Read the MODEL and MENU under the caller's architecture root and follow assigned coverage using
`../arc42/references/coverage-evidence.md`. Existing catalog hits guide reuse, not whether a missing
view is required. Select only the applicable views the design supports; report missing design to
the caller. Keep prose, diagram declarations and parent/adjacent links consistent.

Use the actual reader's rendering environment, including Obsidian when that is the project target.
Record rendering, visual readability and semantic self-checks separately in the caller's result
schema. A successful parse is not a readability check; unavailable inspection is reported, not
passed. Consumed by: the assigned architecture reviewer and architecture-decider — check the
current view evidence before approval; self-checks do not replace their independent review.

## Workflow

1. **Pick the diagram type.** Match the question being answered to the right UML type. "What are the things and how do they relate?" → class. "Who calls whom, in what order?" → sequence. "What modes does this thing move between?" → state. "What are the parts of the system and their interfaces?" → component. "Where does it run?" → deployment. "Which decisions and concurrent actions lead to each outcome?" → activity, following the MENU construction guidance. The decision criteria and what each type communicates are in `references/uml-diagram-types.md`.

2. **Author the Mermaid source.** Write a fenced `mermaid` block using the correct grammar for that diagram type (`classDiagram`, `sequenceDiagram`, `stateDiagram-v2`, and the flowchart-based approximations Mermaid uses for component and deployment views). The established class, sequence, state, component and deployment types have worked, copy-ready examples in `references/mermaid-uml-syntax.md` — that reference file is the only place mermaid code fences live. Read it, adapt the closest example, and keep the diagram focused on one question.

3. **Place it as a view.** A diagram is placed by its scope (system, domain, service, component, concept) and its view type, as the architecture documentation model in the architecture directory's `reference/` folder sets out. Structure of a domain, service or component (domain model, component, class, data model, and a component's state machine) → section 5 (Building Block View), in the subject's folder. A service's or the system's important flows (sequence, state machine, activity) → section 6 (Runtime View). Deployment → section 7 (Deployment View). A pattern used across many services → section 8 (Crosscutting Concepts). Search the catalog first so an existing view of the same subject is updated, not duplicated, and give the view its catalog frontmatter (`view_type`, `scope`, `subject`, `shows`, `lifecycle_state`). The full placement table is in `references/arc42-section-mapping.md`.

4. **Confirm the render target.** GitHub renders Mermaid in Markdown automatically; Docusaurus needs the `@docusaurus/theme-mermaid` theme enabled. Both, plus where Mermaid is weaker than PlantUML, are covered in `references/rendering-targets.md`. Stay Mermaid-first; only note the PlantUML tradeoff when a diagram genuinely exceeds Mermaid's reach.

## Diagram-type cheat sheet

| Question being answered | UML type | Mermaid grammar | arc42 section |
|---|---|---|---|
| What are the entities and how do they relate? | Class | `classDiagram` | 5 — Building Block View (domain or component); 8 when it is the structure of a crosscutting concept |
| Who sends what message, in what order? | Sequence | `sequenceDiagram` | 6 — Runtime View |
| What states does an entity move through? | State | `stateDiagram-v2` | 6 — Runtime View (a service flow); 5 for one component |
| Which branches, concurrent actions and outcomes form the process? | Activity | `flowchart` with explicit activity semantics from the MENU | 6 — Runtime View; 8 for a shared concept |
| What are the parts and their interfaces? | Component | `flowchart` (component view) | 5 — Building Block View |
| What runs on which node/host? | Deployment | `flowchart` (deployment view) | 7 — Deployment View |

(This is a plain prose sketch, not a rendered diagram — all runnable Mermaid lives in the references.)

## Authoring conventions

- Activity views distinguish guarded decisions/merges from forks/joins, show start/termination and significant failure paths, and label loop exits. A generic flowchart is not automatically a UML activity view.
- One diagram answers one question. If a sequence diagram needs ten participants, the boundary is probably wrong — split it.
- Name participants and classes after domain concepts, not implementation classes, in arc42 sections 5–8. Implementation detail belongs in code, not the architecture overview.
- Keep labels short. Mermaid wraps poorly; long edge labels hurt readability in both GitHub and Docusaurus.
- Prefer `stateDiagram-v2` over the legacy `stateDiagram` grammar — it is the supported, actively maintained variant.
- For component and deployment views, Mermaid has no first-class UML notation, so you approximate with `flowchart` plus `subgraph` for boundaries and nodes. The reference shows the agreed conventions so diagrams stay consistent across a repo.

## What you do NOT do

- You do not generate raster images (PNG/SVG export) — you emit Mermaid text and let the render target draw it.
- You do not author the surrounding arc42 sections — you produce the diagram, the catalog frontmatter of its view, and the section and subject folder it belongs in.
- You do not switch tools silently. This skill is Mermaid-first; if a diagram truly needs PlantUML, say so explicitly and explain the tradeoff (see `references/rendering-targets.md`) rather than quietly emitting PlantUML.
- You do not invent UML semantics. Class, sequence, state, component, and deployment diagrams have defined meanings; follow them.

## References

- `references/uml-diagram-types.md` — when to choose class vs sequence vs state vs component vs deployment, and what each communicates.
- `references/mermaid-uml-syntax.md` — real, copy-ready Mermaid examples for every type (the only file with mermaid code fences).
- `references/rendering-targets.md` — Mermaid rendering in GitHub and Docusaurus, and where Mermaid is weak versus PlantUML.
- `references/arc42-section-mapping.md` — where a UML view goes by scope and view type, its catalog frontmatter, and the architecture versions.
