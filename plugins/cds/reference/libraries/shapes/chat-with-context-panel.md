---
kind: shape
name: chat-with-context-panel
aliases: [chat with sidebar, conversation with outputs, chat and artifacts, transcript with context]
status: stable
slots:
  - { name: transcript, required: true, accepts: [chat-transcript] }
  - { name: panel-groups, required: true, accepts: [heading, chat-attachment-card, text] }
  - { name: panel-toggle, required: true, accepts: [icon-button] }
variants: [panel-open, panel-collapsed]
self_contained: true
content_defaults: {}
---

# chat-with-context-panel — A transcript beside what it produced

The conversation column with a companion panel at the inline-end listing what the conversation has produced and what it is drawing on: outputs, referenced files, progress.

The transcript is the chat-transcript arrangement (`libraries/shapes/chat-transcript.md`) unchanged. This arrangement adds the panel beside it and the rule for how the two share the space.

## Why a panel rather than more turns

Files a conversation produces accumulate. Found only inline, the third one is already scrolled out of reach, and finding it means re-reading the conversation. The panel is a stable index of them — the same items, addressable at any time, in the order they were produced.

The panel restates; it does not relocate. An attachment stays in the turn that produced it *and* appears in the panel, so the conversation still reads as a whole.

## Determinations

- Two columns filling the vacant space: the transcript takes the dominant span, the panel a fixed inline size at the inline-end.
- The panel is a column of labelled groups, each a heading over its items, collapsible independently. Groups are ordered most-actionable first — what was produced, then what was referenced.
- Items are chat-attachment-card Components (`libraries/components/chat-attachment-card.md`) at their compact form, or plain rows for items with no file behind them.
- A group's heading carries its count, so a collapsed group still reports what it holds.
- The panel scrolls independently of the transcript.
- `panel-toggle` collapses the panel to its edge, returning the width to the transcript. The collapsed state persists for the surface, since a user who wants the room wants it for the whole session.
- The transcript's column keeps its reading measure when the panel collapses; the extra width becomes margin rather than a wider transcript.
- Below the tablet breakpoint (`foundations/responsive.md` §17.1) the panel becomes a side drawer (`libraries/components/side-drawer.md`) opened by the same toggle, rather than stacking beneath the transcript where it would be unreachable without scrolling past the whole conversation.

## Self-contained behavior

This Shape declares `self_contained: true`. Its fragment carries its own scoped `<style>` and a scoped IIFE `<script>` implementing the panel collapse, the per-group disclosure, and the narrow-viewport drawer promotion — scoped to its own instance.

## Accessibility

- The panel is a labelled `<aside>` region, so a screen reader can reach it directly rather than through the whole transcript.
- Each group is a disclosure whose control carries `aria-expanded` and whose heading names the group and its count.
- The toggle carries `aria-expanded` and an accessible name saying what it shows or hides.
- Reading order is transcript then panel, so a linear reader meets the conversation before its index.
