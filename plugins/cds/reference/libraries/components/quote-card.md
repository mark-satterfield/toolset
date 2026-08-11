---
kind: component
name: quote-card
aliases: [testimonial card, quote panel, customer quote, logo quote card]
status: stable
slots:
  - { name: mark, required: false, accepts: [image, svg-glyph] }
  - { name: quote, required: true, accepts: [text] }
  - { name: attribution, required: true, accepts: [text] }
sizing:
  mark-height: "--icon-size-feature; width auto, so marks of differing proportion align on their optical height"
  mark-gap: "--sp-1-5 between the mark and the quote"
  attribution-gap: "--sp-1-5 between the quote and its attribution"
  inline-padding: "--sp-1-5 from the card's leading rule to its content"
behavior:
  - "static: the card paints, it does not hover or animate"
accessibility:
  - "the quote is a <blockquote> and the attribution its <figcaption> within a <figure>"
  - "the mark is an image whose alt text names the organization, or is aria-hidden when the attribution already names it"
token_bindings: [--border-subtle, --text-primary, --text-secondary, --icon-size-feature, --sp-1-5]
composite: false
---

# Quote card

One attributed quotation presented as a column: the speaker's organization mark at the top, the quotation beneath it, and the attribution at the foot. Separated from its neighbors by a hairline rule rather than by a card border, so a row of quotes reads as one band divided into columns.

## Variants

- `separator`: `leading-rule` (default — a hairline on the card's inline-start edge, so a row of cards shows a rule between each pair and none at the row's outer edges) | `none` (the card stands alone with no rule).
- `mark`: `present` (default) | `absent` — the quote opens the column directly.

## Determinations

- No ground, no border box, no radius: the card is a column of content on the surrounding Section's ground.
- The leading rule is `1px solid var(--border-subtle)` on the inline-start edge, with `var(--sp-1-5)` of inline padding between it and the content. The first card in a row suppresses its rule so the band has no outer edge.
- The mark renders at `height: var(--icon-size-feature); width: auto`, start-aligned, so marks of different proportions sit on a common optical height rather than a common width.
- Quote at the body size, ink `var(--text-primary)`, `var(--sp-1-5)` below the mark. Set as running text with typographic quotation marks — no oversized decorative glyph, no italics.
- Attribution at the compact body size, ink `var(--text-secondary)`, `var(--sp-1-5)` below the quote, anchored to the column's block-end edge via `margin-block-start: auto` so attributions align across a row of unequal quotes.

## Accessibility

- The card is a `<figure>` containing a `<blockquote>` for the quotation and a `<figcaption>` for the attribution, so the relationship between the words and their speaker is in the structure rather than only in the layout.
- The mark is an `<img>` whose `alt` names the organization when the attribution does not, and carries `aria-hidden="true"` when the attribution already names it — announcing the same organization twice reads as two organizations.
- The leading rule is a border, never a character, so it is absent from the accessible name of anything.
