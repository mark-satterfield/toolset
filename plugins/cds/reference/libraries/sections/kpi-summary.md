---
kind: section
name: kpi-summary
aliases: [KPI row, KPI grid, stat row, metrics row, summary tiles]
status: stable
shape: stat-tile-grid
content_contract:
  metric_count: "number of metrics supplied (content-driven)"
  size_variant: "card | tile"
theme: default
composition_notes:
  - "Typical counts per host Page: app-dashboard 3 cards, app-analytics 4 tiles, app-overview-promo 2 tiles."
---

# KPI summary

A set of stat cards or tiles giving the at-a-glance state of the workspace. Each unit is the stat-card component (`libraries/components/`; one component, size variants):

- **Card** variant: small label + large primary metric + a right-side action ("Add funds" / "Setup") or a status microcopy.
- **Tile** variant: small label + metric + optional inline donut/sparkline glyph + a microcopy explainer beneath ("Usage can only be broken down by project.").

The number of units is content-driven — the section renders as many stat units as the content supplies. The section's layout is the stat-tile-grid Shape (`libraries/shapes/stat-tile-grid.md`).

## Determinations

- Zero state: metrics with no data render their zero value ("$0.00", "0", "0.0%") in the same layout — no separate empty plate at this level.
