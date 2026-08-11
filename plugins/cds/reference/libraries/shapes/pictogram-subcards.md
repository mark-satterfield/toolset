---
kind: shape
name: pictogram-subcards
aliases: [animated icon with cards, feature spotlight with sub-cards]
status: stable
slots:
  - { name: pictogram, required: true, accepts: [animated-pictogram] }
  - { name: sub-cards, required: true, accepts: [card-title, blurb, learn-more-cta] }
variants: []
self_contained: true
content_defaults: {}
---

# pictogram-subcards — Pictogram with nested sub-cards

An animated pictogram as the anchor; sub-cards below it, each with its own "learn more" CTA. Sub-card count and pictogram motion style vary per instance.

## Determinations

- The pictogram is centered above the group at a fixed 1:1 aspect ratio. Its motion is decorative and gated behind `@media (prefers-reduced-motion: no-preference)`, rendering as a static glyph under reduced motion; the animation lives in the fragment's own scoped `<style>`/`<script>`, scoped to its own instance.
- Sub-cards follow the card-grid column policy (`libraries/shapes/card-grid.md`): 3 columns at desktop, 2 below the tablet breakpoint (`foundations/responsive.md` §17.1), 1 in the mobile-narrow band, separated by the grid gutter (`foundations/layout.md` §11.6).
- The "learn more" CTA is a tertiary/text button at the foot of each card. The pictogram-to-sub-card gap is `--sp-4`.
