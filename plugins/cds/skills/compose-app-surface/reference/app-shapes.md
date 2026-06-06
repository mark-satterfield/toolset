# App shapes

App-shape catalog for `compose-app-surface` — whole-viewport partitionings (rails, main, side panels, bottom strips) plus the recurring intra-shell page compositions that fill the main area. Non-interchangeable with `reference/shapes.md` (S0–S28), which is scoped to vertically-scrolling landing/marketing pages. Use this catalog when the surface being built is an authenticated application screen rather than a landing-page section stack.

Disjoint naming scheme:

- Shell layouts are letter-coded: `A1`, `A2`, `A3`, `A4`, `A5`.
- Page shapes inside a shell are descriptive names, not letter codes.

Every entry below is a complete, self-contained, brand-neutral spec. Measurements, token bindings, breakpoint behavior, and interaction contracts are definitive and resolve against the foundations (`reference/foundations/responsive.md`, `layout.md`, `accessibility.md`, `motion.md`) and `reference/components.md`.

---

## Shell layouts

### A1 — Single side rail + main

One-line description: Persistent left navigation rail occupies the left edge full-height; remaining viewport width is a single scrollable main pane.

Partitioning rule:

- `rail` (left, fixed width) carries the global navigation tree: workspace switcher at top, grouped section headers (Build / Projects / Analytics / Code / Manage / Organization settings), repeating icon + label item rows, and a bottom user/account block. The rail is the only navigation surface for shells of this type.
- `main` (right, fluid width filling remaining) carries one page composition (greeting + KPIs, settings form, code block, list/empty state, etc.). The main pane owns its own page heading; the rail does not duplicate it.
- No top app bar inside the application chrome — the browser chrome above is the only top strip. The page heading sits directly on the main pane.

Proportions:

- Rail width is fixed; main width is fluid.
- Rail width: `256px` (`--rail-width`), per `components.md` §12.5 "App shell left rail". Below the `md` breakpoint (700px) the rail collapses to a 56px icon-only rail (labels hidden, icons centered); below 480px it collapses entirely to a drawer triggered by a hamburger in a slim top bar, per responsive.md §17.4.
- Section headers in the rail are tertiary-ink small labels. Active row is a filled pill (matches `components.md` §12.5 "App shell left rail" active-row treatment).

Structural skeleton:

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
    <!-- one page shape from the catalog below -->
  </main>
</div>
```

Suits: operational dashboards, analytics views, settings screens, list/empty states, code-as-content screens — any single-focus screen with no secondary chrome.

Interaction contracts:

- Rail rows follow `components.md` §12.5: rest is transparent ground with `text-200` ink; hover paints `bg-400` ground and `text-100` ink over a 150ms `--ease-in-out` color transition (suppressed under `prefers-reduced-motion: reduce`); the active row paints a filled pill at radius `8px` and carries `aria-current="page"`.
- Focus: rows expose the host project's global `:focus-visible` ring per accessibility.md §18.2 (`outline: 2px solid var(--role-focus-ring); outline-offset: 1px`).
- Keyboard: rows are `<a>` anchors inside a `<nav>` landmark — standard sequential Tab order, Enter activates; no arrow-key composite-widget semantics.

---

### A2 — Single side rail + main + right info panel

One-line description: A1 plus a persistent right column carrying contextual help, info, or supplementary content for the work in `main`.

Partitioning rule:

- `rail` (left) — same role as in A1.
- `main` (center, fluid) — primary workspace where the user composes or edits. For a composition surface, this holds a stack of editor cards (system, user, assistant, user) plus an action row beneath.
- `info-panel` (right, fixed width) — contextual surface that scrolls independently of `main`. It holds a help guide: heading + bulleted tips + a doc deep-link card. The panel is part of the chrome, not part of the page content — it persists across composition states.

Proportions:

- Rail `256px` (`--rail-width`, matches A1).
- Info panel `320px` (`--info-panel-width`).
- Main pane is fluid between them.
- No divider between main and info panel; a `--sp-2-5` (32–40px) gutter alone separates them.
- The info panel scrolls independently of `main`: `overflow-y: auto`, `height: 100vh`, sticky to the right edge.

Responsive behavior: the info panel stays visible at and above the `lg` breakpoint (1024px). Between `md` (700px) and `lg` it collapses to an on-demand drawer opened by a "?" help trigger in the main header. Below `md` it is drawer-only.

Structural skeleton:

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

Suits: creative tools and editors where the main work surface benefits from persistent, non-modal help (welcome guides, contextual tips, doc deep-links). Use when help should remain visible while the user works; do not use for help that should only appear on demand.

---

### A3 — Single side rail + main + bottom prompt strip

One-line description: A1 plus a bottom-of-viewport prompt or action strip that stays anchored to the viewport floor while main scrolls above it.

Partitioning rule:

- `rail` (left) — same role as in A1.
- `main` (center, fluid) — page composition fills the area above the bottom strip. For a quickstart surface, main carries a multi-step breadcrumb at top, a centered empty-state prompt, and a right-side template card grid.
- `bottom-strip` (bottom, fixed full-width of main column) — persistent input or action affordance. It holds a "Describe your project…" text input with a send-button glyph on the right.

Proportions:

- Bottom strip is full-width of `main` (does not overlap the rail).
- Bottom strip height: `64px` including `--sp-0-75` (12px) vertical padding.
- Main scrolls behind the bottom strip; the strip stays pinned to the bottom of the `main` column (`position: sticky; bottom: 0`, anchored to the main column rather than the viewport so it never overlaps the rail).

Structural skeleton:

```html
<div class="app-shell app-shell--a3">
  <nav class="app-rail" aria-label="primary">…</nav>
  <main class="app-main app-main--with-bottom-strip">
    <!-- page shape fills here, scrolls if tall -->
  </main>
  <div class="app-bottom-strip" role="region" aria-label="primary input">
    <input type="text" placeholder="Describe your project…">
    <button class="app-bottom-strip__send" aria-label="send">…</button>
  </div>
</div>
```

Suits: project-creation / item-creation / quickstart flows where a persistent prompt input must remain available no matter how the user scrolls the page. Distinct from a chat surface (input is the focal point) — here the prompt is one of several entry paths and the templates above are the primary visual content.

Interaction contracts:

- Stickiness: the bottom strip is sticky to the bottom of the `main` column (`position: sticky; bottom: 0`), not fixed to the viewport, so it tracks the main column's left/right bounds and never overlaps the rail.
- Send button: disabled (`aria-disabled="true"`, dimmed) until the input is non-empty; once submitting it shows a spinner glyph and stays disabled until the response resolves, then returns to the enabled rest state. The button carries an `aria-label="send"`.

---

### A4 — Mini-icon rail + list column + detail viewport

One-line description: Compressed icon-only outer rail on the left, a workspace list column to its right, and a fluid detail viewport filling the remaining width.

Partitioning rule:

- `outer-rail` (left, icon-only) — narrow vertical strip carrying quick-action icons (plus, search, plus-on-circle, settings, etc.) and an account avatar at the bottom. No labels at rest.
- `list-column` (center-left) — workspace-scoped list with a header row (e.g., "Items"), an optional search affordance, and repeating rows for each item in the list. The list supports a tree: parent items can expand to nested children (for example, a parent record expanding to its child files).
- `detail-viewport` (right, fluid) — full read/edit view of the item selected in the list. Carries its own page heading, metadata strip (Added by / Last updated / Trigger), description block, and the item's primary content body.

Proportions:

- Outer rail `56px` wide (matches the icon-only collapsed-rail width used elsewhere in this catalog).
- List column `280px` wide (`--list-column-width`, per layout.md §11.2 application-shell pane).
- Detail viewport fluid, with `24–32px` inner card padding.

Selection model: single-select. Selecting a row loads that item in the detail viewport and marks the row active (filled pill + `aria-current="page"`). When no row is selected — including first load — the detail viewport renders the empty-state card (centered framed icon + "Select an item to view it here" helper).

Responsive behavior: at and above the `lg` breakpoint (1024px) all three panes show. Between `md` (700px) and `lg`, the icon rail and list column persist and the detail viewport narrows. Below `md` the surface becomes a single-column drill-down: the list fills the viewport and selecting a row pushes the detail view over it with a back affordance.

This shell is the application-side equivalent of `components.md` §12.5 "App shell left rail" — A4 fills out the structural shape that section defines.

Structural skeleton:

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

Suits: library/registry browsing surfaces where the user moves laterally across many items with one focused at a time (skills library, connector registry, document library, label library, contact list with detail).

---

### A5 — Form-driven sidebar + canvas/gallery

One-line description: Left sidebar drives configuration via form controls; right pane is a canvas or gallery showing the result of the current configuration (or a gallery of templates that, when picked, populate the form).

Partitioning rule:

- `form-sidebar` (left, fixed width) — labelled form controls grouped into a configuration panel: name input, design-system picker, mode segment (wireframe / high-fidelity), primary Create CTA at the bottom of the panel. Below the form sit project-scope labels ("Only you can see your project by default.") and a docs + identity footer.
- `canvas-or-gallery` (right, fluid) — either a working canvas (live preview of the configured object) or a gallery (Recent / Your designs / Examples / Design systems tab strip with project cards or template cards beneath). The right pane may be a project gallery or an examples gallery with per-template descriptor cards on the right edge.

Proportions:

- Form sidebar `320px` wide (`--form-sidebar-width`).
- Canvas/gallery fluid, taking remaining width.
- The canvas/gallery has its own horizontal tab strip ("Recent / Your designs / Examples / Design systems") at the top.

Sidebar role across modes: in gallery mode the sidebar still drives creation — its Create CTA starts a new object; in editing/canvas mode the sidebar's controls bind to the active object so editing a control updates the canvas live. The sidebar does not swap to a different role between modes; only the right pane changes between gallery and canvas.

Tab-strip routing: the canvas tab strip is URL-routed (each tab is a distinct route segment so a tab is shareable and survives reload), with local state mirroring the active tab for instant paint.

Responsive behavior: at and above `lg` (1024px) both panes show side by side. Between `md` (700px) and `lg` the sidebar narrows to its `280px` floor. Below `md` the sidebar collapses to a top sheet opened by a "Configure" trigger, and the canvas/gallery fills the viewport.

Structural skeleton:

```html
<div class="app-shell app-shell--a5">
  <aside class="app-form-sidebar" aria-label="configuration">
    <header class="app-form-sidebar__brand">Design Tool</header>
    <nav class="app-form-sidebar__mode-tabs" role="tablist">
      <button role="tab" aria-selected="true">Prototype</button>
      <button role="tab">Slide deck</button>
      <button role="tab">From template</button>
      <button role="tab">Other</button>
    </nav>
    <form class="app-form-sidebar__form">
      <label>Project name <input type="text"></label>
      <label>Design system <select>…</select></label>
      <fieldset class="app-form-sidebar__segment">
        <legend class="sr-only">Fidelity</legend>
        <label><input type="radio" name="fidelity" value="wireframe">Wireframe</label>
        <label><input type="radio" name="fidelity" value="high" checked>High fidelity</label>
      </fieldset>
      <button type="submit" class="app-form-sidebar__primary">+ Create</button>
    </form>
    <footer class="app-form-sidebar__footer">
      <span>Docs</span>
      <span>Alex</span>
      <span>Alex's Organization</span>
    </footer>
  </aside>
  <main class="app-canvas">
    <nav class="app-canvas__tabs" role="tablist">
      <button role="tab">Recent</button>
      <button role="tab">Your designs</button>
      <button role="tab" aria-selected="true">Examples</button>
      <button role="tab">Design systems</button>
    </nav>
    <div class="app-canvas__body">
      <!-- gallery cards or live canvas -->
    </div>
  </main>
</div>
```

Suits: creative/design tools (prototype builders, slide editors, generator entry screens) where configuration is parametric and the canvas is the work product. Distinct from A2 (info panel is help, not input) — in A5 the sidebar drives the canvas.

---

## Page shapes

Page shapes describe what fills the `main` pane of a shell. They are reusable across shells where the structure fits; a "Settings form" page shape, for example, can fill A1's main pane or A4's detail viewport. Page shapes are named descriptively, not letter-coded.

### Greeting + KPI card row + content stack

One-line description: Page heading (greeting form), followed by a horizontal row of 3 KPI cards, followed by a token/usage card, followed by a recent-activity or empty-list card.

Section sequence inside it:

1. Greeting heading row (`<h1>` like "Good morning, Alex") + right-side action cluster ("New project", "Create a project").
2. KPI card row (3 cards side-by-side: each carries a small label, a large primary metric, and a right-side action — "Add funds" / "Setup" — or a status microcopy).
3. Single full-width token-volume / activity card (label + sparkline placeholder + right-side action).
4. Single full-width "Recently created" or empty-state card (icon + helper text + primary CTA).

Structural skeleton:

```html
<header class="page-header page-header--greeting">
  <h1>Good morning, Alex</h1>
  <div class="page-header__actions">
    <a class="btn-tertiary">New project</a>
    <button class="btn-primary">Create a project</button>
  </div>
</header>
<section class="kpi-row">
  <article class="kpi-card">…</article>
  <article class="kpi-card">…</article>
  <article class="kpi-card">…</article>
</section>
<section class="activity-card">…</section>
<section class="empty-activity-card">…</section>
```

Suits: operational dashboards that open a workspace — the home page of an application shell. Greeting form personalizes the screen; KPI row gives the at-a-glance state; bottom card gives next-action affordance.

Determinations:

- Greeting branch logic keys off local time: "Good morning" before 12:00, "Good afternoon" from 12:00 to 17:59, "Good evening" from 18:00 onward.
- Card spacing: KPI cards sit in a flex/grid row with `--sp-1-5` (24px) gap; the row stacks to the next full-width card with `--sp-2-5` (32–40px) vertical gap. Card inner padding is `--sp-2` (28–32px).

---

### Filter strip + KPI grid + chart with empty state

One-line description: Filter chip row at top, 2×2 or 1×4 KPI tile grid below, then a tall chart panel beneath that — on first run all data tiles render "No data" state.

Section sequence inside it:

1. Filter chip row: a "Group by" pill, a "Project" pill, a "Model" pill, a "Range" pill, then a right-aligned download glyph button.
2. KPI grid: 4 tiles in a single row, each carrying a small label, a "$0.00" or similar metric, an optional inline donut/sparkline glyph, and a microcopy explainer underneath ("Usage can only be broken down by project.").
3. Chart panel: a card spanning full main width, with a heading ("Daily token cost"), a Y-axis with monetary tick labels, an X-axis with date tick labels, and a centered "No data" plate when empty.

Structural skeleton:

```html
<section class="filter-strip">
  <button class="filter-chip">Group by <span>Model</span> ▾</button>
  <button class="filter-chip">Project <span>All</span> ▾</button>
  <button class="filter-chip">Model <span>All</span> ▾</button>
  <button class="filter-chip">Range <span>Month to date</span> ▾</button>
  <button class="filter-chip filter-chip--icon" aria-label="download">↓</button>
</section>
<section class="kpi-grid kpi-grid--four">
  <article class="kpi-tile">…</article>
  <article class="kpi-tile">…</article>
  <article class="kpi-tile">…</article>
  <article class="kpi-tile">…</article>
</section>
<section class="chart-panel chart-panel--empty">
  <header class="chart-panel__title">Daily token cost</header>
  <div class="chart-panel__body chart-panel__body--empty">
    <p class="chart-panel__empty-label">No data</p>
  </div>
</section>
```

Suits: cost analytics, usage analytics, performance analytics — any screen that combines filter narrowing with summary tiles and a time-series chart. Render the "No data" state on first run; switch to populated state when data arrives.

Determinations:

- Empty vs. populated state: the chart axes, tick labels, and panel chrome render in both states — only the plotted series differs. In the empty state the plot area shows a centered "No data" plate over the static axes; when data arrives the plate is removed and the series draws into the same axes (no relayout). Tick density stays constant.
- Filter chips are dropdown triggers: each carries `aria-haspopup="menu"` and `aria-expanded`, and on click opens a single-select menu popover anchored beneath the chip. Selecting a value updates the chip label and re-queries the tiles and chart. The download chip is a direct action (exports the current view), not a popover.

---

### Multi-step breadcrumb + central empty state + template grid + bottom prompt

One-line description: Numbered step breadcrumb pinned at the top of main; below it, a two-column body — left column carries an empty-state heading + bottom prompt strip, right column carries a search-able templates panel.

Spec values below are representative for a desktop viewport (~1347px wide).

Section sequence inside main:

1. **Step breadcrumb** — anchored at the top of main (`--sp-1-5`, 24px, from the top edge). Full spec in `components.md` §14 Stepper. Width adapts: ~200px at narrow viewports (icons only); grows to fit labels at viewport ≥ 1400px.
2. **Two-column body** (NOT centered empty-state; the body splits into two columns side-by-side):
   - **Left column** (~328px wide): heading "What do you want to build?" + helper sentence "Describe your project or start with a template." + bottom prompt strip pinned at the bottom of this column.
   - **Right column** (711px wide): the templates panel — a self-contained card with 16px padding, 12px radius, 0.5px subtle border on `bg-bg-100` background. Contains: an H2 "Browse templates" + a `Search templates` input + a 2-column grid of 10 template cards.
3. The bottom prompt strip is NOT shell-A3's full-width strip — it sits inside the left column, pinned near the column's bottom edge.

### Templates panel (right column)

- Container: 711 × 762px, padding 16px, border `0.5px solid hsl(var(--border-300))`, border-radius 12px, background `hsl(var(--bg-100))`, vertical flex with 16px gap.
- Header H2 "Browse templates": Primary Sans, 16px / weight 600.
- Search input: full container width (678px), height 36px. Full spec in `components.md` §14 Search field.
- Template grid: `display: grid`, `grid-template-columns: 1fr 1fr` (2 equal cols, ~333px each), `gap: 12px`, 10 cards, vertical scroll on overflow (`overflow-y-auto`, `auto-rows-min`).
- Template card: ~333 × 79px, padding 12px, border `0.5px solid hsl(var(--border-300))`, border-radius 8px, transparent background, `cursor: pointer`, `role="button"`, `tabindex="0"`, hover background `hsl(var(--bg-300))`, `transition` on hover. Vertical flex layout: title 14px `hsl(var(--text-100))` weight 400 → 2px top-margin → description 12px `hsl(var(--text-500))`.

### Left column

- Heading "What do you want to build?" — H1 28px / weight 600, positioned in the vertical center of the left column.
- Bottom prompt strip wrapper: 328 × 66px, pinned near the column bottom, padding `8px 8px 8px 16px`, border `1px solid hsl(var(--border-300))`, border-radius 12px, background `hsl(var(--bg-000))` (white), with the faint-elevation box-shadow from layout.md §11.8. `display: flex`, `align-items: end`, `gap: 8px`, `cursor: text`.
- Bottom prompt textarea: 266 × 48px, font-size 14px (`text-sm`), color `hsl(var(--text-100))`, transparent background, padding `4px 0` (`py-1 px-0`), `resize: none`, `border: none`, `outline: none`, `[field-sizing:content]` (CSS field-sizing for auto-growing textareas), placeholder `Describe your project…` color `hsl(var(--text-500))`.

### Structural skeleton (simplified)

```html
<!-- Top: stepper -->
<ol class="flex min-w-0 items-center gap-3"><!-- see components.md §14 Stepper --></ol>

<!-- Body: two-column flex/grid -->
<section class="quickstart-body grid grid-cols-[1fr_711px] gap-6 h-full">
  <div class="quickstart-body__left flex flex-col justify-between">
    <div class="empty-state text-center my-auto">
      <h1>What do you want to build?</h1>
      <p>Describe your project or start with a template.</p>
    </div>
    <div class="prompt-strip flex cursor-text items-end gap-2 rounded-xl border border-border-300 bg-bg-000 py-2 pl-4 pr-2 shadow-sm">
      <textarea class="hide-focus-ring min-w-0 flex-1 resize-none border-none bg-transparent px-0 py-1 text-sm text-text-100 outline-none placeholder:text-text-500" placeholder="Describe your project…"></textarea>
      <button class="send-btn" aria-label="send">…</button>
    </div>
  </div>
  <div class="quickstart-body__right border-0.5 border-border-300 rounded-xl p-4 flex flex-col gap-4 overflow-hidden bg-bg-100">
    <h2>Browse templates</h2>
    <div class="search-wrap bg-bg-000 border border-border-300 hover:border-border-200 transition-colors h-9 px-3 py-2 flex items-center gap-2 rounded-lg">
      <svg class="size-4" aria-hidden="true"><!-- magnifying glass --></svg>
      <input type="search" placeholder="Search templates" class="flex-1 bg-transparent p-0 outline-none text-xs text-text-100 placeholder:text-text-500">
    </div>
    <div class="grid grid-cols-2 gap-3 auto-rows-min overflow-y-auto pb-5">
      <div class="border-0.5 border-border-300 rounded-lg p-3 flex cursor-pointer flex-col overflow-hidden text-sm transition hover:bg-bg-300" role="button" tabindex="0">
        <div class="text-text-100">Blank project</div>
        <div class="text-text-500 mt-0.5 text-xs">A blank starting point…</div>
      </div>
      <!-- 9 more template cards -->
    </div>
  </div>
</section>
```

Suits: multi-step creation/onboarding flows where both a "start blank" path (left column prompt) and a "start from a template" path (right column gallery) are presented side-by-side, with a persistent step indicator at the top.

Determinations:

- **Active-step visual** — the current step's circle uses `--text-100` for both its border and its numeral; completed steps use a filled accent circle with a check glyph; future steps use `--text-500` ink on a transparent circle with a `--border-300` ring.
- **Click behavior on a template card** — clicking a card populates the prompt strip with that template's starter text and advances the breadcrumb to step 2. The card carries `role="button"` and `tabindex="0"`; Enter and Space activate it.
- **Bottom-strip elevation** — the wrapper uses the faint-elevation shadow from layout.md §11.8 (the closest "raised input" surface token).

---

### Hero promo card + KPI pair + chart pair

One-line description: Page heading at top right, a full-width hero promotional card with title/body/CTA on the left and decorative art thumbnail on the right, then a 1×2 grid of KPI tiles, then a 1×2 grid of chart cards, then an info footer note.

Section sequence inside it:

1. Page heading row (`<h1>` + right-side period picker like "< May 2026 >").
2. Hero promo card: title (e.g., "Build faster with our coding tool") + 1–2-line body + primary "Get started" CTA on the left, decorative thumbnail/art on the right.
3. KPI pair (2 tiles): "Lines of code accepted" / "Suggestion accept rate" — each tile is a label + a large primary metric.
4. Chart pair (2 cards side-by-side): "Activity" / "Usage" — each card with title, axis, baseline ticks, and a legend ("users · sessions" / "users · usage").
5. Info-note footer strip: small icon + helper sentence with embedded link ("Usage figures are estimates for analytics purposes. For details, refer to the usage dashboard.").

Structural skeleton:

```html
<header class="page-header">
  <h1>Product Name</h1>
  <div class="page-header__period-picker">‹ May 2026 ›</div>
</header>
<section class="hero-promo-card">
  <div class="hero-promo-card__text">
    <h2>Build faster with your team</h2>
    <p>Everything your team needs to ship, in one place…</p>
    <button class="btn-primary">Get started ›</button>
  </div>
  <div class="hero-promo-card__art">…</div>
</section>
<section class="kpi-row kpi-row--two">
  <article class="kpi-tile">Items processed <strong>0</strong></article>
  <article class="kpi-tile">Completion rate <strong>0.0%</strong></article>
</section>
<section class="chart-row chart-row--two">
  <article class="chart-card">Activity …</article>
  <article class="chart-card">Usage …</article>
</section>
<aside class="info-note">
  ⓘ Usage figures are estimates… <a>usage dashboard</a>.
</aside>
```

Suits: product-tier or feature-specific overview screens that combine a promo (CTA to onboard or upgrade) with at-a-glance metrics.

Determinations:

- Hero-card art treatment: inline SVG that inherits the `--accent-heroes` slot via `currentColor` (per motion.md §15.6) so it recolors per theme without per-theme artwork. No raster, no animation.
- KPI tile width: the KPI pair spans the full main width split into two equal columns (`1fr 1fr`, `--sp-1-5` gap); the chart pair below uses the same two-column track so the tile and chart columns align vertically.

---

### Empty list state — centered icon + helper + CTA

One-line description: Page heading and subhead at top, a column-header strip beneath (mimicking the table that would render once populated), then a centered empty state — small framed icon glyph, helper line, and a primary CTA.

Section sequence inside it:

1. Page heading row: `<h1>` ("Webhooks") + 1-line subhead ("Webhook endpoints receive event notifications when things happen in your workspace.") + right-side primary CTA ("+ Add webhook endpoint").
2. Column-header strip: a horizontal row of column labels (ID / Name / Status / Created at) drawn lightly, the table's header without any rows beneath it.
3. Centered empty-state plate: small framed icon glyph + 1-line "No webhook endpoints yet" + 1-line helper ("Create one to start receiving event notifications.") + a secondary "+ Add webhook endpoint" button beneath the helper.

Structural skeleton:

```html
<header class="page-header">
  <div>
    <h1>Webhooks</h1>
    <p class="page-header__subhead">Webhook endpoints receive event notifications…</p>
  </div>
  <button class="btn-primary">+ Add webhook endpoint</button>
</header>
<div class="table-headers">
  <span>ID</span><span>Name</span><span>Status</span><span>Created at</span>
</div>
<section class="empty-state">
  <div class="empty-state__icon" aria-hidden="true">🔗</div>
  <p class="empty-state__title">No webhook endpoints yet</p>
  <p class="empty-state__helper">Create one to start receiving event notifications.</p>
  <button class="btn-secondary">+ Add webhook endpoint</button>
</section>
```

Suits: any list/table view where the user has not yet created the first item. The doubled-CTA (top-right + center) is intentional — the top-right keeps the action accessible from any list state, and the center plate makes the empty case its own moment.

Determinations:

- The column-header strip persists once rows exist and becomes the live table header — the same header row that the empty state previews, now with data rows rendering beneath it. No relayout between empty and populated states.
- Icon framing: the empty-state glyph sits inside a circle-stroke frame — a 48px circle with a `1px` `--border-300` ring and no fill, the glyph centered in `--text-500` ink.

---

### Settings form — two-column field groups + destructive zone

One-line description: Page heading, then a top metadata row (Organization name / Members), then form sections grouped as labelled field rows in a 2-column grid, ending with a destructive action button, followed by an info card and a single toggle row.

Section sequence inside it:

1. Page heading (`<h1>` "Organization").
2. Top metadata row: 2 labelled values rendered side-by-side ("Organization name" / "Members"), display-only (no inputs).
3. Address field group: `<label>` + `<input>` for line 1, then a second `<input>` for line 2 beside it.
4. Country/State/City/Postal field group: a 4-column row with `<select>` (country), `<input>` (state), `<input>` (city), `<input>` (postal code).
5. Inline read-only identifier row (e.g., "Organization ID: 7a6d6c1d-…" with a copy glyph).
6. Destructive action row: a red "Delete organization" button, on its own line, no other controls beside it.
7. Info card beneath the form: icon + sentence ("Collaborate with friends and teammates by setting up an organization") + right-aligned "Set up organization" CTA.
8. Standalone toggle row: title + helper + toggle switch on the right ("Allow creating new projects in the default workspace").

Structural skeleton:

```html
<header class="page-header"><h1>Organization</h1></header>
<dl class="settings-meta-row">
  <dt>Organization name</dt><dd>Alex's Individual Org</dd>
  <dt>Members</dt><dd>1</dd>
</dl>
<section class="settings-field-group">
  <label>Primary business address</label>
  <div class="field-row field-row--2col">
    <input type="text" value="5988 Colby Hunt Ct.">
    <input type="text" placeholder="Line 2">
  </div>
  <div class="field-row field-row--4col">
    <label>Country <select>…</select></label>
    <label>State or province <input value="VA"></label>
    <label>City <input value="Haymarket"></label>
    <label>Postal code <input value="20169"></label>
  </div>
</section>
<div class="readonly-identifier-row">
  <span>Organization ID: 7a6d6c1d-…</span>
  <button aria-label="copy">⧉</button>
</div>
<section class="destructive-zone">
  <button class="btn-destructive">Delete organization</button>
</section>
<aside class="info-card">
  <span class="info-card__icon">👥</span>
  <span class="info-card__text">Collaborate with friends and teammates by setting up an organization</span>
  <button class="btn-tertiary">Set up organization</button>
</aside>
<section class="toggle-row">
  <div>
    <h3>Allow creating new projects in the default workspace</h3>
    <p>Allow users to create new projects in the default workspace. Disabling this setting does not affect existing projects or disable Composer usage.</p>
  </div>
  <input type="checkbox" role="switch">
</section>
```

Suits: organization-level, profile-level, or workspace-level settings screens that combine identification (read-only metadata), editable fields, an at-the-bottom destructive action, and one or more standalone toggle rows for cross-cutting preferences.

Determinations:

- Field-group width caps: the 2-col row caps at `max-width: 32rem` (512px); the 4-col row spans full width and wraps to 2-up below the `md` breakpoint. Labels sit above their inputs (not beside) at every breakpoint, per the field-group composition spec below.
- Save model: submit-button save. Edits stage locally and a "Save changes" primary button (disabled until a field is dirty) commits them; there is no save-on-blur. This makes the destructive action and the field edits two clearly separate commits.

---

### Stacked setting cards with toggles + destructive zone

One-line description: A vertical stack of setting cards, each card carrying a section title, a 1–2-paragraph explanation, and one or more controls (toggle, button, or both); destructive actions live inside the cards they belong to, not in a separate zone at the bottom.

Section sequence inside it:

1. Setting card 1 — "Data retention period": title + body paragraph (with inline links) + a row carrying a read-only value ("30 day retention period") and a right-aligned "Contact support ›" link action.
2. Setting card 2 — "Allow user feedback": title + body + right-aligned toggle.
3. Setting card 3 — "Join our Development Partner Program" (with a "NEW" pill next to the title): title + 2 body paragraphs + a right-aligned primary "Join" button.
4. Setting card 4 — "Allow product metrics logging": title + body + right-aligned toggle, plus an inline destructive sub-row beneath the body ("Delete all collected metrics data. This action cannot be undone." + a red "Delete data" button).

Each card is full-width of the main pane. Cards are visually separated by spacing, not dividers.

Structural skeleton:

```html
<article class="setting-card">
  <h2>Data retention period</h2>
  <p>The data retention period only applies to inputs and outputs sent via the host API…</p>
  <div class="setting-card__control-row">
    <span>30 day retention period</span>
    <a class="link">Contact support ›</a>
  </div>
</article>
<article class="setting-card">
  <h2>Allow user feedback</h2>
  <p>Allow users to send feedback on model response…</p>
  <input type="checkbox" role="switch" class="setting-card__toggle">
</article>
<article class="setting-card">
  <h2>Join our Development Partner Program <span class="pill pill--new">NEW</span></h2>
  <p>You can be an active partner in the product's development…</p>
  <p>By joining this program, you agree to our <a>Service Specific Terms…</a></p>
  <button class="btn-primary">Join</button>
</article>
<article class="setting-card setting-card--with-destructive">
  <header>
    <h2>Allow product metrics logging</h2>
    <input type="checkbox" role="switch" class="setting-card__toggle" checked>
  </header>
  <p>Enable metrics collection to track product usage…</p>
  <div class="setting-card__destructive-sub-row">
    <span>Delete all collected metrics data. This action cannot be undone.</span>
    <button class="btn-destructive">Delete data</button>
  </div>
</article>
```

Suits: privacy/security/feature-flag screens where each setting is independently scoped and needs its own explanation. Distinct from the two-column field-group form (Organization) — these are not editable text fields but standalone preference cards.

Determinations:

- Card treatment: each card is `0.5px solid --border-300` border on the page surface (no tint, no shadow) at radius `--radius-xl`, with `--sp-2` inner padding. The figure/ground work is the hairline border, per layout.md §11.8.
- Toggle alignment: the toggle pins to the top-right of the card, vertically aligned with the card title (grid `[1fr_auto]`), so the control is in a consistent position across all cards regardless of body length.

---

### Code block as primary content + actions

One-line description: Page heading, one-line subhead with a usage instruction, then a full-width code block as the page's only primary content, with a language picker on the top-left and Copy/View-Docs actions on the top-right.

Section sequence inside it:

1. Page heading (`<h1>` "Batches").
2. Subhead one-liner ("No batches have been created in the **Default** workspace. Copy the template below to set up your first batch.").
3. Code block panel:
   - Top bar carrying a language picker on the left ("Python ▾") and Copy Code + View Docs actions on the right (each as a glyph + label).
   - Body holds a monospaced code listing with line numbers and syntax highlighting (verbatim sample shown).

Structural skeleton:

```html
<header class="page-header"><h1>Batches</h1></header>
<p class="page-subhead">No batches have been created in the <strong>Default</strong> workspace. Copy the template below to set up your first batch.</p>
<section class="code-panel">
  <header class="code-panel__bar">
    <button class="code-panel__lang-picker">Python ▾</button>
    <div class="code-panel__actions">
      <button>⧉ Copy Code</button>
      <button>📄 View Docs</button>
    </div>
  </header>
  <pre class="code-panel__body"><code>
import vendor_sdk  # placeholder — host project's chosen SDK

client = vendor_sdk.Client(…)
batch_job = client.batch_jobs.create(
  requests=[…]
)
print(batch_job)
  </code></pre>
</section>
```

Suits: developer-facing list/empty surfaces where the API-call template is the most useful empty state. The code itself is the call-to-action — the user copies and runs it elsewhere.

Determinations:

- Language picker: a dropdown trigger (`aria-haspopup="menu"`, `aria-expanded`) offering the host project's supported SDK languages; switching swaps the code body to the equivalent snippet for that language and persists the choice for the session.
- Syntax-highlight token mapping: highlight colors bind to the host project's code-surface role tokens — keywords, strings, comments, and numerics each map to a dedicated `--code-*` role token resolved by the active theme, never hard-coded hex.
- Populated state: once items exist the code block is replaced by the populated table (the empty state and the populated state are mutually exclusive renders of the same route); the "Copy template" affordance moves into a secondary action so the snippet stays reachable.

---

### Modal over list — form with grouped checkboxes

One-line description: A list page (here, an empty list) is overlaid with a centered modal carrying a form: identifier fields at top, then a vertical stack of checkbox groups with parent-and-children semantics; primary actions live inside the modal footer.

Section sequence inside the modal:

1. Modal header row: title ("Create webhook endpoint") + close glyph (×) on the right.
2. Field group 1 — Endpoint URL: label + text input with placeholder ("https://example.com/webhooks").
3. Field group 2 — Name (optional): label + text input with placeholder ("My webhook endpoint").
4. Field group 3 — Description (optional): label + multi-line text input with placeholder ("Receives session lifecycle events").
5. Events-to-subscribe section: a subhead ("Events to subscribe") followed by a vertical stack of parent-and-children checkbox groups. Each parent (Session lifecycle / Threads / Outcomes / Vault lifecycle) has a checkbox + label + right-aligned ratio indicator (4 of 4 / 3 of 3 / 1 of 1 / 3 of 3). Each parent's children render as indented `<label>` rows, each with its own checkbox, a human label, and a code-style identifier ("session.status_run_started" etc.) in a smaller dim font.
6. Modal footer: a right-aligned action pair — a secondary "Cancel" button and a primary "Create" button.

Structural skeleton:

```html
<div class="modal-overlay">
  <div class="modal" role="dialog" aria-labelledby="modal-title">
    <header class="modal__header">
      <h2 id="modal-title">Create webhook endpoint</h2>
      <button class="modal__close" aria-label="close">×</button>
    </header>
    <form class="modal__body">
      <label>Endpoint URL <input type="url" placeholder="https://example.com/webhooks"></label>
      <label>Name (optional) <input type="text" placeholder="My webhook endpoint"></label>
      <label>Description (optional) <textarea placeholder="Receives session lifecycle events"></textarea></label>
      <fieldset class="event-tree">
        <legend>Events to subscribe</legend>
        <div class="event-tree__group">
          <label class="event-tree__parent">
            <input type="checkbox" checked> Session lifecycle <span class="event-tree__ratio">4 of 4</span>
          </label>
          <label class="event-tree__child"><input type="checkbox" checked> Run started <code>session.status_run_started</code></label>
          <label class="event-tree__child"><input type="checkbox" checked> Rescheduled <code>session.status_rescheduled</code></label>
          <label class="event-tree__child"><input type="checkbox" checked> Idled <code>session.status_idled</code></label>
          <label class="event-tree__child"><input type="checkbox" checked> Terminated <code>session.status_terminated</code></label>
        </div>
        <div class="event-tree__group">…</div>
      </fieldset>
    </form>
    <footer class="modal__footer">
      <button class="btn-secondary">Cancel</button>
      <button class="btn-primary">Create</button>
    </footer>
  </div>
</div>
```

Suits: creation flows where the user picks a subscription set across enumerated event groups; also any "permissions" / "scope picker" / "feature gate" creation modal that benefits from grouped multi-select.

Determinations:

- Modal footer: right-aligned secondary "Cancel" + primary "Create" (the primary commits the form; it is disabled until the required Endpoint URL is valid).
- Parent indeterminate state: when some but not all children are checked, the parent checkbox renders the indeterminate (dash) glyph and exposes `aria-checked="mixed"`. Checking the parent selects all children; unchecking it clears all.
- Modal sizing: width `--radius-2xl`-cornered card at `520px` (`--modal-width`), `max-height: 80vh` with the body scrolling internally while header and footer stay fixed.

---

### Command palette overlay over a list page

One-line description: A list page (here, chat history) is overlaid with a centered floating search palette: search input at top, then a vertical list of result rows; the underlying page dims behind the palette.

Section sequence inside the palette:

1. Palette header row: a leading search glyph + an input field with placeholder ("Search chats and projects") + a close glyph on the right.
2. Results list: vertical stack of rows. Each row carries a small leading icon, a primary label, and a right-aligned recency stamp ("↵", "Yesterday", "Past week"). The first row has a return-key glyph indicating it is the active default.
3. Underlying page continues to render with its own heading ("Chats"), search input ("Search chats…"), and recent-chat list, but is visually dimmed beneath the palette.

Structural skeleton:

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
        <span class="palette__row-label">Narrowing job seeker ICP for lean startup</span>
        <span class="palette__row-meta">Yesterday</span>
      </li>
      …
    </ul>
  </div>
</div>
```

Suits: any application surface that benefits from a keyboard-first cross-content jumper (search across chats, files, projects, settings) — typically opened by ⌘K / Ctrl+K. Distinct from the in-page search input — the palette is a global launcher, not a list filter.

Determinations:

- Keyboard contract: ⌘K (macOS) / Ctrl+K (other) opens the palette and focuses the input; Up/Down move the active option; Enter activates the active option; Escape dismisses and returns focus to the trigger. The results list uses `role="listbox"` with `aria-activedescendant` tracking the active option.
- Result grouping: rows carry a relative recency stamp — "Today" for same-day items, "Yesterday" for the prior day, "Past week" for 2–7 days old, then an absolute date (e.g., "May 12") beyond a week. Results are ordered most-recent-first within the current query.

---

### Editor card stack — composition surface

One-line description: A vertical stack of editor cards forming a composition surface, each card representing one role/slot in the composition; below the cards sits an action row carrying secondary affordances (pre-fill / add message pair).

Section sequence inside it:

1. Title row: editable file/document name (`Untitled ▾`) + "Last saved" timestamp + "Save changes" link, with a right-aligned mode toggle ("Prompt / Evaluate" segment) and primary actions ("Get Code", "▶ Run ⌘↵").
2. Configuration row: a model picker pill (`☆ model-name`) + a variables hint ({}) + an "Examples" picker + right-aligned "Templates" link.
3. System Prompt card: label + 1-line helper text ("Define a role, tone or context (optional)") + an `ⓘ` info glyph + a right caret to expand.
4. User card: label + a "✦ Generate Prompt" tertiary action followed by inline input affordance ("or enter instructions or prompt for the model…").
5. Assistant card: label + "Enter the model's response…" placeholder + trailing trash glyph.
6. Repeat User card: another user-message slot.
7. Action row beneath the cards: "[ ] Pre-fill response" toggle + "+ Add message pair" link.

Structural skeleton:

```html
<header class="composer-title-row">
  <button class="composer-title">Untitled ▾</button>
  <span class="composer-saved">Last saved Mar 24, 11:29 PM</span>
  <a class="composer-save-link">Save changes</a>
  <nav class="composer-mode-tabs" role="tablist">
    <button role="tab" aria-selected="true">Prompt</button>
    <button role="tab">Evaluate</button>
  </nav>
  <div class="composer-actions">
    <button class="btn-secondary">Get Code</button>
    <button class="btn-primary">▶ Run ⌘↵</button>
  </div>
</header>
<div class="composer-config-row">
  <button class="model-picker">☆ model-name</button>
  <button class="variables-hint">{ }</button>
  <button class="examples-picker">⚲ Examples</button>
  <a class="templates-link">◇ Templates</a>
</div>
<section class="composer-card composer-card--collapsed">
  <h2>System Prompt <span class="composer-card__helper">Define a role, tone or context (optional)</span></h2>
  <button class="composer-card__expand" aria-label="expand">›</button>
</section>
<section class="composer-card">
  <h2>User</h2>
  <button class="btn-tertiary">✦ Generate Prompt</button>
  <span class="composer-card__helper">or enter instructions or prompt for the model…</span>
</section>
<section class="composer-card">
  <h2>Assistant</h2>
  <p class="composer-card__placeholder">Enter the model's response…</p>
  <button class="composer-card__delete" aria-label="delete">🗑</button>
</section>
<section class="composer-card">
  <h2>User</h2>
  …
</section>
<footer class="composer-action-row">
  <label><input type="checkbox"> Pre-fill response</label>
  <button class="btn-tertiary">+ Add message pair</button>
</footer>
```

Suits: prompt builders, message-flow composers, conversation scripters, script editors — any composition surface where the user assembles a sequence of role-tagged blocks. Pair with shell A2 (the right info panel hosts the welcome/help guide).

Determinations:

- Card expand/collapse: each card has a caret toggle (`aria-expanded`, `aria-controls`); collapsed cards show title + helper only, expanded cards reveal the editable body. "+ Add message pair" appends a new user/assistant card pair at the bottom; each card's trailing trash glyph removes that card. The first card cannot be removed below a single remaining card.
- Drag-to-reorder: cards are reorderable by a drag handle on the left edge; a keyboard alternative moves the focused card with the handle focused and Up/Down arrows. Reordering animates with the standard cross-fade (motion.md §15.3 application-shell register), suppressed under reduced-motion.
- Model picker: a dropdown trigger listing the host project's available models; the selection persists per document and is restored on reopen.

---

### Tool-permission detail — read/write groups with per-row controls

One-line description: Inside an A4 detail viewport, the page renders an integration/connector permission editor: connector header with description and disconnect action, a Tool-permissions section heading, then two collapsible groups (Read-only tools / Write/delete tools) each carrying a default-policy chip and a list of per-tool rows with per-row policy controls.

Section sequence inside the detail viewport:

1. Header row: connector logo + name (e.g., `✦ Connector name`) on the left, "Disconnect" link + 3-dot kebab menu on the right; the kebab may open a small floating menu (View details / Refresh tools list / Remove).
2. Description paragraph (1–3 sentences explaining the connector's capabilities).
3. "Tool permissions" subhead + 1-line helper ("Choose when the integration is allowed to use these tools.").
4. Group 1 — "Read-only tools" with a count badge (`8`) and right-aligned default-policy chip ("Always allow ▾").
5. Repeating tool rows: each row carries a 1-line tool description on the left ("Retrieves a specific record from the connected account.") and 3 per-row policy controls on the right (allow / approve / deny glyph buttons).
6. Group 2 — "Write/delete tools" with count and default-policy chip ("Needs approval ▾"); rows render in the same per-row format.

Structural skeleton:

```html
<header class="connector-detail__header">
  <div class="connector-detail__brand">
    <img class="connector-detail__logo" alt="">
    <h1>Connector name</h1>
  </div>
  <div class="connector-detail__actions">
    <button class="link">Disconnect</button>
    <button class="kebab" aria-label="more">⋮</button>
    <ul class="kebab-menu" hidden>
      <li><button>View details</button></li>
      <li><button>Refresh tools list</button></li>
      <li><button>Remove</button></li>
    </ul>
  </div>
</header>
<p class="connector-detail__description">Connect your account to the integration to quickly access its data…</p>
<section class="tool-permissions">
  <h2>Tool permissions</h2>
  <p>Choose when the integration is allowed to use these tools.</p>
  <details class="tool-group" open>
    <summary>
      <span>Read-only tools <span class="count-badge">8</span></span>
      <button class="default-policy-chip">⊘ Always allow ▾</button>
    </summary>
    <ul>
      <li class="tool-row">
        <p>Retrieves a specific record from the connected account.</p>
        <div class="tool-row__controls">
          <button aria-label="allow">⊘</button>
          <button aria-label="approve">⊕</button>
          <button aria-label="deny">⊗</button>
        </div>
      </li>
      …
    </ul>
  </details>
  <details class="tool-group" open>
    <summary>
      <span>Write/delete tools <span class="count-badge">9</span></span>
      <button class="default-policy-chip">👁 Needs approval ▾</button>
    </summary>
    <ul>…</ul>
  </details>
</section>
```

Suits: integration/connector permission screens, OAuth scope editors, RBAC tool-permission editors — any surface where a list of capabilities groups by default-policy and each row carries a per-item policy override.

Determinations:

- Per-row policy glyphs: the three controls are a `role="radiogroup"` with one selected at a time — allow (the call runs without prompting), approve (the call prompts for approval each time), and deny (the call is blocked). Each carries an explicit `aria-label` ("allow", "approve each call", "deny") and `aria-checked`; the selected glyph paints filled, the others outline.
- Default-policy chip: a dropdown trigger (`aria-haspopup="menu"`, `aria-expanded`) opening a single-select menu (Always allow / Needs approval / Never allow). Choosing a value sets the group default and updates every row that still inherits the default; rows with an explicit override keep their override.

---

### Skill detail — metadata strip + body

One-line description: Inside an A4 detail viewport, the page renders a single skill record: title row with state toggle and kebab, metadata strip in dt/dd pairs, description block, and a content body containing the skill's primary readable content.

Section sequence inside the detail viewport:

1. Title row: `<h1>` record name (e.g., "Record name") + right-aligned enabled-toggle switch + kebab menu (`⋮`).
2. Metadata strip: 3 dt/dd pairs side-by-side — "Added by" / "Last updated" / "Trigger". Compact, single-line.
3. Description block: small "Description" label + free-text paragraph.
4. Content body: a stacked rendering of the skill's content (heading, paragraphs, sub-headings, lists). A small toolbar in the top-right of the body switches between rendered view and raw/source view (eye glyph / `</>` glyph).

Structural skeleton:

```html
<header class="skill-detail__title-row">
  <h1>Record name</h1>
  <div class="skill-detail__actions">
    <input type="checkbox" role="switch" class="skill-detail__toggle" checked>
    <button class="kebab" aria-label="more">⋮</button>
  </div>
</header>
<dl class="skill-detail__meta">
  <dt>Added by</dt><dd>You</dd>
  <dt>Last updated</dt><dd>May 19, 2026</dd>
  <dt>Trigger</dt><dd>Slash command + auto</dd>
</dl>
<section class="skill-detail__description">
  <h2 class="sr-only">Description</h2>
  <p>A short free-text description of what this record does…</p>
</section>
<section class="skill-detail__body">
  <div class="skill-detail__view-toggle">
    <button aria-label="rendered">👁</button>
    <button aria-label="source"><code>&lt;/&gt;</code></button>
  </div>
  <article>
    <h1>Record name</h1>
    <p>The record's primary readable body…</p>
    <h2>Section heading</h2>
    …
  </article>
</section>
```

Suits: any library record viewer (skill / template / preset / saved query / document) where the record has identity metadata up top and a long readable body beneath. The view-toggle pattern (rendered vs. source) is reused for any record that has both a human view and a raw view.

Determinations:

- Title-row toggle: enables or disables the record (an `role="switch"` with `aria-checked`); when off, the record stays in the library but does not activate. The toggle is scoped to the current workspace.
- Kebab menu: opens a floating menu with Edit / Duplicate / Export / Delete (Delete rendered in destructive ink and confirmed before it runs).

---

### Template gallery — example cards with control panels

One-line description: Inside A5's canvas, the Examples tab renders a vertical stack of template entries; each entry has a large preview canvas on the left and a right-side control-panel description (title, dimension controls list, "Use this prompt" CTA) flush to the right edge.

Section sequence inside it:

1. Tab strip at the top of the canvas (Recent / Your designs / Examples / Design systems).
2. Repeating template entry rows. Each entry:
   - Left: a large preview canvas (e.g., a fully styled calculator). Above the preview a small title row ("Calculator Kit") and a "CONSTRUCTION / 13 DIMENSIONS" eyebrow.
   - Right: a control-panel descriptor showing each dimension as a labelled control-group preview (SHELL STYLE — default/flat/brutal/soft/glass; KEY SHAPE — sharp/standard/round/pill/circle; LAYOUT — standard 4×4/scientific 5×6/compact 4×4; DISPLAY — font, size slider, align toggle, show-history toggle; KEY LABELS — sans/mono/serif/oxtech, weight slider, size slider).
   - Far right: a sticky descriptor block carrying the entry title, a 2–4-line description (in quotes — the prompt the user would use), and a primary "Use this prompt" CTA in mapped accent.
3. Below each entry a small file-version trailer ("calculator-kit / v1 — hover: everything ▾").
4. Repeat for the next entry (e.g., "App onboarding" with phone-frame previews).

Structural skeleton:

```html
<section class="template-entry">
  <header class="template-entry__head">
    <span class="template-entry__eyebrow">CONSTRUCTION / 13 DIMENSIONS</span>
    <h2>Calculator Kit</h2>
  </header>
  <div class="template-entry__body">
    <div class="template-entry__preview">
      <!-- live preview canvas -->
    </div>
    <div class="template-entry__control-panel">
      <fieldset>
        <legend>SHELL STYLE</legend>
        <div class="seg"><button aria-pressed="true">Default</button>…</div>
      </fieldset>
      <fieldset>
        <legend>KEY SHAPE</legend>
        <div class="seg">…</div>
      </fieldset>
      …
    </div>
  </div>
  <aside class="template-entry__cta-card">
    <h3>Calculator construction kit</h3>
    <p>"Create a 'Calculator construction kit' — a simple calculator UI with a LOT of tweaks…"</p>
    <button class="btn-primary btn-primary--accent">Use this prompt</button>
  </aside>
  <footer class="template-entry__trailer">calculator-kit / v1 — hover: everything ▾</footer>
</section>
<section class="template-entry">
  <header>…App onboarding…</header>
  …
</section>
```

Suits: prompt-library / template-gallery surfaces where each template carries both a previewable surface and a parameter set the user could explore before choosing it. Each entry is a self-contained advert-plus-demo.

Determinations:

- Control-panel controls are interactive and live-bind to the preview: changing a dimension control re-renders the preview canvas for that entry in place, so the user can explore the parameter space before committing. The "Use this prompt" CTA captures the current configuration.
- The right-side CTA card is sticky within its entry: `position: sticky; top: <header offset>`, pinned for the height of the entry so it stays in view while the user scrolls the preview and controls, then releases at the entry boundary.

---

### Project picker / new-prototype gallery

One-line description: Inside A5's canvas, the Recent tab renders a tabbed strip (Recent / Your designs / Examples / Design systems), a right-aligned search field, and a horizontal row of project cards with a creation prompt as the first card.

Section sequence inside it:

1. Tab strip (Recent / Your designs / Examples / Design systems) on the left + a search input on the far right.
2. Card row: 3 cards side-by-side.
   - Card 1 — onboarding card: small art glyph + title "Learn about the design tool" + "Quick tutorial" link beneath, on a tinted ground.
   - Card 2 — project card: top color-band header tagged "Design system" + thumbnail panel below + project title + recency stamp + owner pill.
   - Card 3 — second project card: same structure as Card 2.

Structural skeleton:

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
  <article class="project-card">
    <header class="project-card__band"></header>
    <div class="project-card__thumb"></div>
    <h3>Project Name</h3>
    <p>Your design · Apr 26</p>
    <span class="pill">Owner</span>
  </article>
</section>
```

Suits: project/file pickers for creative tools, where the user lands and either resumes a recent project or starts a fresh one (creation is owned by A5's left sidebar form, not by this gallery).

Determinations:

- Card hover/selection: on hover a card raises with the faint-elevation shadow (layout.md §11.8) and its border steps from `--border-300` to `--border-200` over a 150ms `--ease-in-out` transition (suppressed under reduced-motion); the card is a link, so `:focus-visible` paints the standard focus ring.
- Card overflow: cards wrap to additional rows (responsive grid, `repeat(auto-fill, minmax(280px, 1fr))`), not horizontal scroll, so every project stays reachable without a horizontal scrollbar.

---

## Composition rules

### Which shell suits which kind of work

- **Operational dashboards, analytics, settings, list views, code-as-content** → A1. Single rail + main is the default for any single-focus screen where the rail's navigation tree is enough chrome.
- **Creative tools and editors with persistent help** → A2. Use only when the help content stays relevant across composition states. If help would only appear on demand (e.g., a "?" button popover), keep A1 and add the popover instead.
- **Project-creation, item-creation, quickstart flows with a persistent prompt input** → A3. The bottom strip earns its space only when the prompt is the keystone of the page.
- **Library/registry browsing** (skills, connectors, documents, labels, contacts with detail) → A4. Mini-rail + list + detail is the right shape for lateral movement across many items.
- **Parametric design tools, prototype builders, generator entry screens** → A5. Form-driven sidebar earns its width only when the form is doing real work (configuring the canvas / picking a template).

### Choosing between shell variants

- A1 vs. A2: choose A2 only when contextual help is genuinely persistent. Do not promote a one-shot welcome banner to an info panel — that belongs inline at the top of A1's main.
- A1 vs. A3: choose A3 only when the bottom prompt is the page's primary input. A "send feedback" button does not justify the strip; a project-creation prompt does.
- A4 vs. A1 with sub-nav: choose A4 only when lateral movement across items is a frequent action. If users typically pick one item and stay there, A1 with a single list-and-detail page composition is enough.
- A5 vs. A2: choose A5 only when the sidebar drives the canvas. Help-and-tips belongs in A2's info panel; configuration-that-renders belongs in A5's form sidebar.

### Mocks vs. app-embedded rendering of the same shape

The `compose-app-surface` skill emits app-embedded code. The `compose-page` skill emits standalone mocks. The same app shape may render in either mode; what differs:

- **Stylesheet wiring.** Mocks (compose-page output) inline the stylesheet set in a `<style>` block inside the document head so the mock is portable and self-contained. App-embedded code (compose-app-surface output) links to the same stylesheet files via `<link rel="stylesheet">` so the host project owns the cascade. Same tokens; different wiring.
- **Mode toggle.** Mocks include a top-right mode toggle (light/dark) so the reviewer can flip between themes inside the mock. App-embedded code does NOT include a mode toggle — the host project owns theming (via a global theme switcher in the host's chrome, or via `prefers-color-scheme` defaulting).
- **Browser chrome treatment.** Mocks render the application shell without browser frame (the mock is the canvas). App-embedded code assumes the host application already owns the browser frame; the rendered shell sits inside whatever route the host routes to.
- **Catalog notes.** Mocks may carry a footnote naming which catalog entries they pull from. App-embedded code does not — the host project is the source of truth.

If a screen needs both modes (one for review, one for production), build it once as an app-embedded surface and wrap it with a mock harness; do not maintain two parallel implementations.

---

## Cross-context component compositions

Compositions that arrange multiple Components for a purpose but are not full page shapes. Each H3 below documents one such composition. Components referenced live in `components.md`.

### Modal dialog with form

**Purpose.** A centered overlay dialog that holds a form for creating a new item, with header (title + close), scrollable body (fields), and footer (cancel + primary CTA). The modal itself is the `§14 Centered dialog` Component in `components.md`; the composition documented here is the dialog + form-field-group + footer-actions pattern.

**Component references.** `§14 Centered dialog` (host), Text inputs (`§14 Standard text input`, `§14 Textarea`), grouped-checkbox-tree Component, primary + secondary buttons (`§14 Primary button`, `§14 Secondary button`).

**Slot definitions.**

- `overlay` (required): full-viewport dim layer beneath the dialog.
- `dialog` (required): centered card.
- `header` (required): title + close button (×).
- `body` (required): vertically scrollable content area holding the form.
- `footer` (required): cancel and primary CTA buttons.

State props: `closed` | `open`; `submit` state: `idle` | `submitting` | `error`.

Sizing:

- Dialog width is `520px` (`--modal-width`), capped at `calc(100vw - 32px)` on narrow viewports.
- Dialog corners use `--radius-md` (12px) and carry the modal-lift shadow from layout.md §11.8 above the dimmed underlying page.
- Body has internal vertical scroll if content exceeds available height; `max-height: 80vh`.

Structural skeleton:

```html
<div class="modal-overlay" role="presentation">
  <div class="modal" role="dialog" aria-labelledby="modal-title" aria-modal="true">
    <header class="modal__header">
      <h2 id="modal-title">Create webhook endpoint</h2>
      <button class="modal__close" aria-label="close">×</button>
    </header>
    <form class="modal__body">
      <label>Endpoint URL <input type="url" placeholder="https://example.com/webhooks"></label>
      <label>Name (optional) <input type="text" placeholder="My webhook endpoint"></label>
      <label>Description (optional) <textarea placeholder="Receives session lifecycle events"></textarea></label>
      <!-- event-tree fieldset; see Grouped checkbox tree composition below -->
    </form>
    <footer class="modal__footer">
      <button class="btn-secondary" type="button">Cancel</button>
      <button class="btn-primary" type="submit">Create</button>
    </footer>
  </div>
</div>
```

Interaction contracts: focus moves to the dialog on open and is trapped within it (Tab cycles inside the dialog) per accessibility.md §18.3; clicking the overlay closes the dialog and so does Escape, both equivalent to Cancel; the open/close transition fades and lifts over 200ms and is reduced to an instant swap under `prefers-reduced-motion: reduce` (motion.md §15.5); the primary CTA shows a spinner and is disabled while `submit` is `submitting`, and surfaces an `aria-live="polite"` error message in the body on `error`.

**Why it matters.** Many creation flows that would otherwise need a full route navigation can stay inline as a modal, preserving context.

---

### Grouped checkbox tree

**Purpose.** A two-level checkbox group where each parent represents a category and each child is a leaf option; the parent shows a "checked count over total" indicator on the right; parent state is `checked` / `indeterminate` / `unchecked` driven by the children. A collapsible-group composition assembled from Checkbox Components.

**Component references.** Checkbox primitives (host project's checkbox Component), label primitives. Indeterminate-state visual treatment for the parent checkbox is a Component-level concern; the composition documented here is the parent+children+ratio-indicator pattern.

**Slot definitions.**

- `group` (repeating): a fieldset for each category.
- `parent` (required per group): checkbox + label + right-aligned ratio indicator ("4 of 4").
- `child` (repeating per group): checkbox + human label + a code-style identifier in a smaller, dimmer font.

State props per parent: `checked` | `unchecked` | `indeterminate`. State props per child: `checked` | `unchecked`.

Sizing:

- Children are indented `--sp-1-5` (24px) relative to their parent.
- Ratio indicator is right-aligned within the parent row, caption-size text.
- Code-style identifier renders in the monospace face at 12px, one step dimmer (`--text-500`) than the human label.

Structural skeleton:

```html
<fieldset class="event-tree">
  <legend>Events to subscribe</legend>
  <div class="event-tree__group">
    <label class="event-tree__parent">
      <input type="checkbox" checked>
      <span class="event-tree__parent-label">Session lifecycle</span>
      <span class="event-tree__ratio">4 of 4</span>
    </label>
    <label class="event-tree__child">
      <input type="checkbox" checked>
      <span class="event-tree__child-label">Run started</span>
      <code class="event-tree__child-id">session.status_run_started</code>
    </label>
    <label class="event-tree__child">…</label>
    <label class="event-tree__child">…</label>
    <label class="event-tree__child">…</label>
  </div>
  <div class="event-tree__group">…</div>
</fieldset>
```

Interaction contracts: the parent checkbox renders the indeterminate (dash) glyph and exposes `aria-checked="mixed"` when some-but-not-all children are checked; clicking the parent toggles all of its children at once (check-all when not fully checked, clear-all when fully checked); each group is collapsible via its `<summary>` (`aria-expanded`, `aria-controls`) and ships expanded by default; the accessible name for each child joins the human label and the code identifier (e.g., "Run started, session.status_run_started") so screen-reader users hear both.

**Why it matters.** Permission pickers, event-subscription pickers, scope selectors, capability pickers — anywhere a user picks subsets across enumerated categories — benefit from a stable two-level pattern.

---

### Two-column / four-column field-group form

**Purpose.** A form-layout composition arranging labelled Input Components in a multi-column row to optimize horizontal space for related fields (address parts, name parts, date ranges). The canonical instances are an Address line 1 + Line 2 pair in a 2-col row and a Country + State + City + Postal set in a 4-col row.

**Component references.** Text input primitives (`§14 Standard text input`), select / combobox primitives, label primitives.

**Slot definitions.**

- `group-label` (required): a heading or single-label sitting above the row.
- `field` (repeating): a `<label>` + a control (`<input>`, `<select>`, etc.) inside a flex cell. The cell wraps both the visible field label and the input.
- `row` (required): a flex container distributing field cells horizontally.

**State enum (per field).** `rest` | `focus` | `invalid` | `disabled`.

**Dimensions.**

- **2-col row container:** `display: flex`, `max-width: 32rem` (512px), `column-gap: 12px`, `row-gap: 12px`. Tailwind utility chain: `flex max-w-lg gap-3`. Each child cell measures 208px wide × 72px tall (input 44px + label-above + 8px vertical rhythm).
- **4-col row container:** `display: flex`, `flex-wrap: wrap`, `column-gap: 12px`, `row-gap: 24px`, `width: 100%`, `align-items: flex-end`. Tailwind utility chain: `flex w-full flex-wrap items-end gap-x-3 gap-y-6`. Cells share width via natural flex sizing (no fixed basis); each cell measures 208px × 72px. At narrower viewports the 4-col row wraps to 2-up because `flex-wrap` is engaged and `flex-basis` is `auto`.
- **Field cell:** flex column carrying the label above the input. Total cell height 72px; input height 44px; the remaining 28px holds the label and an 8–10px gap to the input.
- **Input itself:** 44px tall, padding `0 12px`, `border: 1px solid var(--role-border-subtle)` (a hairline at ~15% alpha against the dark surface), `border-radius: 9.6px` (Tailwind `rounded-[0.6rem]`), `background: var(--role-surface-raised)` (elevated dark surface), `font-size: 16px`, `font-family: var(--typeface-sans)`.
- **Select / combobox trigger** (rendered as `<button role="combobox">`): 42px tall, padding `0 0 0 12px` (right padding handled by an internal chevron), transparent background, no visible border by default.

**Role-token bindings.**

- Field input background → `--bg-200` / equivalent elevated dark surface
- Field input border → `--border-300` (resolves to ~15% alpha of the foreground neutral)
- Field input radius → `--radius-md` (9.6px on this surface; ~0.6rem)
- Row gap → `--space-3` (12px column gap); `--space-6` (24px row gap on the 4-col wrap variant)
- Field label color → `--text-200` (one step dimmer than primary)
- Field input text → `--text-100`

**Responsive collapse.**

- 2-col row: `max-width: 32rem` caps total width so each cell stays close to 250px; below 32rem the row contracts but does not wrap (the 2-col pattern is not designed to collapse).
- 4-col row: `flex-wrap: wrap` is engaged by default; cells reflow to 2-up or 1-up as the parent narrows. The narrower postal-code variant relies on a per-cell width override rather than per-column grid sizing.

Structural skeleton:

```html
<section class="field-group">
  <h3 class="field-group__label">Primary business address</h3>

  <!-- 2-col variant -->
  <div class="flex max-w-lg gap-3">
    <label class="field flex flex-col gap-2 flex-1">
      <span class="field__label">Address line 1</span>
      <input type="text" class="h-11 px-3 rounded-[0.6rem] border border-border-300 bg-bg-200 text-base">
    </label>
    <label class="field flex flex-col gap-2 flex-1">
      <span class="field__label">Address line 2</span>
      <input type="text" class="h-11 px-3 rounded-[0.6rem] border border-border-300 bg-bg-200 text-base">
    </label>
  </div>

  <!-- 4-col variant (wraps at narrow viewports) -->
  <div class="flex w-full flex-wrap items-end gap-x-3 gap-y-6">
    <label class="field flex flex-col gap-2">
      <span class="field__label">Country</span>
      <button role="combobox" class="h-[42px] pl-3 …"></button>
    </label>
    <label class="field flex flex-col gap-2">
      <span class="field__label">State or province</span>
      <input type="text" class="h-11 px-3 …">
    </label>
    <label class="field flex flex-col gap-2">
      <span class="field__label">City</span>
      <input type="text" class="h-11 px-3 …">
    </label>
    <label class="field field--narrow flex flex-col gap-2">
      <span class="field__label">Postal code</span>
      <input type="text" class="h-11 px-3 …">
    </label>
  </div>
</section>
```

**Determinations.**

- **Label typography** — field labels are `text-sm font-medium text-text-200` (14px, weight 500, one step dimmer than primary).
- **Field validation visuals** — an invalid field gets a 1px `--border-danger` border plus a single sentence of helper text below the input in `--error-text`, with `aria-live="polite"` on the message container (accessibility.md §18.6).
- **Per-cell width overrides** — the narrower postal-code cell uses a per-cell `flex-basis` (96px) rather than a column track; all other cells in the 4-col row share equal width (208px) via natural flex sizing.

**Why it matters.** Settings, profile, billing, and onboarding screens all need consistent address/identity form composition. A stable field-group prevents per-screen drift.

---

### Destructive zone

**Purpose.** A divider-delimited section that hosts a Destructive button (Component — see `components.md §14 Destructive button`) — for example a "Delete organization" button (solid red surface, white label) on its own line beneath the form. The composition is the hairline-top-divider + destructive-button pattern, distinct from the button itself.

**Component references.** `§14 Destructive button` (in `components.md`).

**Frame / wrapper zone.**

The destructive action does NOT sit inside a bordered or tinted card. It sits in a section delimited only by a hairline top divider beneath the preceding form:

- Wrapper class: `pt-6 border-t border-border-300`
- Wrapper layout: `display: block`, full container width
- Wrapper padding: `24px 0 0` (top padding only — the divider provides the visual separation; no left/right/bottom padding)
- Wrapper border: 1px solid `hsl(var(--border-300))` on the TOP edge only
- Wrapper background: inherits the page surface (no tint, no card chrome)

This means the "destructive zone" pattern in this product is **divider-delimited, not card-delimited**. A bordered/tinted destructive card is an alternative pattern not used here.

Structural skeleton:

```html
<!-- Destructive zone: hairline-divider-delimited section hosting one Destructive button -->
<section class="pt-6 border-t border-border-300">
  <button class="btn-destructive …">Delete organization</button>
</section>
```

**Confirm-step contract.**

- Activating the destructive button opens a confirmation modal (the "Modal dialog with form" composition above) that restates the consequence and requires an explicit confirm before the action runs. The zone itself does not delete on first click — the confirm step lives in the modal.

**Why it matters.** Every settings page eventually carries a destructive action. The divider-delimited zone visually separates an irreversible action from the editable fields above it, preventing accidental activation while keeping the action discoverable.

---

### Setting card with toggle + destructive sub-row

**Purpose.** A composition that pairs a Setting card Component (with its inline toggle) with an inline destructive sub-row beneath the body — for example an "Allow product metrics logging" card with a "Delete all collected metrics data" sub-row for the associated irreversible action. The destructive sub-row keeps the irreversible action visibly attached to the preference it belongs to rather than dumped in a global destructive zone.

**Component references.** `Setting card`, `§14.3 Switch active` (toggle), `§14 Destructive button` (the destructive button inside the sub-row).

**Slot composition.**

- `setting-card` (host): see the Setting card Component for slot/dimensions/role-token bindings.
- `destructive-sub-row` (added composition slot): an inline row beneath the body carrying a destructive sentence + a Destructive button.

Structural skeleton (composition delta over the base Setting card):

```html
<article class="rounded-xl p-8 flex flex-col gap-6 border-0.5 border-border-300">
  <!-- standard Setting card body (title cell + toggle cell + body cell) -->
  <div class="grid grid-cols-[1fr_auto] gap-x-5 w-full">…</div>
  <!-- destructive sub-row appended beneath the standard card body -->
  <div class="setting-card__destructive-sub-row">
    <span>Delete all collected metrics data. This action cannot be undone.</span>
    <button class="btn-destructive …">Delete data</button>
  </div>
</article>
```

**Determinations.**

- **Destructive sub-row visual treatment** — the sub-row sits beneath the card body, separated by a `1px --border-300` hairline divider, on the same card ground (no separate tint). When the card's toggle is `off`, the sub-row dims to a disabled appearance and its button is disabled, since the data it would delete is no longer being collected.
- **`destructive-inline` button-size variant** — the inline sub-row's destructive button uses the 32px compact size (a step down from the 36px primary destructive height) so it reads as a scoped, secondary-weight action within the card rather than a page-level destructive action.

**Why it matters.** When an irreversible action is tightly scoped to one preference, embedding it inside the preference's card keeps the action's context visible. The pattern is preferred over a global destructive zone for setting-specific delete actions.

---

### Approval-mode tool permission control with collapsible groups

**Purpose.** A two-level permission editor where each group has a default policy (Always allow / Needs approval / Never allow) and each row inside the group can override the group's policy via per-row glyph buttons (allow / approve / deny). The canonical instance is a connector with a Read-only tools group ("Always allow" default, 8 tools) and a Write/delete tools group ("Needs approval" default, 9 tools), each row carrying per-row policy glyph buttons. The composition assembles collapsible groups around Segment-control Components.

**Component references.** `Segment-control` Component (the three Read / Write / Don't allow segments are a Segment-control instance), count-badge primitive, filter-chip / dropdown-trigger Component for the default-policy chip.

**Slot definitions.**

- `group` (repeating): a collapsible section (`<details>`).
- `group-summary` (required per group): group label + count badge + right-aligned default-policy chip.
- `tool-row` (repeating per group): tool description + per-row Segment-control instance for policy override.

State props per group: `expanded` (default) | `collapsed`. Per row: `inherits-default` | `overridden-allow` | `overridden-approve` | `overridden-deny`.

Sizing:

- Group summary row is 44px tall.
- Tool rows are 40px tall.
- Per-row Segment-control sits at the right edge of the row, three small icon buttons in a row.
- Count badge is a small pill containing a digit (e.g., "8", "9").
- Default-policy chip is a pill-shaped picker (similar to the filter chip).

Structural skeleton:

```html
<details class="tool-permissions__group" open>
  <summary class="tool-permissions__summary">
    <span class="tool-permissions__group-label">Read-only tools</span>
    <span class="count-badge">8</span>
    <button class="default-policy-chip" aria-haspopup="menu" aria-expanded="false">
      <span aria-hidden="true">⊘</span> Always allow <span aria-hidden="true">▾</span>
    </button>
  </summary>
  <ul class="tool-permissions__rows">
    <li class="tool-row">
      <p class="tool-row__description">Retrieves a specific record from the connected account.</p>
      <div class="tool-row__controls" role="radiogroup" aria-label="policy">
        <button role="radio" aria-checked="true" aria-label="allow">⊘</button>
        <button role="radio" aria-checked="false" aria-label="approve each call">⊕</button>
        <button role="radio" aria-checked="false" aria-label="deny">⊗</button>
      </div>
    </li>
    …
  </ul>
</details>
<details class="tool-permissions__group" open>
  <summary>
    <span class="tool-permissions__group-label">Write/delete tools</span>
    <span class="count-badge">9</span>
    <button class="default-policy-chip">👁 Needs approval ▾</button>
  </summary>
  <ul>…</ul>
</details>
```

Interaction contracts: the three per-row glyphs map to allow (call runs without prompting), approve (call prompts for approval each time), and deny (call is blocked), in that left-to-right order; each carries an explicit `aria-label` and the group uses the `role="radiogroup"` pattern (one policy selected per row at a time). The default-policy chip is a dropdown trigger opening a single-select menu (Always allow / Needs approval / Never allow). A row whose policy differs from its group default carries a small "overridden" dot marker before its controls so the divergence is visible at a glance. Expand/collapse uses the standard cross-fade (motion.md §15.3 application-shell register) and is reduced to an instant toggle under `prefers-reduced-motion: reduce`.

**Why it matters.** Any connector, integration, OAuth-scope, or RBAC capability editor benefits from a stable two-level policy contract. Without it, each connector page tends to invent a different control idiom.

---

## Notes

File-level notes that apply across the catalog:

- Token values, widths, motion curves, focus-ring contracts, hover/active states, reduced-motion fallbacks, and breakpoint behavior are specified definitively per entry and resolve against the foundations (`reference/foundations/responsive.md`, `layout.md`, `accessibility.md`, `motion.md`).
- This catalog is not exhaustive across all application surfaces. Other surfaces (chat conversation surface, file-tree explorer, multi-pane diff viewer, etc.) are not yet represented and will need their own entries in a later pass.
- Cross-references to `components.md` are made by section number where the component already exists (e.g., A4 references §12.5).
- The disjoint naming scheme (A1–A5 for shells, descriptive names for page shapes); if a later pass needs to expand beyond 26 shells, the scheme extends (A1…A26, then AA1, etc.).
- Shell layouts A1–A5 may not be exhaustive for every host product. Future surfaces with novel partitioning (e.g., split-pane diff editor, multi-tab worktree) will need new letter codes.
