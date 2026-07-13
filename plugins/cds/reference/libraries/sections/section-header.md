---
kind: section
name: section-header
family: landing
aliases: [eyebrow, section header, kicker, section label, heading strip]
status: stable
mode: dynamic
content_contract:
  position: "lead | interstitial"
theme: scheduled
composition_notes:
  - "Precedes another content unit; may appear multiple times within one Section Container"
---

# Section Header / Eyebrow

A standalone label preceding another content unit. The Shape pick consults `position` via `rules/shape-selection/section-header.md`: a `lead` header opens a content run as a left-aligned heading strip; an `interstitial` header marks a transition between two runs as a centered labeled divider. section-header is a full content Section — it counts in the ground-alternation schedule like any other Section.
