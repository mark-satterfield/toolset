---
kind: section
name: publication-list
aliases: [publication list, article list, post index, archive list]
status: stable
shape: listing-rows
content_contract: {}
theme: editorial
composition_notes: []
---

# Publication list

The chronological index of a resource-index Page: every published entry, one row apiece, filterable in place. Its layout is the listing-rows Shape (`libraries/shapes/listing-rows.md`).

## Content

- The filter slot carries a search-input Component (`libraries/components/search-input.md`) used as an inline list filter over the entries.
- Each row carries an entry's date, category, and title.
- The optional sticky sidebar carries supporting content alongside the index.
- The pagination slot carries a pagination indicator (`libraries/components/pagination.md`); no numbered page buttons.
