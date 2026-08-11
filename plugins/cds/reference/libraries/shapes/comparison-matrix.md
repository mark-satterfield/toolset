---
kind: shape
name: comparison-matrix
aliases: [feature comparison, compare plans, comparison table, competitor comparison, plan matrix, feature matrix]
status: stable
slots:
  - { name: filter, required: false, accepts: [list-filter] }
  - { name: subject-headers, required: true, accepts: [text, button] }
  - { name: groups, required: true, accepts: [heading] }
  - { name: rows, required: true, accepts: [text, tooltip] }
  - { name: cells, required: true, accepts: [icon-glyph, outline-pill-badge, text] }
variants: [with-filter, without-filter, static-groups, collapsible-groups]
self_contained: true
content_defaults: {}
---

# comparison-matrix — Attributes down, subjects across, with a way to find a row

A table comparing many attributes across several subjects: attributes run down the start column in named groups, subjects run across the top with their own action, and each cell states whether that subject has that attribute. The arrangement a Section takes when the comparison is too long to read and must be searched.

The subjects are whatever is being compared — the tiers of one offering, or one offering against its competitors. The arrangement does not care which; it fixes how a long comparison stays readable.

Distinct from rate-table, which lists priced units against rate categories and has no per-column action and no grouping, and from comparison-fork, which contrasts two exclusive paths as prose columns rather than as a matrix.

## Determinations

- `filter`, when present, is a list-filter Component (`libraries/components/list-filter.md`) anchored at the start of the header band. It filters the rows in place: matching rows remain, non-matching rows are removed, and a group whose rows have all been removed is removed with them. It never filters the subject columns.
- The subject header is a sticky row: each column carries the subject's name over its own action (`libraries/components/button.md`), so the action stays reachable however far the reader has scrolled. The start column's header is empty — it labels the attributes, which name themselves.
- Groups divide the rows. Each group is a full-width heading row spanning every column, set at the Section's sub-heading role, start-aligned.
- The `collapsible-groups` variant makes each group heading a disclosure carrying its own expand/collapse control at the row's trailing edge, following the disclosure contract in `libraries/shapes/accordion.md`. Groups open by default: a comparison that hides its content on arrival has not compared anything.
- Attribute rows are a start-column label and one cell per subject. A label may carry a tooltip (`libraries/components/tooltip.md`) for a term the label alone cannot carry.
- A cell states one of: **present** (a filled check glyph), **absent** (a light cross glyph), **qualified** (an outline pill badge carrying the qualifying value), or **not applicable** (a muted pill). Presence is never signalled by color alone — the glyph shape carries it, so the matrix survives a monochrome rendering (WCAG 1.4.1).
- Cells are centered in their column; the attribute label is start-aligned. Rows alternate no ground; separation is a hairline `var(--border-subtle)` rule beneath each row.
- Below the tablet breakpoint (`foundations/responsive.md` §17.1) the matrix scrolls horizontally within its own container with the attribute column pinned, rather than reflowing into stacked cards — a comparison that cannot be read across is not a comparison. The page itself never scrolls horizontally.

## Self-contained behavior

This Shape declares `self_contained: true`. Its fragment carries its own scoped `<style>` and a scoped IIFE `<script>` implementing the filter and, in the `collapsible-groups` variant, the disclosure contract — including `aria-expanded` on each group control and the group's `hidden` state. The script scopes itself to its own instance so several matrices on one page never collide.

## Accessibility

- The matrix is a real `<table>` with `<th scope="col">` on each subject header and `<th scope="row">` on each attribute label, so the relationship between a cell and its subject and attribute is announced rather than inferred from position.
- Each cell's state is carried in text for assistive technology — a visually-hidden word accompanying the glyph — because a check glyph alone has no name.
- The filter announces its result count through a polite live region, so a keyboard or screen-reader user learns that filtering removed rows.
- The sticky header row does not obscure focus: a focused control scrolled beneath it is brought into view below it (WCAG 2.4.11).
- Group disclosure controls are `<button>` elements carrying `aria-expanded`, and the group's rows are hidden with `hidden` rather than with visual clipping.

## Universal Section slots

A supplied `eyebrow` and the Section's heading sit above the matrix in the default heading stack. A supplied `media` sits between the heading stack and the header band — the arrangement this Section most often opens with is a pictogram-headline Section directly above it.
