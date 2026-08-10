---
kind: component
name: destructive-button
page_family: shared
aliases: [destructive button, delete button, danger button]
status: stable
slots:
  - { name: leading-icon, required: false, accepts: [warning-glyph, trash-glyph] }
  - { name: label, required: true, accepts: [text] }
sizing:
  height: "--control-height (calibrates to 36px; destructive-primary); --control-height-compact (calibrates to 32px; destructive-inline)"
  width: "content-driven via inline-flex"
  padding: "8px 16px (destructive-primary); 6px 12px (destructive-inline)"
  radius: "--radius-sm (8px)"
behavior: [hover-scale, disabled, loading, reduced-motion]
accessibility: [destructive-focus-ring, disabled-attribute, icon-only-aria-label]
token_bindings:
  - --button-destructive-bg
  - --button-destructive-text
  - --danger-100
  - --text-inverse
composite: false
---

# Destructive button

A button variant reserved for destructive actions (delete, remove, revoke, irrevocable resets). Visually distinct from the primary and secondary buttons via a destructive (red) fill. Fill + label, with an optional leading icon (a warning or trash glyph preceding the label).

The variant inherits the full button base contract (`libraries/components/button.md`): every base behavior and accessibility determination applies unless restated here — including the loading state (rest-state dimensions preserved, label replaced by a `currentColor` spinner, `aria-busy="true"`, clicks ignored, `disabled` not set while loading), the disabled-state attribute choice, the icon-only `aria-label` rule with its 40px minimum hit area, and the tap-target floor.

## Variants

- `destructive-primary` — solid destructive fill + light label at `var(--control-height)` (`foundations/layout.md` §11.11; calibrates to 36px). Reserved for the highest-stakes irreversible action on a settings surface.
- `destructive-inline` — same fill, used inline beside a helper sentence on a setting card. Steps down to `var(--control-height-compact)` (calibrates to 32px) so it reads as a denser inline control beside body text; padding tightens to `6px 12px`.

## Determinations

- `--button-destructive-bg` binds to `--danger-100`; `--button-destructive-text` binds to `--text-inverse`.
- Height `var(--control-height)` (calibrates to 36px; destructive-primary); width is content-driven via `inline-flex`. Padding `8px 16px`. Border `0` (the visual is fill-based). Border-radius `var(--radius-sm)` (8px).
- Font-size `14px`, font-weight `460` (a custom weight via the variable-axis sans face — not 500/600), font-family `var(--typeface-sans)`. Label color `var(--text-inverse)`.
- `display: inline-flex` with centered alignment on both axes. `position: relative` with an isolated stacking context for the fill layer.

## Behavior

- Hover scales the button (subtle `scale-y(1.015)` paired with a matching `scale-x` factor), wrapped in a transition (≈150ms ease); the fill color is hover-invariant. Suppress the scale transform under `prefers-reduced-motion: reduce`.
- Interaction states: `rest` | `hover` | `disabled` (pointer-events removed, 50% opacity, shadows removed) | `confirming` — the confirm-step contract is not part of the button itself; it lives in the surrounding flow.

## Accessibility

- Focus paints the foundation focus ring on `:focus-visible`, resolved to the destructive token: `outline: 2px solid var(--danger-100); outline-offset: 2px` — the ring color matches the control's destructive semantics. (`foundations/accessibility.md` §18.2.)
- Disabled uses the button-base disabled contract (`libraries/components/button.md`): HTML `disabled` attribute, `opacity: 0.5`, `pointer-events: none`.

## Composition

The hairline-divider section that hosts a destructive button (the destructive zone) is a composite component in its own right — the destructive button is its action slot, not the composition itself.
