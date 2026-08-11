---
kind: shape
name: bar-nav-cta
aliases: [menu and button, unbranded nav with action, nested surface nav]
status: stable
slots:
  - { name: nav, required: true, accepts: [horizontal-menu] }
  - { name: cta, required: true, accepts: [tertiary-link, primary-button] }
variants: [start-aligned, end-aligned]
self_contained: false
content_defaults: {}
---

# bar-nav-cta — Nav and action, no mark

A single row holding a nav cluster and one or two conversion actions, with no brand mark. The arrangement a surface takes when the brand is already established elsewhere in the frame — a rail carrying the mark, or a bar above this one — so repeating it in the row would be redundant.

## Determinations

- One flex row holding `nav` and `cta` as one group. The `start-aligned` variant anchors the group at the start of the row; the `end-aligned` variant anchors it at the end via `margin-inline-start: auto`.
- The row must NOT use `justify-content: space-between`: that separates the nav cluster from the action it belongs with.
- `nav` precedes `cta` in source and visual order, so the conversion action terminates the group.
- Below the tablet breakpoint (`foundations/responsive.md` §17.1) the nav cluster collapses into the mobile-drawer trigger (`libraries/components/mobile-drawer.md`); the conversion action stays visible in the row, to the trigger's inline-start (§17.4).

## Landmark consequence

Both navigational slots are filled, so the receiving Section emits `<nav aria-label="primary">` wrapping `nav` and `cta` (`libraries/sections/top-nav.md`, Accessibility). With no mark slot filled, the bar exposes no home link — the frame must offer one elsewhere.
