---
kind: section
name: page-header
aliases: [page heading, greeting header, screen title]
status: stable
shape: heading-action-row
content_contract:
  heading_form: "greeting | title"
  subhead: "present | absent"
  right_cluster: "actions | period-picker | none"
theme: default
composition_notes: []
---

# Page header

The heading row of an app Page: the `<h1>` and the optional cluster of controls beside it. The Page owns its heading — app Shell rails never duplicate it. Its layout is the `heading-action-row` Shape (`libraries/shapes/heading-action-row.md`).

Variants by content:

- **Greeting** — the `<h1>` is a time-personalized greeting ("Good morning, Alex") and the right cluster carries the workspace's create actions (a tertiary link + a primary button).
- **Title + subhead** — a plain `<h1>` with a one-line subhead beneath and an optional primary CTA on the right.
- **Title + period picker** — a plain `<h1>` with a right-aligned period picker ("‹ May 2026 ›").

## Determinations

- Greeting branch logic keys off local time: "Good morning" before 12:00, "Good afternoon" from 12:00 to 17:59, "Good evening" from 18:00 onward.
