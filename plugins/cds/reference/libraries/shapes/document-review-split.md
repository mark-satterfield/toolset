---
kind: shape
name: document-review-split
aliases: [document review, preview and rationale, review pane, draft review, side-by-side review]
status: stable
slots:
  - { name: preview, required: true, accepts: [content] }
  - { name: summary, required: false, accepts: [score-verdict, text] }
  - { name: section-rationale, required: true, accepts: [text, button] }
  - { name: commit-actions, required: true, accepts: [button] }
variants: [rationale-rail, rationale-inline]
self_contained: false
content_defaults: {}
---

# document-review-split — The document beside the reasoning behind it

A rendered document on one side and, on the other, a rail explaining each of its sections and offering to change them. The arrangement for reviewing something a system produced before accepting it.

## The document is the dominant column

The document takes the larger span and renders as it will actually be read — its own type, its own spacing, no review chrome inside it. A review surface that annotates the document in place makes it impossible to judge how the document itself reads, which is the one thing the reviewer is there to do.

The rationale lives beside it, and the two stay aligned: selecting a section in the document brings its rationale into view, and selecting a rationale brings its section into view. Neither is a list the reader has to map onto the other by hand.

## Determinations

- Two columns filling the vacant space: the preview at the dominant span, the rationale rail at the remainder, each scrolling independently.
- `summary`, when present, sits at the rail's block-start: an overall readiness verdict (`libraries/components/score-verdict.md`) with its plain-language reason.
- The rail is one entry per document section: the section's name, why it was written the way it was, and the controls to regenerate or edit just that section.
- Regeneration is per section. A control that rewrites the whole document discards every section the reviewer had already accepted.
- Editing a section happens in the preview, in place, with the rail's entry for that section marking it as edited. The document stays the thing being read.
- `commit-actions` sit at the surface's block-end, spanning both columns: accepting the document as a draft, and discarding.
- Accepting produces a draft rather than a final artifact, so the reviewer's acceptance is a checkpoint and not a publication.
- The `rationale-inline` variant, for a narrow viewport, moves each rationale beneath its own section in a single column, keeping the pairing at the cost of the side-by-side read.
- Below the tablet breakpoint (`foundations/responsive.md` §17.1) the `rationale-inline` variant is used regardless of which variant was declared — two columns at that width leaves neither readable.

## Accessibility

- Each document section and its rationale are associated, so a screen reader moving through the rail can reach the section it describes and back.
- The linked scrolling is a convenience, not the only route: both columns are independently navigable in their own reading order.
- Per-section controls name their verb and their section, since they repeat down the rail.
- Commit actions are the last tab stops in the surface, matching their position.
