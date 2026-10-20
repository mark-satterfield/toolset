# arc42 section model

arc42 is a free, open template for software architecture documentation. Under the project's
architecture documentation model (the MODEL, `reference/architecture-documentation-model.md` under
the architecture root), the arc42 sections hold three kinds of content: the owner's constraints
(section 2), the enterprise-level strategy (section 4), and the architecture itself (sections 3, 5,
6, 7 and 8). The architecture below arc42's level, the detailed design, lives beside it in
`detailed/`. This file states what each section and each folder holds; the MODEL is the authority,
and where the two differ the MODEL is right and this file is corrected.

All of the architecture and design is done during architecture: from the network and the system
context to the classes, object and data models, columns, keys and types, interfaces and names of
one component. Nothing is left for the specs to decide. The only distinction is where each document
is stored: the documents that belong in arc42 go there, and the rest go in `detailed/`.

## Layout

Every section is a folder under `arc42/` whose `README.md` is its entry point and its highest-scope
view: `arc42/01-introduction-and-goals/README.md` through `arc42/12-glossary/README.md`. Inside a
section, views are organised by the subject they describe (`05-building-block-view/<domain>/README.md`,
`05-building-block-view/<domain>/<service>/...`), and files and folders are named for their subject,
never for a PRD, an Epic, a bead id, a date or a pipeline gate. There is no section 9.

The detailed architecture is under `detailed/`, beside `arc42/`, in four folders, each with a
`README.md` that states what belongs there and lists its documents:

| Folder | Holds | `scope` |
|---|---|---|
| `detailed/system/` | Whole-system views below arc42's level: the diagram of the entire AWS ecosystem, detailed network topology, a whole-system data model | system |
| `detailed/cross-component/` | How a set of components works together, short of the whole system: the detail of an integration, a shared contract, a domain's internal structure | cross-component, domain |
| `detailed/components/<component>/` | One component in detail: class and object models, data models with attributes, columns, keys and types, interface and payload schemas, route tables, names, internal diagrams. `<component>` is the repository name, or the component's glossary name for a part inside a repository | service, component |
| `detailed/features/<feature>/` | One feature in detail: the views that span the components the feature uses, named for the feature as the glossary names it | feature |

Not everything is a service or an API. A component is any repository or any part of one: a
service, a library, a web or mobile application, infrastructure. A feature is a capability that
spans components. A document's place follows its scope and level of detail, never how often it
changes or whether it is approved.

The built version uses the same layout inside `built/<element>/`.

## The sections

### 1. Introduction and Goals
What the system is for, its top quality goals and its stakeholders. It orients a reader; the
requirements themselves live in PRDs.

### 2. Architecture Constraints — the owner's
The rules the owner imposes to guide design: few, global (enterprise or project level) and not
specific to one implementation. Only the owner writes them. Every agent and process reads them as the
boundary of a design and writes nothing here; an agent that thinks a constraint should change reports
that to its caller.

### 3. Context and Scope — architecture, system scope
The system context and the landscape: the system as one box, the people and external systems around
it, and what crosses the boundary.

### 4. Solution Strategy — enterprise-level direction
The architectural style and the few approaches everything else follows (for example, an event-based
architecture with one API for authoring and publishing events). About one page. It changes only when a
design alters the direction itself; an implementation choice belongs in the architecture description.

### 5. Building Block View — architecture, structure
The static structure at system, domain, service and component scope: the system container view in
the section `README.md`, then domain views, then service and component views in subject folders.
Container, component, data model and class views live here.

### 6. Runtime View — architecture, behaviour
How the parts behave at runtime: system-wide event and data flows and end-to-end sequences at the
top, and each service's sequences, state machines and activities in its subject folder.

### 7. Deployment View — architecture, infrastructure
What the system runs on: the system deployment in the section `README.md`, the network, and each
service's stacks in its subject folder.

### 8. Crosscutting Concepts — architecture, concepts
Patterns used across many services (for example idempotency, an event envelope, structured
logging), one file per concept, each with its structure and its behaviour. A pattern described here is followed by the next
design unless that design states a reason to change it; it is a design fact with its reason, and
only section 2 holds the owner's constraints. Section 8 also holds the standards and policies
that apply across services (see "Document classes" below).

### 10. Quality Requirements
The quality scenarios the architecture is designed to meet, each with a stimulus and a measurable
response.

### 11. Risks and Technical Debt
Known technical risks and accepted debt in the current design. Work still to do is tracked in beads,
not here.

### 12. Glossary
The terms the architecture uses, so every view and every diagram label means the same thing by the
same word.

## One home for each design fact

One design fact lives in exactly one document. Every other document that needs it links to its
heading. Which section is the home follows from what the fact is:

- Section 3 holds context: what is outside the system and what crosses the boundary.
- Section 4 holds the solution strategy.
- Section 5 holds building blocks: what each block is responsible for, what it owns, what it
  provides to consumers, and its interfaces by name. A shared service, component, layer or library
  states under a heading "Provides" each behaviour consumers obtain from it and must not implement
  themselves, one line per behaviour.
- Section 6 holds runtime: which building blocks interact, in what order, for the important
  scenarios and their failures. It links to a rule; the rule itself is stated in its home.
- Section 7 holds deployment: where each block runs and which stack holds each resource.
- Section 8 holds crosscutting concepts: the rule as a design fact with its reason, for example
  "Because of X, the address is verified by Y"; and the standards and policies that apply across
  services.
- `detailed/` holds the detailed design: the classes, object and data models, keys, types,
  interface and payload schemas, routes and names of one component, the detail of components
  working together, of one feature, or of the whole system.

## Where a fact goes: arc42 or `detailed/`

A statement belongs in arc42 when it stays true if the code is rewritten or a table's keys are
renamed. The detailed design of one component, one feature, components working together or the
whole system belongs in its document under `detailed/`, which the arc42 view of its subject links
to; arc42 states the responsibility and links to the detail, and does not restate it. A limit, a
lifetime, a retention period, a timeout or a retry count is a requirement of the TRD, which the
detailed design applies. A document has a single purpose and holds only facts that belong to its
subject.

## Document classes: views, and standards and policies

An architecture document is of one of two classes. The front matter of each is defined in the
artifact-handoff skill's `schemas/document-front-matter.schema.json`.

- **A view** (`$defs/ArchitectureView`) is one way of looking at one subject at one scope (system,
  domain, cross-component, service, component, feature, concept): a diagram written as Mermaid in
  Markdown and the prose around it. The MODEL's view table says which views a scope usually needs
  and where each belongs; the MENU (`reference/diagram-and-model-types.md`) is the list of view
  types. The views a subject needs depend on what it is: a library, a web application, a piece of
  infrastructure and a service each need different ones, and one document per Epic or per
  checklist item is never the shape. A view is created once for its subject and scope, and is
  enhanced or updated as each later design and build touches it. Every view carries the catalog
  front matter (`view_type`, `scope`, `subject`, `shows`, `lifecycle_state`, `purpose`) described
  in `finding-views.md`.
- **A standard or a policy** (`$defs/ArchitectureStandard`, `document_class: standard` or
  `document_class: policy`) states the requirements every element of its scope meets and how
  compliance is judged, for example the storage properties every S3 bucket carries. It is not a
  view: it has no diagram, no `view_type`, no `scope` and no `shows`. It holds requirements only,
  never an implementation: no construct, library, class or code that meets them. It usually lives
  in section 8; one that governs only the detail of a component lives in that component's folder
  under `detailed/`.
