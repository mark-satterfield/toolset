---
kind: shape
name: record-detail
family: app
aliases: [skill detail, library record viewer, document detail view]
status: stable
slots:
  - { name: title-row, required: true, accepts: [heading, toggle-switch, kebab-menu] }
  - { name: meta-strip, required: true, accepts: [labelled-values] }
  - { name: description, required: true, accepts: [label, paragraph] }
  - { name: body, required: true, accepts: [view-toggle, article-content] }
variants: []
self_contained: false
content_defaults:
  meta: [{ label: "Added by", value: "You" }, { label: "Last updated", value: "May 19, 2026" }, { label: "Trigger", value: "Slash command + auto" }]
---

# record-detail — Metadata strip + readable body

A single library record filling a detail viewport (typically the mini-rail-list-detail Shell's): a title row with an `<h1>` record name, a right-aligned enabled-toggle (the toggle-switch component) and a kebab menu; a compact single-line metadata strip of dt/dd pairs; a description block (small label + free-text paragraph); and a content body — a stacked rendering of the record's readable content with a small top-right toolbar that switches between the rendered view and the raw/source view (eye glyph / `</>` glyph).

The view-toggle pattern (rendered vs. source) applies to any record that has both a human view and a raw view.

## HTML skeleton

```html
<header class="record-detail__title-row">
  <h1>Record name</h1>
  <div class="record-detail__actions">
    <input type="checkbox" role="switch" class="record-detail__toggle" checked>
    <button class="kebab" aria-label="more">⋮</button>
  </div>
</header>
<dl class="record-detail__meta">
  <dt>Added by</dt><dd>You</dd>
  <dt>Last updated</dt><dd>May 19, 2026</dd>
  <dt>Trigger</dt><dd>Slash command + auto</dd>
</dl>
<section class="record-detail__description">
  <h2 class="sr-only">Description</h2>
  <p>A short free-text description of what this record does…</p>
</section>
<section class="record-detail__body">
  <div class="record-detail__view-toggle">
    <button aria-label="rendered">👁</button>
    <button aria-label="source"><code>&lt;/&gt;</code></button>
  </div>
  <article>
    <h1>Record name</h1>
    <p>The record's primary readable body…</p>
    <h2>Section heading</h2>
  </article>
</section>
```

## Determinations

- Title-row toggle: enables or disables the record (a `role="switch"` with `aria-checked`); when off, the record stays in the library but does not activate. The toggle is scoped to the current workspace.
- Kebab menu: opens a floating menu with Edit / Duplicate / Export / Delete — Delete rendered in destructive ink and confirmed before it runs.

Suits any library record viewer (skill, template, preset, saved query, document) where the record has identity metadata up top and a long readable body beneath.
