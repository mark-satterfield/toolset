---
kind: component
name: stat-card
aliases: [stat card, application stat card, stat tile, KPI card, metric card]
status: stable
slots:
  - { name: label, required: true, accepts: [caption] }
  - { name: value, required: false, accepts: [display-number, text] }
  - { name: glyph, required: false, accepts: [filled-donut, dashed-disc, sparkline, status-badge, em-dash] }
  - { name: action, required: false, accepts: [tertiary-button, kebab-menu, link] }
  - { name: microcopy, required: false, accepts: [caption] }
sizing:
  width: "row-derived: flex-1 within the peer row, growing to a max-width cap (calibrates to 500px)"
  height: "content-derived from the slot stack and --sp-1 padding"
  radius: "--radius-md (12px)"
  row_gap: "--sp-1 between peer tiles"
  internal_gap: "component geometry (calibrates to 48px, large-horizontal) | --sp-0-5 (small-vertical)"
  padding: "--sp-1 (large-horizontal) | --sp-1 vertical only (small-vertical)"
behavior: [non-interactive-frame]
accessibility: [article-element, glyph-aria-hidden]
token_bindings:
  - --surface-raised
  - --text-primary
  - --text-tertiary
composite: false
---

# Stat card

An in-app KPI / metric card: a label (caption), an optional display value, an optional glyph that visualizes the value's state, and an optional inline action. One component with two size variants sharing a single frame contract.

## Size variants

- `large-horizontal` (KPI row): `display: inline-flex; flex-direction: row; align-items: center`; gap is component geometry (calibrates to 48px); `padding: var(--sp-1); border: 0; border-radius: var(--radius-md); box-shadow: none`. Carries the display number treatment: 32–40px Primary Sans at weight 600–700, with the caption beside it.
- `small-vertical` (status/progress row): `display: inline-flex; flex-direction: column; gap: var(--sp-0-5); padding: var(--sp-1) 0` (vertical only); same border, radius, and shadow contract. Optimized for status-or-progress rendering — label + glyph + optional microcopy caption.

The two variants differ only in flex-direction, gap, and padding.

## Determinations

- **Frame width is row-derived, not fixed.** Peer tiles sit in a row container (`display: flex; gap: var(--sp-1)`); each tile is `flex-1`, growing up to a max-width cap (calibrates to 500px). Calibrates to 254×176px for the large-horizontal variant (242×176 when peer tile widths shrink to fit the row) and 210×144px for the small-vertical variant at the reference viewport.
- Ground: `var(--surface-raised)` — theme-context dependent. In a dark sub-section the role resolves to a near-black surface; on a light page main the same role resolves to a light surface. There is no separate `deep` wrapper attribute around these tiles; the dark rendering is the natural resolution of `--surface-raised` at this nesting depth in the active theme context.
- Border: none — the tile relies on background contrast against the page ground, not a hairline.
- Border-radius: `var(--radius-md)` (12px, `foundations/layout.md` §11.7).

## Slots in detail

- `label`: the tile caption, in `--text-tertiary`.
- `value`: the primary value when one exists; in the large-horizontal variant it is the 32–40px display number in `--text-primary`.
- `glyph`: one of a filled donut for progress (arc length = percent complete), a dashed disc for "no data", a sparkline for trended values, a status badge (`libraries/components/status-badge.md`) for state labels, or an em-dash placeholder for an absent value. When the glyph renders a status badge, it inherits that component's status → color mapping (per-state status grounds and paired ink roles).
- `action`: an inline "Set up" / "Try a prompt" / "Add funds" affordance. The inline action is a tertiary button (`libraries/components/button.md`) — the quietest affordance, so it sits beside the value without competing for emphasis. When the action is a per-tile overflow menu, use the kebab menu (`libraries/components/kebab-menu.md`) instead.
- `microcopy`: an optional caption line below the glyph in the small-vertical variant.

## State prop

`state`: `populated` | `empty` | `setup-required`. The state → glyph mapping: `populated` → donut/sparkline/value; `empty` → dashed disc or em-dash; `setup-required` → status badge plus inline action.

## Behavior

The tile frame is not interactive (no hover/focus/click handlers on the tile itself). Inline `action` controls carry their own interaction contracts.

## Accessibility

- The tile is a non-interactive `<article>`; inline actions follow the button accessibility contracts.
- The glyph SVG carries `aria-hidden="true"` — the label + value carry the semantic content.

## Structural skeleton

```html
<!-- large-horizontal variant -->
<article class="stat-card stat-card--large-horizontal">
  <span class="stat-card__label-value"><!-- label + optional primary value --></span>
  <span class="stat-card__glyph" aria-hidden="true"><!-- donut, status badge, em-dash, or sparkline --></span>
</article>

<!-- small-vertical variant -->
<article class="stat-card stat-card--small-vertical">
  <span class="stat-card__label"><!-- label, optionally with trailing ⓘ info button --></span>
  <span class="stat-card__glyph" aria-hidden="true"><!-- donut, status badge, em-dash --></span>
  <span class="stat-card__microcopy"><!-- optional caption --></span>
</article>
```
