---
kind: shape
name: centered-stack
family: landing
aliases: [centered hero, hero with video below, text over visual]
status: stable
slots:
  - { name: heading-block, required: true, accepts: [headline, subhead, cta-group] }
  - { name: visual, required: true, accepts: [video, screenshot] }
variants: [visual-video, visual-screenshot]
self_contained: false
content_defaults: {}
---

# centered-stack — Centered text + visual below

Headline + subhead + CTAs centered; the visual (video or screenshot) sits below. Vertical stack, all centered horizontally — text block above visual.

## Determinations

- CTA count is 1–2; the first is a primary button, the optional second a tertiary/text button beside it with a `--sp-1` gap. Above 2 CTAs, use centered-affordance or banner-strip instead.
- The visual sits at a fixed 16:9 aspect ratio, capped at the full marketing primary container (`--container-marketing-primary`), with `--sp-4` between the text block and the visual.
- Below the tablet breakpoint (`foundations/responsive.md` §17.1) the CTA pair stacks vertically full-width; the visual stays 16:9 and reflows to container width.
