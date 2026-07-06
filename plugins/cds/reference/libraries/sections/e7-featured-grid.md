---
kind: section
name: featured-grid
id: E7
family: editorial
aliases: [featured section, featured lead, lead grid]
status: stable
mode: deterministic
content_contract: {}
theme: editorial
composition_notes: []
---

# E7 — Featured grid

The featured-lead pattern of a resource-index page: one lead card beside a stacked column of secondary entries, on the 12-column grid.

## Slots

- `lead` — one editorial-featured-card Component (`libraries/components/editorial-featured-card.md`) spanning grid lines 1–9.
- `side-stack` — a vertical stack of secondary featured cards spanning grid lines 10–13.

## Determinations

- Lead occupies grid lines 1–9; the side stack occupies lines 10–13 (`foundations/layout.md` §11.6 grid).
- Below the tablet breakpoint the grid collapses to a single column: lead first, then the side stack.
- Card titles use the editorial Headline 4 role with an underline at 0.2em offset on hover; deks use Body 3 with the `.serif` modifier; date and category meta use Body 3 agate at `--text-tertiary`.
- Illustration tiles inside featured cards use saturated panel grounds; no photography on the lead card.
- Whole-card hover dims opacity over 200ms; cards fade on scroll into view.
