---
kind: shape
name: logo-marquee
aliases: [logo ticker, scrolling logos, logo wall, marquee]
status: stable
slots:
  - { name: items, required: true, accepts: [logo, icon] }
variants: [right-to-left, left-to-right, pause-on-hover, duplicated-item-set, unique-item-set]
self_contained: true
content_defaults: {}
---

# logo-marquee — Marquee strip of marks

A continuously scrolling full-width row whose repeated item is a single mark — a logo or an icon — with nothing beside it. The marquee family's scroll, self-containment, and item-separation contracts bind (`libraries/shapes/CONVENTIONS.md`, Marquee strips).

## Determinations

- The repeated item is one mark at `height: var(--icon-size-feature); width: auto`, so marks of differing proportion sit on a common optical height rather than a common width.
- Item-to-item spacing is `--sp-4`. Marks are discrete objects, so the strip carries no dividers between them.
- A mark that carries meaning beyond decoration takes an `alt` naming its organization; a mark repeated purely as texture is `aria-hidden`.
