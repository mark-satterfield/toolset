---
kind: shape-selection-rule
name: sub-hero
section: sub-hero
page_family: landing
status: stable
signals: [visual_type]
table:
  - { when: "visual_type == video", primary: sub-hero-split, alternates: [centered-stack] }
default: sub-hero-split
---

# Shape selection — Sub-Hero

The composition signal is video + text + CTA: a video visual resolves to sub-hero-split with centered-stack as the alternate. Candidates are tried in order (primary, then alternates, then `default`) against the Page-Level Aesthetic Constraints (`reference/rules/page-constraints/`). This table is rung 1 of the Shape-assignment waterfall; what happens when every candidate is rejected — the library search, the adapted Shape, and only then generation from scratch — is defined once, in `reference/pipeline.md`.
