# Placing UML views in the arc42 sections

The effective architecture is the `arc42/` folder of the architecture directory, one folder per
section. The architecture documentation model (`reference/architecture-documentation-model.md` in
the architecture directory) decides where a view goes, and `reference/diagram-and-model-types.md`
is the list of view types. Read both before placing a view; this file summarises how UML views fit
them.

A UML diagram is placed by two things together: its **scope** (what it describes) and its **view
type** (how it describes it). The same UML type lands in different sections at different scopes: a
state machine of one Lambda is a component view in section 5, while the state machine of a
service's important flow is a runtime view in section 6.

## Scope and section

| Scope | UML views usually needed | arc42 section | Where inside the section |
|---|---|---|---|
| System | sequence diagrams of key end-to-end flows across services | 6 | `06-runtime-view/<flow>.md` |
| System | deployment diagram of the AWS deployment and network | 7 | `07-deployment-view/README.md`, `network.md` |
| Domain | domain model (class notation) and context map | 5 | `05-building-block-view/<domain>/README.md` |
| Service | component diagram; logical or physical data model | 5 | `05-building-block-view/<domain>/<service>/` |
| Service | sequence, state machine and activity diagrams of its important flows | 6 | `06-runtime-view/<domain>/<service>/` |
| Service | deployment diagram of its stacks | 7 | `07-deployment-view/<domain>/<service>/` |
| Component | class, module or package diagram; physical data model; state machine | 5 | `05-building-block-view/<domain>/<service>/<component>.md` |
| Concept | the concept's structure (class, component) and behaviour (sequence, activity) | 8 | `08-crosscutting-concepts/<concept>.md` |

This table is where to start, not a checklist: the views a subject needs depend on what it is.

Section 8 holds patterns applied across many services (idempotency, the event envelope, how a
runtime library is used). A domain model is not a crosscutting concept: it belongs to its domain
in section 5.

## Every view carries catalog frontmatter

Each view file declares what it describes, so the catalog can answer "which views show this
element?" without reading every file:

```yaml
view_type: sequence diagram        # a type from diagram-and-model-types.md
scope: service                     # system | domain | service | component | concept
subject: SkillSpoke-settings-service
shows:                             # every element that appears in the view
  - settings-api
  - settings-table
lifecycle_state: in-review         # in-review | effective
```

Keep `shows` true to the diagram: every participant, class, node or component it draws is listed.
Before drawing a view, search the catalog for the subject and the elements it shows, so an existing
view is updated rather than a second one added beside it.

## Versions

A view in `arc42/` is the effective version. A proposed design is drawn in
`target/<subject>/` with the same section layout, and the change between effective and target in
`target/<subject>/delta/`. A difference the build delivered is drawn in `built/<subject>/`. Files
and folders are named for their subject, never for a PRD, an Epic, a bead id, a date or a pipeline
gate.

## A view is the diagram and its prose

The diagram shows structure and flow. The prose around it states what the view is for, what the
diagram cannot show (reasons, limits, details of an element) and where the adjacent views are. The
prose describes the design; it states no rules.
