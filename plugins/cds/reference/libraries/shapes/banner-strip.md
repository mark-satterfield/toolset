---
kind: shape
name: banner-strip
family: landing
aliases: [CTA strip, banner, announcement band]
status: stable
slots:
  - { name: headline, required: true, accepts: [headline] }
  - { name: cta-group, required: true, accepts: [button] }
variants: [single-cta, dual-cta]
self_contained: false
content_defaults: {}
---

# banner-strip — Banner strip

A narrow full-width strip: one headline and 1–2 CTAs, no visual.

## Determinations

- The strip takes its Section's scheduled ground from `rules/page-constraints/ground-alternation.md` like every other shape; it does not choose its own ground. Its distinctness comes from its narrow `--section-pad-small` height and single full-width row, not from a self-chosen surface.
- Headline and CTAs sit on one row, headline left and CTAs right, spanning the page-width section wrapper (`.u-container`); vertical padding uses `--section-pad-small`. Below the tablet breakpoint (`foundations/responsive.md` §17.1) the CTAs wrap beneath the headline.
- CTA count is 1 or 2.
