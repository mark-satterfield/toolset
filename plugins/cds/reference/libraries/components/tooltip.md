---
kind: component
name: tooltip
aliases: [tooltip, hover hint, info bubble, help bubble, info tip]
status: stable
slots:
  - { name: anchor, required: true, accepts: [icon-glyph, button, text] }
  - { name: bubble, required: true, accepts: [text] }
sizing:
  max-width: "--column-field-measure capped to a comfortable measure; a tooltip longer than two lines is the wrong component"
  padding: "--sp-0-5 inline, --sp-0-25 block"
  radius: "--radius-xs"
  offset: "--sp-0-5 between the anchor's edge and the bubble"
behavior:
  - "opens on pointer hover and on keyboard focus of the anchor; closes on pointer leave, blur, and Escape"
  - "open delay 300ms on hover, none on focus; close is immediate"
  - "the bubble is hoverable — moving the pointer from the anchor onto the bubble keeps it open"
accessibility:
  - "the anchor is focusable; the bubble is referenced by aria-describedby, never aria-label"
  - "Escape dismisses the bubble while the pointer or focus remains on the anchor (WCAG 1.4.13)"
  - "the bubble is never the only place a piece of information appears"
token_bindings: [--surface-raised, --border-subtle, --text-primary, --radius-xs, --ease-in-out, --sp-0-25, --sp-0-5]
composite: false
---

# Tooltip

A short explanatory bubble that appears beside its anchor on hover or focus. It explains something already on screen; it never carries content that exists nowhere else.

## Variants

- `placement`: `block-end` (default) | `block-start` | `inline-start` | `inline-end` — the bubble flips to the opposite side when the preferred side would overflow the viewport.

## Determinations

- Ground `var(--surface-raised)` with a `1px solid var(--border-subtle)` hairline and `var(--radius-xs)`; ink `var(--text-primary)` at the compact body size.
- Padding `var(--sp-0-5)` inline and `var(--sp-0-25)` block; the bubble sits `var(--sp-0-5)` from the anchor's edge.
- The bubble is capped at a comfortable measure and wraps rather than extending. Content that needs more than two lines belongs in the surrounding copy.
- The bubble carries the surface's raised elevation, no arrow or beak, and no entrance transform — opacity only, over `var(--duration-100)` `var(--ease-in-out)`.
- Reduced motion suppresses the fade; the bubble appears and disappears instantly.

## Accessibility

- The anchor is focusable in its own right — a bare `<span>` is not an anchor. An informational glyph anchor is a `<button type="button">` with an accessible name naming what it explains.
- The bubble carries an `id` referenced by the anchor's `aria-describedby`, so the description supplements the anchor's name rather than replacing it.
- The three WCAG 1.4.13 obligations hold: the bubble is dismissable with Escape without moving the pointer, hoverable so the pointer can travel onto it, and persistent until the pointer leaves, focus moves, or Escape is pressed.
- Tooltip content is supplementary. A surface whose meaning depends on reading a tooltip has moved required content behind a hover.
