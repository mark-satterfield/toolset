---
kind: section
name: doc-header
id: D1
family: docs
aliases: [document title, doc title block, legal page header]
status: stable
mode: deterministic
content_contract: {}
theme: editorial
composition_notes: []
---

# D1 — Doc header

The title block of a documentation page: the page h1 and its metadata row.

## Slots

- `title` — the page h1 at the Editorial-Display-2 role.
- `metadata` — effective-date stamp and "Previous Version" link at the Text Label role; optional language picker (a single-option dropdown by default).

## Determinations

- A single hard 1px rule at `--border-strong` separates the metadata row from the body — the only line work on the page.
- Zero radius anywhere in the header; structure relies on whitespace and the hairline.
