---
kind: shape
name: chip-row
aliases: [chip strip, chip bar, horizontal chip row]
status: stable
slots:
  - { name: chips, required: true, accepts: [button] }
  - { name: icon-action, required: false, accepts: [button] }
variants: [with-icon-action, without-icon-action]
self_contained: false
content_defaults: {}
---

# chip-row — Horizontal chip row

A single horizontal row of compact chip buttons, left-aligned in reading order, with an optional icon-only chip pinned to the row's trailing edge.

```html
<section class="filter-strip">
  <button class="filter-chip">Group by <span>Model</span> ▾</button>
  <button class="filter-chip">Project <span>All</span> ▾</button>
  <button class="filter-chip">Model <span>All</span> ▾</button>
  <button class="filter-chip">Range <span>Month to date</span> ▾</button>
  <button class="filter-chip filter-chip--icon" aria-label="download">↓</button>
</section>
```

## Determinations

- The chips sit on one row in slot order; the optional icon-action chip is right-aligned at the row's trailing edge.
- Chips in the chips slot are dropdown triggers: each carries `aria-haspopup="menu"` and `aria-expanded`, and on click opens a single-select menu popover anchored beneath the chip.
- The icon-action chip is a direct action, not a popover trigger.
