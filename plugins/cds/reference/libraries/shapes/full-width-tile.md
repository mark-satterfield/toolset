---
kind: shape
name: full-width-tile
page_family: editorial
aliases: [tinted tile, illustration tile layout, spanning tile]
status: stable
slots:
  - { name: illustration, required: true, accepts: [illustration] }
variants: []
self_contained: false
content_defaults: {}
---

# full-width-tile — Full-width tinted tile

A single tile spanning the full width of the vacant space: one illustration centered on a tinted ground. The tile carries its own padding scale, distinct from the card scale.

## Determinations

- Corner radius is `--radius-lg`.
- Inner padding scales responsively from `--sp-6` down to `--sp-3` (calibrates to 96px at the reference viewport, 48px below the tablet breakpoint).
- Padding to the neighboring Sections is `--sp-3` (calibrates to 48px).
