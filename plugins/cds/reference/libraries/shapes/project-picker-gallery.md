---
kind: shape
name: project-picker-gallery
aliases: [project picker, recent projects gallery, file picker, new-prototype gallery]
status: stable
slots:
  - { name: tab-strip, required: true, accepts: [tabs, search-input] }
  - { name: card-grid, required: true, accepts: [onboarding-card, project-cards] }
variants: []
self_contained: false
content_defaults:
  tabs: [Recent, "Your designs", Examples, "Design systems"]
  cards:
    - { kind: onboarding, title: "Learn about the design tool", link: "Quick tutorial" }
    - { kind: project, band: "Design system", title: "Design System", meta: "Your design · Apr 26", pill: "Owner" }
    - { kind: project, title: "Project Name", meta: "Your design · Apr 26", pill: "Owner" }
---

# project-picker-gallery — Tabbed project cards with an onboarding lead card

A project/file picker filling the vacant space — it suits an application Shell with a form-sidebar Section, as the Recent-tab view: a tab strip on the left with a right-aligned search input, then a responsive grid of cards. The first card is an onboarding card (small art glyph + title + tutorial link on a tinted ground); the rest are project cards (top color-band header + thumbnail panel + title + recency stamp + owner pill). The number of project cards is content-driven.

Creation is owned by the Shell's form sidebar, not by this gallery — the user lands here to resume a recent project or follow the onboarding path.

## HTML skeleton

```html
<nav class="canvas-tabs" role="tablist">
  <button role="tab" aria-selected="true">Recent</button>
  <button role="tab">Your designs</button>
  <button role="tab">Examples</button>
  <button role="tab">Design systems</button>
  <input type="search" placeholder="Search…" class="canvas-tabs__search">
</nav>
<section class="project-card-row">
  <article class="project-card project-card--onboarding">
    <div class="project-card__art">…</div>
    <h3>Learn about the design tool</h3>
    <a class="link">Quick tutorial</a>
  </article>
  <article class="project-card">
    <header class="project-card__band">Design system</header>
    <div class="project-card__thumb"></div>
    <h3>Design System</h3>
    <p>Your design · Apr 26</p>
    <span class="pill">Owner</span>
  </article>
</section>
```

## Determinations

- Card hover/selection: on hover a card raises with the faint-elevation shadow (`foundations/layout.md` §11.8) and its border steps from `--border-subtle` to `--border-strong` (the hover/emphasis border step) over a 150ms `--ease-in-out` transition (suppressed under reduced-motion). The card is a link, so `:focus-visible` paints the standard focus ring (`foundations/accessibility.md` §18.2).
- Card overflow: cards wrap to additional rows — a responsive grid, `repeat(auto-fill, minmax(var(--app-shell-list-column), 1fr))` (the `--app-shell-list-column` token, `foundations/layout.md` §11.10, as the card floor) — not horizontal scroll, so every project stays reachable without a horizontal scrollbar.
