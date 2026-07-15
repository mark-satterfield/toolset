---
kind: shape
name: lead-side-grid
page_family: editorial
aliases: [featured lead grid, lead plus side stack, lead with side column]
status: stable
slots:
  - { name: lead, required: true, accepts: [featured-card] }
  - { name: side-stack, required: true, accepts: [featured-cards] }
variants: []
self_contained: false
content_defaults: {}
---

# lead-side-grid — Lead card beside a stacked side column

One lead card given the dominant span of the 12-column grid, beside a vertical stack of secondary cards in the remaining columns. The lead carries the visual weight; the side stack reads as a compact index alongside it.

```
| lead (1–9)                      | side-stack (10–13) |
|                                 |  card              |
|                                 |  card              |
|                                 |  card              |
```

## Determinations

- The lead occupies grid lines 1–9; the side stack occupies lines 10–13 (`foundations/layout.md` §11.6 grid).
- Below the tablet breakpoint the grid collapses to a single column: lead first, then the side stack.
- Card titles use the editorial Headline 4 role with an underline at 0.2em offset on hover; deks use Body 3 with the `.serif` modifier; date and category meta use Body 3 agate at `--text-tertiary`.
- Whole-card hover dims opacity over 200ms; cards fade on scroll into view.
