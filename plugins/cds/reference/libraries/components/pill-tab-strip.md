---
kind: component
name: pill-tab-strip
aliases: [segmented control, pill tabs, tab strip, toggle group]
status: stable
slots:
  - { name: strip, required: true, accepts: [button-group] }
  - { name: option, required: true, accepts: [button] }
sizing:
  outer_radius: "16px"
  inner_radius: "12px"
  inner_padding: "4px"
behavior: [active-fill, background-transition, color-glide]
accessibility: [radiogroup-or-tablist, arrow-key-selection]
token_bindings:
  - --surface-tertiary
  - --text-tertiary
  - --text-primary
  - --text-inverse
composite: false
---

# Pill-tab strip

A segmented control where one option is active at a time, painted as an inset pill inside an outer strip. Outer strip + inner buttons.

## Determinations

- Outer radius 16px, inner radius 12px, 4px inner padding.
- Strip ground: `--surface-tertiary`. Option at rest: `--text-tertiary`. Active option: `--text-primary` as the pill fill with `--text-inverse` label ink.

## Behavior

- The active button background paints with `currentColor`; the inner label inherits inverse ink.
- Background transition 200ms; color transition 100ms. Active inner text transitions over 500ms via a slow color glide.

## Accessibility

- When the strip selects a filter/view that updates content in place without revealing/hiding distinct panels: `role="radiogroup"` on the outer strip and `role="radio"` with `aria-checked` on each button.
- When the strip switches between distinct content panels in the same DOM: `role="tablist"` + `role="tab"` + `aria-selected` + `aria-controls` pointing at the `role="tabpanel"`.
- Keyboard contract (both patterns): Tab focuses the group once; Arrow Left / Arrow Right move selection between options and wrap at the boundaries; Space or Enter activate when manual activation is required (tabs that mount expensive content); selection moves with focus when automatic activation is acceptable (radiogroup behavior). (WAI-ARIA APG tabs and radio-group patterns.)
