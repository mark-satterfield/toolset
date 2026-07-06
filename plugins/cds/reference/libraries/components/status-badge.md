---
kind: component
name: status-badge
family: shared
aliases: [status badge, state indicator, status pill]
status: stable
slots:
  - { name: label, required: true, accepts: [text] }
sizing:
  type: "12px caption"
behavior: []
accessibility: [contrast-floor]
token_bindings:
  - --status-positive-bg
  - --status-caution-bg
  - --status-critical-bg
  - --surface-secondary
  - --text-primary
  - --text-inverse
  - --text-tertiary
shell_furniture: false
composite: false
---

# Status badge

An indicator badge keyed to a state (e.g., warm coral for "needs attention", cool sage for "ok"). Ground and ink resolve per state from the status → color mapping. Static at rest.

## Determinations

- 12px caption type. Label text is stored lowercase and rendered uppercase via `text-transform: uppercase` with `0.04em` letter-spacing.

## Status → color mapping

| State | Ground | Ink |
|---|---|---|
| `ok` / `success` | `--status-positive-bg` | `--text-primary` |
| `warning` / `needs-attention` | `--status-caution-bg` | `--text-primary` |
| `error` / `failed` | `--status-critical-bg` | `--text-inverse` |
| `neutral` / `info` | `--surface-secondary` | `--text-tertiary` |

Each ground is a role, not a swatch — the `status-*-bg` roles are constrained (`from_palette: status`) and resolve per theme. Every ground meets the `foundations/accessibility.md` §18.5 readable-text floor against its ink at the 12px caption size.
