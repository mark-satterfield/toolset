---
kind: section
name: doc-body
family: docs
aliases: [document body, reference body, legal body]
status: stable
mode: deterministic
content_contract: {}
theme: editorial
composition_notes: []
---

# Doc body

The long-form reference prose of a documentation page, set in the reading column with an optional sticky side navigation.

## Slots

- `prose` — hand-numbered h2 headings ("1. Section name.", "11. Next section.") with paragraphs, ordered lists, and defined terms.
- `sidebar` — optional sticky sidebar to the right of the reading column, carrying in-page anchor links that honor the root smooth-scroll.

## Determinations

- The prose sits in a `--column-reading` reading column (calibrates to 640px): centered when no sidebar is present, left-aligned with the sticky sidebar to the right when one is. Below 700px the column takes the full content width.
- Section h2s use the editorial Headline 5 role; body paragraphs use Body 2 with the `.serif` modifier.
- Ordered lists set Editorial Serif at the Body 2 size, weight 400, line-height `--lh-140` (calibrates to 23.8px) — a declared departure from the Body 2 `.serif` role's 500 / 155%, as no §13.5 role defines 400-weight serif list text — with decimal markers at every level, no alphabetic nesting.
- Inline `<strong>` keeps the surrounding family at weight 600; defined terms are `<strong>` with bare quote marks in running text.
- No cards, no badges, no shadows, and no state colors anywhere in the body; all-caps disclaimers are set as upper-case source text, never via `text-transform: uppercase`.
