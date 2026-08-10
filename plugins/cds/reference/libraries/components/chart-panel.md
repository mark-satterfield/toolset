---
kind: component
name: chart-panel
page_family: app
aliases: [chart card, metric chart, graph panel, trend card, analytics card]
status: stable
slots:
  - { name: title, required: true, accepts: [text] }
  - { name: headline-value, required: false, accepts: [text] }
  - { name: plot, required: true, accepts: [chart] }
  - { name: legend, required: false, accepts: [text] }
  - { name: equivalent-data, required: true, accepts: [data-table] }
sizing:
  padding: "--sp-1"
  radius: "--radius-lg"
  plot-aspect: "the panel names the plot's aspect; the plot never sizes itself from its data"
  stack-gap: "--sp-0-75 between the title block, the plot, and the legend"
behavior:
  - "static at rest; a plotted point may reveal its value on hover and on focus, never on hover alone"
  - "the equivalent data is reachable from the panel at all times, not only when the chart fails"
accessibility:
  - "every chart has an equivalent tabular form reachable from the same panel — a chart is a rendering of data, never the only copy of it"
  - "series are distinguished by shape, pattern, or direct label as well as by colour"
  - "the plot carries a text description of what it shows and what it trends toward"
token_bindings: [--surface-raised, --border-subtle, --text-primary, --text-secondary, --text-tertiary, --radius-lg, --focus-ring, --sp-0-75, --sp-1]
composite: true
---

# Chart panel

One measure, plotted: a title, the headline figure, the plot, and — always — the same data in a form that can be read without seeing the plot.

## The equivalent data is part of the component

Every chart panel carries its data in tabular form, reachable from the panel through a disclosure or a link. This is not a fallback for when the chart fails to render. It is the second, equal presentation of the same numbers, for a reader who cannot see the plot, who needs exact values rather than a trend, or who wants to copy them.

A panel without it presents data that some readers simply cannot reach, and no amount of description substitutes for the numbers.

## Colour is never the only difference between series

Series are distinguished by **shape** (marker form, line dash pattern, fill hatch) or by **direct labelling** at the series' end, with colour as reinforcement. A legend that maps colours to names requires the reader to hold the mapping while scanning, and fails entirely for a reader who cannot separate the colours (WCAG 1.4.1).

Direct labelling is preferred over a legend wherever the plot has room for it, because it removes the mapping step for every reader.

## Variants

- `plot-kind`: `trend` (a line over time) | `distribution` (a spread across buckets) | `comparison` (a value per category) | `composition` (parts of a total).
- `headline-value`: `present` (default) | `absent` — a panel whose plot is the whole point.
- `equivalent-data`: `inline` (a disclosure beneath the plot) | `linked` (a control opening it in a dialog or drawer).

## Determinations

- Ground `var(--surface-raised)`, `1px solid var(--border-subtle)`, `var(--radius-lg)`, padding `var(--sp-1)`.
- Title at the compact body size, weight 700, in `var(--text-primary)`. The headline value sits beneath it at the display-small role with tabular figures.
- The plot takes the aspect the panel names — it never derives its height from its data, or a sparse series and a dense one produce panels of different heights in the same row.
- Axis labels and tick text at the caption size in `var(--text-tertiary)`; the plot's own ink and grid stay quieter than the data drawn on them.
- A point's exact value is revealed on hover and on `:focus-visible`, through a tooltip (`libraries/components/tooltip.md`). Hover alone would put the values out of reach of a keyboard.
- The legend, when present, sits beneath the plot rather than beside it, so the plot keeps the panel's full width.
- An empty series renders the empty state Component (`libraries/components/empty-state-card.md`) inside the plot's own box, so the panel keeps its height in a row of peers.

## Accessibility

- The equivalent data is a data-table (`libraries/components/data-table.md`) carrying the same values, reachable from the panel at all times.
- The plot carries a text description naming what it shows, its range, and its overall direction — the sentence a sighted reader would take from a glance.
- Series identity is carried by shape or direct label as well as colour (WCAG 1.4.1).
- Interactive points are reachable by keyboard in series order.
- Focus paints the foundation ring on `:focus-visible` (`foundations/accessibility.md` §18.2).
