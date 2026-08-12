---
kind: shape
name: bar-mark-nav-cta
aliases: [full top nav, marketing nav bar, logo menu and button, standard site header]
status: stable
slots:
  - { name: mark, required: true, accepts: [logo] }
  - { name: nav, required: true, accepts: [horizontal-menu] }
  - { name: cta, required: true, accepts: [tertiary-link, primary-button] }
sizing:
  mark: "height var(--topbar-logo-height); width auto — the mark's height in the bar, tracking var(--topbar-height) so the two scale together"
variants: []
self_contained: false
content_defaults: {}
---

# bar-mark-nav-cta — Mark at the start, nav and CTA grouped at the end

A single row holding the brand mark at the start and a nav cluster plus one or two conversion actions grouped together at the end. The arrangement a marketing surface takes when it offers both a navigational set and a conversion action.

## Determinations

- One flex row. The mark sits alone at the start; `nav` and `cta` group together at the end — `margin-inline-start: auto` on the group, or `justify-content: flex-end` after the mark.
- The row must NOT use `justify-content: space-between`: that strands the nav cluster in the middle of the row, detached from both the mark and the CTA.
- The nav links are never centered.
- `nav` precedes `cta` in source and visual order, so the conversion action terminates the row.
- Below the tablet breakpoint (`foundations/responsive.md` §17.1) the nav cluster collapses into the mobile-drawer trigger (`libraries/components/mobile-drawer.md`); the conversion action stays visible in the row, to the trigger's inline-start (§17.4).

## Landmark consequence

Both navigational slots are filled, so the receiving Section emits `<nav aria-label="primary">` wrapping `nav` and `cta`, with the mark's link outside it (`libraries/sections/top-nav.md`, Accessibility).
