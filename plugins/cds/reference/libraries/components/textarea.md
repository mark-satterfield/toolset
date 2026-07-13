---
kind: component
name: textarea
family: shared
aliases: [textarea, multi-line input, text area]
status: stable
slots:
  - { name: field, required: true, accepts: [multi-line-text] }
  - { name: placeholder, required: true, accepts: [text] }
  - { name: helper, required: false, accepts: [caption] }
  - { name: error-message, required: false, accepts: [caption] }
sizing:
  padding: "16px on all sides"
  min_height: "~3 lines of content"
  max_height: "unset by default; capped at the host-feature level when scroll is preferable to growth"
behavior: [hover-border-shift, focus-visible-ring, disabled, error-state, vertical-resize]
accessibility: [aria-invalid, aria-live-error, focus-visible-ring]
token_bindings:
  - --surface-raised
  - --border-subtle
  - --text-primary
  - --text-secondary
  - --error-text
  - --focus-ring
shell_component: false
composite: false
---

# Textarea

The multi-line variant of the text input (`libraries/components/text-input.md`). Slots, theme roles, and behavior follow the text input's contract; the differences are dimensional.

## Determinations

- Generous padding: 16px on all sides.
- Resize affordance defaults to `resize: vertical` so the user can grow the field downward without breaking horizontal layout.
- `min-height` of roughly 3 lines (sufficient room for visible context); `max-height` unset by default and capped at the host-feature level when scroll is preferable to growth.
