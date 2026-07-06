---
kind: section
name: news-updates
id: T12
family: landing
aliases: [news, updates, changelog section, announcements, releases]
status: stable
mode: dynamic
content_contract:
  item_count: int
  has_emphasis_item: bool
theme: scheduled
composition_notes: []
---

# T12 — News / Updates

Recent releases, changelog entries, and announcements. The shape pick branches on `item_count` and `has_emphasis_item` (one featured item leading secondary cards) via `rules/shape-selection/t12.md`.
