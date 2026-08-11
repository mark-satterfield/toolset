---
kind: shape-selection-rule
name: resource-directory
section: resource-directory
status: stable
signals: [has_source_tag_per_item, has_group_headings]
table:
  - { when: "has_group_headings == true", primary: titled-card-run, alternates: [resource-grid] }
  - { when: "has_source_tag_per_item == true", primary: resource-grid, alternates: [tagged-card-grid] }
default: resource-grid
---

# Shape selection — Resource Directory

Items arriving in named groups resolve to titled-card-run, which gives each group its own heading and one row of cards; the group heading is the reason the arrangement exists, so an ungrouped set never takes it. Items carrying source-type tags resolve to resource-grid, with tagged-card-grid as the alternate. Candidates are tried in order (primary, then alternates, then `default`) against the Page-Level Aesthetic Constraints (`reference/rules/page-constraints/`). This table is rung 1 of the Shape-assignment waterfall; what happens when every candidate is rejected — the library search, the adapted Shape, and only then generation from scratch — is defined once, in `reference/pipeline.md`.
