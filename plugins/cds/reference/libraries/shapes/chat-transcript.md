---
kind: shape
name: chat-transcript
aliases: [conversation, chat view, message list, thread, chat panel]
status: stable
slots:
  - { name: title-row, required: false, accepts: [text, action-menu] }
  - { name: turns, required: true, accepts: [chat-message, chat-activity-row] }
  - { name: scroll-affordance, required: false, accepts: [icon-button] }
  - { name: composer, required: true, accepts: [chat-composer] }
variants: [with-title-row, without-title-row]
self_contained: true
content_defaults: {}
---

# chat-transcript — Turns in a column above a pinned composer

The conversation surface: an optional title row, a scrolling column of turns and activity rows, and the composer pinned at the block-end.

The turns are chat-message Components (`libraries/components/chat-message.md`), the process lines are chat-activity-row (`libraries/components/chat-activity-row.md`), and the input is chat-composer (`libraries/components/chat-composer.md`). This arrangement owns the column, the scroll behaviour, and the live region.

## Determinations

- One centred column at a reading measure, not the full width of the vacant space. A transcript that spans a wide viewport makes every response unreadable, and the authored turns' inline-end alignment stops meaning anything.
- `title-row`, when present, is a sticky band at the block-start: the conversation's name at the inline-start with a menu for the actions on the conversation itself.
- Turns and activity rows sit in the column in arrival order at the turn gap from `libraries/components/chat-message.md`.
- The composer is pinned to the column's block-end and never scrolls with the turns. The turns' scroll container ends above it.
- The column is bottom-anchored: it opens scrolled to the most recent turn, and a new turn while the user is already at the bottom keeps them there.
- A user who has scrolled up is not moved. New content arriving does not yank the viewport away from what they are reading — instead `scroll-affordance` appears above the composer, naming that there is newer content, and returns them to the bottom when activated.
- A response that grows while the user is at the bottom keeps the growing edge in view without the column jittering: the scroll follows the content's block-end, not each inserted line.
- The busy indicator, while a response is being prepared and before any content has arrived, sits where that response's turn will begin, so the answer appears where the user is already looking.

## Self-contained behavior

This Shape declares `self_contained: true`. Its fragment carries its own scoped `<style>` and a scoped IIFE `<script>` implementing bottom-anchoring, the scrolled-away detection and its affordance, and the live-region wiring — scoped to its own instance so several transcripts on one page never collide.

## Accessibility

- The turn column is one polite live region declared once. Streaming response content is announced as it arrives; activity rows are not, since they are process rather than content.
- The reading order is the visual order: title, turns oldest to newest, then the composer.
- After a response completes, focus stays in the composer so the user can reply without re-finding it. Focus never jumps to an arriving turn.
- The scroll affordance is a real button naming what it does, reachable by Tab.

## Universal Section slots

Neither universal Section slot is placed by this arrangement: a transcript's content is its turns, and an eyebrow or a Section media above the column would sit between the title and the conversation.
