---
kind: component
name: kebab-menu
aliases: [kebab menu, overflow menu, 3-dot menu, more actions]
status: stable
slots:
  - { name: trigger, required: true, accepts: [icon-button] }
  - { name: menu, required: true, accepts: [floating-panel] }
  - { name: item, required: true, accepts: [menu-row] }
sizing:
  trigger: "icon-button geometry (calibrates to 32×32px); SVG glyph on the --icon-viewbox-md drawing grid centered; padding 0; radius --radius-xs (calibrates to 6px)"
  menu_item: "min-height --list-row-standard; padding --sp-0-5 --sp-0-75; radius --radius-xs"
  menu_width: "content-driven — fits the longest label (calibrates to 160–200px)"
behavior: [lift-and-scale-open, outside-click-close, item-hover, disabled]
accessibility: [menu-pattern, aria-labelled-trigger, focus-visible-ring, tap-target]
token_bindings:
  - --surface-tertiary
  - --button-destructive-bg
  - --focus-ring
composite: false
---

# Kebab menu

A 3-dot trigger that opens a small floating menu carrying secondary actions for the current record. Kebab menus anchor to record headers, where the topbar dropdown panels anchor to nav triggers.

## Determinations

- The trigger inherits the icon-button base: icon-button geometry outer (calibrates to 32×32px), padding `0` with the SVG centered via inline-flex, border-radius `var(--radius-xs)` (calibrates to 6px at this control, per the 6px-radius-step role gap), transparent background at rest, glyph on the `--icon-viewbox-md` drawing grid (`foundations/imagery.md` §16.1).
- **Tap target.** The trigger at its calibrated 32×32px clears the WCAG 2.2 AA minimum target size (2.5.8, 24×24). The 44×44 size is the WCAG 2.5.5 **AAA** target size — host projects targeting AAA ship the trigger at `≥44×44px`.
- Menu panel item dimensions follow the dropdown-panel item rules: `min-height: var(--list-row-standard)` (`foundations/layout.md` §11.11), padding `var(--sp-0-5) var(--sp-0-75)` (calibrates to 8px 12px), `var(--radius-xs)` radius. Panel width is content-driven — it fits the longest label (calibrates to 160–200px). The menu anchors below the trigger and right-aligns to the trigger's right edge.

## Behavior

- Click on the trigger opens the menu; click outside or Escape closes it. Items paint `--surface-tertiary` background on hover over 100ms.
- **Disabled state.** The trigger follows the shared disabled contract: HTML `disabled` attribute, `opacity: 0.5`, `cursor: not-allowed`, `pointer-events: none`. A disabled trigger never opens the menu.
- **Menu open/close motion.** The menu mounts with the lift-and-scale dropdown vocabulary: `transform: scale(0.95) → scale(1)` plus `opacity: 0 → 1` over 200ms with `cubic-bezier(0.4, 0, 0.2, 1)`; `transform-origin: 100% 0` so the panel grows from the trigger's anchor corner. Close reverses over 150ms. Honor `prefers-reduced-motion: reduce` by replacing both with an instant display toggle. (WCAG 2.3.3.)

## Accessibility

- **Focus-visible ring.** The trigger paints the foundation focus ring on `:focus-visible` only: `outline: 2px solid var(--focus-ring); outline-offset: 2px` (`foundations/accessibility.md` §18.2). (WCAG 2.4.7, 2.4.11.)
- The trigger carries `aria-label` (e.g., "more actions"), `aria-haspopup="menu"`, and `aria-expanded`.
- The menu uses `role="menu"`; items use `role="menuitem"`.
- Standard menu keyboard contract: Arrow keys navigate, Enter activates, Escape closes.

## Structural skeleton

```html
<div class="kebab-menu-wrapper">
  <button class="kebab-trigger" aria-label="more actions" aria-haspopup="menu" aria-expanded="false">⋮</button>
  <ul class="kebab-menu" role="menu" hidden>
    <li role="menuitem"><button>View details</button></li>
    <li role="menuitem"><button>Refresh tools list</button></li>
    <li role="menuitem"><button class="kebab-menu__item--destructive">Remove</button></li>
  </ul>
</div>
```

## Kebab glyph

The trigger glyph is three vertically stacked filled circles drawn on the `--icon-viewbox-md` drawing grid (`foundations/imagery.md` §16.1), centered in the slot and painted in `currentColor`. Dot diameter is 1/10 of the grid (calibrates to 2px on the 20-unit grid); dot centers sit 1/5 of the grid apart (calibrates to 4px).

## Destructive-item ink

Destructive menu items render their label in `--button-destructive-bg` (the destructive fill role the destructive button declares as its binding, `libraries/components/destructive-button.md`); on hover the row still paints the `--surface-tertiary` background while the label stays destructive.
