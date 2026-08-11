---
kind: shape
name: bar-mark-cta
aliases: [logo and button, mark with single action, conversion header]
status: stable
slots:
  - { name: mark, required: true, accepts: [logo] }
  - { name: cta, required: true, accepts: [tertiary-link, primary-button] }
variants: []
self_contained: false
content_defaults: {}
---

# bar-mark-cta — Mark at the start, one action at the end

A single row holding the brand mark at the start and one or two conversion actions at the end, with no navigational set between them. The arrangement a surface takes when it offers a way onward but nothing to browse.

## Determinations

- One flex row. The mark sits alone at the start; `cta` sits at the end via `margin-inline-start: auto`.
- The row must NOT use `justify-content: space-between` — the rule holds for every bar arrangement.
- The row holds its arrangement at every breakpoint: with no nav cluster there is nothing to collapse into a drawer, so the action stays in the row.

## Landmark consequence

A conversion slot is filled, so the receiving Section emits `<nav aria-label="primary">` wrapping `cta`, with the mark's link outside it (`libraries/sections/top-nav.md`, Accessibility).
