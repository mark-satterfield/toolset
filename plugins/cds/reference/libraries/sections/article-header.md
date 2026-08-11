---
kind: section
name: article-header
aliases: [article header, post header, article hero]
status: stable
shape: title-meta-stack
content_contract: {}
theme: editorial
composition_notes: []
---

# Article header

The three-line header opening an editorial-detail Page: subjects line, title, date. Its layout is the `centered` variant of the title-meta-stack Shape (`libraries/shapes/title-meta-stack.md`).

## Content

- `eyebrow` — the subjects line: this Section binds the universal eyebrow slot (`libraries/FORMAT.md`, Universal Section slots) to the subjects position above the title. Body 3 with the `.bold` modifier (the role's documented editorial-eyebrow weight range, 500–700), sentence case.
- `title` — the article h1 at the editorial Headline 1 role (`text-wrap: balance`).
- `meta` — the date, Body 3 agate at `--text-tertiary`.

The Article hero Component (`libraries/components/article-hero.md`) realizes this Section.
