---
kind: section
name: recent-list
family: app
aliases: [recently created, recent items card, recent activity list]
status: stable
mode: deterministic
content_contract:
  item_count: "number of recent items (content-driven; zero triggers the empty state)"
theme: default
composition_notes: []
---

# Recent list

A single full-width "Recently created" card listing the workspace's most recent items. When the workspace has no items yet, the card renders its empty state: a centered icon, a one-line helper text, and a primary CTA — the empty state is the screen's next-action affordance.
