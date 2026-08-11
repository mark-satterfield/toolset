---
kind: shape
name: split-text-media
aliases: [two-column hero, text and image side by side]
status: stable
slots:
  - { name: text-column, required: true, accepts: [headline, subhead, cta-group] }
  - { name: visual-column, required: true, accepts: [image, screenshot, video] }
variants: [text-left-visual-right, text-right-visual-left]
self_contained: false
content_defaults: {}
---

# split-text-media — Two-column text/visual

Text + CTAs on one side, a single visual on the other. Horizontal two-column split.

## Determinations

- Column ratio is 50/50 on the 12-column grid (each column spans 6). The grid gutter (`foundations/layout.md` §11.6) separates the columns.
- Below the tablet breakpoint (`foundations/responsive.md` §17.1) the columns stack to a single column — text block first, then the visual; the grid drops to 2 columns and each slot takes the full row.
- The visual is centered vertically against the text column and capped at the column width; it carries no fixed aspect ratio, so source media of any ratio fits.
- The variant choice (which side carries the text) is a Variety Principle alignment decision (`rules/page-constraints/variety-principle.md`), not a property of the shape.
