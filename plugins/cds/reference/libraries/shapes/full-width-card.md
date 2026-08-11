---
kind: shape
name: full-width-card
aliases: [spanning card, promo card layout, summary card layout]
status: stable
slots:
  - { name: lead, required: true, accepts: [label, heading, body, cta-group] }
  - { name: media, required: false, accepts: [illustration, sparkline] }
  - { name: action, required: false, accepts: [button, link] }
variants: [split, summary]
self_contained: false
content_defaults: {}
---

# full-width-card — Full-width card

A single card spanning the full width of the vacant space: a lead content block, an optional media element, and an optional trailing action.

```html
<section class="full-width-card full-width-card--split">
  <div class="full-width-card__lead">
    <h2>…</h2>
    <p>…</p>
    <button class="btn-primary">…</button>
  </div>
  <div class="full-width-card__media">…</div>
</section>
```

## Determinations

- The card spans the full width of the vacant space.
- Card inner padding is `--sp-2`.
- `split` variant: the lead text block sits on the left, the media on the right.
- `summary` variant: the lead (a short label) and the media (the series visualization) fill the card, with the optional action aligned to the right edge.
