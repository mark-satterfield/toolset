---
kind: shape
name: footer-minimal
aliases: [single-row footer, legal row only, bare footer, compact footer]
status: stable
slots:
  - { name: legal, required: true, accepts: [copyright-line, link, locale-control] }
  - { name: brand, required: false, accepts: [logo] }
  - { name: social, required: false, accepts: [social-share-row] }
sizing:
  brand: "height var(--footer-mark-height); width auto — the mark's height in the footer row"
variants: []
self_contained: false
content_defaults: {}
---

# footer-minimal — One legal row

A single row carrying the copyright line and a short run of legal links, optionally preceded by the mark. The arrangement a footer takes when the frame offers no secondary navigation — an application surface, a conversion surface, a single-purpose site.

## Determinations

- One flex row. `brand`, when the content supplies it, sits at the start at this Shape's `sizing.brand` height; `legal` sits at the end via `margin-inline-start: auto`.
- With no `brand`, `legal` runs the full width of the row and is start-aligned.
- The row must NOT use `justify-content: space-between` — the copyright line and its links are one group and stay together.
- `social`, when the content supplies it, joins the end of the row after the legal links.
- Below the mobile-narrow breakpoint (`foundations/responsive.md` §17.1) the row stacks: mark, then legal, each start-aligned.
- There are no columns and no column headings. A footer that needs them is a different arrangement.
