---
kind: shape
name: stat-tile-grid
aliases: [stat row, metric tile row, tile grid, kpi grid]
status: stable
slots:
  - { name: stats, required: true, accepts: [stat-card] }
variants: [single-row, two-by-two]
self_contained: false
content_defaults: {}
---

# stat-tile-grid — Stat tiles in a row or grid

Stat units arranged as one horizontal row of equal columns, or as a 2×2 grid when four units are supplied.

## Determinations

- Layout: one row of equal columns (`1fr` per unit) with a `--sp-1-5` gap. With exactly four units the arrangement may instead be a 2×2 grid (two equal `1fr` columns, two rows, same `--sp-1-5` gap); the arrangement is content-count driven and both are valid for a four-unit set.
- The column count is content-driven — one column per supplied unit.
