---
kind: shape
name: title-meta-stack
aliases: [page header stack, title block, header stack, eyebrow title meta]
status: stable
slots:
  - { name: eyebrow, required: false, accepts: [eyebrow] }
  - { name: title, required: true, accepts: [h1] }
  - { name: meta, required: false, accepts: [meta-row, date] }
variants: [centered, left, left-ruled]
self_contained: false
content_defaults: {}
---

# title-meta-stack — Title/eyebrow/meta header stack

A vertical stack that opens a Page: an optional eyebrow over the page h1 over an optional metadata row. The `centered` variant centers every line; the `left` variant left-aligns the stack; the `left-ruled` variant left-aligns the stack and closes it with a hairline rule beneath the metadata row.

## Determinations

- The stack sits at container width, first in the Page's content flow.
- `centered` variant: all lines center on the reading axis, and the stack sits inside the container width, not the reading column; the title carries `text-align: center`. Padding to the following Section is `--sp-3` (calibrates to 48px at the reference viewport).
- `left-ruled` variant: a single hard 1px rule at `--border-strong` separates the metadata row from what follows. Zero radius anywhere in the stack; structure relies on whitespace and the hairline.
- `left` variant: the stack is left-aligned with no rule; line work is absent.
