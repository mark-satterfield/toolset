---
kind: component
name: filter-chip
page_family: app
aliases: [filter pill, facet picker, filter dropdown chip]
status: stable
slots:
  - { name: label, required: false, accepts: [text] }
  - { name: value, required: true, accepts: [text] }
  - { name: caret, required: true, accepts: [icon] }
  - { name: leading-glyph, required: false, accepts: [icon] }
sizing:
  height: "--control-height-compact"
  width: "content-driven"
  radius: "--radius-sm"
  gap: "internal gap, component geometry"
behavior:
  - "states: rest | hover | focus-visible | open | disabled | invalid"
  - "kind: labelled (default) | icon-only"
  - "caret rotates 180° on open"
accessibility:
  - "inner button: aria-haspopup=dialog + aria-expanded"
  - "Enter/Space opens the dialog popover"
  - "wrapper non-focusable; Tab focuses the inner button"
token_bindings: [--surface-raised, --border-subtle, --border-strong, --focus-ring, --error-text, --text-primary, --text-tertiary, --typeface-sans]
shell_component: false
composite: false
---

# Filter chip

A compact pill-shaped picker that displays a filter facet's label, the current value, and a trailing caret indicating the picker opens a popover when clicked. Renders as a wrapper `<div>` housing a `<button>` (the label+value trigger) plus a sibling caret region — the wrapper carries the visible pill shape and ground; the button is transparent.

## Slots

- `label` (optional): the facet name (e.g., "Group by", "Project", "Range"). Some chips render value-only when context conveys the facet.
- `value` (required): the currently selected value, rendered inline next to the label.
- `caret` (required): a small dropdown caret in the wrapper's right slot.
- `leading-glyph` (optional): a small icon glyph variant — an icon-only chip (e.g., download glyph) without label text.

## Sizing

- Wrapper (the pill): height `--control-height-compact` (calibrates to 32px); padding right-only at the small step (calibrates to 8px); border `0`; radius `--radius-sm` (calibrates to 8px); `display: flex; align-items: center` with an internal gap (calibrates to 6px); ground `--surface-raised` as the control-field fill (calibrates to a translucent 10%-alpha foreground wash over the dark sub-surface at the reference rendering); rest-state ring is a hairline box-shadow ring in `--border-subtle`.
- Inner button: stretches to the wrapper height; left padding at the small step (calibrates to 8px); border `0`; transparent background; same flex alignment and gap.
- Wrapper width: content-driven (calibrates to 105–180px — narrowest at the most concise label+value pair; widest at the longest combined string).
- Type binding: body size at the compact scale (calibrates to 14px), weight 400, `--typeface-sans`, value ink `--text-primary`; label ink `--text-tertiary`.
- Icon-only variant renders as a square at `--control-height-compact` per side, which is also the tap-target floor.

## Behavior

- `hover`: the hairline ring steps from `--border-subtle` to `--border-strong` (only when not focused and not invalid). Transition at the interaction-scale duration `--duration-200` (calibrates to the fast step).
- `focus-visible` (keyboard): wrapper ground steps to the raised popover surface (`--surface-raised`); ring becomes the `--focus-ring` treatment.
- Focus-ring delegation: the inner trigger button suppresses its own `:focus-visible` outline (`outline: none` on the trigger only); the focus treatment paints on the wrapper, so the pill reads as one focused control. This suppression is part of the entry's contract — the `cds-reset` utility deliberately does not set `outline: none`, and without the suppression the foundation `:focus-visible` ring would paint on both the inner button and the wrapper.
- `open`: handled at the popover side. Chip carries the `aria-expanded` toggle.
- `disabled`: pointer events removed, 50% opacity, default cursor.
- `invalid`: the ring paints in `--error-text`.
- Caret rotates 180° on `aria-expanded="true"` over 150ms using `--ease-in-out` (`foundations/motion.md` §15.1); suppress the rotation under `prefers-reduced-motion: reduce`.

## Accessibility

- Inner button: `aria-haspopup="dialog"` (NOT `menu`) — the chip opens a dialog popover for arbitrary controls (radio groups, multi-selects, date pickers).
- Inner button carries `aria-expanded`; the host library toggles it on open.
- Enter/Space opens the dialog (browser default for `<button>`).
- Tab focuses the inner button; the wrapper is non-focusable.

## Structural skeleton

```html
<div class="filter-chip cds-reset"><!-- pill wrapper: --surface-raised ground, --border-subtle ring, --radius-sm -->
  <button aria-haspopup="dialog" aria-expanded="false"
          class="filter-chip__trigger cds-reset"><!-- transparent, stretches to wrapper height -->
    <span class="filter-chip__label-value"><!-- label and current value text --></span>
    <span class="filter-chip__caret" aria-hidden="true"><!-- caret SVG --></span>
  </button>
</div>
```

The `cds-reset` utility (`libraries/components/cds-reset.md`) neutralizes host-cascade styling on the wrapper and trigger.

## Popover panel

The chip opens a `role="dialog"` popover that can hold any control (radio groups, multi-selects, date pickers); the panel contents are supplied by the host. The panel anchors below the chip, left-aligned to the chip's left edge, and follows the dropdown lift-and-scale open vocabulary (`libraries/components/dropdown-panel.md`).
