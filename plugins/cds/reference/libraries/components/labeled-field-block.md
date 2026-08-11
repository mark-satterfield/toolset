---
kind: component
name: labeled-field-block
aliases: [labeled field, field block, titled input, input with instructions, field with actions]
status: stable
slots:
  - { name: label, required: true, accepts: [text] }
  - { name: label-action, required: false, accepts: [icon-button] }
  - { name: tag-row, required: false, accepts: [outline-pill-badge, inverted-pill-badge] }
  - { name: field, required: true, accepts: [text-input, textarea] }
  - { name: helper, required: false, accepts: [text] }
sizing:
  label-type: "the compact body size, weight 700"
  label-gap: "--sp-0-5 between the label row and whatever follows it"
  tag-row-gap: "--sp-0-25 between adjacent tags; --sp-0-5 between the tag row and the field"
  stack-gap: "--sp-0-5 between the field and its helper"
behavior:
  - "the label row's trailing actions apply to the block as a whole (clear it, remove it, attach to it), never to a single character of its content"
  - "the field owns its own focus, error, and disabled contracts"
accessibility:
  - "the label is a real <label> bound to the field by for/id, so clicking it focuses the field"
  - "each label-action is its own <button> with an aria-label naming its verb and the block it acts on"
  - "the helper is referenced by the field's aria-describedby"
token_bindings: [--text-primary, --text-secondary, --text-tertiary, --sp-0-25, --sp-0-5, --focus-ring]
composite: true
---

# Labeled field block

One input presented with its name, the actions that apply to it, and the instructions for filling it. A label row at the top — the field's name at the start, its block-level actions at the end — then an optional row of categorizing tags, then the field itself, then optional helper text.

The field is a text input or textarea Component (`libraries/components/text-input.md`, `libraries/components/textarea.md`), which brings its own border, ground, focus ring, and error contract. This entry composes them; it restates none of them.

Distinct from the editor card (`libraries/components/editor-card.md`), which frames one labelled turn of a message sequence as a card with a corner role badge. This block sits directly on the surrounding ground with no card framing.

## Variants

- `tag-row`: `absent` (default) | `present` — a single row of categorizing tags between the label row and the field, naming what the field's content is classified as.
- `label-action`: `absent` (default) | `present` — one or more icon buttons at the trailing edge of the label row.

## Determinations

- The label row is a flex row: the label at the start, the actions at the end via `margin-inline-start: auto`. The row's height is the label's line box — the actions do not inflate it.
- Label at the compact body size, weight 700, ink `var(--text-primary)`. The name of a field is heavier than the content of one.
- `var(--sp-0-5)` between the label row and what follows, and between the field and its helper.
- The tag row is a single wrapping run of pill badges (`libraries/components/outline-pill-badge.md`, `libraries/components/inverted-pill-badge.md`) with `var(--sp-0-25)` between adjacent tags, start-aligned to the label above it.
- Instructions for filling the field are the field's placeholder when they are a short restatement of what to type, and the helper line when they qualify or constrain what is typed. A placeholder is not a label and never replaces one.
- Helper text at the caption size in `var(--text-secondary)`; the field's own error message overrides it in place rather than stacking beneath it.

## Accessibility

- The label is a `<label>` bound to the field with `for`/`id`. A placeholder is not an accessible name — it disappears on input, and a field whose only name is its placeholder becomes anonymous the moment it is filled.
- Each label action is its own `<button>` with an `aria-label` naming both the verb and the block it acts on, since it sits outside the field and a screen reader reaches it without that context.
- The helper line carries an `id` referenced by the field's `aria-describedby`, so it is announced with the field rather than stranded above it.
- The tags are read as content, not as controls; a tag that filters or removes something is a filter chip (`libraries/components/filter-chip.md`), not a badge.
- Focus paints the foundation ring on `:focus-visible` (`foundations/accessibility.md` §18.2).
