---
kind: shape
name: bar-mark-only
page_family: shared
aliases: [logo-only bar, mark-only bar, brand bar, logo bar, bare header]
status: stable
slots:
  - { name: mark, required: true, accepts: [logo] }
variants: []
self_contained: false
content_defaults: {}
---

# bar-mark-only — Bar carrying the mark alone

A single row holding the brand mark at the start and nothing else. The arrangement a surface takes when it exposes no navigational set: the mark identifies where the page comes from, and nothing competes with the single action the content region asks for.

## Determinations

- One flex row. The mark sits at the start (inline-start); the rest of the row is empty. Inline padding is the page gutter.
- Nothing occupies the end of the row. A trailing affordance is a different arrangement, not a variant of this one.
- The row holds the same mark at every breakpoint. There is no compact form — there is nothing to collapse.
- The receiving Component supplies the bar's height, ground, mark sizing, and focus contract; this Shape supplies position only.

## Landmark consequence

Because no navigational slot is filled, the receiving Section emits no `<nav>` (`libraries/sections/top-nav.md`, Accessibility). The bar contributes exactly one tab stop — the mark's link.
