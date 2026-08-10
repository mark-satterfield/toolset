---
kind: component
name: range-slider
page_family: app
aliases: [slider, time slider, scrubber, range control, value slider]
status: stable
slots:
  - { name: track, required: true, accepts: [control] }
  - { name: thumb, required: true, accepts: [control] }
  - { name: value-readout, required: true, accepts: [text] }
  - { name: bounds, required: false, accepts: [text] }
sizing:
  track-height: "--sp-0-25"
  thumb: "--icon-size-inline diameter, with a hit area meeting the tap-target floor regardless of the thumb's drawn size"
  readout-gap: "--sp-0-5 between the track and its readout"
behavior:
  - "arrow keys move by one step, Page keys by a larger step, Home and End to the bounds"
  - "the readout updates continuously while dragging or stepping; the value is never inferred from the thumb's position"
  - "a slider whose data is not ready is disabled with the reason stated, never silently inert"
accessibility:
  - "role=\"slider\" with aria-valuemin, aria-valuemax, aria-valuenow, and aria-valuetext where the number needs units or words"
  - "keyboard-operable from first Tab without any prior pointer interaction"
  - "the current value is readable as text, never only as the thumb's position"
token_bindings: [--surface-tertiary, --accent-primary, --text-primary, --text-tertiary, --icon-size-inline, --radius-sm, --ease-in-out, --focus-ring, --sp-0-25, --sp-0-5]
composite: false
---

# Range slider

A single value chosen along a continuous range by dragging or stepping. Used where the range itself is meaningful — a year within a span, a threshold within a scale — and where seeing the position matters as much as the value.

## The readout is not optional

The current value is always shown as text beside the track. A thumb's position communicates approximately; a user setting a threshold or scrubbing to a year needs exactly. The readout also makes the value available to anyone who cannot see the thumb.

## Variants

- `bounds`: `absent` (default) | `present` — the range's ends labelled beneath the track's ends.
- `steps`: `continuous` (default) | `ticks` — discrete positions marked on the track, where the values are countable and landing between them is meaningless.
- `state`: `ready` (default) | `disabled` — the underlying data is not available, with the reason stated rather than the control silently ignoring input.

## Determinations

- The track is `var(--sp-0-25)` tall at `var(--radius-sm)`, ground `var(--surface-tertiary)`, with the portion up to the thumb painted `var(--accent-primary)`.
- The thumb is an `--icon-size-inline` circle. Its hit area meets the tap-target floor from `foundations/accessibility.md` regardless of the drawn size, so a small thumb stays grabbable.
- The readout sits `var(--sp-0-5)` from the track at the compact body size in `var(--text-primary)`, with tabular figures so it does not jitter as the value changes.
- Bounds labels sit beneath the track's ends at the caption size in `var(--text-tertiary)`.
- Dragging updates the value continuously. Whatever consumes the value decides whether to follow every change or settle on release; the control reports every change either way.
- The thumb has no transition while being dragged — a thumb that eases toward the pointer lags behind it. Stepping by keyboard does transition, over `var(--duration-100)` `var(--ease-in-out)`, and reduced motion drops it.
- A `disabled` slider states why in a tooltip (`libraries/components/tooltip.md`) rather than appearing operable and doing nothing.

## Accessibility

- `role="slider"` carrying `aria-valuemin`, `aria-valuemax`, and `aria-valuenow`, plus `aria-valuetext` wherever the raw number needs a unit or a word to make sense.
- Arrow keys move by one step, Page keys by a larger step, Home and End go to the bounds. The control is operable from the first Tab without any prior pointer interaction.
- The value is text as well as position (WCAG 1.4.1).
- Focus paints the foundation ring on `:focus-visible` (`foundations/accessibility.md` §18.2).
