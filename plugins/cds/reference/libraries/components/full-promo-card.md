---
kind: component
name: full-promo-card
page_family: landing
aliases: [promo card, bordered promo card, product callout card]
status: stable
slots:
  - { name: content, required: true, accepts: [content-stack] }
sizing:
  radius: "--radius-xl (foundations/layout.md §11.7)"
  padding: "32px"
  border: "1px solid --border-subtle"
behavior: []
accessibility: [non-interactive-container, whole-card-link-option]
token_bindings:
  - --border-subtle
  - --surface-primary
composite: false
---

# Full promo card

A bordered card with a transparent fill used for product or feature callouts on landing surfaces: a 1px outer border, transparent fill, and a content stack inside. Static at rest.

## Determinations

- Radius `--radius-xl` (resolved in `foundations/layout.md` §11.7); inner padding 32px; border `1px solid var(--border-subtle)`.

## Accessibility

- The card is a non-interactive container — focus and hover live on the controls inside (CTA buttons, links).
- If a host implementation makes the entire card a single interactive surface, wrap the contents in a single `<a>` or `<button>` and apply the foundation focus ring (`outline: 2px solid var(--focus-ring); outline-offset: 2px`) to the wrapping interactive element on `:focus-visible`. (WCAG 2.4.7, 2.4.11.)
