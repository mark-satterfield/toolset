---
kind: shape
name: split-banner-fork
page_family: landing
aliases: [stacked path bands, mirrored fork bands, two-band fork]
status: stable
slots:
  - { name: path-bands, required: true, accepts: [headline, blurb, cta, visual] }
variants: [text-first-band-left, text-first-band-right]
self_contained: false
content_defaults: {}
---

# split-banner-fork — Stacked mirrored fork bands

Two full-width bands stacked vertically, one per path; each band is a text/visual split, and the second band mirrors the first's alignment.

## Determinations

- Count is fixed at exactly two bands, rendered in the order the content supplies them. Each band spans the page-width section wrapper (`.u-container`) as a single full-width row.
- Within a band, the text (headline, blurb, CTA) and the visual sit in a 50/50 split on the 12-column grid (each spans 6), separated by the grid gutter (`foundations/layout.md` §11.6). The second band mirrors the first: whichever side carries the text in band one carries the visual in band two.
- The two bands are separated vertically by `--sp-4`. Both bands take the Section's scheduled ground from `rules/page-constraints/ground-alternation.md`; the Shape's distinctness comes from the mirrored alignment, not a self-chosen surface.
- The band headings sit in the left register within their text column, matching the reading axis of the copy beside the visual.
- Below the tablet breakpoint (`foundations/responsive.md` §17.1) each band stacks to a single column — text block first, then the visual — and the bands hold their source order; the grid drops to 2 columns and each slot takes the full row.
- The variant choice (which side the first band's text takes) is a Variety Principle alignment decision (`rules/page-constraints/variety-principle.md`), not a property of the shape.
