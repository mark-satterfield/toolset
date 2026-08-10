---
kind: component
name: action-card
page_family: shared
aliases: [resource card, card with buttons, feature card with actions, glyph card, multi-action card]
status: stable
slots:
  - { name: glyph, required: false, accepts: [icon-glyph] }
  - { name: title, required: true, accepts: [heading] }
  - { name: title-badge, required: false, accepts: [inverted-pill-badge, outline-pill-badge] }
  - { name: description, required: true, accepts: [text] }
  - { name: actions, required: true, accepts: [button] }
sizing:
  padding: "--sp-1"
  radius: "--radius-lg"
  title-gap: "--sp-0-75 between the glyph and the title"
  stack-gap: "--sp-0-5 between the title row and the description"
  action-row-gap: "--sp-0-5 between adjacent actions"
behavior:
  - "each action is its own control with its own target; activating one never activates another or the card"
  - "the card's own target, when it has one, excludes every action's hit area"
  - "hover raises the card one elevation step over --duration-150"
accessibility:
  - "an action is never nested inside the card's own interactive element — nested interactive elements produce an invalid accessibility tree"
  - "each action carries an accessible name stating its verb and its subject, since it is reached without the card's context"
  - "an icon-only action carries an aria-label; a glyph alone is not a name"
token_bindings: [--surface-raised, --border-subtle, --text-primary, --text-secondary, --text-tertiary, --radius-lg, --ease-in-out, --focus-ring, --sp-0-5, --sp-0-75, --sp-1]
composite: true
---

# Action card

A card describing one thing and offering the ways to act on it: a leading glyph and title with an optional badge, a short description beneath, and a row of one or more actions at the foot — each action going somewhere of its own.

The actions are button Components (`libraries/components/button.md`); this entry composes them and fixes the contract that lets several independent targets live inside one card.

Distinct from the link card (`libraries/components/link-card.md`), which is one target and nothing else, and from the media header card (`libraries/components/media-header-card.md`), which identifies a subject with a tinted band and carries no actions.

## Several targets in one card

A card that is itself clickable and also contains buttons has more than one target, and the relationship between them is the load-bearing part:

- Every action is a sibling of the card's own target in the DOM, never a descendant of it. An `<a>` or `<button>` inside another `<a>` or `<button>` is invalid HTML, produces an unpredictable accessibility tree, and makes activation depend on which pixel was hit.
- The card's own target, when present, is a stretched link covering the card's box. Each action sits above it with its own stacking context, so the action's hit area subtracts from the card's.
- The card's accessible name is its title. Each action's accessible name states its own verb and subject, because a screen reader user arrives at an action without having heard the card.
- Tab order is: the card's target, then each action in source order.

A card whose only affordances are its actions declares the `inert` target variant and is not clickable itself. That is the simpler shape and the better default when every action is explicit.

## Variants

- `target`: `inert` (default — the card is a container; only its actions are targets) | `whole-card` (the card carries a stretched link in addition to its actions).
- `action-emphasis`: `secondary` (default — every action is a secondary button) | `mixed` (the first action is secondary and the remainder are icon-only tertiary buttons).

## Determinations

- Card: ground `var(--surface-raised)`, `1px solid var(--border-subtle)`, `var(--radius-lg)`, padding `var(--sp-1)`.
- Title row: the glyph at `--icon-size-feature` on the `--icon-viewbox-xl` grid, `var(--sp-0-75)` from the title. Title at the body size, weight 700, ink `var(--text-primary)`. The optional badge sits inline after the title, wrapping with it.
- Description at the compact body size, ink `var(--text-secondary)`, `var(--sp-0-5)` below the title row.
- The action row anchors the card's block-end edge via `margin-block-start: auto`, so cards in a row align their actions however long their descriptions run. Adjacent actions are `var(--sp-0-5)` apart.
- Hover raises the card one elevation step (`foundations/layout.md` §11.8) over `var(--duration-150)` `var(--ease-in-out)`; the actions do not move within it.

## Accessibility

- No action is ever a descendant of the card's own target. This is the contract, not a preference.
- An icon-only action carries an `aria-label` naming its verb and subject; the glyph itself is `aria-hidden`.
- The title is a heading at the level the surrounding run establishes.
- Focus paints the foundation ring on `:focus-visible` (`foundations/accessibility.md` §18.2), independently on the card's target and on each action.
- Every action meets the tap-target floor from `foundations/accessibility.md` even in its icon-only form.
- Reduced motion suppresses the hover raise (WCAG 2.3.3).
