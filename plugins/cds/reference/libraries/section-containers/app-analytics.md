---
kind: section-container
name: app-analytics
family: app
aliases: [analytics screen, usage analytics, cost analytics, reporting view]
status: stable
default_shell: A1
sections:
  - { id: AS5, required: true }
  - { id: AS2, required: true, notes: "tile size variant; typical content: 4 stat tiles, arranged as one row or a 2×2 grid (AS2's content-count-driven arrangement)" }
  - { id: AS6, required: true, notes: "typical content: one full-width time-series panel" }
constraints: []
register:
  motion_register: application-shell
---

# App analytics

An analytics screen combining filter narrowing with summary tiles and a time-series chart: a filter chip strip at top, a stat-tile grid below it (one row or 2×2, per AS2's arrangement), then a tall chart panel spanning the full main width. Fills the main pane of an app Shell (default A1).

Suits cost analytics, usage analytics, and performance analytics — any screen where the user narrows a data set with filters and reads the result as tiles plus a chart.

## Determinations

- On first run (no data yet) every data-bearing Section renders its zero state: tiles show zero-valued metrics, the chart panel shows its "No data" plate. Selecting a filter value re-queries both the tiles and the chart.
