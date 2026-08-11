---
kind: component
name: table-column-header
aliases: [column header, sortable header, table header cell, column sort control]
status: stable
slots:
  - { name: label, required: true, accepts: [text] }
  - { name: sort-glyph, required: false, accepts: [icon-glyph] }
  - { name: sort-ordinal, required: false, accepts: [text] }
  - { name: resize-handle, required: false, accepts: [control] }
sizing:
  height: "--list-row-standard"
  padding: "--sp-0-5 inline"
  gap: "--sp-0-25 between the label and its sort glyph"
  resize-handle-width: "--sp-0-5 hit area centred on the column's trailing edge"
behavior:
  - "sort cycles ascending, descending, unsorted on each activation of the header"
  - "a pinned column stays fixed while the rest of the table scrolls horizontally, and casts a hairline edge to show the seam"
  - "the resize handle is draggable by pointer and adjustable by arrow keys once focused"
accessibility:
  - "the header is a <th scope=\"col\"> whose sort state is carried by aria-sort, and whose control is a real <button> inside it"
  - "the sort ordinal is announced as part of the header's name so multi-column order is audible"
  - "the resize handle is a separate focusable control with its own accessible name and keyboard step"
token_bindings: [--surface-secondary, --border-subtle, --text-primary, --text-tertiary, --list-row-standard, --ease-in-out, --focus-ring, --sp-0-25, --sp-0-5]
composite: false
---

# Table column header

One column's header cell: its name, its sort state and position within a multi-column sort, its pinned state, and the handle that resizes it.

## Multi-column sort

A table may sort on several columns at once. Each participating header carries a **direction glyph** and an **ordinal** naming its position in the sort order — first, second, third. Without the ordinal, two sorted columns are indistinguishable from two independently-sorted ones, and the user cannot tell which is breaking ties.

Activating a header cycles it through ascending, descending, and unsorted. A header entering the sort joins at the end of the order; a header leaving it closes the gap so the ordinals stay contiguous.

## Variants

- `sortable`: `true` (default) | `false` — a column whose values have no meaningful order carries no control and no glyph, rather than a control that does nothing.
- `pinned`: `none` (default) | `inline-start` | `inline-end` — the column holds its edge while the table scrolls horizontally.
- `resizable`: `true` (default) | `false`.
- `align`: `start` (default) | `end` — numeric columns align to the end, and their header aligns with them.

## Determinations

- Height `var(--list-row-standard)`, inline padding `var(--sp-0-5)`, ground `var(--surface-secondary)`, with a `1px solid var(--border-subtle)` rule beneath the whole header row.
- Label at the compact body size, weight 700, ink `var(--text-primary)`.
- The sort glyph sits `var(--sp-0-25)` after the label at `--icon-size-inline`; the ordinal follows it at the caption size in `var(--text-tertiary)`. An unsorted sortable header shows its glyph only on hover and `:focus-visible`, so the header row is not a field of arrows.
- A pinned column paints a hairline on the edge facing the scrolling body, so the seam between fixed and scrolling content is visible.
- The resize handle is a `var(--sp-0-5)` hit area centred on the column's trailing edge, painting a rule on hover and while dragging. It never narrows a column below the width of its own label.
- The header row is sticky to the block-start of the table's scroll container, so column identity survives scrolling.
- Header labels never wrap. A label too long for its column truncates with an ellipsis and carries its full text as the cell's accessible name.

## Accessibility

- The header is a `<th scope="col">`. Its sort control is a `<button>` within the cell rather than a click handler on the cell, so it is reachable and announced as an activatable control.
- Sort state is carried by `aria-sort` on the header (`ascending`, `descending`, or `none`), and the ordinal is part of the button's accessible name so multi-column order is audible.
- The resize handle is a separate focusable control with its own accessible name and a documented keyboard step, so column width is adjustable without a pointer.
- Focus paints the foundation ring on `:focus-visible` (`foundations/accessibility.md` §18.2), independently on the sort control and the resize handle.
