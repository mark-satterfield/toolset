---
kind: shape
name: kanban-board
page_family: app
aliases: [board, pipeline board, stage columns, tracking board, swimlanes]
status: stable
slots:
  - { name: column-header, required: true, accepts: [text] }
  - { name: cards, required: true, accepts: [kanban-card] }
  - { name: column-overflow, required: false, accepts: [tertiary-link] }
  - { name: board-switcher, required: false, accepts: [saved-view-bar] }
variants: [fixed-columns, configurable-columns]
self_contained: true
content_defaults: {}
---

# kanban-board — Records as cards in state columns

A horizontal run of columns, one per state, each holding the cards currently in that state. Moving a card between columns is how the record's state changes.

The cards are the kanban-card Component (`libraries/components/kanban-card.md`); this arrangement owns the columns, the drag, and the overflow.

## Determinations

- The board is a horizontal run of equal-width columns filling the vacant space, scrolling horizontally within its own container when the columns exceed the width. The page never scrolls horizontally.
- Each column is a block-start header — its name and its card count — over a vertical stack of cards `--sp-0-75` apart, scrolling within the column when it exceeds the board's height.
- The header holds its position while the column's cards scroll, so a user deep in one column always knows which one they are in.
- A column's count is the true total in that state, not the number rendered. A column that renders a bounded number of cards states the total in its header and offers `column-overflow` — a link to the full set in the table view — so a card is never unreachable because its column is long.
- Drop targets are the whole column, not a gap between cards. A board whose columns are states does not order cards within a state, so an insertion point would imply a precision the model does not have.
- The column a card is dragged over highlights as a whole; the card's origin column holds its gap open until the drop resolves.
- A drop that requires more information than the drag carries — a state that needs a reason — opens a dialog (`libraries/components/dialog.md`) after the drop, with the card resting in its new column while the dialog is open and returning to its origin if the dialog is dismissed.
- The `configurable-columns` variant lets a build define which states exist and which column each maps to; every state maps to exactly one column, so no record can be in two columns or in none.
- `board-switcher`, when present, is a saved-view-bar (`libraries/components/saved-view-bar.md`) above the board, switching whole column configurations.

## The board and the table are one record set

A board and a table over the same records show the same values. A change made on either is a change to the record, so a card dragged on the board is a row updated in the table. Neither surface is a copy of the other.

## Self-contained behavior

This Shape declares `self_contained: true`. Its fragment carries its own scoped `<style>` and a scoped IIFE `<script>` implementing pointer drag, the keyboard move contract from `libraries/components/kanban-card.md`, drop-target highlighting, and the live-region announcements — scoped to its own instance so several boards never collide.

## Accessibility

- Each column is a labelled region whose accessible name is its header, so a screen reader user can navigate column by column.
- Every drag has a keyboard equivalent, and every move announces its outcome — the destination column and the card's position — through a polite live region.
- A drop that opens a dialog moves focus into the dialog and returns it to the card afterwards.
