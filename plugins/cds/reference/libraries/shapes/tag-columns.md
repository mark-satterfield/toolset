---
kind: shape
name: tag-columns
aliases: [tag cloud columns, category columns, pill columns]
status: stable
slots:
  - { name: columns, required: true, accepts: [column-header, category-pills] }
variants: [three-column, four-column, five-column]
self_contained: false
content_defaults: {}
---

# tag-columns — Pill/tag cloud columns

3–5 vertical columns of category pills side by side, each column with its own header.

## Determinations

- Columns sit on the 12-column grid, evenly dividing the row by column count; the grid gutter (`foundations/layout.md` §11.6) separates them. Below the tablet breakpoint (`foundations/responsive.md` §17.1) the columns stack to a single column, header then pills, in source order.
- Pills within a column render in the order the content supplies them (no automatic re-sort). Each pill is a non-interactive outline pill-badge by default; a pill that filters or navigates is a `<button>`/`<a>` with the foundation focus ring, per the badge's interactive variant in the components library.
