---
kind: section
name: filter-strip
page_family: app
aliases: [filter chip row, filter bar, query chips]
status: stable
shape: chip-row
content_contract:
  filters: "list of filter dimensions (label + current value each)"
  export_action: "present | absent"
theme: default
composition_notes: []
---

# Filter strip

A row of filter chips at the top of a data screen — one chip per filter dimension ("Group by", "Project", "Model", "Range"), each showing its label and current value — with an optional download action. Its layout is the chip-row Shape (`libraries/shapes/chip-row.md`): each filter dimension fills a chip in the chips slot, and the export action, when present, fills the icon-action slot.

## Determinations

- Selecting a value from a chip's menu updates the chip's label and re-queries the data Sections downstream of the strip.
- The download chip exports the current view.
