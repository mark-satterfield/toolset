---
kind: shape
name: prompt-templates-split
aliases: [quickstart two-column, create-or-browse split, prompt plus template gallery]
status: stable
slots:
  - { name: prompt-column, required: true, accepts: [heading, helper-text, prompt-strip] }
  - { name: templates-panel, required: true, accepts: [panel-heading, search-input, template-grid] }
variants: []
self_contained: false
content_defaults:
  template_count: 10
  panel_heading: "Browse templates"
  search_placeholder: "Search templates"
  prompt_placeholder: "Describe your project…"
  first_card: { title: "Blank project", description: "A blank starting point…" }
---

# prompt-templates-split — Prompt column beside a templates panel

Two columns filling the vacant space below a step indicator: the left column carries a centered empty-state heading, helper sentence, and a prompt strip pinned near the column's bottom; the right column is a self-scrolling templates panel with a heading, a search input, and a two-column card grid.

## Layout

- **Split.** Two columns over the Section's content width: the templates panel takes roughly two-thirds (`grid-template-columns: minmax(0, 1fr) minmax(0, 67%)`), the prompt column the remainder, separated by a `--sp-1-5` gutter. Calibrates to 328px (prompt) / 711px (panel) columns at the reference desktop viewport (~1347px, inside the vacant space of an application Shell).
- **Height.** The body fills the vacant space's height remaining below the step indicator; the templates panel stretches to that height and scrolls its grid internally. Calibrates to a 762px panel at the reference viewport.

## Templates panel

- Container: padding `--sp-1`, radius `--radius-md`, hairline border (1px alpha-thinned `--border-subtle`, `foundations/layout.md` §11.9), background `--surface-secondary`, vertical flex with a `--sp-1` gap.
- Panel heading: Primary Sans at panel-heading scale, weight `--fw-600` (calibrates to 16px).
- Search input: the `search-input` component (its height contract applies), spanning the panel's inner width — panel width minus 2 × `--sp-1` padding (calibrates to 678px).
- Template grid: `display: grid`, two equal columns (`1fr 1fr`), `--sp-0-75` gap, `auto-rows-min`, vertical scroll on overflow. Card width derives as (panel inner width − gap) ÷ 2 (calibrates to ~333px); card height is content-driven — title, description, and padding (calibrates to ~79px).
- Template card: padding `--sp-0-75`, radius `--radius-sm`, hairline border (1px alpha-thinned `--border-subtle`), transparent background, `cursor: pointer`, `role="button"`, `tabindex="0"`, hover background `--surface-tertiary` with a color transition. Vertical flex: title in `--text-primary` at body-small scale weight `--fw-400` (calibrates to 14px), then a hairline top margin (calibrates to 2px), then the description in `--text-tertiary` at caption scale (calibrates to 12px).

## Prompt column

- Heading ("What do you want to build?") at page-title scale, weight `--fw-600` (calibrates to 28px), positioned in the vertical center of the column, with the helper sentence beneath.
- Prompt strip wrapper: full column width (calibrates to 328px), content-driven height (calibrates to 66px), pinned near the column's bottom edge. Padding `--sp-0-5` with a `--sp-1` leading pad (calibrates to 8px 8px 8px 16px), border `1px solid var(--border-subtle)`, radius `--radius-md`, background `--surface-raised`, faint-elevation shadow (`foundations/layout.md` §11.8). `display: flex`, `align-items: end`, `--sp-0-5` gap, `cursor: text`.
- Prompt textarea: fills the strip minus its padding, gap, and send control (calibrates to 266px wide); auto-grows from a single-line minimum via `field-sizing: content` (calibrates to 48px tall). Body-small type (calibrates to 14px) in `--text-primary`, transparent background, `--sp-0-25` block padding and zero inline padding, `resize: none`, no border or outline; placeholder in `--text-tertiary`.

## HTML skeleton

```html
<section class="quickstart-body">
  <div class="quickstart-body__left">
    <div class="empty-state">
      <h1>What do you want to build?</h1>
      <p>Describe your project or start with a template.</p>
    </div>
    <div class="prompt-strip">
      <textarea placeholder="Describe your project…"></textarea>
      <button class="send-btn" aria-label="send">…</button>
    </div>
  </div>
  <div class="quickstart-body__right">
    <h2>Browse templates</h2>
    <div class="search-wrap"><!-- search-input component --></div>
    <div class="template-grid">
      <div class="template-card" role="button" tabindex="0">
        <div class="template-card__title">Blank project</div>
        <div class="template-card__description">A blank starting point…</div>
      </div>
      <!-- one card per supplied template -->
    </div>
  </div>
</section>
```

## Determinations

- Template-card activation: clicking a card populates the prompt strip with that template's starter text. The card carries `role="button"` and `tabindex="0"`; Enter and Space activate it.
- Prompt-strip elevation: the wrapper uses the faint-elevation shadow from `foundations/layout.md` §11.8 (the raised-input surface treatment).
- The number of template cards is content-driven; the grid scrolls vertically when the supplied set exceeds the panel height.
