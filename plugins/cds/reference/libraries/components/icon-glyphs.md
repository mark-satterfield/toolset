---
kind: component
name: icon-glyphs
family: shared
aliases: [icon, glyph, system icon, ui glyph]
status: stable
slots: []
sizing:
  drawing_grid: "--icon-viewbox-md (20) — the default glyph grid; every glyph is authored on viewBox=\"0 0 20 20\""
  container: "--icon-size-inline | --icon-size-marginalia | --icon-size-feature | --icon-size-button per placement (foundations/imagery.md icon scale)"
behavior: []
accessibility:
  - "decorative glyph carries aria-hidden=\"true\"; a glyph that is the sole content of a control takes its name from the control's aria-label (libraries/components/button.md)"
  - "recolors with the surrounding theme through currentColor; no glyph names a swatch"
token_bindings:
  - --text-tertiary
shell_component: false
composite: false
content_defaults: {}
---

# icon-glyphs

The system's deterministic, license-clean glyph set — the first source the artwork resolution order (`artwork.md`) consults for a needed icon or button glyph. Each glyph is one inline SVG authored on the `--icon-viewbox-md` (20) drawing grid, drawn as filled shapes with `fill="currentColor"` on every inner path and `fill="none"` on the outer `<svg>`, per the icon rules in `foundations/imagery.md`. A glyph inherits `--text-tertiary` by default and recolors with its theme; the rendered container size comes from the placement's `--icon-size-*` token, never from a width baked into the markup.

## Glyphs

### arrow-right

```html
<svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path fill="currentColor" d="M3 9 H12 V6 L17 10 L12 14 V11 H3 Z"/></svg>
```

### arrow-left

```html
<svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path fill="currentColor" d="M17 9 H8 V6 L3 10 L8 14 V11 H17 Z"/></svg>
```

### chevron-down

```html
<svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path fill="currentColor" d="M3.5 7 L10 13.5 L16.5 7 L16.5 8.9 L10 15.4 L3.5 8.9 Z"/></svg>
```

### chevron-right

```html
<svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path fill="currentColor" d="M7 3.5 L13.5 10 L7 16.5 L8.9 16.5 L15.4 10 L8.9 3.5 Z"/></svg>
```

### check

```html
<svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path fill="currentColor" d="M7.5 13.5 L4 10 L2.6 11.4 L7.5 16.3 L17.4 6.4 L16 5 Z"/></svg>
```

### close

```html
<svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path fill="currentColor" d="M6.4 5 L10 8.6 L13.6 5 L15 6.4 L11.4 10 L15 13.6 L13.6 15 L10 11.4 L6.4 15 L5 13.6 L8.6 10 L5 6.4 Z"/></svg>
```

### search

```html
<svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path fill="currentColor" fill-rule="evenodd" d="M8.5 2.5 A6 6 0 1 0 8.5 14.5 A6 6 0 1 0 8.5 2.5 Z M8.5 4.5 A4 4 0 1 1 8.5 12.5 A4 4 0 1 1 8.5 4.5 Z M13.2 12.8 L17.5 17.1 L16.1 18.5 L11.8 14.2 Z"/></svg>
```

### menu

```html
<svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path fill="currentColor" d="M3 5 H17 V7 H3 Z M3 9 H17 V11 H3 Z M3 13 H17 V15 H3 Z"/></svg>
```

### copy

```html
<svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path fill="currentColor" fill-rule="evenodd" d="M7 6 H17 V17 H7 Z M9 8 V15 H15 V8 Z"/><path fill="currentColor" d="M4 3 H13 V5 H6 V13 H4 Z"/></svg>
```

### external-link

```html
<svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path fill="currentColor" fill-rule="evenodd" d="M3 8 H11 V17 H3 Z M5 10 V15 H9 V10 Z"/><path fill="currentColor" d="M11 3 H17 V9 H15 V6.4 L10.4 11 L9 9.6 L13.6 5 H11 Z"/></svg>
```

### plus

```html
<svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path fill="currentColor" d="M9 3 H11 V9 H17 V11 H11 V17 H9 V11 H3 V9 H9 Z"/></svg>
```

### minus

```html
<svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path fill="currentColor" d="M3 9 H17 V11 H3 Z"/></svg>
```

### info

```html
<svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path fill="currentColor" fill-rule="evenodd" d="M10 3 A7 7 0 1 0 10 17 A7 7 0 1 0 10 3 Z M8.9 6.2 A1.1 1.1 0 1 1 11.1 6.2 A1.1 1.1 0 1 1 8.9 6.2 Z M9 9.5 H11 V14.5 H9 Z"/></svg>
```

### warning

```html
<svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path fill="currentColor" fill-rule="evenodd" d="M10 3 L18 16.5 H2 Z M9 8 H11 V12.5 H9 Z M9 13.8 H11 V15.8 H9 Z"/></svg>
```

### play

```html
<svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path fill="currentColor" d="M6 4 L16 10 L6 16 Z"/></svg>
```

### download

```html
<svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path fill="currentColor" d="M9 3 H11 V9 H14 L10 13.5 L6 9 H9 Z M4 15 H16 V17 H4 Z"/></svg>
```

## Determinations

- Every glyph is authored on the `--icon-viewbox-md` (20) grid: `viewBox="0 0 20 20"`. The outer `<svg>` sets `fill="none"`; every inner `<path>` sets `fill="currentColor"`, so a glyph takes its ink from the surrounding text color and recolors with the active theme.
- Glyphs with a knockout — `search`, `copy`, `external-link`, `info`, `warning` — carry `fill-rule="evenodd"` so the interior counter reads as negative space.
- The markup names no width or height. The rendered container size is the placement's `--icon-size-*` token (`--icon-size-inline`, `--icon-size-marginalia`, `--icon-size-feature`, `--icon-size-button`); the glyph scales to fill it.
- A decorative glyph carries `aria-hidden="true"`. When a glyph is the sole content of a control, the control supplies the accessible name through its `aria-label` and the glyph stays `aria-hidden` (`libraries/components/button.md`).
