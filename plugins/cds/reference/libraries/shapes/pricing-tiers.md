---
kind: shape
name: pricing-tiers
family: landing
aliases: [pricing cards, pricing table, plan cards, tier comparison]
status: stable
slots:
  - { name: segment-toggle, required: true, accepts: [pill-tab-strip] }
  - { name: tier-cards, required: true, accepts: [pricing-card] }
variants: [two-tier, three-tier, four-tier]
self_contained: true
content_defaults:
  segment_toggle:
    segments: [Individual, Team]
---

# pricing-tiers — Tier card row with segment toggle

A horizontal row of 2–4 tier cards with a segment toggle anchored above; selecting a segment swaps the tier set in place.

## Determinations

- The section spans the full page-width wrapper (`.u-container`), never a narrower reading column; the tier cards lay out across the 12-column grid within it, so a 3–4-tier row never cramps into a narrow column.
- The segment toggle is centered above the row and uses the pill-tab-strip Component contract (components library) as a `role="radiogroup"`: it filters the tier set in place (the row is the only panel; no distinct panels swap). The segment count follows the content; the toggle labels are content (declared defaults in `content_defaults`).
- One tier may be marked featured: it paints an accent-colored border at the card-hairline weight (1px, `foundations/layout.md` §11.9) and a featured pill at its top, and sits in the visual center of the row. Tier cards use the pricing-card Component contract (components library).
- Below the tablet breakpoint (`foundations/responsive.md` §17.1) the tier row stacks to a single column with the featured tier first.
- The segment-swap behavior is Shape-level: the fragment carries its own scoped `<style>` and IIFE `<script>` implementing the radiogroup keyboard contract from `foundations/accessibility.md`, scoped to its own instance.
