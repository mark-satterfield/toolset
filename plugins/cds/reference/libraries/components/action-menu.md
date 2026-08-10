---
kind: component
name: action-menu
page_family: app
aliases: [popup menu, account menu, user menu, context menu, command menu, overflow actions]
status: stable
slots:
  - { name: header, required: false, accepts: [text] }
  - { name: item, required: true, accepts: [label, icon-glyph, shortcut-hint, chevron-glyph] }
  - { name: divider, required: false, accepts: [rule] }
sizing:
  panel-min-width: "--column-field-measure is the cap; the panel sizes to its longest item and never below a comfortable minimum"
  panel-padding: "--sp-0-5"
  panel-radius: "--radius-md"
  item-height: "--list-row-standard"
  item-padding: "--sp-0-5 inline"
  item-radius: "--radius-xs"
  glyph-gap: "--sp-0-75 between an item's leading glyph and its label"
  header-height: "--list-row-standard, sharing the item inline padding"
behavior:
  - "item states: rest | hover | disabled; hover paints the hover stratum over --duration-100"
  - "an item may carry a trailing shortcut-hint (the action is immediate) or a trailing chevron (the item opens a submenu) — never both"
  - "opens from a trigger that owns the open state; closes on selection, on Escape, and on pointer-down outside the panel"
accessibility:
  - "panel is role=\"menu\"; items are role=\"menuitem\"; a submenu item carries aria-haspopup=\"menu\" and aria-expanded"
  - "the header line is not an item: it is aria-hidden or exposed via the menu's aria-label, never focusable"
  - "arrow-key cycling with wrap, Home/End to the ends, Escape closes and returns focus to the trigger"
  - "dividers are decorative: role=\"separator\" with no tab stop"
token_bindings: [--surface-raised, --surface-tertiary, --border-subtle, --text-primary, --text-secondary, --text-tertiary, --list-row-standard, --radius-md, --radius-xs, --ease-in-out, --focus-ring, --sp-0-5, --sp-0-75]
composite: false
---

# Action menu

The floating panel of commands a trigger opens — an account row, an overflow glyph, a toolbar button. The menu owns its items the way a table owns its rows: what an item carries is supplied per item, not modelled as a separate entry.

Distinct from the dropdown panel (`libraries/components/dropdown-panel.md`), which reveals grouped *navigation* below a top-nav trigger. This panel carries *commands*: things that happen, plus the occasional navigation among them.

## Item anatomy

An item is a leading glyph, a label, and one optional trailing affordance:

- a **shortcut hint** (`libraries/components/shortcut-hint.md`) when the item performs its action immediately, or
- a **chevron** when the item opens a submenu.

An item carries at most one trailing affordance. A row that both fires immediately and opens a submenu describes two different contracts to the user.

## Variants

- `item-kind`: `command` (default — activates and closes the menu) | `submenu` (opens a nested panel on hover, Enter, Space, or the inline-end arrow key) | `disabled` (ink drops to `--text-tertiary`, no hover, `aria-disabled="true"`, still focusable so its presence is discoverable).
- `header`: `absent` (default) | `present` — one non-interactive line at the panel's block-start identifying whose menu this is (an account identifier, a record name).

## Determinations

- Panel: ground `var(--surface-raised)`, `1px solid var(--border-subtle)`, `var(--radius-md)`, padding `var(--sp-0-5)`, with the raised elevation from `foundations/layout.md` §11.8.
- The panel sizes to its longest item and wraps no item; a label too long for a comfortable measure is truncated with an ellipsis and carries its full text as the item's accessible name.
- Item: height `var(--list-row-standard)`, inline padding `var(--sp-0-5)`, radius `var(--radius-xs)`, glyph-to-label gap `var(--sp-0-75)`. Label at the compact body size, ink `var(--text-primary)`; leading glyph and trailing affordance at `var(--text-tertiary)`.
- Hover paints the theme's hover stratum — one step above the panel ground — over `var(--duration-100)` `var(--ease-in-out)`.
- The header line is set at the compact body size in `var(--text-secondary)` and never paints a hover state.
- Dividers are a hairline `var(--border-subtle)` rule inset to the panel's padding, with `var(--sp-0-5)` above and below. They group items; they do not label them.
- The trailing shortcut hint and the trailing chevron occupy the same trailing column, so items align whichever they carry.

## Accessibility

- The panel is `role="menu"` and each item is `role="menuitem"`. A submenu item adds `aria-haspopup="menu"` and `aria-expanded`.
- Arrow keys cycle with wrap; Home and End jump to the ends; typing a character moves to the next item starting with it. Enter and Space activate. Escape closes the panel and returns focus to the trigger that opened it.
- The inline-end arrow key opens a submenu and moves focus into it; the inline-start arrow key closes it and returns focus to the parent item.
- Dividers carry `role="separator"` and are not focusable. The header carries no role and is not focusable — it names the menu, so the trigger's `aria-label` or the menu's `aria-label` carries the same identity for a screen reader.
- Focus paints the foundation ring on `:focus-visible` (`foundations/accessibility.md` §18.2).
- Reduced motion suppresses the open transition and the hover fade; states swap instantly (WCAG 2.3.3).
