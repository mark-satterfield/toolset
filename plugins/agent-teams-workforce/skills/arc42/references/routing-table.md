# Routing table (detailed)

This is the full intent-signal to sub-skill mapping for the arc42 router. The router's `SKILL.md` carries the summary; this file carries the disambiguation detail. Match on intent, not keywords alone — the same word ("update", "diagram") can route to different sub-skills depending on the object.

## Authoring and maintenance

| Intent signal | Examples | Dispatch to |
|---|---|---|
| Create a SAD that does not yet exist | "write the architecture document", "start an arc42 doc for this service", "document the architecture from scratch", "we have no SAD — make one" | `arc42-author` |
| Change content in a SAD that already exists | "update section 5", "the database changed, fix the SAD", "revise the solution strategy", "supersede the old constraint", "add a crosscutting concept for logging" | `arc42-maintain` |

If a SAD's existence is unknown, run the Bootstrap probe in the router before choosing between author and maintain. Author is for the empty-state; maintain is for every subsequent edit.

## Extraction (the source feed)

| Intent signal | Examples | Dispatch to |
|---|---|---|
| Read the SAD as the upstream source for a TRD or spec | "pull the constraints for the TRD", "extract the solution strategy", "what crosscutting concepts apply to this spec", "give me the decisions index", "feed the architecture source into the spec author" | `arc42-extract` |

`arc42-extract` only ever returns sections 2, 4, 8, 9 (see `source-of-truth-map.md`). A request to "read section 6" for orientation is not an extraction — answer it as a plain read or route to maintain if the user wants to change it.

## Verification

| Intent signal | Examples | Dispatch to |
|---|---|---|
| Check the SAD for quality, completeness, or staleness | "audit the architecture doc", "is the SAD up to date", "lint the arc42 sections", "check for broken ADR links", "does every quality goal have a scenario", "find changelog prose that shouldn't be here" | `arc42-verify` |

## Diagrams — C4 vs. UML

This is the most common ambiguity. The deciding question: *is the diagram about the system's structural decomposition into software/infrastructure units (C4), or about the structure and behavior of code and interactions (UML)?*

| Intent signal | Examples | Dispatch to |
|---|---|---|
| C4 model levels | "system context diagram", "container diagram", "component diagram (C4)", "how do the services fit together", "C4 level 1/2/3/4", "deployment topology as C4" | `c4-diagramming` |
| UML diagram types | "sequence diagram", "class diagram", "state machine", "activity diagram", "UML component diagram", "deployment diagram (UML)", "show the call flow", "model the object structure" | `uml-diagramming` |

Note the two genuine overlaps and how to break them:

- **"Component diagram"** exists in both notations. If the user said "C4" or is decomposing a container into its internal parts, route to `c4-diagramming`. If they mean UML component-and-interface modeling, route to `uml-diagramming`. When unclear, ask the single disambiguating question.
- **"Deployment diagram"** exists in both. C4 deployment maps containers to infrastructure nodes; UML deployment models artifacts on nodes at a finer grain. Default to `c4-diagramming` for "how does it deploy / what runs where" and `uml-diagramming` only when the user explicitly says UML or wants artifact-level modeling.

Both diagramming sub-skills read sections 3, 5, 6, and 7 from the SAD for their source content and write their diagram source (as fenced code) into reference files, never into the SAD body's prohibited blocks.

## Explicit override

| Intent signal | Dispatch to |
|---|---|
| The user names a sub-skill outright ("use arc42-verify", "run c4-diagramming") | Bypass all routing; load the named sub-skill directly |

## Disambiguation budget

Ask **exactly one** question when intent is unclear, with at most two options. Never stack questions. If the user supplies the SAD path or names a section plus a verb (author/maintain/extract/verify), route deterministically without asking.
