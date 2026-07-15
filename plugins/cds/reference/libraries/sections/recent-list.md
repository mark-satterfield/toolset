---
kind: section
name: recent-list
page_family: app
aliases: [recently created, recent items card, recent activity list]
status: stable
shape: list-empty-state
content_contract:
  item_count: "number of recent items (content-driven; zero triggers the empty state)"
theme: default
composition_notes: []
---

# Recent list

A single full-width "Recently created" card listing the workspace's most recent items. Its layout is the list-empty-state Shape (`libraries/shapes/list-empty-state.md`): a header, a column-header strip, and rows beneath it once items exist.

## Content

- The card lists the workspace's most recent items, newest first.
- When the workspace has no items yet (`item_count` is zero), the card renders its empty state: a centered icon, a one-line helper text, and a primary CTA — the empty state is the screen's next-action affordance.
