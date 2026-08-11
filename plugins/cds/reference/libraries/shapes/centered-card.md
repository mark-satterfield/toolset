---
kind: shape
name: centered-card
aliases: [floating card, single centered card, conversion card layout]
status: stable
slots:
  - { name: input, required: true, accepts: [text-input] }
  - { name: primary-cta, required: true, accepts: [button] }
  - { name: divider, required: false, accepts: [divider-label] }
  - { name: secondary-ctas, required: false, accepts: [button-group] }
  - { name: legal, required: false, accepts: [legal-blurb] }
variants: []
self_contained: false
content_defaults: {}
---

# centered-card — Single centered floating card

A single floating card centered in the vacant space, its slots stacked vertically inside it in order: input, primary-cta, divider, secondary-ctas, legal. The surrounding ground reflows around the card.

## Determinations

- Max-width is `--container-conversion-card` (calibrates to 448px) and holds at every breakpoint; the surrounding ground reflows.
- Inner padding is `--sp-2` at its floor (calibrates to 28px).
- Radius is `--radius-2xl` at the top of its clamp — the one place in the system that uses it (calibrates to 32px).
- Border is a 0.5px-feeling `1px solid` ink at 15% opacity; the shadow is the soft-floating 4-layer low-opacity stack (`foundations/layout.md` §11.8).
- The card surface is transparent against the page ground.
- The `input` slot sizing calibrates to 44px height, 9.6px radius, 12px horizontal padding at the reference viewport; a required marker in the slot carries a `--sp-0-25` left margin (calibrates to 4px).
- Secondary actions carry a 0.5px-feeling border and transparent fill; a secondary action carrying a 16×16 logo sets a `--sp-0-5` gap between the logo and its label (calibrates to 8px).
- Hover motion: scale 1.005 × 1.015 on the primary CTA with a 200ms `::after` radial-gradient highlight bloom; 100ms color and border transitions on the secondary buttons.
