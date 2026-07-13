---
kind: section
name: pricing
family: landing
aliases: [pricing, plans, pricing table, tiers, rates]
status: stable
mode: dynamic
content_contract:
  pricing_model: "subscription-tiers | usage-rates"
  has_segment_toggle: bool
theme: scheduled
composition_notes: []
---

# Pricing

Investment tiers or usage rates. The pricing model is one of two: `subscription-tiers` (named plans) or `usage-rates` (per-unit rates); a segmented offering carries a toggle between audience segments.

The Shape pick branches on `pricing_model` and `has_segment_toggle` via `rules/shape-selection/pricing.md`.
