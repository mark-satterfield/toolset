---
kind: component
name: catalog-card
aliases: [catalog card, grid card, badge card]
status: stable
slots:
  - { name: badge, required: true, accepts: [outline-pill-badge] }
  - { name: title, required: true, accepts: [heading] }
  - { name: body, required: true, accepts: [text] }
  - { name: meta, required: true, accepts: [text] }
sizing:
  padding: "--sp-2 (28–32px clamp, foundations/layout.md §11.4)"
  radius: "--radius-lg (16px, foundations/layout.md §11.7)"
  internal_gap: "--sp-0-75 (12px)"
behavior: []
accessibility: []
token_bindings:
  - --surface-raised
  - --border-subtle
composite: false
---

# Catalog card

A grid-item card carrying a label badge plus title, body, and meta. Static at rest.

## Determinations

- A small label badge sits in the top-left; it follows the outline pill badge spec (`libraries/components/outline-pill-badge.md`: `0.5rem 0.75rem` padding, 12px caption type).
- Card padding `--sp-2` (28–32px clamp, `foundations/layout.md` §11.4); border-radius `--radius-lg` (16px, §11.7); internal gap between badge, title, body, and meta is `--sp-0-75` (12px).
