---
kind: component
name: text-input
page_family: shared
aliases: [text input, standard text input, input, form field]
status: stable
slots:
  - { name: field, required: true, accepts: [single-line-text] }
  - { name: placeholder, required: true, accepts: [text] }
  - { name: helper, required: false, accepts: [caption] }
  - { name: error-message, required: false, accepts: [caption] }
  - { name: error-glyph, required: false, accepts: [warning-glyph] }
sizing:
  height: "44px"
  radius: "--radius-md (calibrates to 9.6px at the captured surface; ladder default 12px)"
  horizontal_padding: "12px"
  helper_top_margin: "--sp-0-25 (4px)"
behavior: [hover-border-shift, focus-visible-ring, disabled, error-state]
accessibility: [aria-invalid, aria-live-error, focus-visible-ring, tap-target]
token_bindings:
  - --surface-raised
  - --border-subtle
  - --text-primary
  - --text-secondary
  - --text-tertiary
  - --error-text
  - --focus-ring
shell_component: false
composite: false
---

# Text input

A single-line text input: hairline border + light fill + label-via-placeholder.

## Determinations

- 44px height, `var(--radius-md)` radius (calibrates to 9.6px at the captured surface; ladder default 12px, `foundations/layout.md` §11.7), 12px horizontal padding. The label is hidden in favor of the placeholder.
- The 44px height also satisfies the WCAG 2.5.5 (AAA) target size — comfortably above the WCAG 2.2 AA minimum (2.5.8, 24×24).

## Behavior

- Border shifts to `--text-secondary` on hover; the outline appears on `:focus-visible` only.
- **Focus-visible ring.** `outline: 2px solid var(--focus-ring); outline-offset: 2px` per the foundation focus-ring contract. (WCAG 2.4.7, 2.4.11.)
- **Disabled state.** `opacity: 0.5; cursor: not-allowed; pointer-events: none`. The input also carries the HTML `disabled` attribute so it is excluded from form submission and tab order.

## Error state

The border shifts to `--error-text`; the input carries `aria-invalid="true"`. A leading or trailing warning glyph in `--error-text` is optional. The error message renders below the input in `--error-text` inside an `aria-live="polite"` container (`foundations/accessibility.md` §18.6).

## Helper-text slot

Helper text renders as a caption below the input: tertiary ink (`--text-tertiary`), 13px, weight 400, with `--sp-0-25` (4px) top margin. When both helper text and an error message can appear, the error message replaces the helper text in the same slot.
