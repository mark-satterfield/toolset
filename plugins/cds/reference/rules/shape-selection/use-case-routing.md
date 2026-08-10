---
kind: shape-selection-rule
name: use-case-routing
section: use-case-routing
page_family: landing
status: stable
signals: [item_count, taxonomy_type, has_subitems_per_category]
table:
  - { when: "item_count >= 3 and item_count <= 4 and (taxonomy_type == role or taxonomy_type == discipline)", primary: tagged-card-grid, alternates: [card-grid] }
  - { when: "item_count >= 5 and has_subitems_per_category", primary: tag-columns, alternates: [] }
default: tagged-card-grid
---

# Shape selection — Use-Case Routing

A small role- or discipline-tagged set reads as a tagged grid; five or more categories that each carry sub-items spread into tag columns. Candidates are tried in order (primary, then alternates, then `default`) against the Page-Level Aesthetic Constraints (`reference/rules/page-constraints/`). This table is rung 1 of the Shape-assignment waterfall; what happens when every candidate is rejected — the library search, the adapted Shape, and only then generation from scratch — is defined once, in `reference/pipeline.md`.
