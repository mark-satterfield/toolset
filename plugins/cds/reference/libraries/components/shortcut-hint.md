---
kind: component
name: shortcut-hint
aliases: [keyboard shortcut, shortcut chip, hotkey hint, key hint, accelerator]
status: stable
slots:
  - { name: keys, required: true, accepts: [text] }
sizing:
  type: "the compact body size (calibrates to 14px), weight 400"
  gap: "--sp-0-25 between adjacent key tokens"
behavior:
  - "static; the hint never activates anything and is never a tab stop"
  - "an always variant paints at rest; an on-hover variant is transparent until its host is hovered or focus-visible, then fades in over --duration-100"
accessibility:
  - "aria-hidden: the hint restates a shortcut the host control already announces, so exposing it twice reads as duplicate content"
  - "the host control carries the shortcut in its own accessible name or aria-keyshortcuts"
  - "never the only indication that a shortcut exists"
token_bindings: [--text-tertiary, --ease-in-out, --sp-0-25]
composite: false
---

# Shortcut hint

The keyboard accelerator for a control, rendered beside it as quiet ink. One or more key tokens set as plain text — a modifier run and a key, in the platform's own notation.

## Variants

- `visibility`: `always` (painted at rest) | `on-hover` (transparent until the host control is hovered or takes `:focus-visible`, then fades in).

## Determinations

- Ink `var(--text-tertiary)` at the compact body size, weight 400. The hint is always quieter than the label it accompanies.
- Key tokens are separated by `var(--sp-0-25)` and are not individually boxed — no per-key border, ground, or radius.
- The hint sits at the trailing edge of its host, after the label, and never displaces the label when it appears.
- The `on-hover` variant transitions opacity over `var(--duration-100)` `var(--ease-in-out)`, and reserves its own width at rest so the row does not reflow when it appears.

## Accessibility

- The hint carries `aria-hidden="true"`. The shortcut belongs to the control, so the control announces it — via `aria-keyshortcuts` or its accessible name — and a screen reader hearing it twice hears two different things.
- Discoverability never depends on hover alone: a control whose only shortcut disclosure is an `on-hover` hint is unusable to a keyboard-only or touch user, so the shortcut is also registered where the surface lists its commands.
