---
kind: component
name: skeleton-block
aliases: [skeleton, loading placeholder, shimmer, content placeholder, loading block]
status: stable
slots:
  - { name: block, required: true, accepts: [shape] }
sizing:
  dimensions: "the block takes the dimensions of the content it stands in for — the placing Component or Shape supplies them; this entry supplies no size of its own"
  radius: "--radius-xs for a text line; the replaced element's own radius for anything else"
  line-gap: "--sp-0-5 between stacked text lines"
behavior:
  - "a slow pulse between two ground strata; suppressed entirely under reduced motion, where the block renders as a static fill"
  - "replaced by real content in place, with no entrance animation on the content that arrives"
accessibility:
  - "the skeleton region carries aria-busy=\"true\" and the blocks themselves are aria-hidden"
  - "the region announces once when loading begins and once when it completes — never on each block"
  - "focus never lands on a skeleton block"
token_bindings: [--surface-secondary, --surface-tertiary, --radius-xs, --ease-in-out, --sp-0-5]
composite: false
---

# Skeleton block

A neutral fill standing in the exact place and at the exact size of content that has not arrived. It holds the layout still so the surface does not resize when data lands.

## It takes its size from what it replaces

This entry declares no dimensions. A skeleton line in a table row is the row's height; a skeleton card is the card's box; a skeleton facet card holds that card's aspect ratio. The placing Component or Shape supplies the geometry, because the whole point is that the placeholder occupies the same space its content will.

A skeleton that collapses, or that sizes itself to some default, causes the reflow it exists to prevent.

## Variants

- `kind`: `line` (a text line at the type's line height, at `--radius-xs`) | `block` (a rectangle taking the replaced element's own radius) | `circle` (an avatar or glyph position).
- `lines`: for the `line` kind, the count of stacked lines, the last set shorter than the rest so a paragraph placeholder reads as prose rather than as a bar chart.

## Determinations

- Ground is a slow pulse between `var(--surface-secondary)` and `var(--surface-tertiary)` over roughly two seconds, `var(--ease-in-out)`, infinite. One stratum of contrast — a placeholder that flashes competes with the content around it.
- Every skeleton in one region pulses in phase. Blocks animating independently read as many things loading rather than one.
- Under `prefers-reduced-motion: reduce` the pulse is removed entirely and the block renders as a static `var(--surface-secondary)` fill (`foundations/motion.md` §15.5). Motion is not the signal; occupancy is.
- The skeleton carries no text, no glyph, and no spinner inside it.
- Real content replaces the skeleton in place with no entrance animation of its own. A fade-in on arriving content, stacked on the pulse that preceded it, reads as a second load.
- A load that resolves faster than a few hundred milliseconds shows no skeleton at all — a placeholder that appears and vanishes is a flash, not feedback.

## Accessibility

- The container being populated carries `aria-busy="true"` while its skeletons are shown, and drops it when content arrives.
- The blocks themselves carry `aria-hidden="true"`. A screen reader has no use for the shape of absent content.
- The region announces once when loading begins and once when it completes, through a polite live region — not once per block.
- No skeleton is focusable, so tabbing through a loading region does not stop on nothing.
