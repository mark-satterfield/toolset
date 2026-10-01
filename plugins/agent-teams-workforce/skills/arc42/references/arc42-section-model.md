# arc42 section model

arc42 is a free, open template for software architecture documentation. Under the project's
architecture documentation model (the MODEL, `reference/architecture-documentation-model.md` under
the architecture root), the arc42 sections hold three kinds of content: the owner's constraints
(section 2), the enterprise-level strategy (section 4), and the architecture itself (sections 3, 5,
6, 7 and 8). This file states what each section holds; the MODEL is the authority, and where the two
differ the MODEL is right and this file is corrected.

## Layout

Every section is a folder under `arc42/` whose `README.md` is its entry point and its highest-scope
view: `arc42/01-introduction-and-goals/README.md` through `arc42/12-glossary/README.md`. Inside a
section, views are organised by the subject they describe (`05-building-block-view/<domain>/README.md`,
`05-building-block-view/<domain>/<service>/...`), and files and folders are named for their subject,
never for a PRD, an Epic, a bead id, a date or a pipeline gate. There is no section 9.

The target and built versions use the same section layout inside `target/<subject>/` and
`built/<subject>/`; a target's delta sits in `target/<subject>/delta/`.

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
design unless that design states a reason to change it; it is not a rule.

### 10. Quality Requirements
The quality scenarios the architecture is designed to meet, each with a stimulus and a measurable
response.

### 11. Risks and Technical Debt
Known technical risks and accepted debt in the current design. Work still to do is tracked in beads,
not here.

### 12. Glossary
The terms the architecture uses, so every view and every diagram label means the same thing by the
same word.

## Views and scopes

A view is one way of looking at one subject at one scope (system, domain, service, component,
concept): a diagram written as Mermaid in Markdown and the prose around it. The MODEL's view table
says which views a scope usually needs and which section each belongs in; the MENU
(`reference/diagram-and-model-types.md`) is the list of view types. Every view carries the catalog
frontmatter (`view_type`, `scope`, `subject`, `shows`, `lifecycle_state`) described in
`finding-views.md`.
