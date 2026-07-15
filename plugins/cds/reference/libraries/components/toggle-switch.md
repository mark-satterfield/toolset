---
kind: component
name: toggle-switch
page_family: shared
aliases: [switch, toggle, on/off switch]
status: stable
slots:
  - { name: track, required: true, accepts: [pill-body] }
  - { name: thumb, required: true, accepts: [circle] }
sizing:
  track-height: "--switch-height (size variants: compact | regular)"
  track-width: "1.8 × --switch-height"
  track-padding: "2px inset"
  thumb: "--switch-height − 4px, circular"
  thumb-travel: "0.8 × --switch-height"
behavior:
  - "states: off | on; thumb slides over --duration-200"
  - "track hover step and checked-hover step per theme binding"
accessibility:
  - "button role=switch + aria-checked; Space and Enter toggle"
  - "foundation focus ring on :focus-visible"
token_bindings: [--switch-active-bg, --surface-tertiary, --surface-raised, --focus-ring]
shell_component: false
composite: false
---

# Toggle switch

Boolean on/off control with a sliding thumb: a pill track containing a circular thumb. The single switch component of the system; the setting card (`libraries/components/setting-card.md`) embeds it in its toggle slot.

## Geometry

All dimensions derive from one geometry token, `--switch-height` (the track height):

- Track: `--switch-height` tall × `1.8 × --switch-height` wide; fully rounded; 2px inset padding.
- Thumb: circular at `--switch-height − 4px` per side.
- Thumb travel (OFF → ON): `0.8 × --switch-height` (equivalently: track width − thumb − 2 × padding).

Two size variants bind the token:

- `compact` — the default control-scale switch; calibrates to an 18–20px height (a 32×18 to 36×20 track).
- `regular` — the setting-card embed scale; calibrates to a 24px height (a 43×24 track with a 20×20 thumb and ~19px travel).

Where a rendered instance's measured geometry and a derived value disagree, the render proof is the final arbiter of the variant's calibration values.

## Color contract

- ON track: `--switch-active-bg` (the chromatic signal), thumb right.
- OFF track: `--surface-tertiary` (gray fill), thumb left.
- Thumb fill: `--surface-raised`, with a small shadow.
- Hover steps the track one shade within the same role's theme binding (OFF-hover and ON-hover are theme-bound shades of `--surface-tertiary` and `--switch-active-bg` respectively).

**Reservation.** The `--switch-active-bg` and `--focus-ring` roles are reserved for switches and the conversion-input focus ring respectively — both constrained (`from_palette: signals`/`borders`) — so no other control surface paints with these. The toggle switch is the only place the chromatic state swatch paints a control surface.

**Contrast.** `--switch-active-bg` resolves to the same chromatic signal the focus ring uses on conversion inputs; the ON-state ground must meet contrast against the thumb fill `--surface-raised` to remain perceivable.

## Behavior

The thumb slides between OFF (left) and ON (right) over `--duration-200` (calibrates to 200ms).

## Accessibility

- The switch is a `<button role="switch">` carrying `aria-checked="true|false"`; the visual state and the `aria-checked` value are always synchronized. Hosts may mirror the state in a `data-state` attribute for styling. (WAI-ARIA APG switch pattern.)
- Space and Enter both toggle the switch (WAI-ARIA APG + HTML default for `<button>`). Tab focuses the switch as a single control.
- Focus ring on `:focus-visible` follows the foundation focus-ring contract (`outline: 2px solid var(--focus-ring); outline-offset: 2px`, `foundations/accessibility.md` §18.2).
- Disabled: the HTML `disabled` attribute, `opacity: 0.5`, `cursor: not-allowed`, `pointer-events: none`; `aria-checked` continues to reflect the current state.
- Honor `prefers-reduced-motion: reduce` by suppressing the thumb-slide transition; the thumb snaps to the new position. (WCAG 2.3.3.)

## Structural skeleton

```html
<button role="switch" aria-checked="true" data-state="true"
        class="toggle-switch cds-reset"><!-- track: --switch-active-bg when checked, --surface-tertiary when off -->
  <span class="toggle-switch__thumb"><!-- --surface-raised, slides 0.8 × --switch-height --></span>
</button>
```

The `cds-reset` utility (`libraries/components/cds-reset.md`) neutralizes host-cascade styling on the button.
