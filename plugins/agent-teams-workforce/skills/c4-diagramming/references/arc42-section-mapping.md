# Placing C4 views in the arc42 sections

The effective architecture is the `arc42/` folder of the architecture directory, one folder per
section. The architecture documentation model (`reference/architecture-documentation-model.md` in
the architecture directory) decides what each section holds and where a view goes, and
`reference/diagram-and-model-types.md` is the list of view types. Read both before placing a view;
this file summarises how C4 views fit them. C4 is a notation for structure; the model says which
section and subject folder each structure view belongs in.

## What each section holds

| arc42 section | Holds | C4 views here |
|---|---|---|
| 1 | Introduction and goals | none |
| 2 | The owner's constraints only. Pipeline agents read it and never write it. | none |
| 3 | Context and scope at system scope | system context (C4 Level 1), landscape |
| 4 | Enterprise-level strategy, about one page | none; the strategy may link to the views in 3 and 5 |
| 5 | Building blocks at system, domain, service and component scope | container (C4 Level 2), component (C4 Level 3), code (C4 Level 4) |
| 6 | Runtime behaviour at system and service scope | dynamic (`C4Dynamic`) for one scenario; most runtime views are UML sequence or activity diagrams |
| 7 | Deployment at system and service scope | deployment |
| 8 | Patterns used across many services | component views of a concept's structure |
| 10 | Quality requirements | none |
| 11 | Risks and technical debt | none |
| 12 | Glossary | none |

## Scope and folder

| Scope | C4 view | Where |
|---|---|---|
| System | system context, landscape | `03-context-and-scope/README.md` |
| System | container view of every service | `05-building-block-view/README.md` |
| Domain | container view of the domain's services | `05-building-block-view/<domain>/README.md` |
| Service | component view of one service | `05-building-block-view/<domain>/<service>/` |
| Component | code view, only when a component is complex enough to justify it | `05-building-block-view/<domain>/<service>/<component>.md` |
| System | deployment of the AWS environment and network | `07-deployment-view/README.md`, `network.md` |
| Service | deployment of the service's stacks | `07-deployment-view/<domain>/<service>/` |
| Concept | component view of a concept's structure | `08-crosscutting-concepts/<concept>.md` |

C4 numbering and arc42 numbering do not line up: C4 Level 1 (system context) is in section 3, and
the building block view in section 5 starts at C4 Level 2 (container).

## Every view carries catalog frontmatter

Each view file declares what it describes, so the catalog can answer "which views show this
element?" without reading every file:

```yaml
view_type: container diagram       # a type from diagram-and-model-types.md
scope: system                      # system | domain | service | component | concept
subject: SkillSpoke                # the one thing this view describes
shows:                             # every element that appears in the view
  - SkillSpoke-settings-service
  - shared-events-service
lifecycle_state: in-review         # in-review | effective
```

Keep `shows` true to the diagram: every person, system, container and component it draws is
listed. Before drawing, search the catalog for the subject and its elements, so an existing view is
updated rather than a second one added beside it. Adding an element usually changes views at more
than one scope: a new service changes the system container and integration views and adds its own
component views.

## Versions

A view in `arc42/` is the effective version. A proposed design is drawn in `target/<subject>/`
with the same section layout, and the change between effective and target in
`target/<subject>/delta/`. A difference the build delivered is drawn in `built/<subject>/`. Files
and folders are named for their subject, never for a PRD, an Epic, a bead id, a date or a pipeline
gate.

## A view is the diagram and its prose

The diagram shows structure. The prose around it states what the view is for, what the diagram
cannot show (reasons, limits, an element's responsibility and interface) and where the adjacent
views are. The prose describes the design; it states no rules.
