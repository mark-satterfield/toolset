---
kind: shape
name: titled-card-run
page_family: shared
aliases: [card group with heading, titled card row, section with see-more link, grouped cards]
status: stable
slots:
  - { name: group-heading, required: true, accepts: [heading] }
  - { name: see-more, required: false, accepts: [tertiary-link] }
  - { name: cards, required: true, accepts: [media-header-card, action-card, link-card, catalog-card] }
variants: [single-run, stacked-runs]
self_contained: false
content_defaults: {}
---

# titled-card-run — A compact group heading over one row of cards

A small heading naming a group of cards, with an optional link at the far end of the same row leading to the fuller view, above a single row of equal cards. The arrangement a surface takes when it presents several named groups in sequence and each group is one row deep.

Distinct from card-grid, which is cards with no heading of their own, and from heading-action-row, which is a heading row with controls and no content beneath it. The heading and its row of cards are one Section here, because the heading names exactly the cards beneath it.

## Determinations

- The heading row is a flex row: `group-heading` at the start, `see-more` at the end via `margin-inline-start: auto`, baseline-aligned so the link sits on the heading's baseline rather than its box.
- The heading is a group label, not a section title: it is set one step below the Section's heading role, at weight 700. A group heading competing with the Section's own heading flattens the hierarchy.
- `see-more` is a tertiary link naming the fuller view it opens. It never restates the heading.
- `--sp-1` between the heading row and the card row.
- The card row is a single row of equal columns — 3 or 4 at desktop — collapsing to 2 below the tablet breakpoint and 1 below the mobile-narrow breakpoint (`foundations/responsive.md` §17.1). Cards stretch to a common height so the row's block-end edge is straight.
- Every card in one run is the same Component. Mixing card Components within a run breaks the scanning pattern the arrangement exists to create.
- The `stacked-runs` variant repeats the heading-row-plus-card-row unit, with `--sp-3` between adjacent runs. Each run's cards may be a different Component from the previous run's, since each run is its own group.

## Universal Section slots

A supplied `eyebrow` sits above the first group heading at the caption role, start-aligned. A supplied `media` is not placed by this arrangement — the cards are the content.
