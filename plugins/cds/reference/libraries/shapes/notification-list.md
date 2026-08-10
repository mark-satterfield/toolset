---
kind: shape
name: notification-list
page_family: app
aliases: [notification center, inbox, alerts list, notification panel, activity inbox]
status: stable
slots:
  - { name: header-row, required: true, accepts: [heading, button] }
  - { name: scope-tabs, required: false, accepts: [pill-tab-strip] }
  - { name: rows, required: true, accepts: [notification-row] }
  - { name: empty-state, required: true, accepts: [empty-state-card] }
variants: [panel, page]
self_contained: false
content_defaults: {}
---

# notification-list — Notifications with their bulk verbs at the head

A header row carrying the list's name and the verbs that apply to all of it, optional scope tabs, then the rows.

The rows are notification-row Components (`libraries/components/notification-row.md`); this arrangement owns the header, the scoping, and the empty states.

## Determinations

- The header row is the list's name with its unread count, and a mark-all-read action at the inline-end. The count is the true unread total, not the number rendered.
- `scope-tabs`, when present, divide the list into unread, all, and archived. Archived is reachable here rather than hidden, because clearing a notification moves it there and a user who cleared something by accident needs a route back to it.
- Rows stack with a hairline between them, no gap. A notification list is scanned, and gaps between rows halve how many are visible at once.
- The list scrolls within its own container. In the `panel` variant that container is a fixed-height popover anchored to its trigger; in the `page` variant it is the vacant space.
- The empty state differs by scope and says which one it is: no unread notifications is a different message from no notifications at all, and a filtered-empty archive is a third. One generic empty message for all three tells the user nothing about whether to change scope.
- A notification arriving while the list is open is inserted at the top without moving the reader's scroll position, and the header's count updates.
- Rows are never removed from under the pointer. A row cleared by its own action animates out; a row that becomes read elsewhere changes state in place rather than leaving the list.

## Accessibility

- The rows are a list, so their count and each row's position are announced.
- The header's unread count is a live region, so it is heard when it changes.
- Scope tabs are a tablist controlling the list region.
- Clearing a row moves focus to the next row, so the list can be worked through by keyboard end to end.
