---
kind: component
name: detail-row
page_family: shared
aliases: [feature row, icon detail row, titled description row, spec row, two-column row]
status: stable
slots:
  - { name: glyph, required: false, accepts: [icon-glyph] }
  - { name: title, required: true, accepts: [heading] }
  - { name: description, required: true, accepts: [text] }
  - { name: action, required: false, accepts: [button] }
sizing:
  column-split: "the title column takes 4 of the 12 grid columns and the description column the remaining 8; both collapse to one column below the tablet breakpoint"
  glyph-gap: "--sp-0-75 between the glyph and the title"
  row-padding: "--sp-2 block"
  action-gap: "--sp-1 between the description and its action"
behavior:
  - "static: the row paints, it does not hover or animate"
accessibility:
  - "the title is a heading at the level its surrounding run establishes; the row itself takes no role"
  - "the glyph is decorative and aria-hidden — the title carries the meaning"
  - "the action, when present, is its own control naming its own verb and subject"
token_bindings: [--border-subtle, --text-primary, --text-secondary, --text-tertiary, --sp-0-75, --sp-1, --sp-2]
composite: false
---

# Detail row

One point stated across two columns: a glyph and a short title at the start, the explanation at the end, and optionally one action beneath the explanation. The unit of a run of points that share a structure — capabilities, guarantees, specifications.

Distinct from the marginalia row (`libraries/components/marginalia-row.md`), which is an editorial pattern with a fixed 35ch measure and an optional table-of-contents rail. This row is a two-column split on the page grid.

## Variants

- `glyph`: `present` (default) | `absent` — the title column carries the title alone.
- `action`: `absent` (default) | `present` — one tertiary or secondary button beneath the description.

## Determinations

- The row is a two-column split on the 12-column grid (`foundations/layout.md` §11): the title column takes 4 columns, the description column takes 8. Below the tablet breakpoint (`foundations/responsive.md` §17.1) the columns stack, title first.
- Both columns are start-aligned to their column's block-start edge, so the title and the first line of the description sit on the same baseline.
- Glyph at `--icon-size-feature` on the `--icon-viewbox-xl` grid, `var(--sp-0-75)` from the title, ink `var(--text-tertiary)`.
- Title at the body size, weight 700, ink `var(--text-primary)`. It wraps within its column rather than spilling into the description column.
- Description at the body size, ink `var(--text-secondary)`.
- The action sits `var(--sp-1)` beneath the description, start-aligned to it.
- The row supplies its own block padding of `var(--sp-2)`. Separation between adjacent rows is the arranging Shape's contract, not this entry's — a row draws no rule of its own.

## Accessibility

- The title is a heading at the level the surrounding run establishes, so a run of rows reads as a list of peers.
- The glyph carries `aria-hidden="true"`; it decorates the title, it does not restate it.
- The action is its own control with an accessible name stating its verb and its subject, since a screen reader reaches it after the description rather than with the title.
- Focus paints the foundation ring on `:focus-visible` (`foundations/accessibility.md` §18.2).
