---
kind: section
name: hero-promo
page_family: app
aliases: [promo card, hero promotional card, upgrade banner card]
status: stable
shape: full-width-card
content_contract:
  cta_label: "primary CTA text"
theme: default
composition_notes: []
---

# Hero promo card

A promotional card on an app Page: a title ("Build faster with your team"), a 1–2-line body, and a primary CTA in the text block; a decorative art thumbnail beside it. The promo is the screen's onboarding or upgrade moment. Its layout is the `full-width-card` Shape (`libraries/shapes/full-width-card.md`), `split` variant — the text block carries the lead, the art carries the media.

## Determinations

- Art treatment: inline SVG that inherits the `--accent-heroes` slot via `currentColor` (`foundations/motion.md` §15.6) so it recolors per theme without per-theme artwork. No raster, no animation.
