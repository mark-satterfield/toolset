---
kind: shape-selection-rule
name: faq
section: faq
status: stable
signals: [item_count, copy_density_per_item]
table:
  - { when: "item_count <= 6 and copy_density_per_item == brief", primary: faq-card-grid, alternates: [accordion] }
  - { when: "item_count > 8", primary: faq-two-column, alternates: [accordion] }
  - { when: "always", primary: accordion, alternates: [] }
default: accordion
---

# Shape selection — FAQ

The accordion is the default and serves any count, keeping long answers collapsed so the page stays scannable. A short set (six or fewer) of brief answers picks faq-card-grid, where every answer stays open in a card. A long set (more than eight) picks faq-two-column, an indexed rail beside open answers. Candidates are tried in order (primary, then alternates, then `default`) against the Page-Level Aesthetic Constraints (`reference/rules/page-constraints/`). This table is rung 1 of the Shape-assignment waterfall; what happens when every candidate is rejected — the library search, the adapted Shape, and only then generation from scratch — is defined once, in `reference/pipeline.md`.
