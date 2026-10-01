# Finding views through the catalog

Downstream phases (the TRD, Specs, Tasks, an integration, a review) read the views that show the
elements they work on. They find them through the catalog, not by reading sections in order and not
from a packet of extracted sentences.

## The catalog

Every view declares what it describes in its frontmatter:

```yaml
view_type: container diagram       # a type from reference/diagram-and-model-types.md
scope: system                      # system | domain | service | component | concept
subject: <system>                  # the one thing this view describes
shows:                             # every element that appears in the view
  - <service-a>
  - <service-b>
lifecycle_state: effective         # in-review | effective
```

The catalog is that frontmatter across every file under the architecture root. An Obsidian Base at
the root lists it for people; an agent reads the same fields from the files directly. The version a
view belongs to is the folder it lives in: `arc42/` is effective, `target/<subject>/` is a target,
`target/<subject>/delta/` is its delta, `built/<subject>/` is built.

## Finding the views for an element

1. List every Markdown file under the architecture root whose frontmatter names the element in
   `subject` or `shows`. Match the element by the name the glossary and the repositories use.
2. Group the hits by version (the folder) and by scope. An element usually appears at more than one
   scope — a service shows in the system container view, its domain view and its own component,
   data and sequence views — and a phase that changes the element reads all of them.
3. Read each view's `lifecycle_state`. An `effective` view has been reviewed and approved. An
   `in-review` view is input to check: read it, and do not assume it is complete or correct.
4. Read every open target under `target/` that shows the same element, so a new design does not
   contradict a design already in progress.

## What each phase reads

| Phase | Reads |
|---|---|
| A new design (target) | The constraints in section 2, the strategy in section 4, and every effective view and open target that shows an element the design touches |
| TRD, Specs, Tasks | The delta in `target/<subject>/delta/`, and the target views it points to |
| Integration of an approved target | The target and delta, and every effective view that shows a changed element |
| Correction from built | The built views in `built/<subject>/`, and every effective view that shows an element they differ on |

## When the catalog is incomplete

A view with missing or invalid catalog frontmatter cannot be found this way. Report it to the caller
by path; do not fall back to guessing which views matter, because a view the phase misses is a view
it leaves contradicting the design.
