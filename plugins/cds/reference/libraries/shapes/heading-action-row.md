---
kind: shape
name: heading-action-row
aliases: [page heading row, title with actions, heading with right cluster]
status: stable
slots:
  - { name: heading, required: true, accepts: [h1] }
  - { name: subhead, required: false, accepts: [text] }
  - { name: right-cluster, required: false, accepts: [actions, period-picker] }
variants: []
self_contained: false
content_defaults: {}
---

# heading-action-row — Heading beside a right-aligned control cluster

A single full-width row at the top of the vacant space: a heading block anchored to the left edge and an optional cluster of controls right-aligned on the same row, the two ends pushed apart across the Section's content width (`display: flex`, `justify-content: space-between`).

## Layout

- **Heading block.** An `<h1>` at the row's left edge; when a subhead is present it stacks as a one-line paragraph directly beneath the `<h1>` inside the heading block.
- **Right cluster.** A horizontal group of controls (action links/buttons or a period picker) laid out inline with a `--sp-0-5` gap between controls, aligned to the vertical center of the `<h1>` row — a subhead does not shift it.

## Determinations

- The right cluster centers vertically against the `<h1>` line, not against the heading block's full height.
- The heading block takes the remaining row width; the right cluster sizes to its content and never wraps beneath the heading.
