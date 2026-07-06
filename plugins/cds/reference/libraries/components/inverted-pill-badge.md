---
kind: component
name: inverted-pill-badge
family: shared
aliases: [inverted pill, filled badge, counter badge, emphasis badge]
status: stable
slots:
  - { name: label, required: true, accepts: [text] }
sizing:
  radius: "--radius-sm (8px)"
  min_width: "4rem"
  line_height: "1"
  padding: "0.5rem 0.75rem (defaults to the outline pill badge values)"
  type: "12px caption (defaults to the outline pill badge values)"
behavior: []
accessibility: []
token_bindings:
  - --text-primary
  - --surface-primary
shell_furniture: false
composite: false
---

# Inverted pill badge

A filled pill that inverts ink — used for emphasis labels and counters. Static at rest.

## Determinations

- Ground is `--text-primary`; label ink is `--surface-primary` (the inversion).
- `var(--radius-sm)` radius (8px, `foundations/layout.md` §11.7), `min-width: 4rem`, `line-height: 1`.
- Padding and type size default to the sibling outline pill badge values (`0.5rem 0.75rem` padding, 12px caption) so the two pill variants align vertically when placed side-by-side. Host projects may override.
