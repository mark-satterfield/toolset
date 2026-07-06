---
kind: shape
name: lead-plus-carousel
family: landing
aliases: [featured card with carousel, lead story with more]
status: stable
slots:
  - { name: lead-card, required: true, accepts: [featured-card] }
  - { name: companion-carousel, required: true, accepts: [card] }
variants: [lead-left, lead-right, carousel-scroll, carousel-paginate]
self_contained: true
content_defaults: {}
---

# lead-plus-carousel — Lead card with companion carousel

One featured large card; secondary cards in a carousel beside it.

## Determinations

- The lead card spans grid columns 1–6 and the companion carousel spans 7–12, giving a 50/50 footprint with the lead at full height and the carousel showing secondary cards with a peek of the next.
- The companion carousel inherits card-carousel behavior (`libraries/shapes/card-carousel.md`): snap, prev/next, and reduced-motion handling, implemented in the fragment's own scoped `<style>`/IIFE `<script>` scoped to its own instance.
- Below the tablet breakpoint (`foundations/responsive.md` §17.1) the lead card stacks above the carousel, which is finger-scrollable.
