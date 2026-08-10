---
kind: shape-selection-rule
name: pricing
section: pricing
page_family: landing
status: stable
signals: [pricing_model, has_segment_toggle]
table:
  - { when: "pricing_model == subscription-tiers and has_segment_toggle", primary: pricing-tiers, alternates: [] }
  - { when: "pricing_model == usage-rates", primary: rate-table, alternates: [pricing-tiers] }
  - { when: "pricing_model == feature-comparison", primary: comparison-matrix, alternates: [rate-table] }
default: pricing-tiers
---

# Shape selection — Pricing

The pick follows the pricing model: subscription tiers with a segment toggle render as pricing-tiers; usage rates render as a rate table; a full attribute-by-subject comparison renders as comparison-matrix, which is searchable and carries a CTA per subject column because a comparison that long is scanned rather than read. Candidates are tried in order (primary, then alternates, then `default`) against the Page-Level Aesthetic Constraints (`reference/rules/page-constraints/`). This table is rung 1 of the Shape-assignment waterfall; what happens when every candidate is rejected — the library search, the adapted Shape, and only then generation from scratch — is defined once, in `reference/pipeline.md`.
