---
kind: shape
name: cta-panel
family: landing
aliases: [call to action, CTA band, final CTA, conversion band]
status: stable
slots:
  - { name: headline, required: true, accepts: [headline] }
  - { name: subhead, required: true, accepts: [subhead] }
  - { name: cta-group, required: true, accepts: [button] }
variants: [single-cta, dual-cta]
self_contained: false
content_defaults: {}
---

# cta-panel — Full-width CTA panel

A tall full-width band: headline, subhead, and CTAs in a vertically centered content block.

## Determinations

- CTA count is 1–2: a primary button plus an optional tertiary peer. Content is centered both horizontally and vertically.
- The band height comes from `--section-pad-large` top and bottom against a centered content block, giving the tall full-width feel without a fixed pixel height.
- The panel takes its Section's scheduled ground from `rules/page-constraints/ground-alternation.md`. Darkness is a theme island, not a variant of this shape: a dark CTA band is a named theme island declared on the Section Container, applied on top of the scheduled ground.
