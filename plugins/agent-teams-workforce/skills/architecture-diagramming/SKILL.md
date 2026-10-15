---
name: architecture-diagramming
description: >-
  The one place that owns how architecture diagrams are drawn and checked: every diagram and
  model type in the project's list of view types (what each is for, how it differs from its
  neighbours, when to choose it, which Mermaid kind draws it, with a correct example), and the
  rendered-readability rule — nothing in the rendered image overlaps — with its required
  verification by rendering each diagram to PNG and looking at it. Loaded by
  architecture-diagram-author, c4-diagram-author and uml-diagram-author, and referenced by the
  c4-diagramming and uml-diagramming skills. Use when choosing a view type, drawing any
  architecture diagram in Mermaid, or checking that a drawn diagram is readable.
triggers:
  - which diagram type
  - draw an architecture diagram
  - context map vs system context
  - container vs component vs deployment
  - sequence vs activity vs state
  - diagram labels overlap
  - render mermaid to png
  - check diagram readability
---

# Architecture diagramming

Every architecture view is a Mermaid diagram and the prose around it. This skill decides which
diagram a view needs and how to draw it so the rendered image reads cleanly. The project's
architecture documentation model (`reference/architecture-documentation-model.md` under the
architecture root) decides which views a subject needs, where they go and their catalog
frontmatter; its list of view types (`reference/diagram-and-model-types.md`) names the types.
`view_type` is always a name from that list.

## Workflow

1. **Name the reader's question and the scope** (system, domain, service, component, concept).
   A diagram answers one question at one scope. If you cannot state the question, do not draw.
2. **Choose the type** from the table below and the family reference it points to. Read the
   "Which one" table at the top of that reference: it says how the type differs from the types
   near it. Reuse an existing view that already answers the question; do not draw a second copy
   of the same graph under another type name.
3. **Draw it** with the Mermaid kind and conventions the reference gives, adapting its example.
   Use the glossary's names for every element. Draw only what the design you were given
   contains.
4. **Make it readable and verify it** as `references/readability.md` requires: render every
   diagram to PNG, look at each image, and fix until nothing overlaps.
5. **Write the prose** around the diagram: what the view is for, the detail the diagram leaves
   out (edge detail goes in a table keyed by the edge label or step number), and links to the
   parent and adjacent views.

## Types

| Type | Mermaid kind | Reference | Usual arc42 section |
|---|---|---|---|
| Enterprise architecture diagram | `flowchart` with domain subgraphs | `types-context-and-landscape.md` | 3 |
| Ecosystem view | `flowchart` | `types-context-and-landscape.md` | 3 |
| System context diagram (C4 L1) | C4-notation `flowchart` or `C4Context` | `types-context-and-landscape.md` | 3 |
| Context diagram | `flowchart` | `types-context-and-landscape.md` | 3 |
| Landscape diagram | C4-notation `flowchart` or `C4Context` | `types-context-and-landscape.md` | 3 |
| Context map (DDD; not in the list) | `flowchart` | `types-context-and-landscape.md` | 5 (domain) |
| Container diagram (C4 L2) | C4-notation `flowchart` or `C4Container` | `types-structure.md` | 5 |
| Service diagram | `flowchart` | `types-structure.md` | 5 |
| Application diagram | `flowchart` | `types-structure.md` | 5 |
| 3-tier architecture diagram | `flowchart TB` with tier subgraphs | `types-structure.md` | 5 |
| N-tier architecture diagram | `flowchart TB` with layer subgraphs | `types-structure.md` | 5 |
| Logical architecture diagram | `flowchart` | `types-structure.md` | 5 |
| Subsystem diagram | `flowchart` with subgraphs | `types-structure.md` | 5 |
| Component diagram (C4 L3 / UML) | C4-notation `flowchart` or `C4Component` | `types-structure.md` | 5; 8 for a concept |
| Module diagram | `flowchart` | `types-structure.md` | 5 |
| Package diagram | `flowchart` with package subgraphs | `types-structure.md` | 5 |
| Code diagram (C4 L4) | `classDiagram` | `types-structure.md` | 5 |
| Class diagram | `classDiagram` | `types-structure.md` | 5; 8 for a concept |
| Object diagram | `classDiagram` with instance labels | `types-structure.md` | 5 |
| Sequence diagram | `sequenceDiagram` | `types-behaviour.md` | 6; 8 for a concept |
| Activity diagram | `flowchart` with activity semantics | `types-behaviour.md` | 6; 8 for a concept |
| State machine diagram | `stateDiagram-v2` | `types-behaviour.md` | 6; 5 for one component |
| Workflow diagram | `flowchart` with role swimlanes | `types-behaviour.md` | 6 |
| Process flow diagram | `flowchart TD` | `types-behaviour.md` | 6 |
| Data flow diagram | `flowchart` | `types-behaviour.md` | 6 |
| Integration diagram | `flowchart` | `types-behaviour.md` | 5 or 6 |
| Conceptual model | `classDiagram`, names only | `types-data-and-domain.md` | 5 |
| Domain model | `classDiagram` with DDD stereotypes | `types-data-and-domain.md` | 5 |
| Logical data model | `erDiagram` | `types-data-and-domain.md` | 5 |
| Physical data model | `erDiagram` | `types-data-and-domain.md` | 5 |
| Entity-relationship diagram | `erDiagram` | `types-data-and-domain.md` | 5 |
| Physical architecture diagram | `flowchart` with account/region subgraphs | `types-deployment.md` | 7 |
| Deployment diagram (C4 / UML) | `flowchart` or `C4Deployment` | `types-deployment.md` | 7 |
| Infrastructure diagram | `flowchart` with stack subgraphs | `types-deployment.md` | 7 |
| Network diagram | `flowchart` with trust-zone subgraphs | `types-deployment.md` | 7 |
| Environment diagram | `flowchart LR` | `types-deployment.md` | 7 |

## The distinctions that matter most

- **System context vs context map.** A system context shows one system, its people and the
  external systems around it. A context map shows bounded contexts (model and language
  boundaries) and the integration pattern between each pair. Different questions; never one in
  place of the other.
- **Container vs component vs deployment.** Container: the deployable units of one system.
  Component: the parts inside one container. Deployment: which node or cloud resource each piece
  of software runs on. A database is a container; the server or managed service hosting it
  belongs to the deployment view.
- **Sequence vs activity vs state.** Sequence: messages between participants over time.
  Activity: control flow through guarded decisions, merges, forks and joins to distinct
  outcomes. State: the lifecycle of one entity, its states and the events that move it.
- **Logical vs physical.** Logical views never name hosts, accounts or regions; physical views
  place the same responsibilities on real infrastructure.
- **Domain model vs class diagram vs data model.** Business meaning; implementation structure;
  stored shape. Keep domain identity separate from storage keys.

C4 views follow the levels and notation of the `c4-diagramming` skill and UML views the
semantics of the `uml-diagramming` skill; both take type choice, Mermaid conventions and the
readability rule from here.

## Readability is required

The owner reads diagrams as rendered images. Nothing may overlap: no box on a box, no label on a
label, box or line, no line through a box it does not connect. Keep edge labels to a few words
and put detail beside the diagram; split diagrams where many edges converge; choose the
direction that spreads edges; use the ELK layout when crowded. Render every diagram to PNG with
the Mermaid CLI (`scripts/render-check.sh` here), open each PNG with the Read tool, and fix until
the image is clean. The rule, the techniques and the reporting are in
`references/readability.md`. PNGs are verification evidence written to a scratch directory; they
are never committed beside the views.

## What you do NOT do

- You do not declare a `view_type` that is not in the project's list of view types.
- You do not draw an element, edge, state or message the design you were given does not contain,
  and you do not invent elements to fill a visual gap.
- You do not report a diagram as readable without having rendered it and looked at the image.
- You do not put fenced Mermaid in this file; every example lives in `references/`.

## References

- `references/readability.md` — the rendered-readability rule, the techniques to meet it, and the
  required render-and-inspect verification.
- `references/types-context-and-landscape.md` — enterprise, ecosystem, system context, context,
  landscape and context map.
- `references/types-structure.md` — container, service, application, tiered, logical, subsystem,
  component, module, package, code, class and object views.
- `references/types-behaviour.md` — sequence, activity, state machine, workflow, process flow,
  data flow and integration views.
- `references/types-data-and-domain.md` — conceptual, domain, logical and physical data models,
  and ERDs.
- `references/types-deployment.md` — physical architecture, deployment, infrastructure, network
  and environment views.
- `scripts/render-check.sh` — renders every Mermaid block of the given files to PNG and prints
  the paths.
