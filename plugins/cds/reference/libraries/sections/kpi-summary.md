---
kind: section
name: kpi-summary
family: app
aliases: [KPI row, KPI grid, stat row, metrics row, summary tiles]
status: stable
mode: deterministic
content_contract:
  metric_count: "number of metrics supplied (content-driven)"
  size_variant: "card | tile"
theme: default
composition_notes:
  - "Typical counts per host container: app-dashboard 3 cards, app-analytics 4 tiles, app-overview-promo 2 tiles."
---

# KPI summary

A grid of stat cards or tiles giving the at-a-glance state of the workspace — one horizontal row, or a 2×2 grid when four units are supplied. Each unit is the stat-card component (`libraries/components/`; one component, size variants):

- **Card** variant: small label + large primary metric + a right-side action ("Add funds" / "Setup") or a status microcopy.
- **Tile** variant: small label + metric + optional inline donut/sparkline glyph + a microcopy explainer beneath ("Usage can only be broken down by project.").

The number of units is content-driven — the section renders as many stat units as the content supplies, in equal columns.

## Determinations

- Layout: one row of equal columns (`1fr` per unit) with a `--sp-1-5` gap. With exactly four units the section may instead arrange them as a 2×2 grid (two equal `1fr` columns, two rows, same `--sp-1-5` gap); the arrangement is content-count driven and both are valid for a four-unit set.
- Zero state: metrics with no data render their zero value ("$0.00", "0", "0.0%") in the same layout — no separate empty plate at this level.
