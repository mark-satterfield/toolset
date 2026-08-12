---
kind: shape
name: bar-mark-nav
aliases: [logo and menu, docs nav bar, branded nav without action, mark with menu]
status: stable
slots:
  - { name: mark, required: true, accepts: [logo] }
  - { name: nav, required: true, accepts: [horizontal-menu] }
sizing:
  mark: "height var(--topbar-logo-height); width auto — the mark's height in the bar, tracking var(--topbar-height) so the two scale together"
variants: []
self_contained: false
content_defaults: {}
---

# bar-mark-nav — Mark at the start, nav at the end

A single row holding the brand mark at the start and a nav cluster at the end, with no conversion action terminating it. The arrangement a surface takes when it offers a navigational set but asks for nothing.

## Determinations

- One flex row. The mark sits alone at the start; `nav` sits at the end via `margin-inline-start: auto`.
- The row must NOT use `justify-content: space-between` — the rule holds for every bar arrangement.
- The nav links are never centered.
- Below the tablet breakpoint (`foundations/responsive.md` §17.1) the nav cluster collapses into the mobile-drawer trigger (`libraries/components/mobile-drawer.md`), which takes the end of the row.

## Landmark consequence

A navigational slot is filled, so the receiving Section emits `<nav aria-label="primary">` wrapping `nav`, with the mark's link outside it (`libraries/sections/top-nav.md`, Accessibility).
