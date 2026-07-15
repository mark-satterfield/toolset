---
kind: section
name: related-content
page_family: editorial
aliases: [related content, related articles, read next]
status: stable
shape: card-grid
content_contract: {}
theme: editorial
composition_notes: []
---

# Related content

The closing content Section of an editorial-detail page: a rail of related entries inviting the reader onward. Its layout is the card-grid Shape (`libraries/shapes/card-grid.md`) with exactly 3 cards in a single row.

## Content

- The cards are realized by the related-rail Component (`libraries/components/related-rail.md`) carrying exactly 3 items.
- The rail title uses the editorial Headline 4 role; item deks use Body 3 with the `.serif` modifier.
- Whole-card hover dims opacity over 200ms; cards fade on scroll into view per the editorial motion register.
