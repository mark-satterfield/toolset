---
kind: component
name: dropdown-panel
family: shared
aliases: [dropdown, nav dropdown, mega menu, flyout menu]
status: stable
shell_furniture: true
composite: false
slots:
  - { name: trigger, required: true, accepts: [nav-link, button] }
  - { name: panel, required: true, accepts: [link-list, link-grid] }
  - { name: item, required: true, accepts: [link, row] }
sizing:
  flat-menu-width: "200px — intrinsic panel width for 1–4 link lists"
  mega-panel-width: "spans 7–9 columns of the 12-column grid within the marketing container; calibrates to 656–864px at the reference container width"
  lift-and-scale-width: "256px — intrinsic panel width for compact sub-nav menus"
  item-min-height: "var(--list-row-standard) (40px)"
  item-padding: "8px 12px"
  item-radius: "var(--radius-xs) (4px)"
behavior:
  - "flat/mega open: grid-template-rows 0 → auto + opacity 0 → 1 over 600ms, cubic-bezier(0.16, 1, 0.3, 1); grows from zero row-height, never translates"
  - "lift-and-scale open: scale(0.95) → scale(1) + opacity 0 → 1 over 200ms, cubic-bezier(0.4, 0, 0.2, 1), transform-origin 50% 0"
  - "item hover paints --surface-tertiary over 100ms"
accessibility:
  - "trigger: aria-haspopup=\"menu\" + aria-expanded; panel: role=\"menu\"; items: role=\"menuitem\""
  - "arrow-key cycling with wrap; Enter/Space activate; Escape closes and returns focus to the trigger"
  - "prefers-reduced-motion: reduce replaces open/close animations with an instant display toggle"
token_bindings: [--surface-tertiary, --list-row-standard, --radius-xs]
---

# Dropdown panel

Reveals grouped link lists or grids below a topbar trigger, opened on hover (desktop) or click (touch). Shell furniture: it descends from the topbar's primary-nav triggers.

## Variants

| Variant | Panel width | Use for |
|---|---|---|
| Flat menu | 200px (intrinsic) | 1–4 link lists. |
| Mega panel | 7–9 grid columns (calibrates to 656–864px at the reference container) | Multi-column link grids; centered above multiple trigger columns. |
| Lift-and-scale | 256px (intrinsic) | Compact sub-nav menus that need a small entrance affordance. |

## Determinations

- Dropdown items: `min-height: var(--list-row-standard)` (40px — the standard list-row step), `padding: 8px 12px`, `border-radius: var(--radius-xs)`.
- Hover paints the item background `--surface-tertiary` over 100ms.
- Flat and mega panels open with `grid-template-rows: 0 → auto` and `opacity: 0 → 1` over 600ms, curve `cubic-bezier(0.16, 1, 0.3, 1)`. The panel grows from zero row-height; do not translate.
- Lift-and-scale panel opens with `transform: scale(0.95) → scale(1)` plus `opacity: 0 → 1` over 200ms, curve `cubic-bezier(0.4, 0, 0.2, 1)`. Set `transform-origin: 50% 0`.

## Accessibility

- Trigger uses `aria-haspopup="menu"` and `aria-expanded` toggling.
- Panel carries `role="menu"`; items carry `role="menuitem"`. (WAI-ARIA APG menu pattern.)
- Tab cycles through visible items.
- Arrow Up / Arrow Down move focus between adjacent menu items; Arrow Down on the last item wraps to the first; Arrow Up on the first wraps to the last. Enter and Space activate the focused item.
- Escape closes the panel and returns focus to the trigger.
- Panel closes on click outside the trigger and the panel itself, on scroll past the trigger, and on Escape.
- Touch: on touch input the trigger toggles open on first tap and closes on a second tap of the trigger or a tap outside the panel. Hover-to-open is suppressed on touch input.
- Honor `prefers-reduced-motion: reduce` by replacing the open/close animations with an instant display toggle. (WCAG 2.3.3.)
