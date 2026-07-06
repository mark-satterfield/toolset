---
kind: shape
name: resource-grid
family: landing
aliases: [resources section, content library grid, article grid]
status: stable
slots:
  - { name: cards, required: true, accepts: [source-tag, card-title, blurb, thumbnail] }
variants: []
self_contained: false
content_defaults:
  source_tags: [Docs, Blog, Video]
---

# resource-grid — Resource grid with source tags

A card grid in which each card carries a source-type tag, a title, a blurb, and an optional thumbnail.

## Determinations

- Inherits the card-grid column policy (`libraries/shapes/card-grid.md`): 3 columns at desktop, 2 below the tablet breakpoint (`foundations/responsive.md` §17.1), 1 in the mobile-narrow band, with the grid gutter (`foundations/layout.md` §11.6) on both axes and the `--card-index` stagger on entry. Cards use the catalog-card Component contract (components library).
- The source tag sits in the card's top-left corner as a small label badge (per the catalog-card contract). Tag styling is uniform — one neutral badge treatment across all source types, not color-per-source — so the grid reads as one set; the tag's text carries the source-type distinction.
- The source-tag set is content: it is extensible, and the declared defaults in `content_defaults` are the drafted-mode scaffold; supplied content overrides them.
