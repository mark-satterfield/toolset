---
kind: shape
name: icon-link-row
page_family: editorial
aliases: [share row layout, link icon row, inline icon row]
status: stable
slots:
  - { name: row, required: true, accepts: [icon-links] }
variants: []
self_contained: false
content_defaults: {}
---

# icon-link-row — Icon-link row above a hairline rule

A single horizontal row of icon links set above a hairline top rule, aligned to the reading column of the content it closes.

## Determinations

- A single hairline top rule (`foundations/layout.md` §11.9) separates the row from the content above it; the row carries no other line work.
- The row sits inside the `--column-reading` reading column, aligned with the content it follows.
