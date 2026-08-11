---
kind: shape
name: logo-text-marquee
aliases: [logo and label ticker, scrolling logo captions, marked text marquee]
status: stable
slots:
  - { name: items, required: true, accepts: [logo, text] }
variants: [right-to-left, left-to-right, pause-on-hover, duplicated-item-set, unique-item-set]
self_contained: true
content_defaults: {}
---

# logo-text-marquee — Marquee strip of a mark beside one line

A continuously scrolling full-width row whose repeated item pairs a mark with a single line of text beside it. The marquee family's scroll, self-containment, and item-separation contracts bind (`libraries/shapes/CONVENTIONS.md`, Marquee strips).

## Determinations

- The item is two columns: the mark at the inline-start at `height: var(--icon-size-feature); width: auto`, and the text line beside it, `--sp-1` apart, vertically centered on the mark.
- The text line sets at the body role in `--text-primary` on one line without wrapping. The whole item is capped at the `--column-medium` measure across both columns; an item needing more than one line of text belongs in logo-text-pair-marquee.
- Item-to-item spacing is `--sp-4`, with the family's `--border-subtle` hairline centered in each gap.
- The mark is `aria-hidden` when the text line already names its organization, since announcing the same organization twice reads as two organizations.
- The strip renders as a `<ul>`, one `<li>` per item.
