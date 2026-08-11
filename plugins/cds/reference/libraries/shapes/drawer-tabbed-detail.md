---
kind: shape
name: drawer-tabbed-detail
aliases: [record drawer, tabbed detail panel, detail drawer contents, record inspector]
status: stable
slots:
  - { name: identity, required: true, accepts: [text] }
  - { name: verdict, required: false, accepts: [score-verdict] }
  - { name: stage-control, required: false, accepts: [select-menu] }
  - { name: tab-strip, required: true, accepts: [pill-tab-strip] }
  - { name: panels, required: true, accepts: [content] }
variants: [with-verdict, without-verdict]
self_contained: true
content_defaults: {}
---

# drawer-tabbed-detail — One record, divided into tabs

The contents of a side drawer showing a single record: a header carrying who the record is and its current standing, then a tab strip dividing everything else into panes.

The panel it fills is the side drawer Component (`libraries/components/side-drawer.md`), which owns the drawer's edge, entrance, focus trap, and close. This arrangement owns what is inside it.

## Determinations

- The header is the drawer's sticky header band, arranged as three parts: `identity` at the inline-start, `verdict` and `stage-control` grouped after it, and the drawer's close control at the inline-end.
- `identity` is the record's name over its qualifying line — the two facts that tell the user which record this is.
- `verdict`, when present, is a score-verdict Component (`libraries/components/score-verdict.md`) at its `compact` density; its breakdown lives in one of the panes rather than in the header.
- `stage-control` is a select menu (`libraries/components/select-menu.md`) editing the record's state directly from the header. A change made here is the same change made anywhere else in the build: the surface that opened the drawer reflects it without being reopened.
- The tab strip sits beneath the header, still within the sticky band, so the panes scroll under it and the user never loses their place among the tabs.
- Each pane scrolls independently within the drawer's body and remembers its own scroll position while the drawer stays open.
- The first pane is the record's structured fields. Later panes hold the longer material — notes, history, an activity timeline, a score breakdown — in the order the surface declares.
- A pane with no content renders the empty state Component (`libraries/components/empty-state-card.md`) rather than an absent tab. Removing a tab because it happens to be empty makes the tab set vary between records.

## Deep-linkable panes

Each pane is addressable, so a link can open the drawer with a named pane already selected. The selected pane is part of the surface's address, not hidden interaction state — a user who is sent to a record's history should arrive at its history.

## Self-contained behavior

This Shape declares `self_contained: true`. Its fragment carries its own scoped `<style>` and a scoped IIFE `<script>` implementing the tablist keyboard contract from `foundations/accessibility.md` — arrow-key movement, `aria-selected` management, and the pane-to-address binding — scoped to its own instance.

## Accessibility

- The tab strip is a `role="tablist"`, each tab a `role="tab"` with `aria-controls`, and each pane a `role="tabpanel"` with `aria-labelledby`.
- The header's identity is the drawer's accessible name, so opening announces which record was opened.
- Changing the stage announces the new state through a polite live region and leaves focus on the control.
