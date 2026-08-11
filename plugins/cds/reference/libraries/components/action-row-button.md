---
kind: component
name: action-row-button
aliases: [row button, full-width action row, new-item row, list action row, command row]
status: stable
slots:
  - { name: leading-glyph, required: false, accepts: [icon-glyph] }
  - { name: label, required: true, accepts: [text] }
  - { name: shortcut, required: false, accepts: [shortcut-hint] }
  - { name: trailing-action, required: false, accepts: [icon-button] }
sizing:
  height: "--list-row-standard"
  padding: "--sp-0-5 inline"
  radius: "--radius-sm"
  glyph-chip: "a circular chip sized to --icon-size-marginalia holding a glyph at --icon-viewbox-md"
  gap: "--sp-0-75 between the glyph chip and the label"
behavior:
  - "spans the full inline width of its container rather than sizing to its label"
  - "the shortcut hint and the trailing action are revealed on hover and on focus-visible, and reserve their width at rest so the row never reflows"
  - "the trailing action is a separate control with its own target — activating it does not activate the row"
accessibility:
  - "the row is a <button> or an <a> depending on whether it acts or navigates; the trailing action is always its own <button> or <a>"
  - "the trailing action is a real sibling in the DOM, never nested inside the row's own interactive element"
  - "both controls are reachable by Tab in source order; neither is discoverable by hover alone"
token_bindings: [--surface-secondary, --surface-tertiary, --text-primary, --text-tertiary, --list-row-standard, --radius-sm, --icon-size-marginalia, --ease-in-out, --focus-ring, --sp-0-5, --sp-0-75]
composite: false
---

# Action row button

A full-width row that acts like a button: a glyph chip at the start, a label beside it, and — revealed on hover or focus — the action's keyboard shortcut and a secondary action of its own. The primary affordance for the one thing a panel most wants the user to do.

Distinct from the button (`libraries/components/button.md`), which sizes to its label and sits inline among other controls. This row claims the full width of its container and reads as a destination within a panel.

## Variants

- `reveal`: `on-hover` (default — the shortcut and trailing action fade in on hover or `:focus-visible`) | `always` (both painted at rest, for a surface with no pointer).
- `emphasis`: `quiet` (default — `--surface-secondary` ground) | `plain` (transparent ground, hover only).

## Two targets, one row

The row and its trailing action are two controls, not one. The row occupies the full width and carries the primary action; the trailing action sits at the trailing edge and does something else with the same subject.

- Both are siblings in the DOM. The trailing action is never nested inside the row's own `<button>` or `<a>` — nested interactive elements produce an invalid accessibility tree and unpredictable activation.
- The row's own hit area stops short of the trailing action's, so a pointer never fires the wrong one.
- Each carries its own accessible name. The trailing action's name states its own verb and subject, since a screen reader reaches it without the row's context.

## Determinations

- Height `var(--list-row-standard)`, inline padding `var(--sp-0-5)`, radius `var(--radius-sm)`.
- Ground `var(--surface-secondary)` in the `quiet` variant; hover paints the theme's hover stratum over `var(--duration-100)` `var(--ease-in-out)`.
- The leading glyph sits in a circular chip at `var(--icon-size-marginalia)`, filled one stratum above the row's ground, with the glyph drawn on the `--icon-viewbox-md` grid. The chip is `var(--sp-0-75)` from the label.
- Label at the compact body size, ink `var(--text-primary)`.
- The shortcut hint (`libraries/components/shortcut-hint.md`) sits directly after the label in its `on-hover` visibility; the trailing action anchors the row's trailing edge via `margin-inline-start: auto`.
- Both revealed affordances reserve their width at rest, so the row's contents hold position when they appear.

## Accessibility

- The row is a `<button type="button">` when it acts and an `<a>` when it navigates. The trailing action is likewise its own element and carries an `aria-label` naming its verb and subject.
- Tab visits the row, then the trailing action, in source order. Neither depends on hover to be reachable: the `on-hover` reveal is triggered by `:focus-visible` as well as `:hover`, so a keyboard user sees exactly what a pointer user sees.
- The keyboard shortcut is announced through the row's `aria-keyshortcuts`, not through the visual hint, which is `aria-hidden`.
- Focus paints the foundation ring on `:focus-visible` (`foundations/accessibility.md` §18.2), on each control independently.
- Reduced motion suppresses the reveal transition; the affordances appear instantly (WCAG 2.3.3).
