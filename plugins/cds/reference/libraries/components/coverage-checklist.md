---
kind: component
name: coverage-checklist
page_family: app
aliases: [topic coverage, completeness checklist, progress checklist, covered items, checklist]
status: stable
slots:
  - { name: item, required: true, accepts: [text, icon-glyph] }
  - { name: completeness-signal, required: true, accepts: [text] }
  - { name: item-action, required: false, accepts: [tertiary-link] }
sizing:
  item-height: "--list-row-compact"
  item-padding: "--sp-0-5 inline"
  marker: "--icon-size-inline on the --icon-viewbox-sm drawing grid"
  gap: "--sp-0-5 between an item's marker and its label"
behavior:
  - "items may be completed in any order; the list records what has been covered, it does not sequence it"
  - "a skipped item stays in the list as skipped, so it can be returned to"
  - "the completeness signal states what remains, and states plainly when nothing does"
accessibility:
  - "each item's state is carried by its marker glyph and its accessible name, never by ink or a tick's colour alone"
  - "the list is a real list so its length and each item's position are announced"
  - "the completeness signal is a live region so progress is heard as it changes"
token_bindings: [--text-primary, --text-secondary, --text-tertiary, --status-positive-bg, --list-row-compact, --icon-size-inline, --focus-ring, --sp-0-5]
composite: false
---

# Coverage checklist

What has been covered, what has been skipped, and what remains — for work that has no fixed order.

Distinct from the stepper (`libraries/components/stepper.md`), which is a linear sequence with a current position and a next step. Nothing here is next. The items can be addressed in any order, revisited after being covered, and skipped without blocking anything.

## Skipped is a state, not a removal

An item the user chose to skip stays in the list, marked as skipped. Removing it would hide a decision the user may want to reverse, and would make the list's length depend on the path taken through it.

Skipped and remaining are visually distinct, because "I decided not to" and "I have not got to it" are different, and only one of them is worth returning to.

## Variants

- `item-state`: `remaining` | `covered` | `skipped`.
- `item-action`: `absent` (default) | `present` — a link to address or revisit that item directly from the list.

## Determinations

- Each item is a row at `var(--list-row-compact)`: marker at the inline-start, label beside it `var(--sp-0-5)` away, optional action at the inline-end.
- `remaining`: an outline marker, label in `var(--text-primary)`.
- `covered`: a filled check marker in `var(--status-positive-bg)`, label in `var(--text-secondary)`.
- `skipped`: a distinct marker glyph — not an empty one and not a check — label in `var(--text-tertiary)`. Three states need three glyph shapes; two glyphs and a tint is two states with a decoration.
- The completeness signal sits at the list's block-end, stating how many remain and naming them where the count is small enough to name.
- When nothing remains the signal says so in plain words rather than showing a full bar. A bar at its end is a shape the reader must interpret; a sentence is not.
- The list draws no connector between items. A connector implies sequence, and there is none.

## Accessibility

- Item state is carried by the marker's shape and by the item's accessible name (WCAG 1.4.1).
- The list is a real `<ul>` so its length and each item's position are announced.
- The completeness signal is a polite live region, so covering an item is heard as progress rather than requiring the user to go and re-read the list.
- Item actions are real links or buttons naming the item they address.
