---
kind: component
name: pagination
family: editorial
aliases: [pagination, pager, prev-next]
status: stable
slots:
  - { name: indicator, required: true, accepts: [position-text] }
  - { name: prev-link, required: true, accepts: [text-link] }
  - { name: next-link, required: true, accepts: [text-link] }
sizing: {}
behavior: [disabled-boundary-links]
accessibility: [nav-landmark, decorative-indicator, disabled-semantics]
token_bindings:
  - --text-tertiary
shell_furniture: false
composite: false
---

# Pagination

Indicator-plus-text-links pagination: a "1 / 3" position indicator with Prev/Next text links. Never numbered page buttons. Static at rest.

## Accessibility

- Prev/Next are `<a>` when navigating to a distinct URL, or `<button>` when re-rendering in place.
- Wrap the strip in `<nav aria-label="Pagination">` per WAI-ARIA landmark guidance.
- Disabled Prev (on the first page) and disabled Next (on the last page) render with `opacity: 0.5; pointer-events: none; cursor: not-allowed` and `aria-disabled="true"` (link variant) or the HTML `disabled` attribute (button variant).
- The "1 / 3" indicator is decorative — wrap it in `<span aria-hidden="true">` and provide an adjacent visually-hidden `<span>` reading "Page 1 of 3" for screen readers.
- Keyboard contract is the HTML default: Tab visits Prev, then Next (the indicator is non-focusable and skipped); Enter activates `<a>`; Enter and Space activate `<button>`. (WAI-ARIA APG link/button patterns.)
