---
kind: section
name: pricing
aliases: [pricing, plans, pricing table, tiers, rates]
status: stable
content_contract:
  pricing_model: "subscription-tiers | usage-rates | feature-comparison"
  has_segment_toggle: bool
theme: scheduled
composition_notes: []
---

# Pricing

Investment tiers or usage rates. The pricing model is one of three: `subscription-tiers` (named plans), `usage-rates` (per-unit rates), or `feature-comparison` (many attributes compared across several subjects — the tiers of one offering, or one offering against its competitors). A segmented offering carries a toggle between audience segments.

The Shape pick branches on `pricing_model` and `has_segment_toggle` via `rules/shape-selection/pricing.md`.
