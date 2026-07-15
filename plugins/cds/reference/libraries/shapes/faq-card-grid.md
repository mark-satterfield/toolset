---
kind: shape
name: faq-card-grid
page_family: landing
aliases: [FAQ cards, question card grid, card FAQ]
status: stable
slots:
  - { name: cards, required: true, accepts: [question, answer] }
variants: []
self_contained: false
content_defaults: {}
---

# faq-card-grid — Question/answer card grid

Each question and its answer sit together in a card, laid out as a grid; every answer is visible at once, with no expand/collapse.

## Determinations

- Cards render in the order the content supplies them, each pairing its question heading over its answer body. Card padding rides `--sp-2`, the card-padding default.
- The grid holds 3 columns at desktop, 2 below the tablet breakpoint, and 1 below the mobile-narrow breakpoint (`foundations/responsive.md` §17.1), with the grid gutter (`foundations/layout.md` §11.6) on both axes and the `--card-index` stagger on entry — the shared card-grid column policy.
- The card row sits in the left register; each card's question heading and answer align to their reading axis.
- Cards hold a uniform height per grid row: every card in a row takes the height of the tallest card in that row.
