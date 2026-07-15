---
kind: shape
name: alternating-rows
page_family: landing
aliases: [zigzag layout, alternating feature rows, image-text rows]
status: stable
slots:
  - { name: rows, required: true, accepts: [image, headline, blurb, cta] }
variants: [image-left-first, image-right-first]
self_contained: false
content_defaults: {}
---

# alternating-rows — Alternating image+text rows

A vertical stack of horizontal rows; each row pairs an image with a text block (headline, blurb, optional CTA), and the image side alternates row by row. The variant sets which side row 1 starts on.

## Determinations

- Row count is content-driven, 2 or more. Each row is a 50/50 split on the 12-column grid, separated by the grid gutter (`foundations/layout.md` §11.6).
- Below the tablet breakpoint (`foundations/responsive.md` §17.1) every row collapses to a single column with image above text, regardless of the desktop side — alternation is dropped on narrow widths so reading order stays consistent top-to-bottom.
- Row-to-row gap is `--sp-5`.
