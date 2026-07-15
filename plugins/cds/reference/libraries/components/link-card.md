---
kind: component
name: link-card
page_family: editorial
aliases: [link card, navigation card, asset card]
status: stable
slots:
  - { name: title, required: true, accepts: [heading] }
  - { name: body, required: true, accepts: [text] }
sizing:
  border: "hairline (--border-subtle)"
behavior: [hover-color-transition]
accessibility: [whole-card-anchor, focus-visible-ring]
token_bindings:
  - --text-primary
  - --text-secondary
  - --border-subtle
shell_component: false
composite: false
---

# Link card

A card that links to another page or asset, with emphasis on the title: title + body + hairline border.

## Determinations

- Title renders in Editorial Serif at the H6 scale.
- Border is the `--border-subtle` hairline.

## Behavior

- Hover transitions the title text from `--text-primary` toward `--text-secondary` over 300ms — secondary is the conventional next-step ink for the hover target.

## Accessibility

- The entire card wraps in a single `<a>` so the focus ring lights the full card, not a sub-element.
- On `:focus-visible`, paint the foundation focus ring (`outline: 2px solid var(--focus-ring); outline-offset: 2px`).
