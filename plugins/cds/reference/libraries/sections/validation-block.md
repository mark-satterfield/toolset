---
kind: section
name: validation-block
aliases: [testimonials, customer quotes, social proof, validation block]
status: stable
content_contract:
  item_count: int
  has_metric_per_item: bool
  logos_presence: bool
theme: scheduled
composition_notes: []
---

# Validation Block

Validation via customer quotes, with or without logos. Quote-bearing validation: each item is a quote, optionally carrying a quantified result and an accompanying logo — logo-only validation belongs to trust-strip.

The Shape pick branches on `item_count`, `has_metric_per_item`, and `logos_presence` (whether logos accompany the quotes) via `rules/shape-selection/validation-block.md`.
