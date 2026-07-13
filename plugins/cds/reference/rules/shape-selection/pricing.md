---
kind: shape-selection-rule
name: pricing
section: pricing
family: landing
status: stable
signals: [pricing_model, has_segment_toggle]
table:
  - { when: "pricing_model == subscription-tiers and has_segment_toggle", primary: pricing-tiers, alternates: [] }
  - { when: "pricing_model == usage-rates", primary: rate-table, alternates: [pricing-tiers] }
default: pricing-tiers
---

# Shape selection — Pricing

The pick follows the pricing model: subscription tiers with a segment toggle render as pricing-tiers; usage rates render as a rate table. Candidates are tried in order (primary, then alternates, then `default`) against the Page-Level Aesthetic Constraints (`reference/rules/page-constraints/`); if every candidate is rejected, the composer falls back to agent-generated layout and records that in the decisions sidecar.
