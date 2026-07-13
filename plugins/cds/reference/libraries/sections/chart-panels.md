---
kind: section
name: chart-panels
family: app
aliases: [chart panel, chart row, chart cards, time-series panel]
status: stable
mode: deterministic
content_contract:
  chart_count: "number of charts supplied (content-driven)"
  legend: "present | absent per chart"
theme: default
composition_notes:
  - "Typical counts per host container: app-analytics one full-width panel; app-overview-promo a pair of cards on the container's shared two-column track."
---

# Chart panels

One or more chart cards. Each card carries a heading ("Daily token cost", "Activity", "Usage"), a Y-axis with tick labels (monetary or count), an X-axis with date tick labels, an optional legend ("users · sessions"), and — when the series is empty — a centered "No data" plate over the static axes.

A single chart spans the full main width; multiple charts sit side by side in equal columns with a `--sp-1-5` gap.

## Determinations

- Empty vs. populated state: the chart axes, tick labels, and panel frame render in **both** states — only the plotted series differs. In the empty state the plot area shows a centered "No data" plate over the static axes; when data arrives the plate is removed and the series draws into the same axes (no relayout). Tick density stays constant.
