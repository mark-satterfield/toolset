---
kind: component
name: topbar
page_family: shared
aliases: [nav, nav bar, top nav, menu bar, header nav, site header]
status: stable
shell_component: true
composite: false
slots:
  - { name: logo, required: true, accepts: [svg-glyph, asset-pair] }
  - { name: primary-nav, required: true, accepts: [nav-link, dropdown-trigger] }
  - { name: conversion-cta, required: true, accepts: [tertiary-link, primary-button] }
sizing:
  height: "var(--topbar-height) — geometry.components.topbar.height; calibrates to 84px at the desktop reference viewport, with a narrow-viewport floor (calibrates to 64px below 480px) declared as the token's mobile_floor"
  logo-height: "var(--topbar-logo-height) — geometry.components.topbar.logo-height; tracks var(--topbar-height) so the logo scales with the bar; calibrates to 40px at the 84px reference bar height"
  action-height: "var(--topbar-action-height) — derived from var(--topbar-height); calibrates to 36px at the 84px reference bar height"
behavior:
  - "static at rest; primary-action button uses the page-wide primary button vocabulary"
  - "caret-flush variant applies asymmetric radius when the CTA abuts a dropdown caret"
accessibility:
  - "landmark: <header role=\"banner\"> containing <nav aria-label=\"primary\">; logo link outside the inner nav"
  - "keyboard: sequential Tab order (logo, nav links, CTAs); no arrow-key menubar semantics at the top level"
  - "logo paints via currentColor so contrast inherits from --text-primary"
token_bindings: [--nav-bg, --text-primary, --topbar-height, --topbar-logo-height, --topbar-action-height, --radius-sm]
---

# Topbar

A fixed-position desktop bar that anchors global navigation and conversion CTAs without painting a visible boundary. It realizes the Shell's top-nav Section: it frames the content region and does not participate in the Page's ground alternation.

## Slots

- **logo** — by default a single SVG glyph rendered at `var(--topbar-logo-height)`, vertically centered, painting via `fill="currentColor"` so it inherits `--text-primary` and recolors with the theme. A multi-color brand mark MAY instead declare an `assets.logo` light/dark image pair (`mode: asset-pair`): the topbar emits both images and the active one is selected by color-mode in CSS (no JS), each still rendered at `var(--topbar-logo-height)`. Either way the design system owns the logo height — a composed page never hardcodes it, and a page-block `<style>` re-declaring the logo height is an audit violation.
- **primary-nav** — required cluster of nav items, right-aligned. Each item is either a plain nav link or a dropdown trigger that opens a dropdown-panel component — a trigger carries `aria-haspopup="menu"` and `aria-expanded`, and its panel carries `role="menu"`. A nav item with children renders as a dropdown-panel trigger + panel (flat / mega / lift-and-scale), not a bare link; the panel structure, variants, and keyboard contract live in `components/dropdown-panel.md`.
- **conversion-cta** — 1–2 right-aligned conversion actions, typically a tertiary text link followed by a filled primary button.

## Variants

- `cta-adjacency`: `standalone` (default) | `caret-flush` — asymmetric radius `var(--radius-sm) 0 0 var(--radius-sm)` (left-rounded only) so the button's right edge meets an adjacent dropdown caret cleanly.

## Determinations

- `position: fixed; top: 0; z-index: 100`.
- Background = `--nav-bg`, the topbar's dedicated navigation-ground role (a `from_palette: backgrounds` component role). It is bound per theme to the same ground as the section directly beneath it — the page ground, `--surface-primary` — so the nav blends seamlessly into the first section with no seam. The topbar has no standalone color of its own.
- Height = `var(--topbar-height)`. The narrow-viewport floor is the token's `mobile_floor`, emitted by re-declaring `--topbar-height` at `:root` inside `@media (max-width: 480px)`; `.topbar { height: var(--topbar-height) }` inherits it. Topbar height is a single value across every surface within a build.
- Logo sizing: `.topbar-logo` (and its `img` / inline `svg`) renders at `height: var(--topbar-logo-height); width: auto`, vertically centered. Both the bar and the logo resolve from system tokens, so the logo scales with the bar.
- No bottom border. No drop shadow. The nav blends into the page ground.
- Layout — logo left, nav + CTA right. The bar is a single flex row: the logo sits alone at the start (left); the primary-nav cluster and the conversion-cta are grouped together at the end (right) — e.g. `margin-inline-start: auto` on the nav group (or `justify-content: flex-end` after the logo). The nav links are never centered, and the row must NOT use `justify-content: space-between` — that strands the nav in the middle.
- Nav-link type at the small-body sans size (15px), weight 400.
- Primary-action button: `var(--topbar-action-height)` tall, mapped primary fill, mapped inverse text, radius `var(--radius-sm)` (calibrates to the captured 8–10px range).

## Accessibility

- Landmark contract: the topbar host element is a `<header role="banner">` containing a `<nav aria-label="primary">` that wraps `primary-nav` and `conversion-cta`. The logo link sits outside the inner nav so the nav lists only navigational and conversion controls. (WAI-ARIA landmark guidance.)
- Keyboard contract: Tab visits the logo, each primary-nav link in source order, then each conversion CTA in source order. Shift+Tab reverses. Nav links and CTAs use the default semantics of `<a>` (Enter activates) and `<button>` (Enter + Space activate). No arrow-key navigation between top-level nav links — the topbar is not a `role="menubar"`; arrow-key cycling is reserved for the dropdown panels that descend from each trigger.
- Conversion CTAs follow the primary button focus contract.
