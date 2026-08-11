---
kind: component
name: social-share-row
aliases: [share row, social share, share icons]
status: stable
slots:
  - { name: icon-links, required: true, accepts: [icon-link-pair] }
  - { name: top-rule, required: true, accepts: [hairline] }
sizing:
  margin_top: "--sp-3 (foundations/layout.md §11.4)"
  padding_top: "--sp-3 (foundations/layout.md §11.4)"
  icon_hit_area: "32×32px with a 20×20 SVG glyph centered"
behavior: [icon-hover-color-shift]
accessibility: [aria-labelled-icon-links, focus-visible-ring, tap-target]
token_bindings:
  - --border-strong
  - --text-primary
  - --text-tertiary
  - --focus-ring
composite: false
---

# Social-share row

A two-icon share row above a hairline rule, typically at the foot of an editorial article: two icon links + a 1px top rule. Static at rest.

## Determinations

- `margin-top` and `padding-top` are both `--sp-3` (resolved in `foundations/layout.md` §11.4).
- Icon links inherit the product family's icon-button base — a `32×32px` touch hit-area with a `20×20` SVG glyph centered.
- **Tap target.** The 32×32 hit area clears the WCAG 2.2 AA minimum target size (2.5.8, 24×24). The 44×44 size is the WCAG 2.5.5 **AAA** target size — host projects targeting AAA ship the icon links at `≥44×44px`.

## Behavior

- **Social-icon hover:** the icon's `currentColor` glyph shifts from `--text-tertiary` toward `--text-primary` over 100ms — matching the footer-link hover treatment so the row reads as one consistent hover vocabulary.

## Accessibility

- Each icon link is an `<a>` with an `aria-label` naming the destination service (e.g., `aria-label="Share on LinkedIn"`); the SVG glyph carries `aria-hidden="true"`.
- Focus paints the foundation focus ring on `:focus-visible` (`outline: 2px solid var(--focus-ring); outline-offset: 2px`). (WCAG 2.4.7, 2.4.11.)

## Default service pair

The row ships a "copy link" action and a generic "share" action (the platform Web Share API where available, falling back to copy-link) as its default pair, so the row carries no brand-network dependency. Host projects may substitute named-network icons by replacing the two slots.
