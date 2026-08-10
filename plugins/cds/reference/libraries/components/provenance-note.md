---
kind: component
name: provenance-note
page_family: shared
aliases: [source note, data source, attribution line, freshness note, sourced from]
status: stable
slots:
  - { name: source, required: true, accepts: [text, tertiary-link] }
  - { name: freshness, required: false, accepts: [text] }
  - { name: glyph, required: false, accepts: [icon-glyph] }
sizing:
  gap: "--sp-0-25 between the glyph and the source, and between the source and the freshness"
  offset: "--sp-0-25 between the value and the note beneath it"
behavior:
  - "static; the note reports where a value came from and does not respond to interaction beyond its optional source link"
accessibility:
  - "the note is associated with the value it qualifies rather than standing alone"
  - "a relative freshness phrase also carries the absolute timestamp as its accessible title"
token_bindings: [--text-tertiary, --icon-size-inline, --sp-0-25]
composite: false
---

# Provenance note

Where a value came from and how current it is, stated beneath the value. A figure a system derived, retrieved, or inferred is only as trustworthy as its source, and a surface that shows the figure without the source asks the user to trust it blind.

Pairs with the confidence indicator (`libraries/components/confidence-indicator.md`): confidence says how sure, provenance says from where. A derived value often carries both, and they read on separate lines — the value, then confidence beside it, then provenance beneath.

## Variants

- `freshness`: `absent` (default) | `present` — an "as of" phrase after the source.
- `source-link`: `text` (default — the source named in plain words) | `link` — the source names a destination the user can open to verify it.

## Determinations

- One line beneath the value it qualifies, inset to the value's inline-start edge, `var(--sp-0-25)` below it.
- Caption size in `var(--text-tertiary)` — the quietest text role. The note is always subordinate to the value.
- The optional glyph sits at the line's inline-start at `--icon-size-inline`.
- Source and freshness are separated by a middle dot with `var(--sp-0-25)` on each side.
- Freshness is stated in the terms that matter for the value: a relative phrase where recency is what counts, an absolute date where the exact moment is what counts. A cached or stale value says so in words rather than being silently presented as current.
- The note wraps to the value's own measure rather than extending past it.

## Accessibility

- The note is associated with its value — within the same container, or referenced by the value's `aria-describedby` — so the two are announced together.
- A relative freshness phrase carries the absolute timestamp in a `<time datetime>` element, so a reader who needs the exact moment can reach it.
- A linked source is a real link whose accessible name identifies the destination, not "source".
