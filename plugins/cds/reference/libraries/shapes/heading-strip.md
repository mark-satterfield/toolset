---
kind: shape
name: heading-strip
aliases: [section label, standalone heading, section heading strip]
status: stable
slots:
  - { name: heading, required: true, accepts: [h2] }
  - { name: eyebrow, required: false, accepts: [eyebrow] }
variants: [with-eyebrow, without-eyebrow]
self_contained: false
content_defaults: {}
---

# heading-strip — Standalone heading strip

An H2 (and optional eyebrow) acting as a section label, with no content beneath. Single-row block: a vertical stack of the optional eyebrow over the H2.

## Determinations

- The strip spans the page-width section wrapper (`.u-container`) and is left-aligned, matching the reading-axis of the Sections it labels.
- Vertical padding uses `--section-pad-small`; the eyebrow-to-H2 gap is `--sp-0-75`.
- The eyebrow is the universal Section slot at its default placement (`libraries/FORMAT.md`, Universal Section slots), rendered directly above the H2.
