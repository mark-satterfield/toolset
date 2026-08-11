---
kind: component
name: mobile-drawer
aliases: [hamburger menu, mobile nav, mobile menu, nav drawer, drawer]
status: stable
composite: false
slots:
  - { name: hamburger, required: true, accepts: [button] }
  - { name: drawer, required: true, accepts: [nav-link-list] }
  - { name: item, required: true, accepts: [nav-link] }
sizing:
  drawer: "position: fixed; inset: 0; z-index: 101 — full viewport"
  hamburger: "40×40px button; 16×1px top line and 8×1px bottom line in currentColor"
  scroll-mask-inset: "var(--container-margin) — the side-gutter clamp"
behavior:
  - "opens with clip-path inset(0 0 100%) → inset(0 0 0%) over 800ms on var(--ease-in-out-expo), wiping down from the top edge; closes with the reverse animation over 400ms"
  - "items stagger in 80ms apart, chained 320ms after the panel wipe-in"
  - "scrolling content fades at top and bottom edges via a linear-gradient mask"
accessibility:
  - "hamburger: aria-label + aria-controls + aria-expanded disclosure contract; inset 2px focus ring"
  - "drawer: role=\"dialog\" aria-modal=\"true\" wrapping a <nav>; full focus trap"
  - "Escape closes and returns focus to the hamburger; reduced motion drops all animation to an instant display toggle"
token_bindings: [--surface-primary, --container-margin, --ease-in-out-expo]
---

# Mobile drawer

Collapses the desktop topbar into a full-viewport drawer at mobile widths, sharing the same DOM as the topbar. It realizes the Shell's persistent top-nav Section at mobile widths.

## Variants

- `state`: `closed` (default) | `open`.
- `motion-mode`: `animated` (default) | `reduced` (instant display toggle under `prefers-reduced-motion: reduce`).

## Determinations

- Drawer: `position: fixed; inset: 0; z-index: 101`.
- Drawer background = `--surface-primary`.
- Hamburger button is 40×40px with a 16×1px top line and an 8×1px bottom line in `currentColor`.
- Hamburger button has an inset 2px focus ring (`outline-offset: -2px`).
- Drawer opens with `clip-path: inset(0 0 100%) → inset(0 0 0%)` over 800ms on `var(--ease-in-out-expo)` — the curve reserved for max-height and panel reveals over longer durations — wiping down from the top edge.
- Drawer closes with the reverse animation over 400ms.
- Drawer items stagger in 80ms apart with `animation-delay: calc(320ms + var(--item-index) * 80ms)` to chain after the panel wipe-in.
- Drawer content uses a soft `mask-image: linear-gradient(to bottom, transparent 0%, white var(--container-margin), white calc(100% - var(--container-margin)), transparent 100%)` to fade the top and bottom edges as content scrolls.
- Reduced-motion override: drop all drawer animations to an instant display toggle.

## Accessibility

- Hamburger ARIA contract: `<button type="button" aria-label="Open menu" aria-controls="<drawer-id>" aria-expanded="false">`; `aria-expanded` flips to `"true"` while the drawer is open and `aria-label` updates to `"Close menu"`. (WAI-ARIA APG disclosure pattern.)
- Drawer role / labelling: the drawer is a full-viewport takeover, so it is `<div role="dialog" aria-modal="true" aria-label="Site navigation">` wrapping a `<nav>` for the link list. (WAI-ARIA APG modal-dialog pattern.)
- Focus trap: when the drawer opens, focus moves to the drawer's first focusable element (typically the close affordance or the first nav item). Tab cycles forward within the drawer; Shift+Tab cycles backward; both wrap at the boundaries. Focus cannot escape to background content.
- Keyboard: Escape closes the drawer and returns focus to the hamburger trigger. Enter and Space on a focused nav item activate the link.
