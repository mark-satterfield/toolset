---
kind: shape
name: list-empty-state
page_family: app
aliases: [empty list, empty table state, zero state list]
status: stable
slots:
  - { name: page-header, required: true, accepts: [heading, subhead, primary-cta] }
  - { name: column-headers, required: true, accepts: [column-labels] }
  - { name: empty-plate, required: true, accepts: [icon, title, helper-text, secondary-cta] }
variants: []
self_contained: false
content_defaults:
  page_title: "Webhooks"
  subhead: "Webhook endpoints receive event notifications when things happen in your workspace."
  primary_cta: "+ Add webhook endpoint"
  columns: [ID, Name, Status, "Created at"]
  empty_title: "No webhook endpoints yet"
  empty_helper: "Create one to start receiving event notifications."
---

# list-empty-state — Centered icon + helper + CTA over a previewed table

A list/table view before the first item exists: a page heading with subhead and a right-side primary CTA, a lightly drawn column-header strip beneath it (the table's header without rows), then a centered empty-state plate — a small framed icon glyph, a one-line title, a one-line helper, and a secondary CTA.

The doubled CTA (top-right + center plate) is intentional: the top-right keeps the action reachable from any list state; the center plate makes the empty case its own moment.

## HTML skeleton

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

## Determinations

- The column-header strip persists once rows exist and becomes the live table header — the same header row the empty state previews, with data rows rendering beneath it. No relayout between empty and populated states.
- Icon framing: the glyph sits inside a circle-stroke frame — a circular plate of 3 × `--sp-1` (48px) with a `1px` `--border-subtle` ring and no fill, the glyph centered in `--text-tertiary` ink.
