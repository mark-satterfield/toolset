---
kind: shape
name: logo-text-pair-marquee
aliases: [attributed quote ticker, scrolling sourced quotes, logo and two-line marquee, cited statement marquee]
status: stable
slots:
  - { name: items, required: true, accepts: [logo, primary-line, secondary-line] }
variants: [right-to-left, left-to-right, pause-on-hover, duplicated-item-set, unique-item-set, primary-first, secondary-first]
self_contained: true
content_defaults: {}
---

# logo-text-pair-marquee — Marquee strip of a mark beside two lines

A continuously scrolling full-width row whose repeated item pairs a mark with two stacked lines of text beside it — the fullest item the marquee family carries. The family's scroll, self-containment, item-separation, and two-line contracts bind (`libraries/shapes/CONVENTIONS.md`, Marquee strips).

## Determinations

- The item is two columns: the mark at the inline-start at `height: var(--icon-size-feature); width: auto`, and the two-line stack beside it, `--sp-1` apart. The stack's block-start edge aligns to the mark's, so the mark reads as belonging to the first line rather than floating against the pair.
- The item is capped at the `--column-medium` measure across both columns; each line wraps within the text column rather than extending the item, so the strip's item widths stay even.
- Item-to-item spacing is `--sp-4`, with the family's `--border-subtle` hairline centered in each gap.
- The mark, its lines, and their order are one unit for assistive technology: the item is a single list entry carrying all three, and the mark is `aria-hidden` when one of its lines already names the organization.
- The strip renders as a `<ul>`, one `<li>` per item.
