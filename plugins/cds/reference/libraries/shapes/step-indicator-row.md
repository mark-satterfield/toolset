---
kind: shape
name: step-indicator-row
aliases: [stepper row, wizard step row, progress step strip]
status: stable
slots:
  - { name: stepper, required: true, accepts: [stepper] }
variants: [icons-only, with-labels]
self_contained: false
content_defaults: {}
---

# step-indicator-row — Step indicator row

A single horizontal row holding a numbered step indicator, anchored at the top of the vacant space (`--sp-1-5` from the top edge).

## Determinations

- Width adapts to the viewport: at narrow viewports the stepper compresses to icons only (width fits the step circles and gaps; calibrates to ~200px); at wide viewports it grows to fit the step labels (calibrates to labels showing at ≥ 1400px).
- Active-step visual: the current step's circle uses `--text-primary` for both its border and its numeral; completed steps use a filled accent circle with a check glyph; future steps use `--text-tertiary` ink on a transparent circle with a `--border-subtle` ring.
