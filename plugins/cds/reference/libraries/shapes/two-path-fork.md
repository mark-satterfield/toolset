---
kind: shape
name: two-path-fork
family: landing
aliases: [path picker, choice cards, dual path cards]
status: stable
slots:
  - { name: path-cards, required: true, accepts: [headline, blurb, cta, visual] }
variants: [with-card-visual, without-card-visual]
self_contained: false
content_defaults: {}
---

# two-path-fork — Path picker (2-card fork)

Two large parallel cards representing exclusive paths, each with its own headline, blurb, and CTA.

## Determinations

- Count is fixed at exactly two. The cards are a 50/50 split on the 12-column grid (each spans 6); the grid gutter (`foundations/layout.md` §11.6) separates them. Each card uses the full-promo-card Component contract (components library).
- Below the tablet breakpoint (`foundations/responsive.md` §17.1) the cards stack to a single column in source order: the first-listed path renders on top.
