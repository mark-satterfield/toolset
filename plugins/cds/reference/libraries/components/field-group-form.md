---
kind: component
name: field-group-form
family: app
aliases: [address form, multi-column form row, field group, form row]
status: stable
slots:
  - { name: group-label, required: true, accepts: [heading, label] }
  - { name: row, required: true, accepts: [flex-container] }
  - { name: field, required: true, accepts: [label, input, select] }
sizing:
  2col-row: "flex row capped at --column-field-measure, gaps --sp-0-75"
  4col-row: "wrapping flex row at full width, column gap --sp-0-75, row gap --sp-1-5"
  cell: "natural flex sizing; height derives from input + label + gap"
  input-height: "text-input contract"
  input-radius: "--radius-md"
behavior:
  - "state per field: rest | focus | invalid | disabled"
  - "4-col row wraps to 2-up / 1-up as the parent narrows"
accessibility:
  - "invalid fields: --error-text border + aria-live=polite helper sentence"
token_bindings: [--surface-raised, --border-subtle, --error-text, --text-primary, --text-secondary, --typeface-sans]
shell_furniture: false
composite: true
---

# Field-group form

A form-layout composition arranging labelled input Components in a multi-column row to optimize horizontal space for related fields (address parts, name parts, date ranges). The canonical instances are an Address line 1 + Line 2 pair in a 2-col row and a Country + State + City + Postal set in a 4-col row.

## Component references

Text input primitives (`libraries/components/text-input.md`), select / combobox primitives, label primitives.

## Slots

- `group-label` (required): a heading or single label sitting above the row.
- `field` (repeating): a `<label>` + a control (`<input>`, `<select>`, etc.) inside a flex cell. The cell wraps both the visible field label and the input.
- `row` (required): a flex container distributing field cells horizontally.

State enum (per field): `rest` | `focus` | `invalid` | `disabled`.

## Dimensions

- **2-col row container:** `display: flex`, `max-width: var(--column-field-measure)` (`foundations/layout.md` §11.2; calibrates to 512px), column and row gaps at `--sp-0-75` (calibrates to 12px). Cells share width via natural flex sizing (each cell calibrates to 208×72px at the reference viewport).
- **4-col row container:** `display: flex; flex-wrap: wrap`, column gap `--sp-0-75` (calibrates to 12px), row gap `--sp-1-5` (calibrates to 24px), `width: 100%`, `align-items: flex-end`. Cells share width via natural flex sizing (no fixed basis; each cell calibrates to 208×72px). At narrower viewports the 4-col row wraps to 2-up because `flex-wrap` is engaged and `flex-basis` is `auto`.
- **Field cell:** a flex column carrying the label above the input. Cell height derives from the input height plus the label line and an 8–10px vertical rhythm gap (calibrates to 72px total with a 44px input).
- **Input itself:** the standard text-input height (calibrates to 44px), padding `0 --sp-0-75` (calibrates to 12px), border `1px solid --border-subtle` (a hairline at ~15% alpha against the dark surface), radius `--radius-md` (calibrates to 9.6px on this surface), ground `--surface-raised` (elevated surface), body type size (calibrates to 16px) in `--typeface-sans`.
- **Select / combobox trigger** (rendered as `<button role="combobox">`): input height minus the border box (calibrates to 42px), left padding `--sp-0-75` (right padding handled by an internal chevron), transparent background, no visible border by default.

## Role-token bindings

- Field input ground → `--surface-raised`
- Field input border → `--border-subtle` (resolves to an alpha-thinned hairline)
- Field input radius → `--radius-md` (calibrates to 9.6px)
- Row gaps → `--sp-0-75` column / `--sp-1-5` row (4-col wrap variant)
- Field label ink → `--text-secondary` (one step dimmer than primary)
- Field input text → `--text-primary`

## Responsive collapse

- 2-col row: the `--column-field-measure` cap keeps each cell near half the row; below the cap the row contracts but does not wrap (the 2-col pattern is not designed to collapse).
- 4-col row: `flex-wrap: wrap` is engaged by default; cells reflow to 2-up or 1-up as the parent narrows. The narrower postal-code variant relies on a per-cell width override rather than per-column grid sizing.

## Structural skeleton

```html
<section class="field-group">
  <h3 class="field-group__label">Primary business address</h3>

  <!-- 2-col variant -->
  <div class="field-group__row field-group__row--2col">
    <label class="field">
      <span class="field__label">Address line 1</span>
      <input type="text" class="field__input">
    </label>
    <label class="field">
      <span class="field__label">Address line 2</span>
      <input type="text" class="field__input">
    </label>
  </div>

  <!-- 4-col variant (wraps at narrow viewports) -->
  <div class="field-group__row field-group__row--4col">
    <label class="field">
      <span class="field__label">Country</span>
      <button role="combobox" class="field__select"></button>
    </label>
    <label class="field">
      <span class="field__label">State or province</span>
      <input type="text" class="field__input">
    </label>
    <label class="field">
      <span class="field__label">City</span>
      <input type="text" class="field__input">
    </label>
    <label class="field field--narrow">
      <span class="field__label">Postal code</span>
      <input type="text" class="field__input">
    </label>
  </div>
</section>
```

## Determinations

- **Label typography** — field labels are body compact scale (calibrates to 14px), weight 500, ink `--text-secondary`.
- **Field validation visuals** — an invalid field gets a `1px --error-text` border plus a single sentence of helper text below the input in `--error-text`, with `aria-live="polite"` on the message container (`foundations/accessibility.md` §18.6).
- **Per-cell width overrides** — the narrower postal-code cell uses a per-cell `flex-basis` (calibrates to 96px) rather than a column track; all other cells in the 4-col row share equal width via natural flex sizing.

Settings, profile, billing, and onboarding screens all need consistent address/identity form composition; a stable field group prevents per-screen drift.
