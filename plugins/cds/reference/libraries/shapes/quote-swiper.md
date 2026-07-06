---
kind: shape
name: quote-swiper
family: landing
aliases: [testimonial slider, rotating quotes, quote carousel]
status: stable
slots:
  - { name: quote-viewport, required: true, accepts: [quote, attribution, metric] }
  - { name: logo-carousel, required: true, accepts: [logo] }
variants: [auto-advance-on, auto-advance-off, with-metric, without-metric]
self_contained: true
content_defaults: {}
---

# quote-swiper — Quote swiper with logos

A rotating quote in a viewport (one quote at a time with attribution) stacked above a paired logo carousel; both rotate in sync.

## Determinations

- Quote count and logo count are equal and paired one-to-one — each quote is bound to its source's logo; the logo carousel advances to the same index as the quote.
- Auto-advance is off by default; when on, it pauses on hover/focus and is suppressed under reduced motion, falling back to manual prev/next. Advance interval is ~7s when auto-advance is on.

## Self-containment

The synchronized rotation is shape-level behavior, not provided by the generated component stylesheet or any shared script. The fragment carries its own scoped `<style>` and a scoped IIFE `<script>` that scopes itself to its own instance(s) so multiple copies on one page never collide; it implements the paired quote/logo index advance, the hover/focus pause, and the reduced-motion suppression with manual prev/next as the static fallback.
