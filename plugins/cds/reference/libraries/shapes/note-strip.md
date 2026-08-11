---
kind: shape
name: note-strip
aliases: [helper strip, footnote row, caption strip]
status: stable
slots:
  - { name: icon, required: true, accepts: [span] }
  - { name: note, required: true, accepts: [p] }
variants: [with-link, without-link]
self_contained: false
content_defaults: {}
---

# note-strip — Small note strip

A single narrow row: a leading glyph followed by one short sentence, which may carry an embedded link. A quiet annotation row that sits beneath heavier content without competing with it.

## Determinations

- Icon and note sit on one row, icon leading, baseline-aligned with the sentence.
- The row is set in tertiary ink (`--text-tertiary`) at caption scale.
