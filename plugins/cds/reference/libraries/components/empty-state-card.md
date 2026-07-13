---
kind: component
name: empty-state-card
family: app
aliases: [empty state, empty-state card, zero state]
status: stable
slots:
  - { name: glyph, required: true, accepts: [line-art-svg] }
  - { name: caption, required: true, accepts: [text] }
  - { name: action, required: true, accepts: [secondary-button] }
sizing:
  padding: "--sp-2-5 (32–40px clamp, foundations/layout.md §11.4)"
  glyph: "48×48px"
  glyph_to_caption_gap: "--sp-1-5 (24px)"
  caption_to_action_gap: "--sp-1 (16px)"
behavior: []
accessibility: []
token_bindings:
  - --surface-raised
  - --text-tertiary
shell_component: false
composite: false
---

# Empty-state card

A card that occupies the location of an absent list/grid and explains the empty state with a glyph, caption, and action. Static at rest.

## Determinations

- Card padding `--sp-2-5` (32–40px clamp, `foundations/layout.md` §11.4), content centered.
- The glyph is a centered `48×48px` tiny line-art SVG in `--text-tertiary`, sitting `--sp-1-5` (24px) above the caption.
- Caption in tertiary ink at body-2 size.
- The action below is a secondary button (`libraries/components/button.md`) — empty states offer a recovery action, not a conversion, so the dominant primary fill is reserved for the populated surface. The button sits `--sp-1` (16px) below the caption.
