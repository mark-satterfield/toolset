---
kind: shape
name: rail-nav-only
page_family: app
aliases: [bare rail, rows-only sidebar, minimal rail]
status: stable
slots:
  - { name: menu, required: true, accepts: [vertical-menu] }
variants: []
self_contained: false
content_defaults: {}
---

# rail-nav-only — Rows alone

A rail column holding one vertical menu and nothing else. The arrangement a rail takes when the brand and the account live elsewhere in the frame — a top bar carrying the mark, an account menu in a header — so repeating either in the rail would be redundant.

## Determinations

- The rail is a flex column holding one `menu`, starting at the column's block-start edge. The menu owns its own items and their spacing.
- When the menu overflows the column, the menu scrolls.
- Nothing anchors to the block-end edge; a rail that needs an anchored piece is a different arrangement.
