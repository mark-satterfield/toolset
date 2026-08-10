---
kind: section
name: top-nav
page_family: shared
aliases: [topbar, top bar, nav, nav bar, top nav, menu bar, header nav, site header]
status: stable
shell_edge: block-start
content_contract:
  carries_mark: "true | false"
  nav_item_count: "integer — top-level navigational items the frame offers"
  conversion_action_count: "integer — conversion actions the frame offers"
theme: default
composition_notes: []
variants: [scroll-behavior, cta-adjacency]
sizing:
  height: "var(--topbar-height) — geometry.components.topbar.height; calibrates to 84px at the desktop reference viewport, with a narrow-viewport floor (calibrates to 64px below 480px) declared as the token's mobile_floor"
  mark-height: "var(--topbar-logo-height) — geometry.components.topbar.logo-height; tracks var(--topbar-height) so the mark scales with the bar; calibrates to 40px at the 84px reference bar height"
  action-height: "var(--topbar-action-height) — derived from var(--topbar-height); calibrates to 36px at the 84px reference bar height"
behavior:
  - "scroll-behavior static at rest; the hide-on-scroll variant translates the bar off-screen on downward scroll and restores it on upward scroll"
  - "the bar paints no boundary and casts no shadow, so it blends into the ground beneath it"
accessibility:
  - "landmark: <header role=\"banner\">; the inner <nav aria-label=\"primary\"> is emitted ONLY when the received Shape fills a navigational or conversion slot"
  - "keyboard: sequential Tab order over whatever the Shape places, in source order; no arrow-key menubar semantics at the top level"
  - "hide-on-scroll is suppressed while focus is inside the bar (WCAG 2.4.11 Focus Not Obscured, AA)"
token_bindings: [--nav-bg, --text-primary, --topbar-height, --topbar-logo-height, --topbar-action-height, --radius-sm]
---

# Top nav

The Shell Section pinned to the block-start edge of the canvas: a fixed bar that frames the vacant space a Page nests into and does not participate in the Page's ground alternation.

**This entry fixes the surface; the Shape fixes the arrangement.** Height, ground, pinning, mark sizing, landmark, and focus are the bar's own properties and live here. What the bar carries — a mark alone, a mark and a menu, a mark with a menu and a conversion action, a menu with no mark — and where each piece sits in the row is the contract of the Shape this Section receives from the ShapeLibrary (`libraries/shapes/`, the `bar-*` arrangements). A bar with different contents is a different Shape over this one Section, never an optional slot on a Component.

The pieces a `bar-*` Shape places carry their own contracts: `libraries/components/logo.md`, `libraries/components/horizontal-menu.md`, `libraries/components/button.md`, `libraries/components/dropdown-panel.md`, `libraries/components/mobile-drawer.md`.

## Shape assignment

Lazy by default: the Shape resolves at build time from `carries_mark`, `nav_item_count`, and `conversion_action_count` via `rules/shape-selection/top-nav.md`. A ShellDefinition that names a `bar-*` Shape up front is assigned eagerly and the rule does not run.

## Variants

- `scroll-behavior`: `static` (default) | `hide-on-scroll` — the bar hides on downward scroll and reappears on upward scroll. Editorial surfaces only.
- `cta-adjacency`: `standalone` (default) | `caret-flush` — the trailing conversion button takes an asymmetric radius `var(--radius-sm) 0 0 var(--radius-sm)` (left-rounded only) so its right edge meets an adjacent dropdown caret cleanly.

## Determinations

- `position: fixed; top: 0; z-index: 100`.
- Ground = `--nav-bg`, the bar's dedicated navigation-ground role (a `from_palette: backgrounds` component role). It is bound per theme to the same ground as the Section directly beneath it — the page ground, `--surface-primary` — so the bar blends seamlessly into the first Section with no seam. The bar has no standalone color of its own.
- Height = `var(--topbar-height)`. The narrow-viewport floor is the token's `mobile_floor`, emitted by re-declaring `--topbar-height` at `:root` inside `@media (max-width: 480px)`; the bar's height rule inherits it. Bar height is a single value across every surface within a build.
- Mark sizing: a mark placed in the bar renders at `height: var(--topbar-logo-height); width: auto`, vertically centered, so the bar and the mark scale together. The design system owns that height — a composed page never hardcodes it, and a page-block `<style>` re-declaring it is an audit violation.
- No bottom border. No drop shadow. The bar blends into the page ground.
- The bar is a single flex row. Which slots it carries, and where they sit within the row, is entirely the received Shape's contract.
- Conversion button: `var(--topbar-action-height)` tall, mapped primary fill, mapped inverse text, radius `var(--radius-sm)` (calibrates to the captured 8–10px range).

### hide-on-scroll

```css
.top-nav.is-hide-on-scroll {
  transition: transform 0.3s ease;
}
.top-nav.is-hide-on-scroll.is-hidden {
  transform: translateY(-100%);
}
@media (prefers-reduced-motion: reduce) {
  .top-nav.is-hide-on-scroll { transition: none; }
}
```

- The `is-hidden` class is added on downward scroll past the bar height and removed on upward scroll.
- Threshold: 8px of cumulative downward scroll past the bar height before `is-hidden` is added; reveal on any upward scroll of 4px or more. Scroll handling is debounced to one evaluation per animation frame (`requestAnimationFrame`) so detection stays off the main scroll path.

## Accessibility

- Landmark contract: the bar's host element is a `<header role="banner">`. **When the received Shape fills a navigational or conversion slot**, it contains a `<nav aria-label="primary">` wrapping them, and the mark's link sits outside that inner nav so the nav lists only navigational and conversion controls. **When the Shape fills neither**, the bar emits no `<nav>` at all — a navigation landmark wrapping a lone home link reports a navigational set that does not exist. (WAI-ARIA landmark guidance.)
- Keyboard contract: Tab visits whatever the Shape places, in source order. A mark-only bar contributes exactly one tab stop. Shift+Tab reverses. Menu items and conversion actions use the default semantics of `<a>` (Enter activates) and `<button>` (Enter + Space activate). No arrow-key navigation between top-level items — the bar is not a `role="menubar"`; arrow-key cycling is reserved for the dropdown panels that descend from a trigger.
- Conversion actions follow the primary button focus contract.
- Under `hide-on-scroll`: while focus is inside the bar, `is-hidden` is not applied — the hide is suppressed until focus leaves, so a keyboard user's focused control is never scrolled off-screen (WCAG 2.4.11). Reduced motion drops the transition so the bar snaps between states.
