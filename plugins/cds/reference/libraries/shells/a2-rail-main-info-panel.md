---
kind: shell
name: a2-rail-main-info-panel
id: A2
family: app
aliases: [editor with help panel, workspace with side help, three-column editor shell]
status: stable
furniture:
  - { component: left-rail, placement: left pane, notes: "same contract as A1" }
panes:
  - { name: rail, width: var(--app-shell-rail-width), collapse: "same ladder as A1: icon-only below the tablet breakpoint, drawer in the mobile-narrow range" }
  - { name: main, width: fluid (between rail and info-panel), collapse: none }
  - { name: info-panel, width: var(--app-shell-info-panel), collapse: "visible at and above the desktop breakpoint; between the tablet and desktop breakpoints → on-demand drawer behind a \"?\" help trigger in the main header; below the tablet breakpoint → drawer-only" }
content_slot: { kinds: [section-container], families: [app] }
---

# A2 — Single side rail + main + right info panel

A1 plus a persistent right column carrying contextual help, info, or supplementary content for the work in `main`.

## Partitioning

- `rail` (left) — same role as in A1.
- `main` (center, fluid) — primary workspace where the user composes or edits. For a composition surface, this holds a stack of editor cards plus an action row beneath.
- `info-panel` (right, fixed width) — contextual surface that scrolls independently of `main`. It holds a help guide: heading + bulleted tips + a doc deep-link card. The panel is part of the chrome, not part of the page content — it persists across composition states.

## Determinations

- Rail width `--app-shell-rail-width` (matches A1). Info panel width `--app-shell-info-panel` (`foundations/layout.md` §11.10). Main pane is fluid between them.
- No divider between main and info panel; a `--sp-2-5` gutter alone separates them.
- The info panel scrolls independently of `main`: `overflow-y: auto`, `height: 100vh`, sticky to the right edge.
- Collapse ladder: the info panel stays visible at and above the desktop breakpoint (`foundations/responsive.md` §17.1). Between the tablet and desktop breakpoints it collapses to an on-demand drawer opened by a "?" help trigger in the main header. Below the tablet breakpoint it is drawer-only.

## Structural skeleton

```html
<div class="app-shell app-shell--a2">
  <nav class="app-rail" aria-label="primary">…</nav>
  <main class="app-main">
    <header class="app-main__title-row">
      <h1>Untitled</h1>
      <div class="app-main__actions">…</div>
    </header>
    <section class="app-workspace">
      <!-- editor cards / composition surface -->
    </section>
  </main>
  <aside class="app-info-panel" aria-label="contextual help">
    <h2>Getting started</h2>
    <ul>…</ul>
    <a class="info-panel__link-card">Learn more in the docs</a>
  </aside>
</div>
```

## Frame register

- Motion is the application register: cross-fades on tab and route changes, 200ms control transitions, dropdown chevron rotation; no hero reveal animations.
- Primary-action emphasis stays reserved — the loudest CTA emphasis belongs to marketing surfaces, never inside the app frame.
- Panes paint `default` theme grounds. Code panels use the local `code` theme wrapper and stay dark in both color-modes.
- Modal dialogs center on a dimmed backdrop without blur.

## Suits

Creative tools and editors where the main work surface benefits from persistent, non-modal help (welcome guides, contextual tips, doc deep-links). The help must remain visible while the user works; help that should only appear on demand belongs in A1 with a popover.

- A2 vs. A1: A2 is correct only when contextual help is genuinely persistent and stays relevant across composition states; a one-shot welcome banner belongs inline at the top of A1's main, not in an info panel.
- A2 vs. A5: A2's info panel is help, not input. Configuration-that-renders belongs in A5's form sidebar.
