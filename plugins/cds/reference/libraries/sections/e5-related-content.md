---
kind: section
name: related-content
id: E5
family: editorial
aliases: [related content, related articles, read next]
status: stable
mode: deterministic
content_contract: {}
theme: editorial
composition_notes: []
---

# E5 — Related content

The closing content Section of an editorial-detail page: a rail of related entries.

## Slots

- `rail` — the related-rail Component (`libraries/components/related-rail.md`) carrying exactly 3 items.

## Determinations

- The rail title uses the editorial Headline 4 role; item deks use Body 3 with the `.serif` modifier.
- Whole-card hover dims opacity over 200ms; cards fade on scroll into view per the editorial motion register.
