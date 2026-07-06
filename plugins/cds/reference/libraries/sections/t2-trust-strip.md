---
kind: section
name: trust-strip
id: T2
family: landing
aliases: [trust strip, logo strip, logo bar, customer logos, logo wall]
status: stable
mode: dynamic
content_contract:
  item_count: int
theme: scheduled
composition_notes: []
---

# T2 — Trust Strip

Validation via customer/brand logos, without quotes. A logos-only set: the items are logos and nothing else — quote-bearing validation belongs to T3.

The shape pick branches on `item_count` — how many logos the content supplies — via `rules/shape-selection/t2.md`. No other content signal branches T2.
