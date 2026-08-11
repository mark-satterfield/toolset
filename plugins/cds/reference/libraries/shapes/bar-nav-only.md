---
kind: shape
name: bar-nav-only
aliases: [menu-only bar, nav without logo, unbranded header, section nav bar]
status: stable
slots:
  - { name: nav, required: true, accepts: [horizontal-menu] }
variants: [start-aligned, end-aligned]
self_contained: false
content_defaults: {}
---

# bar-nav-only — Bar carrying a nav cluster and no mark

A single row holding a nav cluster and nothing else. The arrangement a surface takes when the brand is already established elsewhere in the frame — a rail carrying the mark, or a nested surface below a branded bar — so repeating it in the row would be redundant.

## Determinations

- One flex row holding the `nav` cluster. The `start-aligned` variant anchors it at the start of the row; the `end-aligned` variant anchors it at the end.
- The row must NOT use `justify-content: space-between` — with a single cluster there is nothing to distribute, and the rule holds for every bar arrangement.
- Below the tablet breakpoint (`foundations/responsive.md` §17.1) the cluster collapses into the mobile-drawer trigger (`libraries/components/mobile-drawer.md`).

## Landmark consequence

A navigational slot is filled, so the receiving Section emits `<nav aria-label="primary">` wrapping the cluster (`libraries/sections/top-nav.md`, Accessibility). With no mark slot filled, the bar exposes no home link — the frame must offer one elsewhere.
