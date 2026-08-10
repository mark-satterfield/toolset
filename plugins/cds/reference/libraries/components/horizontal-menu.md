---
kind: component
name: horizontal-menu
page_family: shared
aliases: [horizontal nav, nav links, menu row, inline menu, top nav links]
status: stable
slots:
  - { name: items, required: true, accepts: [item] }
sizing:
  item-gap: "--sp-1-5 between adjacent items"
  glyph-gap: "--sp-0-5 between an item's label and a trailing caret, when it carries one"
behavior:
  - "item states: rest | hover | current"
  - "an item with children is a dropdown-panel trigger, not a bare link (libraries/components/dropdown-panel.md)"
  - "items are <a> anchors because they navigate — not <button> — except a dropdown trigger, which is a <button>"
accessibility:
  - "the menu is a list of links; it takes no role of its own and is never a role=\"menubar\""
  - "the current item carries aria-current=\"page\""
  - "sequential Tab order; arrow-key cycling belongs to the dropdown panels that descend from a trigger, never to the top-level run"
token_bindings: [--text-primary, --text-secondary, --ease-in-out, --focus-ring, --sp-0-5, --sp-1-5]
composite: false
---

# Horizontal menu

An inline run of navigable items laid out along a single axis. The menu owns its items the way a table owns its rows: what each item carries — a plain label, a label with a trailing caret opening a panel — is supplied per item, not modelled as a separate entry.

## Variants

- `item-kind`: `link` (default) | `trigger` — a trigger carries `aria-haspopup="menu"` and `aria-expanded`, and opens a dropdown-panel whose structure and keyboard contract live in `libraries/components/dropdown-panel.md`.

## Determinations

- The menu is a single-axis run with `var(--sp-1-5)` between adjacent items.
- Item type: the small body sans size (calibrates to 15px), weight 400.
- Rest item ink `var(--text-secondary)`; hover and current ink `var(--text-primary)`.
- Hover transition: color over `var(--duration-100)` `var(--ease-in-out)`.
- Items never centre themselves within their container — where the run sits is the contract of the Shape positioning it.
- A trigger carries a trailing caret at `var(--sp-0-5)` from its label; the caret rotates on `aria-expanded="true"`.

## Accessibility

- Items are `<a>` elements, except a trigger, which is a `<button>`. The current destination carries `aria-current="page"`.
- The run introduces no `role` of its own and is never a `role="menubar"` — there is no arrow-key navigation between top-level items. Arrow-key cycling is reserved for the dropdown panels that descend from a trigger.
- Focus paints the foundation ring on `:focus-visible` (`foundations/accessibility.md` §18.2).
- Reduced motion: honor `prefers-reduced-motion: reduce` by suppressing the colour and caret transitions. (WCAG 2.3.3.)
