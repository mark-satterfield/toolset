---
kind: shape-selection-rule
name: site-footer
section: site-footer
status: stable
signals: [column_count, carries_brand_island]
table:
  - { when: "column_count > 0 && carries_brand_island", primary: footer-brand-columns-legal, alternates: [footer-columns-legal] }
  - { when: "column_count > 0 && !carries_brand_island", primary: footer-columns-legal, alternates: [] }
  - { when: "column_count == 0", primary: footer-minimal, alternates: [] }
default: footer-minimal
---

# Shape selection — Site footer

The footer's arrangement is determined by how much secondary navigation the frame carries and whether the brand is restated as its own block. A frame with no nav columns takes the minimal arrangement — one legal row — rather than an empty grid.

`carries_social` does not branch the pick: every footer arrangement places a social row when the content supplies one and renders nothing when it does not.

Candidates are tried in order (primary, then alternates, then `default`) against the Page-Level Aesthetic Constraints (`reference/rules/page-constraints/`). This table is rung 1 of the Shape-assignment waterfall; what happens when every candidate is rejected — the library search, the adapted Shape, and only then generation from scratch — is defined once, in `reference/pipeline.md`.
