---
kind: shape
name: text-pair-marquee
aliases: [two-line ticker, scrolling statements, attributed text marquee, quote ticker]
status: stable
slots:
  - { name: items, required: true, accepts: [primary-line, secondary-line] }
variants: [right-to-left, left-to-right, pause-on-hover, duplicated-item-set, unique-item-set, primary-first, secondary-first]
self_contained: true
content_defaults: {}
---

# text-pair-marquee — Marquee strip of two-line items

A continuously scrolling full-width row whose repeated item is two stacked lines of text in one column, with no mark beside them. The marquee family's scroll, self-containment, item-separation, and two-line contracts bind (`libraries/shapes/CONVENTIONS.md`, Marquee strips).

## Determinations

- The item is one column holding both lines, capped at the `--column-medium` measure. Each line wraps within that cap rather than extending the item, so the strip's item widths stay even.
- Item-to-item spacing is `--sp-4`, with the family's `--border-subtle` hairline centered in each gap.
- The two lines are one unit for assistive technology: the item is a single list entry carrying both, so a secondary line naming a source is never announced as a separate item.
- The strip renders as a `<ul>`, one `<li>` per item.
