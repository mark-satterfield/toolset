---
kind: component
name: notification-row
page_family: app
aliases: [notification, alert row, inbox row, message row, notice row]
status: stable
slots:
  - { name: unread-marker, required: false, accepts: [icon-glyph] }
  - { name: summary, required: true, accepts: [text] }
  - { name: detail, required: false, accepts: [text] }
  - { name: timestamp, required: true, accepts: [text] }
  - { name: row-actions, required: true, accepts: [icon-button] }
sizing:
  padding: "--sp-0-75 block, --sp-0-5 inline"
  unread-marker: "--sp-0-5 diameter in a reserved column, so read and unread rows share one inline offset"
  stack-gap: "--sp-0-25 between the summary and its detail"
behavior:
  - "the row's body is a target that opens what the notification is about and marks it read in the same act"
  - "the row's actions are separate targets and do not open the notification"
  - "clearing removes the row from the list without destroying it — the notification moves to the archive"
accessibility:
  - "the unread state is carried by the row's accessible name, never by a dot or a weight alone"
  - "each action names its verb and its notification, since actions repeat down the list"
  - "clearing announces the outcome and moves focus to the next row, so a list can be worked through by keyboard"
token_bindings: [--surface-secondary, --border-subtle, --text-primary, --text-secondary, --text-tertiary, --accent-primary, --ease-in-out, --focus-ring, --sp-0-25, --sp-0-5, --sp-0-75]
composite: true
---

# Notification row

One notification in a list: what happened, when, whether it has been read, and the controls to read or clear it.

## Unread is a word, not a dot

The unread state is part of the row's accessible name and is carried visually by a marker glyph *and* the summary's weight. A coloured dot alone fails a monochrome rendering and says nothing to a screen reader, and unread is the single most important fact about a row in this list.

The marker's column is reserved on read rows too, so the list has one inline offset and rows do not shift as they are read.

## Clearing is not deleting

Clearing removes the row from the active list and moves the notification to an archive. The notification still exists, is still findable, and is destroyed later by a retention rule rather than by the click. A control that reads as tidying up should not be the one that destroys the record.

## Variants

- `state`: `unread` (default) | `read`.
- `detail`: `absent` (default) | `present` — one supporting line beneath the summary.

## Determinations

- The row is a flex row: the unread marker column at the inline-start, the summary and detail stacked beside it, the timestamp and actions grouped at the inline-end.
- Padding `var(--sp-0-75)` block and `var(--sp-0-5)` inline; a `1px solid var(--border-subtle)` rule between adjacent rows.
- `unread`: ground `var(--surface-secondary)`, summary at weight 700 in `var(--text-primary)`, marker painted `var(--accent-primary)`.
- `read`: transparent ground, summary at weight 400 in `var(--text-secondary)`, marker column empty.
- Detail at the caption size in `var(--text-tertiary)`, one line, truncating.
- Timestamp at the caption size in `var(--text-tertiary)`, before the actions.
- Row actions are quiet glyph buttons, present at rest on every row rather than on hover — a hover-revealed action is unreachable on touch and invisible to a user scanning for what they can do.
- The row body's target and each action are siblings, following the nested-target contract in `libraries/components/action-card.md`.

## Accessibility

- The unread state is part of the row's accessible name (WCAG 1.4.1).
- Each action's accessible name joins its verb to the notification, since identical labels repeat down the list.
- Clearing announces the outcome through a polite live region and moves focus to the next row, so a list can be worked through end to end by keyboard without focus falling to the document.
- Focus paints the foundation ring on `:focus-visible` (`foundations/accessibility.md` §18.2).
