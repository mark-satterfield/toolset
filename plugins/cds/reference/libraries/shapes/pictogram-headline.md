---
kind: shape
name: pictogram-headline
page_family: shared
aliases: [icon over headline, pictogram header, illustrated section title, mascot headline, animated icon heading]
status: stable
slots:
  - { name: pictogram, required: true, accepts: [svg-glyph, animated-media] }
  - { name: headline, required: true, accepts: [heading] }
  - { name: subhead, required: false, accepts: [text] }
  - { name: cta, required: false, accepts: [button] }
variants: [with-subhead, with-cta, mark-only]
self_contained: false
content_defaults: {}
---

# pictogram-headline — Pictogram above a centered headline

A centered column opening with a small pictogram, the section's headline beneath it, and optionally one supporting line and one action. Nothing follows within the Section: the arrangement introduces the run of Sections after it rather than holding content of its own.

Distinct from centered-stack, which places its visual *below* the heading block as the Section's main content, and from pictogram-subcards, which anchors a run of sub-cards. Here the pictogram is a small mark above the words, and the words are the point.

## Determinations

- One centered column. Every part is centered on the column's axis, and the column takes the `--column-medium` measure so the headline breaks on a comfortable line rather than the full page width.
- The pictogram sits at the column's block-start edge, sized to the feature icon scale (`foundations/imagery.md` §16.1), with `--sp-1-5` beneath it. It is small relative to the headline — it marks the section, it does not illustrate it.
- Headline directly beneath the pictogram at the Section's heading role.
- `subhead`, when the content supplies it, sits `--sp-1` beneath the headline at the body size and takes the reading measure so it breaks on two or three lines rather than one long one.
- `cta`, when the content supplies it, sits `--sp-2` beneath whatever precedes it, centered.
- The centered register binds: this arrangement is only correct where the content that follows it also reads centered or reads as a full-width run of peers (`libraries/shapes/CONVENTIONS.md`, Heading alignment registers). A centered headline never sits above left-reading long-form content.

## Animated pictogram

The `pictogram` slot accepts an animated asset. When it carries one, the animated-media contract binds (`foundations/imagery.md` §16.5): a static first frame is supplied as the reduced-motion fallback, the animation is gated behind `@media (prefers-reduced-motion: no-preference)`, and an animation running longer than five seconds carries a pause control. The layout is identical either way — the animation never changes the pictogram's box.

## Universal Section slots

An `eyebrow` supplied by the Section sits between the pictogram and the headline at the caption role, centered. A supplied `media` is not placed by this arrangement: the pictogram is this Shape's visual, and a Section carrying both wants a different arrangement.
