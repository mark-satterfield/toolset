---
kind: component
name: vertical-menu
page_family: shared
aliases: [vertical nav, menu list, nav list, sidebar menu, stacked menu]
status: stable
slots:
  - { name: items, required: true, accepts: [item] }
  - { name: group-label, required: false, accepts: [label] }
sizing:
  item-height: "--list-row-compact (the dense list-row step; calibrates to 36px)"
  item-padding: "--sp-0-5 inline; an item carrying a leading glyph inflates its inline-start padding to reserve the glyph column (calibrates to 40px)"
  item-gap: "--sp-0-75 between a leading glyph and its label; calibrates to 12px"
  item-radius: "--radius-sm"
  stack-gap: "--sp-0-25 between adjacent items"
behavior:
  - "item states: rest | hover | current"
  - "the current item paints a filled pill — no left bar, no border indicator; the fill alone marks the selection"
  - "items are <a> anchors because they navigate — not <button>"
accessibility:
  - "the menu is a list of links; it takes no role of its own and introduces no arrow-key composite-widget semantics"
  - "the current item carries aria-current=\"page\""
  - "sequential Tab order; foundation focus ring on :focus-visible; reduced motion suppresses the hover transition"
token_bindings: [--surface-tertiary, --text-primary, --text-secondary, --text-tertiary, --list-row-compact, --radius-sm, --ease-in-out, --focus-ring, --sp-0-25, --sp-0-5, --sp-0-75]
composite: false
---

# Vertical menu

A stacked run of navigable items, optionally divided by group labels. The menu owns its items the way a table owns its rows: the item is the menu's internal structure, and what each item carries — a glyph and a label, a label alone, a label and a trailing count — is supplied per item, not modelled as a separate entry.

## Variants

- `glyph-column`: `absent` (base inline padding) | `present` (inline-start padding inflates to reserve the glyph column). Applied consistently across a group so the labels align.

## Determinations

- The menu is a vertical stack with `var(--sp-0-25)` between adjacent items.
- Item height `var(--list-row-compact)`; inline padding `var(--sp-0-5)`; glyph-to-label gap `var(--sp-0-75)`; border-radius `var(--radius-sm)`.
- Item type: the compact body size (calibrates to 14px), weight 400.
- Current item: the full item paints at `var(--radius-sm)` with ground `var(--surface-tertiary)` — the deepest stratification within the theme — and ink `var(--text-primary)`.
- Rest item: transparent ground, ink `var(--text-secondary)`.
- Hover item: ground at the theme's hover stratum — one step above the surrounding surface, one below the current item's — ink `var(--text-primary)`.
- Hover transition: color, background-color, border-color, text-decoration-color, fill, and stroke over `var(--duration-150)` `var(--ease-in-out)`.
- Group labels sit above the run they introduce, in `var(--text-tertiary)`.

## Accessibility

- Items are `<a>` elements; the current destination carries `aria-current="page"`.
- The menu introduces no `role` of its own and no arrow-key navigation — the surrounding landmark decides the navigational contract, and a list of links is not a `role="menu"`.
- Focus paints the foundation ring on `:focus-visible` (`foundations/accessibility.md` §18.2).
- Reduced motion: honor `prefers-reduced-motion: reduce` by suppressing the hover transition; the state swaps instantly. (WCAG 2.3.3.)
