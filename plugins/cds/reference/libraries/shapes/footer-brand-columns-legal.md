---
kind: shape
name: footer-brand-columns-legal
aliases: [brand footer, logo and columns footer, footer with tagline]
status: stable
slots:
  - { name: brand, required: true, accepts: [logo, text] }
  - { name: columns, required: true, accepts: [link-column] }
  - { name: social, required: false, accepts: [social-share-row] }
  - { name: legal, required: true, accepts: [copyright-line, link, locale-control] }
variants: []
self_contained: false
content_defaults: {}
---

# footer-brand-columns-legal — Brand island beside link columns, above a legal row

A brand island — the mark with a single line beneath it — set against a grid of link columns, with a full-width legal row beneath both. The arrangement a footer takes when the frame restates who it is at the foot of every page.

## Determinations

- One row on the 12-column grid (`foundations/layout.md` §11): `brand` takes the leading columns, `columns` takes the remainder as its own sub-grid of 3–5 link columns.
- `brand` is the mark at the Section's mark height with one line of text beneath it, stacked and start-aligned. The line is content the frame supplies; the island renders the mark alone when it does not.
- Below the tablet breakpoint the brand island moves above the column grid and both run full width; the columns collapse to 2, and to 1 below the mobile-narrow breakpoint (`foundations/responsive.md` §17.1).
- Each column is a heading followed by its links, stacked. The heading is the column's `<h3>`.
- `social`, when the content supplies it, is a single row beneath the brand island within its block.
- `legal` is a full-width row beneath everything, separated by the Section's legal-row separation. It carries the copyright line, the legal links, and a locale control when the content supplies one.
