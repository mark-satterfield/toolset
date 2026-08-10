---
kind: shape
name: labeled-detail-rows
page_family: shared
aliases: [feature rows, spec list, capability rows, rule-separated rows, two-column detail list]
status: stable
slots:
  - { name: rows, required: true, accepts: [detail-row] }
variants: [with-glyphs, without-glyphs]
self_contained: false
content_defaults: {}
---

# labeled-detail-rows — Hairline-separated rows of title and explanation

A vertical run of two-column rows, each a short title in the start column and its explanation in the end column, divided by hairline rules. The arrangement a Section takes when it makes several points that share a structure and differ only in content — guarantees, capabilities, specifications.

Distinct from alternating-rows, which pairs each row with an image and flips the image side down the run. There is no media here: the run reads as a specification, not as a story.

## Determinations

- One vertical stack of detail-row Components (`libraries/components/detail-row.md`), each taking the full width of the Section's container.
- A `1px solid var(--border-subtle)` rule separates adjacent rows. The run draws a rule above the first row and none after the last, so the run reads as a bounded band rather than as a list that stopped.
- The rows share a column split — the title column and the description column align down the whole run — so a reader scans the titles as one column.
- Row block padding comes from the row Component; this arrangement supplies only the rules between them.
- The left register binds: the content reads left, so any heading above the run is start-aligned (`libraries/shapes/CONVENTIONS.md`, Heading alignment registers). A centered heading above this run is a composition error.
- `with-glyphs` and `without-glyphs` apply to the whole run: every row carries a glyph or none does, so the title column starts at one inline offset down the run.

## Universal Section slots

A supplied `eyebrow` and the Section's heading sit above the run in the default heading stack, start-aligned, with the run's first rule beneath them. A supplied `media` sits between the heading stack and the first row, full width.
