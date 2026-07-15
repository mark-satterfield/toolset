---
kind: shape
name: logo-marquee
page_family: landing
aliases: [logo ticker, scrolling logos, logo wall, marquee]
status: stable
slots:
  - { name: items, required: true, accepts: [logo, icon] }
variants: [right-to-left, left-to-right, pause-on-hover, duplicated-item-set, unique-item-set]
self_contained: true
content_defaults: {}
---

# logo-marquee — Marquee strip

A continuously scrolling single full-width horizontal row of logos/icons; items may duplicate to fill the loop.

## Determinations

- The item set duplicates to fill at least two viewport widths so the loop is seamless. Default scroll direction is right-to-left.
- Scroll completes one full loop in ~40s (a calm, non-distracting speed); item-to-item spacing is `--sp-4`. The strip pauses on hover.
- The animation is purely decorative: it is gated behind `prefers-reduced-motion: no-preference` and the strip renders as a static, wrapped row under reduced motion.

## Self-containment

This scroll is shape-level animation, not a component-family style, so the generated component stylesheet does not define it. The shape fragment must therefore be self-contained: it carries its own scoped `<style>` with the keyframes. Under `@media (prefers-reduced-motion: no-preference)` the `.cds-marquee__track` is `flex-wrap: nowrap` and runs a `transform: translateX(-50%)` loop over the duplicated item set for the ~40s duration; the reduced-motion baseline is `flex-wrap: wrap`, static. A fragment that only sets `flex-wrap: wrap` and defers keyframes to "the stylesheet" is broken — the strip will never scroll.
