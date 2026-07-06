---
kind: section
name: use-case-routing
id: T6
family: landing
aliases: [use cases, who it's for, personas, for teams, audience routing]
status: stable
mode: dynamic
content_contract:
  item_count: int
  taxonomy_type: "discipline | role | workload | surface | null"
  has_subitems_per_category: bool
theme: scheduled
composition_notes: []
---

# T6 — Use-Case Routing

Which audience, role, or job this is for. Each item is a category routing a visitor segment; a category may carry sub-items beneath it.

The shape pick branches on `item_count`, `taxonomy_type` (role/discipline tagging), and `has_subitems_per_category` via `rules/shape-selection/t6.md`.
