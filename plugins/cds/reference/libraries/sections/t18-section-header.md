---
kind: section
name: section-header
id: T18
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

# T18 — Section Header / Eyebrow

A standalone label preceding another content unit. The shape pick consults `position` via `rules/shape-selection/t18.md`: a `lead` header opens a content run as a left-aligned heading strip; an `interstitial` header marks a transition between two runs as a centered labeled divider. T18 is a full content Section — it counts in the ground-alternation schedule like any other Section.
