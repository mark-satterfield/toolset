---
kind: component
name: editorial-featured-card
page_family: editorial
aliases: [featured card, editorial card, illustration card]
status: stable
slots:
  - { name: illustration-tile, required: true, accepts: [tinted-svg-tile] }
  - { name: title, required: true, accepts: [heading] }
  - { name: dek, required: true, accepts: [text] }
  - { name: date, required: true, accepts: [text] }
sizing:
  tile_aspect_ratio: "1:1 for side items; 16:9 for the lead item"
  svg_padding: "48–64px around the centered SVG"
  bottom_border: "editorial hairline at the 0.5px weight step: 1px solid --border-subtle alpha-thinned per layout.md §11.9 (calibrates to a 0.5px-weight hairline)"
behavior: [hover-dim]
accessibility: []
token_bindings:
  - --text-primary
  - --tile-ground-1
  - --tile-ground-2
  - --tile-ground-3
composite: false
---

# Editorial featured card

A featured editorial item — a tinted illustration tile paired with title, dek, and date.

## Determinations

- Tile aspect-ratio 1:1 for side items, 16:9 for the lead item. The SVG is centered with `padding: 48–64px`.
- Title underline at 0.2em offset. Bottom border is the editorial side-item hairline at the 0.5px weight step of `foundations/layout.md` §11.9: painted as `1px solid var(--border-subtle)` with the ink alpha-thinned to the 0.15–0.3 band (calibrates to the 0.5px-weight hairline; browsers paint the alpha-thinned 1px more consistently than a literal sub-pixel border).
- The saturated panel ground binds to a feature-tile ground role (`--tile-ground-1` / `--tile-ground-2` / `--tile-ground-3`, `from_palette: panels`) — pick a ground number per the applicable rules, never a color. The number space is open: `tile-ground-1..N` are valid as declared in the YAML, emitted as `.feature-tile--N`.

## Behavior

- Whole-card opacity dims to 0.6 on hover over 200ms.

## Lead-vs-side selection

The first item in the collection renders as the `lead` (16:9 tile, larger title scale); every subsequent item renders as a `side` item (1:1 tile). When a section shows a single item, it always uses the `lead` treatment.
