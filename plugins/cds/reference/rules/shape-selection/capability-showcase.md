---
kind: shape-selection-rule
name: capability-showcase
section: capability-showcase
status: stable
signals: [item_count, has_visual_per_item, copy_density_per_item, taxonomy_type]
table:
  - { when: "item_count == 3 and copy_density_per_item == short and not has_visual_per_item", primary: card-grid, alternates: [tagged-card-grid] }
  - { when: "item_count == 4 and taxonomy_type != null", primary: tagged-card-grid, alternates: [card-grid] }
  - { when: "item_count >= 2 and item_count <= 4 and has_visual_per_item and copy_density_per_item != short", primary: alternating-rows, alternates: [tabbed-panels] }
  - { when: "item_count >= 5 and item_count <= 6 and has_visual_per_item", primary: tabbed-panels, alternates: [alternating-rows] }
  - { when: "item_count >= 10", primary: card-carousel, alternates: [tag-columns] }
  - { when: "taxonomy_type != null and not has_visual_per_item", primary: tag-columns, alternates: [card-grid] }
default: card-grid
---

# Shape selection — Capability Showcase

The pick balances count against weight: few light items grid, a taxonomy tags the grid, substantial copy-plus-visual pairs alternate in rows, a mid-sized visual set tabs, a large set carousels, and categorical pills without visuals fall into tag columns. Rows are ordered — the first matching predicate wins. Candidates are tried in order (primary, then alternates, then `default`) against the Page-Level Aesthetic Constraints (`reference/rules/page-constraints/`). This table is rung 1 of the Shape-assignment waterfall; what happens when every candidate is rejected — the library search, the adapted Shape, and only then generation from scratch — is defined once, in `reference/pipeline.md`.
