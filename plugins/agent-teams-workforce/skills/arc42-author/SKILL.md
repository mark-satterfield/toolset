---
name: arc42-author
description: >-
  Authors architecture views to the project's architecture documentation model:
  a new architecture in the arc42 section folders, the views for a new subject,
  or a target and its delta for a proposed change. Each view is a diagram
  (Mermaid) and the prose around it, at the scope it describes, with the catalog
  frontmatter that lets every phase find it. It writes no constraints, no
  decision records and no section 9. Use when the user asks to design, write,
  scaffold or start an architecture, to write the views for a feature, service
  or component, or to write a target or delta architecture for a change.
triggers:
  - write a target architecture
  - write the delta
  - design the architecture for this feature
  - add the views for a new service
  - create the architecture documentation
  - scaffold arc42
  - bootstrap arc42
  - document the system architecture
  - write a building block view
  - write a runtime view
  - write a deployment view
  - write a crosscutting concept
---

# arc42 Author — write architecture views

You write views the architecture does not yet hold:

- **A target and its delta** for a proposed change, in `target/<subject>/` and
  `target/<subject>/delta/`. This is the usual job.
- **The views for a new subject**, or **a new architecture** in `arc42/` when the project has none.

You do not change existing effective views; integrating an approved target into `arc42/` is
`arc42-maintain`. You do not verify; that is `arc42-verify`.

## Read first

1. The project's architecture documentation model (the MODEL), at
   `reference/architecture-documentation-model.md` under the architecture root the router resolved.
   It is the authority for what goes where; this skill tells you how to write it.
2. The list of view types (the MENU), at `reference/diagram-and-model-types.md`.
3. `../arc42/references/` — the section model, the living-document rules and how views are found
   through the catalog.
4. This skill's `references/section-templates.md` — what each section's views hold and the Mermaid
   skeletons.

## Inputs a design starts from

A design starts from the effective architecture (MODEL, "How a change moves through the versions",
step 1):

- the owner's constraints in `arc42/02-architecture-constraints/`;
- the strategy in `arc42/04-solution-strategy/`;
- every effective view, at every scope, that shows an element the design touches, found through the
  catalog (`../arc42/references/finding-views.md`);
- every open target under `target/` that shows the same elements, so two designs in progress do not
  contradict each other.

An `in-review` view, and code that was not built from reviewed architecture, is input to check, not
evidence the design is right.

## Authoring procedure

1. **Name the subject.** The feature, service, component or layer the views describe, as the glossary
   and the repositories name it. It names the folder (`target/<subject>/`) and appears in every
   view's `subject`. It is never a PRD, an Epic, a bead id or a date.
2. **Find every scope the change reaches.** An element appears in views at more than one scope.
   Adding a service, for example, changes the system container and integration views and adds the
   service's own component, data and sequence views. List the existing views the catalog returns for
   each element the design touches. Establish the subject inventory independently of those hits,
   apply the MODEL coverage obligations, and identify applicable views with no file yet. Follow
   `../arc42/references/coverage-evidence.md`; the MENU guides which views answer each question.
3. **Write the target views.** New views for new elements, and a changed copy of each existing view
   that shows a changed element, at every scope where it appears. Each view goes in the section
   folder the MODEL's view table names, inside the version's folder, and is named for its subject.
4. **Write the delta.** In `target/<subject>/delta/`, the views that show only what changes between
   effective and target: what is added, changed and removed, stated as the target has it. Specs and
   Tasks are made from the delta, so every change in the target appears in it.
5. **Write each view as a diagram and its prose.** The diagram (Mermaid, fenced in the view file)
   shows structure and flow. The prose states what the view is for, what the diagram cannot show
   (reasons, limits, details of an element) and where the adjacent views are. A view that is only
   prose, or only a diagram, is the exception.
6. **Add the catalog frontmatter** to every view: `view_type` (a type from the MENU), `scope`,
   `subject`, `shows` (every element in the view, by its glossary or repository name), and
   `lifecycle_state: in-review`. Keep any classification fields the project uses beside them.
7. **Follow the established patterns.** A design follows what the effective architecture establishes
   (every API so far is REST, so the next API is REST) unless it states a reason and evidence to
   change it. A change of pattern is written into the target's views, and into its section 8 or
   section 4 copy when the pattern or the direction itself changes.
8. **Supply coverage evidence.** Map assigned obligations to the views authored, adjacent-view links
   and checks actually performed. Check diagram content against its declaration and MENU semantics;
   distinguish rendering from visual readability and semantic correctness. Report unchecked work or
   an unsupported design to the caller. Author self-checks are not independent review or approval.

## What a view contains

- A description of the design, in present tense, as this version holds it.
- Reasons where a reader needs them, in the prose around the diagram.
- Claims about AWS that a reviewer can check against the AWS documentation.

A view does not contain requirements, history, decision records, rules ("services MUST …") or open
items (`../arc42/references/living-document-rules.md`). A question you cannot answer from the inputs
goes in your report to the caller, not into a view.

## Constraints are the owner's

Section 2 holds the owner's constraints. You read them and write nothing in
`02-architecture-constraints/`, in any version, because only the owner writes constraints
(`references/constraints-guide.md`). When a design would need a constraint to change, report that to
the caller with the reason.

## A new architecture

When the project has no architecture yet, create `arc42/` with one folder per section,
`01-introduction-and-goals/` through `12-glossary/` (no section 9), each with a `README.md`. Write the
views the inputs support, starting from the system scope: context (section 3), container (section 5
entry point), system flows (section 6), system deployment (section 7 entry point). The MODEL
determines whether an entry point embeds or links its highest-scope view. Leave section 2's
`README.md` for the owner to fill. A section the inputs cannot fill yet stays as its folder and a
`README.md` holding only the section title; the gap goes in your report, not into the file.

## What you do NOT do

- You do not edit an effective view. That is `arc42-maintain`, after a target is approved.
- You do not write constraints, decision records, ADRs or a section 9.
- You do not name a file or folder for a PRD, an Epic, a bead id, a date or a pipeline gate.
- You do not approve your own target. Every file you write is `in-review`.

Consumed by: the assigned architecture reviewer and architecture-decider — check authored coverage evidence against the MODEL before target approval.

## References

- `references/section-templates.md` — what each section's views hold, per scope, with Mermaid
  skeletons.
- `references/constraints-guide.md` — what a constraint is, and that the pipeline reads section 2 and
  never writes it.
- `references/solution-strategy-guide.md` — what section 4 holds.
- `references/crosscutting-concepts-guide.md` — how a section 8 concept is written.
- `../arc42/references/` — the shared section model, living-document rules and catalog.
