---
kind: component
name: data-table
aliases: [table, data grid, records table, list table, tabular view, grid]
status: stable
slots:
  - { name: selection-column, required: false, accepts: [checkbox] }
  - { name: column-headers, required: true, accepts: [table-column-header] }
  - { name: rows, required: true, accepts: [text, status-badge, score-verdict, confidence-indicator] }
  - { name: row-actions, required: false, accepts: [row-action-menu] }
sizing:
  row-height: "--list-row-standard for the default density; --list-row-compact for the compact density"
  cell-padding: "--sp-0-5 inline"
  header-height: "--list-row-standard"
behavior:
  - "one row is one record; a row is activatable as a whole and opens that record's detail"
  - "the table scrolls horizontally within its own container while pinned columns hold their edges; the page never scrolls horizontally"
  - "rows render progressively as the body scrolls, and the scrollbar reflects the full result count rather than the rendered window"
accessibility:
  - "a real <table> with <th scope=\"col\"> headers and <th scope=\"row\"> on the identifying cell of each row"
  - "grid keyboard navigation: arrow keys move by cell, Home and End to row ends, Page keys by viewport, and the row's own activation on Enter"
  - "the rendered window is a rendering detail — aria-rowcount and aria-rowindex report the true position in the full set"
token_bindings: [--surface-primary, --surface-secondary, --surface-tertiary, --border-subtle, --text-primary, --text-secondary, --list-row-standard, --list-row-compact, --ease-in-out, --focus-ring, --sp-0-5]
composite: true
---

# Data table

The one tabular surface. Every list of records in a build renders through this Component, so sorting, pinning, resizing, selection, and keyboard navigation behave identically wherever a user meets a table.

It composes the column header (`libraries/components/table-column-header.md`), the per-row action menu (`libraries/components/row-action-menu.md`), the expansion panel (`libraries/components/row-expansion-panel.md`), and the bulk action bar (`libraries/components/bulk-action-bar.md`). The surrounding filter, saved-view, and pagination furniture is the arrangement's — `libraries/shapes/data-table-view.md`.

Distinct from listing-rows (`libraries/shapes/listing-rows.md`), which is a chronological reading list with no column model, and from the comparison matrix (`libraries/shapes/comparison-matrix.md`), which compares attributes across a fixed handful of subjects.

## Variants

- `density`: `default` (row height `--list-row-standard`) | `compact` (`--list-row-compact`).
- `selection`: `none` (default) | `multi` — a leading checkbox column, with a header checkbox that selects every row in the current result set and reports a mixed state when some are selected.
- `row-expansion`: `none` (default) | `inline` — a row discloses a panel beneath itself (`libraries/components/row-expansion-panel.md`).

## Determinations

- Rows carry no ground. Separation is a `1px solid var(--border-subtle)` rule beneath each row — zebra striping doubles the visual noise of a dense grid without adding information.
- Hover paints the theme's hover stratum across the whole row, so the row reads as one target.
- The selected row state paints `var(--surface-tertiary)` and persists while the pointer is elsewhere, so selection is distinguishable from hover.
- Cell inline padding `var(--sp-0-5)`. Text cells truncate with an ellipsis and carry their full text as the cell's accessible name; they never wrap, because a wrapping cell breaks the row rhythm the grid depends on.
- Numeric cells use tabular figures and align to the inline-end with their headers.
- The table scrolls horizontally inside its own `overflow-x: auto` container. The page body never scrolls horizontally.
- Rendering is windowed: only the rows near the viewport are in the document, and the scroll container's extent reflects the full result count so the scrollbar tells the truth about how much there is.
- A row is one record and is activatable as a whole. Controls inside a row — the selection checkbox, the action menu, an inline control — are siblings of the row's own target, never descendants of it, following the nested-target contract in `libraries/components/action-card.md`.

## Empty and loading

- No results renders the empty state Component (`libraries/components/empty-state-card.md`) in the table's body, with the column header row still drawn. Removing the headers hides the shape of what is missing.
- While the first page loads, rows render as skeleton blocks (`libraries/components/skeleton-block.md`) at the table's own row height, so the surface does not resize when data arrives.

## Accessibility

- A real `<table>`. Column headers are `<th scope="col">`; the cell that identifies the record is a `<th scope="row">`, so every other cell is announced with both its column and its record.
- Keyboard navigation is the grid pattern: arrow keys move cell to cell, Home and End go to the row's ends, Page keys move by viewport, and Enter activates the row. Tab moves out of the table rather than through every cell.
- Windowed rendering is invisible to assistive technology: `aria-rowcount` reports the full result count and each row carries its true `aria-rowindex`, so a screen reader is never told there are forty rows when there are four thousand.
- Sorting and filtering announce the new result count through a polite live region.
- Focus paints the foundation ring on `:focus-visible` (`foundations/accessibility.md` §18.2).
