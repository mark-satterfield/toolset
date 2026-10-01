# Routing table (detailed)

This is the full intent-signal to sub-skill mapping for the arc42 router. The router's `SKILL.md`
carries the summary; this file carries the disambiguation detail. Match on intent, not keywords
alone — the same word ("update", "diagram") can route to different sub-skills depending on the
object.

## Authoring and maintenance

| Intent signal | Examples | Dispatch to |
|---|---|---|
| Write views that do not exist yet: a new architecture, a new subject, or a target and delta for a change | "design the architecture for this feature", "write the target for the settings service", "add the views for the new service", "write the delta", "document the architecture from scratch" | `arc42-author` |
| Bring the effective version up to date | "integrate the approved target", "apply the approved design to arc42", "the build differs from the architecture, correct it", "update every view that shows this service" | `arc42-maintain` |

A proposed change is written as a target and its delta first, because the effective version changes
only by integrating an approved target or by correcting it from what was built. A request to "change
section 5" for a design that has not been approved is an `arc42-author` target, not an
`arc42-maintain` edit.

## Finding views

| Intent signal | Examples | Dispatch to |
|---|---|---|
| Find the views that show an element | "which views show the settings service", "where is the event envelope described", "what does the delta change" | No sub-skill: answer from the catalog per `finding-views.md` |

## Verification

| Intent signal | Examples | Dispatch to |
|---|---|---|
| Check the architecture against the MODEL | "audit the architecture", "is the catalog frontmatter complete", "lint the arc42 folders", "find history or open items in the views", "do any views contradict each other" | `arc42-verify` |

## Diagrams — C4 vs. UML

The deciding question: *is the diagram about the system's structural decomposition into software or
infrastructure units (C4), or about the structure and behaviour of code and interactions (UML)?*

| Intent signal | Examples | Dispatch to |
|---|---|---|
| C4 model levels | "system context diagram", "container diagram", "component diagram (C4)", "how do the services fit together", "C4 level 1/2/3/4", "deployment topology as C4" | `c4-diagramming` |
| UML diagram types | "sequence diagram", "class diagram", "state machine", "activity diagram", "UML component diagram", "deployment diagram (UML)", "show the call flow", "model the object structure" | `uml-diagramming` |

The two genuine overlaps and how to break them:

- **"Component diagram"** exists in both notations. If the user said "C4" or is decomposing a
  container into its internal parts, route to `c4-diagramming`. If they mean UML component-and-
  interface modelling, route to `uml-diagramming`. When unclear, ask the single disambiguating
  question.
- **"Deployment diagram"** exists in both. C4 deployment maps containers to infrastructure nodes;
  UML deployment models artifacts on nodes at a finer grain. Default to `c4-diagramming` for "how
  does it deploy / what runs where" and `uml-diagramming` when the user says UML or wants
  artifact-level modelling.

A diagram is part of a view: it is written in the view file it belongs to, with the prose around it
and the view's catalog frontmatter, in the section and version the MODEL names.

## Explicit override

| Intent signal | Dispatch to |
|---|---|
| The user names a sub-skill outright ("use arc42-verify", "run c4-diagramming") | Bypass all routing; load the named sub-skill directly |

## Disambiguation budget

Ask one question when intent is unclear, with at most two options, and do not stack questions. When
the user supplies the architecture root, the version and subject, and a verb (author, maintain,
verify), route without asking.
