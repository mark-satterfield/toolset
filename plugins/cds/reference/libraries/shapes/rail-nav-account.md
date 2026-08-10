---
kind: shape
name: rail-nav-account
page_family: app
aliases: [rail with account, unbranded sidebar with account, rows and account]
status: stable
slots:
  - { name: menu, required: true, accepts: [vertical-menu] }
  - { name: account, required: true, accepts: [account-row] }
variants: []
self_contained: false
content_defaults: {}
---

# rail-nav-account — Rows, account

A rail column holding a vertical menu from the block-start edge and an account row anchored at the block-end edge, with no brand mark. The arrangement an app Shell takes when the mark lives in the top-nav Section, so repeating it in the rail would be redundant.

## Determinations

- The rail is a flex column. `menu` starts at the column's block-start edge and owns its own items and their spacing.
- `account` anchors at the block-end edge via `margin-block-start: auto`, sitting below the rows however few of them there are.
- When the menu overflows the column, the menu scrolls and the account row holds its edge.
