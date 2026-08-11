---
kind: section
name: section-header
aliases: [eyebrow, section header, kicker, section label, heading strip]
status: stable
content_contract:
  position: "lead | interstitial"
  has_pictogram: bool
theme: scheduled
composition_notes:
  - "Precedes another content unit; may appear multiple times within one Page"
---

# Section Header / Eyebrow

A standalone label preceding another content unit. The Shape pick consults `position` via `rules/shape-selection/section-header.md`: a `lead` header opens a content run as a left-aligned heading strip, or as a centered pictogram over the heading when the content supplies a mark; an `interstitial` header marks a transition between two runs as a centered labeled divider. section-header is a full content Section — it counts in the ground-alternation schedule like any other Section.
