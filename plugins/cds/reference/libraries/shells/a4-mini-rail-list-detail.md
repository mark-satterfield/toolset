---
kind: shell
name: a4-mini-rail-list-detail
id: A4
family: app
aliases: [master-detail, three-pane shell, list and detail, library browser shell]
status: stable
furniture:
  - { component: left-rail, placement: left pane, notes: "icon-only variant: quick-action icons plus an account avatar at the bottom; no labels at rest" }
panes:
  - { name: outer-rail, width: var(--app-shell-mini-rail), collapse: "persists between the tablet and desktop breakpoints; below the tablet breakpoint the whole surface becomes a single-column drill-down" }
  - { name: list-column, width: var(--app-shell-list-column), collapse: "persists between the tablet and desktop breakpoints; below the tablet breakpoint the list fills the viewport" }
  - { name: detail-viewport, width: fluid (remaining viewport width), collapse: "narrows between the tablet and desktop breakpoints; below the tablet breakpoint it pushes over the list with a back affordance" }
content_slot: { kinds: [section-container], families: [app] }
---

# A4 — Mini-icon rail + list column + detail viewport

Compressed icon-only outer rail on the left, a workspace list column to its right, and a fluid detail viewport filling the remaining width. The three panes persist across routes; the detail viewport is the only pane that swaps.

## Partitioning

- `outer-rail` (left, icon-only) — narrow vertical strip carrying quick-action icons (new, search, settings, etc.) and an account avatar at the bottom. No labels at rest.
- `list-column` (center-left) — workspace-scoped list with the workspace switcher at its top, a header row (e.g., "Items"), an optional search affordance, and repeating rows for each item. The list supports a tree: parent items expand to nested children (for example, a parent record expanding to its child files). Sub-items indent under section headers and carry no icon.
- `detail-viewport` (right, fluid) — full read/edit view of the item selected in the list. Carries its own page heading, metadata strip (Added by / Last updated / Trigger), description block, and the item's primary content body. No topbar sits above the detail viewport.

## Determinations

- Outer rail width `--app-shell-mini-rail` (`foundations/layout.md` §11.10 — the icon-only rail width shared with A1's collapsed state).
- Outer-rail icons render at `--icon-size-app-rail` (`foundations/imagery.md` §16.1 icon scale) with a `--sp-1-5` vertical gap between icons.
- List column width `--app-shell-list-column` (`foundations/layout.md` §11.10). The column may carry a host-provided drag handle on its right edge; the handle constrains resizing to the token's declared 280–320px range, and the chosen width persists per user.
- No divider between the outer rail and the list column; subtle whitespace alone separates them.
- Detail viewport is fluid; inner cards cap between `--column-medium` and `--app-shell-detail-card-max` (`foundations/layout.md` §11.10), with `--sp-1-5` to `--sp-2` inner padding.
- Card radii: `--radius-md` on stat cards; `--radius-lg` on hero-promo and empty-state cards.
- Selection model: single-select. Selecting a row loads that item in the detail viewport and marks the row active (filled pill on `--surface-tertiary` + `aria-current="page"`). When no row is selected — including first load — the detail viewport renders the empty-state card (centered framed icon + "Select an item to view it here" helper).
- Collapse ladder: at and above the desktop breakpoint (`foundations/responsive.md` §17.1) all three panes show. Between the tablet and desktop breakpoints the icon rail and list column persist and the detail viewport narrows. Below the tablet breakpoint the surface becomes a single-column drill-down: the list fills the viewport and selecting a row pushes the detail view over it with a back affordance.
- The rail and list rows share the rail component's structural contract (`libraries/components/left-rail.md`).

## Typography register

- Page title: Headline 5, weight 600.
- Section headers in the rail and list column: Body 3, weight 500, ink at `--text-tertiary`.
- Item row label: Body 3, weight 400.
- Stat caption: Body 3.
- Stat display numeral: Primary Sans, weight 600–700 (calibrates to 32–40px), prefixed by `$` for currency.
- Form-field label: Body 3 sans, above the field.

## Component vocabulary

- Stat cards and empty-state cards.
- Hero promo cards for in-app announcements.
- Toggle switches with the chromatic active fill (`--switch-active-bg`).
- Destructive buttons with `--error-fill` background and light ink.
- Centered modal dialogs on a dimmed backdrop without blur (optional inline modal for create/edit dialogs).

## Structural skeleton

```html
<div class="app-shell app-shell--a4">
  <nav class="app-mini-rail" aria-label="quick actions">
    <button class="app-mini-rail__icon" aria-label="new">+</button>
    <button class="app-mini-rail__icon" aria-label="search">⌕</button>
    …
    <div class="app-mini-rail__avatar">A</div>
  </nav>
  <nav class="app-list-column" aria-label="items">
    <header class="app-list-column__header">
      <h2>Items</h2>
      <div class="app-list-column__actions">⌕ +</div>
    </header>
    <ul class="app-list-column__group">
      <li class="app-list-column__section-header">Group label</li>
      <li class="app-list-column__item is-active is-expanded">
        Item name
        <ul class="app-list-column__nested">
          <li>Child item</li>
          <li>Nested group ›</li>
        </ul>
      </li>
      <li class="app-list-column__item">Another item</li>
      …
    </ul>
  </nav>
  <main class="app-detail-viewport">
    <header class="app-detail-viewport__title-row">
      <h1>Item name</h1>
      <div class="app-detail-viewport__toggle">…</div>
    </header>
    <dl class="app-detail-viewport__meta">
      <dt>Added by</dt><dd>You</dd>
      <dt>Last updated</dt><dd>May 19, 2026</dd>
      <dt>Trigger</dt><dd>Manual + auto</dd>
    </dl>
    <section class="app-detail-viewport__body">…</section>
  </main>
</div>
```

## Frame register

- Motion is the application register: cross-fades on tab and route changes, 200ms control transitions (toggle slide), dropdown chevron rotation; no hero reveal animations. Calm motion, dense content, clear active states.
- Primary-action emphasis stays reserved — the loudest CTA emphasis belongs to marketing surfaces, never inside the app frame.
- Panes paint `default` theme grounds. Code panels use the local `code` theme wrapper and stay dark in both color-modes.
- Modal dialogs center on a dimmed backdrop without blur.

## Suits

Library/registry browsing surfaces where the user moves laterally across many items with one focused at a time (skills library, connector registry, document library, label library, contact list with detail).

- A4 vs. A1 with sub-nav: A4 is correct only when lateral movement across items is a frequent action. When users typically pick one item and remain focused on it, A1 with a single list-and-detail page composition is enough.
