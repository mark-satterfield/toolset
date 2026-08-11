---
kind: section
name: trust-strip
aliases: [trust strip, logo strip, logo bar, customer logos, logo wall]
status: stable
content_contract:
  item_count: int
theme: scheduled
composition_notes: []
---

# Trust Strip

Validation via customer/brand logos, without quotes. A logos-only set: the items are logos and nothing else — quote-bearing validation belongs to validation-block.

The Shape pick branches on `item_count` — how many logos the content supplies — via `rules/shape-selection/trust-strip.md`. No other content signal branches trust-strip.
