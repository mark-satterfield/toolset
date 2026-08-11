---
kind: shape
name: rail-mark-nav-account
aliases: [branded rail, rail with logo and account, app sidebar with brand]
status: stable
slots:
  - { name: mark, required: true, accepts: [logo] }
  - { name: menu, required: true, accepts: [vertical-menu] }
  - { name: account, required: true, accepts: [account-row] }
variants: []
self_contained: false
content_defaults: {}
---

# rail-mark-nav-account — Mark, rows, account

A rail column holding the brand mark at the block-start edge, a vertical menu beneath it, and an account row anchored at the block-end edge. The arrangement an app Shell takes when the rail carries the brand, so the frame needs no top bar.

## Determinations

- The rail is a flex column. `mark` sits first, at the column's block-start edge and the rail's inline-start.
- `menu` follows the mark — one vertical-menu Component, which owns its own items.
- `account` anchors at the block-end edge via `margin-block-start: auto`, sitting below the rows however few of them there are.
- The gap between the mark and the menu is `--sp-1`; the menu supplies its own internal item spacing.
- When the menu overflows the column, the menu scrolls and both the mark and the account row hold their edges.
