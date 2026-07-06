---
kind: section
name: filter-strip
id: AS5
family: app
aliases: [filter chip row, filter bar, query chips]
status: stable
mode: deterministic
content_contract:
  filters: "list of filter dimensions (label + current value each)"
  export_action: "present | absent"
theme: default
composition_notes: []
---

# AS5 — Filter strip

A horizontal row of filter chips at the top of a data screen — one chip per filter dimension ("Group by", "Project", "Model", "Range"), each showing its label and current value — with an optional right-aligned download glyph button.

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

- Filter chips are dropdown triggers: each carries `aria-haspopup="menu"` and `aria-expanded`, and on click opens a single-select menu popover anchored beneath the chip. Selecting a value updates the chip label and re-queries the data Sections downstream of the strip.
- The download chip is a direct action (exports the current view), not a popover trigger.
