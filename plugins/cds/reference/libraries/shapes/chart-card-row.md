---
kind: shape
name: chart-card-row
aliases: [chart row, chart card columns, panel row]
status: stable
slots:
  - { name: charts, required: true, accepts: [chart-card] }
variants: []
self_contained: false
content_defaults: {}
---

# chart-card-row — Chart cards in a row

One or more chart cards side by side. A single card spans the full width of the vacant space; multiple cards sit in equal columns.

## Determinations

- One row of equal columns (`1fr` per card) with a `--sp-1-5` gap. The column count is content-driven — one column per supplied chart card; a single card takes the full width of the vacant space.
