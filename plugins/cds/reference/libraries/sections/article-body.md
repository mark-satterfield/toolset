---
kind: section
name: article-body
page_family: editorial
aliases: [article body, post body, article content]
status: stable
shape: reading-column
content_contract: {}
theme: editorial
composition_notes: []
---

# Article body

The long-form prose of an editorial-detail page. Its layout is the `reading-column` Shape (`libraries/shapes/reading-column.md`), in the `centered` variant with no sidebar; the editorial page family supplies the typography register below.

## Content

- `prose` — headings, paragraphs, lists, blockquotes, inline links.

## Determinations

- Body paragraphs use the editorial Body 2 role with the `.serif` modifier; section h2s use Headline 5.
- Inline links carry the same ink as body text, underlined at 0.08em thickness with 0.18em offset.
- Blockquotes use the `--text-secondary` ink; their rule and padding geometry is the `reading-column` Shape's blockquote determination.
- The theme does not rotate inside the body; the whole Section stays on the principal editorial theme.
