---
kind: shape
name: stacked-quotes
page_family: landing
aliases: [testimonial stack, pull quotes, quote stack]
status: stable
slots:
  - { name: quotes, required: true, accepts: [quote, attribution, logo, metric] }
variants: [with-logo, without-logo, with-metric, without-metric]
self_contained: false
content_defaults: {}
---

# stacked-quotes — 3-up stacked pull-quotes

Three quote blocks stacked vertically with no card framing or surface around each quote; attribution (name/role/org) sits under each.

## Determinations

- Three quotes is the default; the shape accepts 2–4 quotes using the same stacked treatment when a Section needs a different count.
- Quotes are centered in a `--column-medium` reading column inside the page-width section, with `--sp-5` between blocks. Attribution sits directly beneath each quote in tertiary ink.
