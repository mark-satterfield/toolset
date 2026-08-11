---
kind: shape
name: command-palette
aliases: [command palette, search palette, quick switcher, cmd-k overlay]
status: stable
slots:
  - { name: underlying-page, required: true, accepts: [list-page] }
  - { name: palette-header, required: true, accepts: [search-glyph, search-input, close-action] }
  - { name: results, required: true, accepts: [result-rows] }
variants: []
self_contained: false
content_defaults:
  search_placeholder: "Search chats and projects"
  rows:
    - { label: "How to use the product", meta: "↵" }
    - { label: "Planning next week's release notes", meta: "Yesterday" }
---

# command-palette — Floating search palette over a list page

A centered floating search palette overlaying an application page: a header row with a leading search glyph, an input field, and a close glyph; beneath it a vertical list of result rows, each carrying a small leading icon, a primary label, and a right-aligned recency stamp. The first row shows a return-key glyph marking it as the active default. The underlying page continues to render — its own heading, search input, and list — visually dimmed beneath the palette.

The palette is a global launcher, not a list filter — distinct from an in-page search input.

## HTML skeleton

```html
<div class="palette-overlay">
  <div class="palette" role="dialog" aria-label="search">
    <header class="palette__header">
      <span class="palette__search-glyph">⌕</span>
      <input type="search" placeholder="Search chats and projects" autofocus>
      <button class="palette__close" aria-label="close">×</button>
    </header>
    <ul class="palette__results" role="listbox">
      <li role="option" aria-selected="true">
        <span class="palette__row-icon">💬</span>
        <span class="palette__row-label">How to use the product</span>
        <span class="palette__row-meta">↵</span>
      </li>
      <li role="option">
        <span class="palette__row-icon">💬</span>
        <span class="palette__row-label">Planning next week's release notes</span>
        <span class="palette__row-meta">Yesterday</span>
      </li>
    </ul>
  </div>
</div>
```

## Determinations

- Keyboard contract: ⌘K (macOS) / Ctrl+K (other) opens the palette and focuses the input; Up/Down move the active option; Enter activates the active option; Escape dismisses and returns focus to the trigger. The results list uses `role="listbox"` with `aria-activedescendant` tracking the active option.
- Result grouping: rows carry a relative recency stamp — "Today" for same-day items, "Yesterday" for the prior day, "Past week" for 2–7 days old, then an absolute date ("May 12") beyond a week. Results order most-recent-first within the current query.

Suits any application surface that benefits from a keyboard-first cross-content jumper (search across chats, files, projects, settings).
