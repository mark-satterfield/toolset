---
kind: section
name: illustration-tile
family: editorial
aliases: [featured illustration, article illustration, hero image tile]
status: stable
mode: deterministic
content_contract: {}
theme: editorial
composition_notes: ["the only saturated panel surface in an editorial-detail container"]
---

# Illustration tile

A tinted illustration tile between the article header and the body: a single full-width tile whose ground is a saturated panel color from the `panels` palette.

## Slots

- `illustration` — one illustration, centered on the tinted ground.

## Determinations

- The tile is the only saturated panel surface on the page; every other Section stays on the principal editorial theme.
- Corner radius is `--radius-lg`.
- Inner padding scales responsively from `--sp-6` down to `--sp-3` (calibrates to 96px at the reference viewport, 48px below the tablet breakpoint).
- Padding to the neighboring Sections is `--sp-3` (calibrates to 48px).
