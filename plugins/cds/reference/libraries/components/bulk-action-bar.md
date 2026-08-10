---
kind: component
name: bulk-action-bar
page_family: app
aliases: [selection bar, batch actions, bulk operations, multi-select toolbar, selection toolbar]
status: stable
slots:
  - { name: count, required: true, accepts: [text] }
  - { name: clear-selection, required: true, accepts: [tertiary-link] }
  - { name: actions, required: true, accepts: [button] }
  - { name: destructive-action, required: false, accepts: [destructive-button] }
sizing:
  height: "--list-row-standard"
  padding: "--sp-0-5 inline"
  radius: "--radius-md"
  gap: "--sp-0-5 between adjacent actions"
behavior:
  - "appears when a selection exists and clears with the selection; it never occupies space at rest"
  - "the selection survives sorting and pagination within a result set, and the count states the true total"
  - "a destructive bulk action requires a confirmation naming the count"
accessibility:
  - "the bar's arrival is announced through a live region stating the count, without moving focus"
  - "each action names its verb and the number of records it will affect"
  - "the bar is reachable by Tab immediately after the selection control that produced it"
token_bindings: [--surface-raised, --border-subtle, --text-primary, --text-secondary, --radius-md, --ease-in-out, --focus-ring, --sp-0-5]
composite: true
---

# Bulk action bar

The verbs that apply to a multi-record selection, with the count of what is selected and a way to let it go. Present only while a selection exists.

## The count is load-bearing

Every label states scope. The bar names how many records are selected, and each action names how many it will affect, because a bulk verb whose reach is unstated is the easiest destructive mistake in an application. "Delete" and "Delete 47 opportunities" are different offers.

Selection persists across sorting and pagination within one result set, so the count can exceed what is on screen. That makes stating it mandatory rather than decorative.

## Variants

- `placement`: `pinned` (default — the bar pins above the table's block-end edge, floating over the rows) | `inline` — the bar takes the filter row's position, displacing it while a selection exists.
- `destructive`: `absent` (default) | `present` — a destructive verb, separated from the others.

## Determinations

- Height `var(--list-row-standard)`, inline padding `var(--sp-0-5)`, radius `var(--radius-md)`, ground `var(--surface-raised)` with a `1px solid var(--border-subtle)` hairline and the raised elevation from `foundations/layout.md` §11.8.
- The count sits at the inline-start at the compact body size in `var(--text-primary)`, followed by the clear-selection link in `var(--text-secondary)`.
- Actions group at the inline-end via `margin-inline-start: auto`, `var(--sp-0-5)` apart, as secondary buttons.
- The destructive action is separated from the rest by `var(--sp-1)` and a hairline, and uses the destructive button Component (`libraries/components/destructive-button.md`). Distance is what prevents a mis-aimed click.
- Entrance is an opacity transition over `var(--duration-150)` `var(--ease-in-out)` with no translation; reduced motion drops it.
- The `pinned` placement never covers the last row: the table's scroll container reserves the bar's height while the bar is present.

## Confirmation

A destructive bulk action opens a confirmation dialog (`libraries/components/dialog.md`) whose message names the count and what is irreversible about it. The confirmation's primary action restates the verb and count rather than saying "confirm" — the last thing a user reads before an irreversible action should be what the action is.

A non-destructive bulk action does not confirm. A confirmation on a reversible verb trains the user to dismiss confirmations.

## Accessibility

- The bar's arrival is announced through a polite live region stating the count. Focus does not move — the user is mid-selection.
- Each action's accessible name states its verb and the count it applies to.
- The bar is reachable by Tab immediately after the selection control that produced it, so a keyboard user who has just selected rows finds the verbs next rather than at the end of the table.
- Focus paints the foundation ring on `:focus-visible` (`foundations/accessibility.md` §18.2).
