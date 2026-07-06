---
kind: component
name: period-picker
family: app
aliases: [date range picker, time period selector, range chip]
status: stable
slots:
  - { name: label, required: true, accepts: [text] }
  - { name: value, required: true, accepts: [text] }
  - { name: popover-trigger, required: true, accepts: [button] }
sizing:
  height: "--control-height-compact"
  width: "content-driven"
  radius: "--radius-sm"
behavior:
  - "states: rest | hover | open | disabled"
  - "activation opens a role=dialog date-range popover"
accessibility:
  - "wrapper role=combobox; inner button aria-haspopup=dialog + aria-expanded"
  - "dialog focus-trap contract on the panel"
token_bindings: [--surface-raised, --border-subtle, --text-primary, --text-tertiary, --typeface-sans]
shell_furniture: false
composite: false
---

# Period picker

A control letting the user select the currently-rendered time period. The default pattern is a dropdown-trigger pill that opens a date-range dialog. Structurally identical to the filter chip (`libraries/components/filter-chip.md`), differing only in the dialog contents it opens.

## Slots

- `label` (required): the facet name (e.g., "Range").
- `value` (required): the currently selected value, rendered to the right of the label.
- `popover-trigger` (required): the wrapper itself acts as the dropdown trigger via `aria-haspopup="dialog"`.

## Sizing

- Wrapper: height `--control-height-compact` (calibrates to 32px); width content-driven (calibrates to 104–201px); padding right-only at the small step (calibrates to 8px); radius `--radius-sm` (calibrates to 8px); border `0`; ground `--surface-raised` as the control-field fill (calibrates to the translucent field wash at the reference rendering); `display: inline-flex; align-items: center` with an internal gap (calibrates to 6px).
- Inner button: `flex: 1; padding: 0` (right pad handled by the wrapper; left pad at the small step, calibrates to 8px).
- Inner button children: two `<span>` slots — a label span in `--text-tertiary` and a value span in `--text-primary`.
- Row container: sibling chips sit in a flex row with a gap (calibrates to 12px); chips separated by thin divider spans painted in `--border-subtle`.
- Type: body size at the compact scale (calibrates to 14px), weight 400, ink `--text-primary`.

## Behavior

- `hover` is not declared as a separate visual; the chip remains at rest until focused/opened.
- `focus-visible`: wrapper ground steps to the raised popover surface (`--surface-raised`).
- `open`: wrapper retains the focus-visible ground; the popover panel is a separate component.
- `disabled`: 50% opacity; pointer events removed.

## Accessibility

- Wrapper is `<div role="combobox">`; the inner `<button aria-haspopup="dialog" aria-expanded="false">` is the actual trigger.
- Activation opens a `role="dialog"` popover (NOT `listbox` — this is a date-range picker dialog).
- Disabled gating uses `data-[disabled]` attributes.

## Structural skeleton

```html
<div role="combobox" class="period-picker cds-reset"><!-- --surface-raised ground, --radius-sm, --control-height-compact -->
  <button class="period-picker__trigger cds-reset" aria-haspopup="dialog" aria-expanded="false">
    <span class="period-picker__label"><!-- --text-tertiary -->{label}</span>
    <span class="period-picker__value"><!-- --text-primary -->{value}</span>
  </button>
</div>
```

The `cds-reset` utility (`libraries/components/cds-reset.md`) neutralizes host-cascade styling on the wrapper and trigger.

## Popover panel

Activation opens a `role="dialog"` date-range picker holding two calendar grids (start and end) plus a column of preset ranges (Today, Last 7 days, Last 30 days, This month, Custom). Selecting a preset or completing a custom range updates the chip's `value` slot and closes the dialog, returning focus to the trigger. The panel follows the dropdown lift-and-scale open vocabulary (`libraries/components/dropdown-panel.md`) and the modal-dialog focus-trap contract.
