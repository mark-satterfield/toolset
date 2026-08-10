---
kind: shape-selection-rule
name: trust-strip
section: trust-strip
page_family: landing
status: stable
signals: [item_count]
table:
  - { when: "item_count >= 10", primary: logo-marquee, alternates: [card-grid] }
  - { when: "item_count <= 8", primary: card-grid, alternates: [logo-marquee] }
default: card-grid
---

# Shape selection — Trust Strip

The pick is driven by logo count: a large set scrolls as a marquee, a small set sits as a static grid. trust-strip's items are logos only by definition, so `item_count` is the sole branching signal. Candidates are tried in order (primary, then alternates, then `default`) against the Page-Level Aesthetic Constraints (`reference/rules/page-constraints/`). This table is rung 1 of the Shape-assignment waterfall; what happens when every candidate is rejected — the library search, the adapted Shape, and only then generation from scratch — is defined once, in `reference/pipeline.md`.
