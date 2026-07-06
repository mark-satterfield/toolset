---
kind: shape
name: numbered-steps
family: landing
aliases: [how it works, step row, 1-2-3 steps]
status: stable
slots:
  - { name: steps, required: true, accepts: [step-number, title, blurb] }
variants: [digit-numbering, ordinal-numbering, vertical]
self_contained: false
content_defaults: {}
---

# numbered-steps — Numbered step row

A horizontal row of columns (typically 3) with explicit ordinal numbering on each step; each step carries a step number, title, and blurb. The `vertical` variant stacks the steps as a single-column numbered list at all viewports.

## Determinations

- Default step count is 3; columns sit on the 12-column grid at 4 columns each. When step count exceeds 3, the row wraps onto additional grid rows rather than scrolling, keeping each step at the same column width.
- Below the tablet breakpoint (`foundations/responsive.md` §17.1) steps stack to a single column in numeric order. Numbering uses leading digits (1, 2, 3) by default.
- The `vertical` variant applies the single-column stacked arrangement at all viewports, capped at a `--column-medium` column inside the page-width section; it reads at any step count.
- The step sequence is semantically an ordered list (`<ol>`) so the ordering is conveyed without relying on the visual numbers alone.
