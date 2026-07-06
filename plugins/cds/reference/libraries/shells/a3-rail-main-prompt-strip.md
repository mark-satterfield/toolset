---
kind: shell
name: a3-rail-main-prompt-strip
id: A3
family: app
aliases: [quickstart shell, prompt-anchored shell, creation flow with prompt bar]
status: stable
furniture:
  - { component: left-rail, placement: left pane, notes: "same contract as A1" }
panes:
  - { name: rail, width: var(--app-shell-rail-width), collapse: "same ladder as A1: icon-only below the tablet breakpoint, drawer in the mobile-narrow range" }
  - { name: main, width: fluid (remaining viewport width), collapse: none }
  - { name: bottom-strip, width: "full width of the main column", collapse: "none — sticky to the bottom of the main column at every breakpoint" }
content_slot: { kinds: [section-container], families: [app] }
---

# A3 — Single side rail + main + bottom prompt strip

A1 plus a bottom-of-viewport prompt or action strip that stays anchored to the viewport floor while main scrolls above it.

## Partitioning

- `rail` (left) — same role as in A1.
- `main` (center, fluid) — the Section Container fills the area above the bottom strip. For a quickstart surface, main carries a multi-step breadcrumb at top, a centered empty-state prompt, and a right-side template card grid.
- `bottom-strip` (bottom, full width of the main column) — persistent input or action affordance: a "Describe your project…" text input with a send-button glyph on the right.

## Determinations

- The bottom strip spans the full width of `main` and does not overlap the rail.
- Bottom strip height is `--app-shell-bottom-strip` (`foundations/layout.md` §11.10), including `--sp-0-75` vertical padding.
- Main scrolls behind the bottom strip; the strip stays pinned to the bottom of the `main` column.

## Structural skeleton

```html
<div class="app-shell app-shell--a3">
  <nav class="app-rail" aria-label="primary">…</nav>
  <main class="app-main app-main--with-bottom-strip">
    <!-- the resolved Section Container renders here, scrolls if tall -->
  </main>
  <div class="app-bottom-strip" role="region" aria-label="primary input">
    <input type="text" placeholder="Describe your project…">
    <button class="app-bottom-strip__send" aria-label="send">…</button>
  </div>
</div>
```

## Interaction contracts

- Stickiness: the bottom strip is sticky to the bottom of the `main` column (`position: sticky; bottom: 0`), not fixed to the viewport, so it tracks the main column's left/right bounds and never overlaps the rail.
- Send button: disabled (`aria-disabled="true"`, dimmed) until the input is non-empty; while submitting it shows a spinner glyph and stays disabled until the response resolves, then returns to the enabled rest state. The button carries `aria-label="send"`.

## Frame register

- Motion is the application register: cross-fades on tab and route changes, 200ms control transitions, dropdown chevron rotation; no hero reveal animations.
- Primary-action emphasis stays reserved — the loudest CTA emphasis belongs to marketing surfaces, never inside the app frame.
- Panes paint `default` theme grounds. Code panels use the local `code` theme wrapper and stay dark in both color-modes.
- Modal dialogs center on a dimmed backdrop without blur.

## Suits

Project-creation, item-creation, and quickstart flows where a persistent prompt input must remain available no matter how the user scrolls the page. Distinct from a chat surface (where the input is the focal point) — here the prompt is one of several entry paths and the templates above are the primary visual content.

- A3 vs. A1: the bottom strip earns its space only when the prompt is the keystone of the page. A "send feedback" button does not justify the strip; a project-creation prompt does.
