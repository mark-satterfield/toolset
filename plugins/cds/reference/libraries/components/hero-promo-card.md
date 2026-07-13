---
kind: component
name: hero-promo-card
family: landing
aliases: [hero promo card, hero-adjacent promo]
status: stable
slots:
  - { name: title, required: true, accepts: [heading] }
  - { name: body, required: true, accepts: [text] }
  - { name: cta, required: true, accepts: [tertiary-button] }
  - { name: sub-panel, required: true, accepts: [decorative-dark-panel] }
sizing:
  padding: "--sp-2-5 (32–40px clamp, foundations/layout.md §11.4)"
  radius: "--radius-xl (16–24px clamp, foundations/layout.md §11.7)"
  sub_panel_radius: "--radius-lg (16px)"
behavior: []
accessibility: []
token_bindings:
  - --surface-raised
  - --text-primary
  - --accent-heroes
shell_component: false
composite: false
---

# Hero promo card

A landing-page hero-adjacent promo with a decorative dark sub-panel inside the card: title + body + tertiary CTA + the sub-panel. Static at rest.

## Determinations

- Card padding `--sp-2-5` (32–40px clamp, `foundations/layout.md` §11.4); card radius `--radius-xl` (16–24px clamp, §11.7).
- The decorative sub-panel uses a local `deep` wrapper, sits at radius `--radius-lg` (16px), occupies the lower or trailing third of the card, and paints the `--accent-heroes` glyph (`foundations/motion.md` §15.6) via `currentColor` on the near-black ground.
- The accent glyph is supplied per theme through the `--accent-heroes` slot — never author per-theme artwork.
