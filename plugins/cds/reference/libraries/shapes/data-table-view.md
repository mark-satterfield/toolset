---
kind: shape
name: data-table-view
aliases: [table screen, records view, list view, opportunities table, data grid view]
status: stable
slots:
  - { name: heading-row, required: true, accepts: [heading, button] }
  - { name: saved-views, required: false, accepts: [saved-view-bar] }
  - { name: filter-row, required: true, accepts: [list-filter, filter-chip, filter-builder-panel] }
  - { name: table, required: true, accepts: [data-table] }
  - { name: pagination, required: true, accepts: [pagination, select-menu] }
variants: [with-saved-views, without-saved-views, with-filter-builder]
self_contained: false
content_defaults: {}
---

# data-table-view — A records surface, top to bottom

The standard arrangement of a table screen filling the vacant space: a heading row, the saved views, the filter row, the table, and the pagination controls beneath it.

Every part but the table is furniture around it; the table itself is the data-table Component (`libraries/components/data-table.md`), which owns its own columns, rows, selection, and keyboard model.

## Determinations

- One vertical stack at the full width of the vacant space, each band spanning it.
- `heading-row` is the heading-action-row arrangement (`libraries/shapes/heading-action-row.md`): the surface's name at the start, its primary action at the end.
- `saved-views` sits directly beneath the heading with `--sp-1` above the filter row.
- `filter-row` is a single row: the free-text filter at the start, facet chips beside it, and the advanced-filter trigger at the end. The filter builder panel (`libraries/components/filter-builder-panel.md`) opens from that trigger and displaces the table downward rather than overlaying it, so the user can see the result set change as they build.
- The table occupies the remaining block space and scrolls within itself; the surrounding bands hold their positions.
- `pagination` sits beneath the table: the rows-per-screen control at the inline-start, the position indicator and prev/next at the inline-end.
- The bulk action bar (`libraries/components/bulk-action-bar.md`), when a selection exists, pins above the table's block-end edge inside the table's own band — not over the pagination row, which stays reachable.
- Every band holds its position when the table's contents change. A filter that empties the result set leaves the heading, the views, the filters, and the pagination in place, with the empty state inside the table's body.

## Entrance

The bands enter in document order — heading, views, filters, table — as a staged fade, each band beginning shortly after the one above it. The table's rows do not stagger individually; a grid whose rows arrive one at a time reads as loading rather than as arriving. Reduced motion renders every band in its final state immediately (`foundations/motion.md` §15.5).

## Universal Section slots

A supplied `eyebrow` sits above the heading row at the caption role. A supplied `media` is not placed by this arrangement — the table is the content.
