---
kind: section
name: publication-list
family: editorial
aliases: [publication list, article list, post index, archive list]
status: stable
mode: deterministic
content_contract: {}
theme: editorial
composition_notes: []
---

# Publication list

The chronological index of a resource-index page: a filter input above a row-per-entry list with date, category, and title columns.

## Slots

- `filter` — a search-input Component (`libraries/components/search-input.md`) used as an inline list filter, at full content width above the list.
- `rows` — one row per entry: date, category, title columns.
- `sidebar` — optional sticky sidebar.
- `pagination` — a pagination indicator (`libraries/components/pagination.md`); no numbered page buttons.

## Determinations

- On the 12-column grid the list content spans grid lines 1–10; the optional sticky sidebar spans lines 11–13.
- Column headers use the editorial Caption role (the role carries its own letter-spacing), uppercase via CSS.
- Date and category meta use Body 3 agate at `--text-tertiary`.
- Below the tablet breakpoint the rows collapse to stacked cards; below 700px the sticky sidebar is hidden.
