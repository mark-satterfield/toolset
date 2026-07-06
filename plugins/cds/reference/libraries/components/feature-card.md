---
kind: component
name: feature-card
family: landing
aliases: [feature card, marginalia card, hairline card]
status: stable
slots:
  - { name: anchor, required: true, accepts: [hairline-edge] }
  - { name: content, required: true, accepts: [content-stack] }
sizing:
  padding: "12px (small) | 16px (medium) | 24px (large) | 32px (x-large)"
  anchor_border: "1px solid --border-subtle on the left or top edge"
behavior: []
accessibility: []
token_bindings:
  - --border-subtle
  - --text-primary
shell_furniture: false
composite: false
---

# Feature card

A marginalia-style content card with a hairline anchor on the left or top edge: the anchor plus a content stack. Static at rest.

## Determinations

- The left border is `1px solid var(--border-subtle)` — the marginalia anchor.
- Padding variants: `small` 12px, `medium` 16px, `large` 24px, `x-large` 32px.

## Variant selection

Use `small` (12px) for dense list-adjacent cards, `medium` (16px) as the default in-flow card, `large` (24px) for standalone feature callouts, and `x-large` (32px) for hero-adjacent cards that anchor a section. Match the variant to the section padding role in `foundations/layout.md` §11.3 — denser sections take the smaller paddings.
