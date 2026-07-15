---
kind: section
name: doc-body
page_family: docs
aliases: [document body, reference body, legal body]
status: stable
shape: reading-column
content_contract: {}
theme: editorial
composition_notes: []
---

# Doc body

The long-form reference prose of a documentation page. Its layout is the `reading-column` Shape (`libraries/shapes/reading-column.md`) — the `with-sidebar` variant when in-page navigation is supplied, otherwise `centered`; the docs page family supplies the typography register below.

## Content

- `prose` — hand-numbered h2 headings ("1. Section name.", "11. Next section.") with paragraphs, ordered lists, and defined terms.
- `sidebar` — optional in-page anchor links that honor the root smooth-scroll.

## Determinations

- Section h2s use the editorial Headline 5 role; body paragraphs use Body 2 with the `.serif` modifier.
- Ordered lists set Editorial Serif at the Body 2 size, weight 400, line-height `--lh-140` (calibrates to 23.8px) — a declared departure from the Body 2 `.serif` role's 500 / 155%, as no §13.5 role defines 400-weight serif list text — with decimal markers at every level, no alphabetic nesting.
- Inline `<strong>` keeps the surrounding family at weight 600; defined terms are `<strong>` with bare quote marks in running text.
- No cards, no badges, no shadows, and no state colors anywhere in the body; all-caps disclaimers are set as upper-case source text, never via `text-transform: uppercase`.
