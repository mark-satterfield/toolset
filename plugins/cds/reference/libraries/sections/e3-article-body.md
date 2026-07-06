---
kind: section
name: article-body
id: E3
family: editorial
aliases: [article body, post body, article content]
status: stable
mode: deterministic
content_contract: {}
theme: editorial
composition_notes: []
---

# E3 — Article body

The long-form prose of an editorial-detail page, set inside the centered reading column.

## Slots

- `prose` — headings, paragraphs, lists, blockquotes, inline links.

## Determinations

- The prose sits in a `--column-reading` centered reading column (calibrates to 640px) inside the container; below 700px the column takes the full container width.
- Body paragraphs use the editorial Body 2 role with the `.serif` modifier; section h2s use Headline 5.
- Inline links carry the same ink as body text, underlined at 0.08em thickness with 0.18em offset.
- Blockquotes set text at `--text-secondary` behind a 1px left rule at `--border-strong`, padded `--sp-0-25` block and `--sp-1` inline-start (calibrates to `4px 0 4px 16px`).
- The theme does not rotate inside the body; the whole Section stays on the principal editorial theme.
