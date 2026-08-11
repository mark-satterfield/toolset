---
kind: shape
name: listing-rows
aliases: [row list with column headers, entry rows, chronological row list]
status: stable
slots:
  - { name: filter, required: false, accepts: [search-input] }
  - { name: rows, required: true, accepts: [date, category, title] }
  - { name: sidebar, required: false, accepts: [sidebar-content] }
  - { name: pagination, required: false, accepts: [pagination] }
variants: [with-sidebar, without-sidebar]
self_contained: false
content_defaults: {}
---

# listing-rows — Row-per-entry list with column headers

A filter input at full content width above a row-per-entry list, each row carrying date, category, and title columns beneath a column-header strip, with an optional sticky sidebar alongside and a pagination indicator below.

## Determinations

- On the 12-column grid the list content spans grid lines 1–10; the optional sticky sidebar spans lines 11–13 (`foundations/layout.md` §11.6 grid).
- Column headers use the editorial Caption role (the role carries its own letter-spacing), uppercase via CSS.
- Date and category meta use Body 3 agate at `--text-tertiary`.
- Below the tablet breakpoint the rows collapse to stacked cards; the sticky sidebar is hidden below the narrow-viewport cutoff (calibrates to 700px).
