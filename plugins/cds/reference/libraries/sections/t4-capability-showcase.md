---
kind: section
name: capability-showcase
id: T4
family: landing
aliases: [features, feature grid, capabilities, what it does, feature showcase]
status: stable
mode: dynamic
content_contract:
  item_count: int
  has_visual_per_item: bool
  copy_density_per_item: "short | medium | long"
  taxonomy_type: "discipline | role | workload | surface | null"
theme: scheduled
composition_notes: []
---

# T4 — Capability Showcase

What the product can do: features, surfaces, tools. The section type with the widest shape range in the landing family — the pick tracks how many capabilities there are, how visual each one is, and how much copy each carries.

The shape pick branches on `item_count`, `has_visual_per_item`, `copy_density_per_item`, and `taxonomy_type` (a non-null taxonomy with no visuals marks the items as categorical pills) via `rules/shape-selection/t4.md`.
