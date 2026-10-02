# Finding views through the catalog

Downstream phases (the TRD, Specs, Tasks, an integration, a review) read the views that show the
elements they work on. The catalog locates existing views; the MODEL determines which views are
needed, including views that have no file yet. Read the full relevant views rather than a packet of
extracted sentences. Coverage evidence is described in `coverage-evidence.md`.

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

Packaged design support files (for example `arc42/design-packages/` build specs, composer state, HTML, stylesheets and assets) are not architecture views. Exclude that package subtree from view inventories, missing-frontmatter findings and lifecycle-promotion lists; follow its files only as design references from relevant views. Consumed by: architecture survey, authors, maintainers and conformance reviewers — keeps generated UI artifacts out of architectural coverage and promotion. This does not exempt package bytes from the workflow's existing write/snapshot protection.

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

## Finding coverage that the catalog cannot list

Before declaring coverage complete, establish the subjects and changed elements from the supplied
design and source inventory, independently of the existing view files. Apply the MODEL's coverage
obligations at every affected scope; use the MENU to select views for the reader questions. Then
compare those obligations with catalog hits and the actual file inventory, including files whose
metadata is missing or invalid. Record naming aliases explicitly. No catalog hit is a discovery
result, not a conclusion that the view is unnecessary.

Read adjacent parent, runtime, deployment, data and shared-concern views as the MODEL requires.
A per-change assessment follows the effects of that change across scopes; it does not certify all
unrelated architecture. A whole-project assessment needs an explicit project-wide inventory and
separately commissioned scope. Missing design evidence is reported to the caller, never filled by
inventing a design or dismissed as not applicable.
