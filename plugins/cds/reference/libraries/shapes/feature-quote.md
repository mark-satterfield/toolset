---
kind: shape
name: feature-quote
aliases: [hero testimonial, big quote, featured quote]
status: stable
slots:
  - { name: quote, required: true, accepts: [quote] }
  - { name: metric, required: false, accepts: [metric] }
  - { name: attribution, required: true, accepts: [attribution] }
variants: [with-metric, without-metric]
self_contained: false
content_defaults: {}
---

# feature-quote — Single hero quote

One large quote, often with a metric, treated as a near-hero element: a single dominant block at near-hero scale.

## Determinations

- The quote is capped at a `--column-medium` reading column inside the page-width section with `text-wrap: balance` and runs no longer than ~240 characters; longer testimonials use stacked-quotes instead.
- When present, the metric sits above the quote as an oversized display number (Primary Sans, weight 600–700), with attribution below the quote.
- Vertical padding uses `--section-pad-large` to give the block its near-hero scale.
