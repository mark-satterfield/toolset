---
kind: component
name: article-hero
page_family: editorial
aliases: [article hero, editorial hero, article header]
status: stable
slots:
  - { name: eyebrow, required: true, accepts: [subjects-row] }
  - { name: title, required: true, accepts: [headline-1] }
  - { name: date-row, required: true, accepts: [text] }
  - { name: byline, required: false, accepts: [text] }
  - { name: illustration-tile, required: true, accepts: [tinted-svg-tile] }
sizing:
  tile_aspect_ratio: "16:9 at the tablet breakpoint and above; 4:3 below 700px"
  tile_inner_padding: "calc(var(--card-padding-md) * 2) around the centered SVG; --sp-4 (52–64px clamp) below 700px"
behavior: []
accessibility: []
token_bindings:
  - --text-primary
  - --tile-ground-1
  - --tile-ground-2
  - --tile-ground-3
composite: false
---

# Article hero

The editorial detail page's hero — a centered three-line header above a tinted illustration tile: eyebrow (Subjects row) + title (Headline 1) + date row + illustration tile. Static at rest.

## Determinations

- Title at the Headline 1 scale, centered, `text-wrap: balance`. The date row sits below in tertiary ink.
- The illustration tile holds a 16:9 aspect-ratio with inner padding `calc(var(--card-padding-md) * 2)` around the centered SVG — calibrates to 96–128px across the clamp range at the reference viewport.
- The tile ground is a saturated panel ground (the `--tile-ground-N` feature-tile roles).

## Title truncation

Titles are never truncated — the hero title is the page's primary content and wraps to as many lines as needed, with `text-wrap: balance` keeping line lengths even. The illustration tile reflows below the wrapped title rather than the title clipping.

## Multi-author byline

The date row hosts an optional byline slot: author names join with comma separators and a final "and" (e.g., "By A, B, and C"), rendered inline in the same tertiary ink as the date, separated from the date by a `·` middot. Beyond three authors, show the first two followed by "and N others".

## Illustration tile breakpoint behavior

The tile holds its 16:9 aspect-ratio at the tablet breakpoint and above; below 700px (`foundations/responsive.md` §17.1) it relaxes to 4:3 to preserve glyph legibility in the narrower column, and the inner padding drops to the derivation's lower bound (`--sp-4`, 52–64px clamp).
