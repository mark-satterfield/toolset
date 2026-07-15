---
kind: shape
name: sub-hero-split
page_family: landing
aliases: [mid-page hero, secondary hero, video CTA split]
status: stable
slots:
  - { name: visual-column, required: true, accepts: [video] }
  - { name: text-column, required: true, accepts: [headline, cta-pair] }
variants: [video-left-text-right, video-right-text-left]
self_contained: false
content_defaults: {}
---

# sub-hero-split — Sub-hero with video and CTA pair

A mid-page hero-like restatement: video on one side, headline plus a CTA pair on the other, in a horizontal two-column split.

## Determinations

- The section spans the full page-width wrapper (`.u-container`), never a narrower reading column; the two columns lay out across the 12-column grid within it.
- The CTA pair is exactly two CTAs: a primary button plus a tertiary peer. A single-action restatement is split-text-media (`libraries/shapes/split-text-media.md`), not this shape.
- Columns are 50/50 on the 12-column grid (each spans 6); the grid gutter (`foundations/layout.md` §11.6) separates them. The video sits at a fixed 16:9 aspect ratio capped at its column width.
- Below the tablet breakpoint (`foundations/responsive.md` §17.1) the columns stack with the video above the text/CTA column, and the CTA pair stacks full-width.
