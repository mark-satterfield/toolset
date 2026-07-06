---
kind: shell
name: a1-rail-main
id: A1
family: app
aliases: [app shell, sidebar layout, single rail app, dashboard shell]
status: stable
furniture:
  - { component: left-rail, placement: left pane, notes: "workspace switcher at top, grouped nav tree, account block at bottom" }
panes:
  - { name: rail, width: var(--app-shell-rail-width), collapse: "below the tablet breakpoint → icon-only at var(--app-shell-mini-rail); in the mobile-narrow range → drawer behind a hamburger in a slim top bar" }
  - { name: main, width: fluid (remaining viewport width), collapse: none }
content_slot: { kinds: [section-container], families: [app] }
---

# A1 — Single side rail + main

Persistent left navigation rail occupies the left edge full-height; the remaining viewport width is a single scrollable main pane.

## Partitioning

- `rail` (left, fixed width) carries the global navigation tree: workspace switcher at top, grouped section headers, repeating icon + label item rows, and a bottom user/account block. The rail is the only navigation surface for this shell.
- `main` (right, fluid) carries one Section Container. The main pane owns its own page heading; the rail does not duplicate it.
- No top app bar inside the application chrome — the browser chrome above is the only top strip. The page heading sits directly on the main pane.

## Determinations

- Rail width is fixed at `--app-shell-rail-width` (`foundations/layout.md` §11.10); main width is fluid.
- Collapse ladder: below the tablet breakpoint (`foundations/responsive.md` §17.1) the rail collapses to an icon-only rail at `--app-shell-mini-rail` (`foundations/layout.md` §11.10) — labels hidden, icons centered. In the mobile-narrow range it collapses entirely to a drawer triggered by a hamburger in a slim top bar, per `foundations/responsive.md` §17.4.
- Section headers in the rail are tertiary-ink small labels. The active row is a filled pill (the rail component's active-row treatment, `libraries/components/left-rail.md`).

## Structural skeleton

```html
<div class="app-shell app-shell--a1">
  <nav class="app-rail" aria-label="primary">
    <div class="app-rail__workspace-switcher">…</div>
    <ul class="app-rail__group">
      <li class="app-rail__section-header">Build</li>
      <li class="app-rail__item is-active">Composer</li>
      <li class="app-rail__item">Files</li>
      …
    </ul>
    <div class="app-rail__account">…</div>
  </nav>
  <main class="app-main">
    <!-- the resolved Section Container renders here -->
  </main>
</div>
```

## Interaction contracts

- Rail rows follow the rail component contract (`libraries/components/left-rail.md`): rest is transparent ground with secondary ink; hover paints a raised ground with primary ink over a 150ms `--ease-in-out` color transition (suppressed under `prefers-reduced-motion: reduce`); the active row paints a filled pill at `--radius-sm` on `--surface-tertiary` and carries `aria-current="page"`.
- Focus: rows expose the host project's global `:focus-visible` ring per `foundations/accessibility.md` §18.2 (`outline: 2px solid var(--focus-ring); outline-offset: 1px`).
- Keyboard: rows are `<a>` anchors inside a `<nav>` landmark — standard sequential Tab order, Enter activates; no arrow-key composite-widget semantics.

## Frame register

- Motion is the application register: cross-fades on tab and route changes, 200ms control transitions, dropdown chevron rotation; no hero reveal animations.
- Primary-action emphasis stays reserved — the loudest CTA emphasis belongs to marketing surfaces, never inside the app frame.
- Panes paint `default` theme grounds. Code panels use the local `code` theme wrapper and stay dark in both color-modes.
- Modal dialogs center on a dimmed backdrop without blur.

## Suits

Operational dashboards, analytics views, settings screens, list/empty states, code-as-content screens — any single-focus screen where the rail's navigation tree is enough chrome. A1 is the default app shell.

- A1 vs. A2: A1 hosts on-demand help (a "?" popover) and one-shot welcome banners inline at the top of main; A2 is for genuinely persistent help.
- A1 vs. A3: A1 is correct unless a bottom prompt is the page's primary input.
- A1 vs. A4: A1 with a list-and-detail page composition in main is correct when users typically pick one item and remain focused on it; A4 is for frequent lateral movement across items.
