---
kind: section
name: article-header
id: E1
family: editorial
aliases: [article header, post header, article hero]
status: stable
mode: deterministic
content_contract: {}
theme: editorial
composition_notes: []
---

# E1 — Article header

The centered three-line header opening an editorial-detail Section Container: subjects line, title, date, stacked and centered.

## Slots

- `subjects` — the eyebrow Component, this Section's declared eyebrow slot (the editorial exception named in `rules/page-constraints/eyebrow-scope.md`). Body 3 with the `.bold` modifier (the role's documented editorial-eyebrow weight range, 500–700), sentence case.
- `title` — the article h1 at the editorial Headline 1 role (`text-wrap: balance`, `text-align: center`).
- `date` — Body 3 agate at `--text-tertiary`.

## Determinations

- All three lines center on the reading axis; the header sits inside the container width, not the reading column.
- Padding to the following Section is `--sp-3` (calibrates to 48px at the reference viewport).
- The Article hero Component (`libraries/components/article-hero.md`) implements this arrangement.
