---
kind: shape
name: footer-columns-legal
aliases: [footer grid, multi-column footer, link columns and copyright]
status: stable
slots:
  - { name: columns, required: true, accepts: [link-column] }
  - { name: social, required: false, accepts: [social-share-row] }
  - { name: legal, required: true, accepts: [copyright-line, link, locale-control] }
variants: []
self_contained: false
content_defaults: {}
---

# footer-columns-legal — Link columns above a legal row

A grid of link columns with a full-width legal row beneath it. The arrangement a footer takes when the frame's secondary navigation is the footer's whole job and the brand is not restated here.

## Determinations

- The columns sit on the 12-column grid (`foundations/layout.md` §11): 4–6 columns at desktop, collapsing to 2 below the tablet breakpoint and 1 below the mobile-narrow breakpoint (`foundations/responsive.md` §17.1).
- Each column is a heading followed by its links, stacked. The heading is the column's `<h3>`; the links follow in source order.
- `social`, when the content supplies it, is a single row beneath the column grid and above the legal row.
- `legal` is a full-width row beneath everything, separated by the Section's legal-row separation. It carries the copyright line, the legal links, and a locale control when the content supplies one.
- Below the mobile-narrow breakpoint the legal row stacks its parts rather than wrapping them.
