---
kind: section
name: doc-header
page_family: docs
aliases: [document title, doc title block, legal page header]
status: stable
shape: title-meta-stack
content_contract: {}
theme: editorial
composition_notes: []
---

# Doc header

The title block of a documentation page: the page h1 and its metadata row. Its layout is the `left-ruled` variant of the title-meta-stack Shape (`libraries/shapes/title-meta-stack.md`); the eyebrow slot is unfilled.

## Content

- `title` — the page h1 at the Editorial-Display-2 role.
- `meta` — effective-date stamp and "Previous Version" link at the Text Label role; optional language picker (a single-option dropdown by default).

The Shape's hairline beneath the metadata row is the only line work on the page.
