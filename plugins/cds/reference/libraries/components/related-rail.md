---
kind: component
name: related-rail
aliases: [related rail, related-content rail, sibling articles, read-more rail]
status: stable
slots:
  - { name: heading, required: true, accepts: [headline-4] }
  - { name: items, required: true, accepts: [link-grid] }
sizing:
  arrow_glyph: "SVG arrow on the --icon-viewbox-lg drawing grid, rendered at grid size (calibrates to 30×30px)"
  inter_item_gap: "the 12-column grid gutter (32px, foundations/layout.md §11.6) above the tablet breakpoint; --sp-1-5 (24px) when stacked"
behavior: [item-hover-color-transition]
accessibility: []
token_bindings:
  - --text-primary
  - --text-secondary
composite: false
---

# Related rail

The sibling-article rail at the bottom of editorial detail pages: a heading plus a 3-item link grid, each item carrying a title, a dek, and a "Read more" arrow link.

## Determinations

- Heading at the Headline 4 scale. Each item: Headline 6 title + Body 3 serif dek + tertiary "Read more" arrow link whose SVG arrow is drawn on the `--icon-viewbox-lg` drawing grid (`foundations/imagery.md` §16.1, the read-more arrow grid) and rendered at grid size (calibrates to 30×30px).

## Behavior

- Item color transitions to `--text-secondary` over 200ms.

## Item selection

The rail renders exactly three items supplied by the host's content layer; the component does not choose them. When fewer than three are supplied, the grid renders the available items and collapses unused columns rather than padding with placeholders.

## Responsive collapse

Three columns at the tablet breakpoint and above (≥700px, `foundations/responsive.md` §17.1); two columns from 480–700px; a single column below 480px. Inter-item gap follows the `foundations/layout.md` §11.6 grid gutter (32px) above tablet and reduces to `--sp-1-5` (24px) when stacked.
