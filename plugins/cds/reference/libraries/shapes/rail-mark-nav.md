---
kind: shape
name: rail-mark-nav
aliases: [branded rail without account, rail with logo, app sidebar with brand only]
status: stable
slots:
  - { name: mark, required: true, accepts: [logo] }
  - { name: menu, required: true, accepts: [vertical-menu] }
variants: []
self_contained: false
content_defaults: {}
---

# rail-mark-nav — Mark, rows

A rail column holding the brand mark at the block-start edge and a vertical menu beneath it, with nothing anchored at the block-end edge. The arrangement an app Shell takes when the rail carries the brand and the account affordance lives elsewhere in the frame.

## Determinations

- The rail is a flex column. `mark` sits first, at the column's block-start edge and the rail's inline-start.
- `menu` follows the mark — one vertical-menu Component, which owns its own items.
- The gap between the mark and the menu is `--sp-1`; the menu supplies its own internal item spacing.
- Nothing anchors to the block-end edge; a rail that needs an anchored piece is a different arrangement.
- When the menu overflows the column, the menu scrolls and the mark holds its edge.
