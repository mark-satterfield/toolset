---
kind: component
name: row-action-menu
aliases: [row actions, per-row menu, record actions, inline actions, quick actions]
status: stable
slots:
  - { name: quick-action, required: false, accepts: [icon-button] }
  - { name: overflow-trigger, required: true, accepts: [icon-button] }
  - { name: menu, required: true, accepts: [action-menu] }
sizing:
  height: "matches the row's height so the cluster never inflates the row"
  gap: "--sp-0-25 between adjacent quick actions"
  trigger: "--icon-size-marginalia square hit area"
behavior:
  - "the cluster is present and visible on every row at rest — it does not appear only on hover"
  - "quick actions are the one or two verbs used most; everything else lives behind the overflow trigger"
  - "activating an action never activates the row"
accessibility:
  - "each control is a sibling of the row's own target, never nested inside it"
  - "every action names its verb and its record, since a screen reader reaches it without the row's context"
  - "the menu follows the action-menu keyboard contract and returns focus to the trigger on close"
token_bindings: [--text-tertiary, --text-primary, --surface-tertiary, --icon-size-marginalia, --radius-xs, --ease-in-out, --focus-ring, --sp-0-25]
composite: true
---

# Row action menu

The verbs available on one record, in that record's row: one or two direct controls plus an overflow trigger opening the rest.

Composes the action menu (`libraries/components/action-menu.md`) for the overflow panel. Distinct from the kebab menu (`libraries/components/kebab-menu.md`), which anchors to a record's *header* on a detail surface; this cluster repeats on every row of a table.

## Always visible

The cluster paints at rest on every row, not on hover. A hover-revealed action is undiscoverable on touch, invisible to a user scanning for what they can do, and unreachable without a pointer. The controls are quiet at rest — `var(--text-tertiary)` glyphs on no ground — and rise to `var(--text-primary)` on row hover, which is a change in emphasis rather than in existence.

## Variants

- `quick-actions`: `none` (default — overflow trigger only) | `one` | `two`. Beyond two, the column starts competing with the record's own data.

## Determinations

- The cluster occupies the row's trailing cell, pinned to the inline-end so it holds its position while the table scrolls horizontally.
- Each control is an `--icon-size-marginalia` square hit area with `var(--radius-xs)`, `var(--sp-0-25)` apart.
- Glyphs paint `var(--text-tertiary)` at rest and `var(--text-primary)` while the row is hovered or holds focus, over `var(--duration-100)` `var(--ease-in-out)`.
- Hovering an individual control paints the theme's hover stratum behind that control only, so the target under the pointer is unambiguous.
- The cluster's height matches the row's; it never inflates the row, in either density.
- The overflow menu opens anchored to its trigger, flipping to the block-start when the row is near the container's end so the panel stays in view.

## Accessibility

- Every control is a `<button>` and a sibling of the row's own target, never a descendant, following the nested-target contract in `libraries/components/action-card.md`.
- Each accessible name joins the verb to the record — a column of "delete" buttons is indistinguishable to a screen reader without it.
- The overflow panel follows the action menu's keyboard contract: arrow-key cycling, Escape closes, and focus returns to the trigger.
- Every control meets the tap-target floor from `foundations/accessibility.md` in its icon-only form.
- Focus paints the foundation ring on `:focus-visible` (§18.2).
