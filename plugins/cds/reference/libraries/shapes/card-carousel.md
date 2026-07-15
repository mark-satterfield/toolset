---
kind: shape
name: card-carousel
page_family: landing
aliases: [carousel, card slider, horizontal scroller]
status: stable
slots:
  - { name: cards, required: true, accepts: [card] }
  - { name: controls, required: true, accepts: [prev-button, next-button] }
  - { name: pagination, required: false, accepts: [pagination-indicator] }
variants: [with-pagination-dots, without-pagination-dots, auto-advance-on, auto-advance-off]
self_contained: true
content_defaults: {}
---

# card-carousel — Horizontal carousel

A single horizontal row of cards exceeding the viewport width, with prev/next arrows and scroll/paging affordances; more items than fit on screen.

## Determinations

- Card width derives from the container: cards are a fixed width sized so roughly 3 fit within `--container-marketing-primary` at desktop, with the next card peeking ~10% to signal overflow. Inter-card gap is `--sp-1-5`.
- Scroll snaps card-by-card (`scroll-snap-type: x mandatory`, `scroll-snap-align: start`). Auto-advance is off by default; when on, it pauses on hover and on focus within the carousel, and is suppressed under `prefers-reduced-motion: reduce`.
- Prev/next controls carry `aria-label` and are disabled (with `aria-disabled`) at the start/end. Below the tablet breakpoint (`foundations/responsive.md` §17.1) the row is finger-scrollable and the arrows hide.

## Self-containment

Paging and prev/next behavior are Shape-level, not provided by the generated component stylesheet or any shared script. The fragment carries its own scoped `<style>` and a scoped IIFE `<script>` that scopes itself to its own instance(s) so multiple carousels on one page never collide; it implements the control states (`aria-disabled` at ends), snap-aligned paging, and the auto-advance pause/suppression rules, with motion gated by reduced motion.
