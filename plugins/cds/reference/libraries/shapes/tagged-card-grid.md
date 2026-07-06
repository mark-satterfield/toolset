---
kind: shape
name: tagged-card-grid
family: landing
aliases: [labeled card grid, category card grid]
status: stable
slots:
  - { name: cards, required: true, accepts: [tag, title, blurb, icon, cta] }
variants: [with-card-cta, without-card-cta, with-icon, without-icon, default-fill, colored]
self_contained: false
content_defaults: {}
---

# tagged-card-grid — Tagged card grid

card-grid plus an eyebrow tag/pill above each card title. The tag/pill sits above the card title inside each card; the grid itself inherits card-grid.

## Determinations

- Tags use the Outline pill badge spec from the components library (caption type, sentence case, `--radius-xs` corners). Styling is uniform across cards — one consistent neutral pill rather than color-per-category, so the grid reads as one set.
- The tag sits `--sp-0-75` above the title. All other layout — column policy, gaps, card specs, entry stagger — inherits card-grid.
- The per-card tag/pill is an authorized eyebrow site under `rules/page-constraints/eyebrow-scope.md`.
