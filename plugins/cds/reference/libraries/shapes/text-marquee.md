---
kind: shape
name: text-marquee
aliases: [text ticker, scrolling text strip, phrase marquee, statement ticker]
status: stable
slots:
  - { name: items, required: true, accepts: [text] }
variants: [right-to-left, left-to-right, pause-on-hover, duplicated-item-set, unique-item-set]
self_contained: true
content_defaults: {}
---

# text-marquee — Marquee strip of single lines

A continuously scrolling full-width row whose repeated item is one line of text with no mark beside it. The marquee family's scroll, self-containment, item-separation, and two-line contracts bind (`libraries/shapes/CONVENTIONS.md`, Marquee strips).

## Determinations

- The repeated item is a single line at the body role in `--text-primary`, set on one line without wrapping. An item too long to sit on one line at the `--column-medium` measure belongs in text-pair-marquee, which gives it a second line.
- Item-to-item spacing is `--sp-4`, with the family's `--border-subtle` hairline centered in each gap.
- The strip is a list of peer statements: it renders as a `<ul>` so the item count and boundaries are conveyed without relying on the dividers alone.
