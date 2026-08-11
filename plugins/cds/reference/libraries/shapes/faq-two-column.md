---
kind: shape
name: faq-two-column
aliases: [two-column FAQ, question rail, indexed FAQ]
status: stable
slots:
  - { name: question-rail, required: true, accepts: [question-anchor] }
  - { name: answer-column, required: true, accepts: [question, answer] }
variants: [sticky-rail, static-rail]
self_contained: false
content_defaults: {}
---

# faq-two-column — Two-column indexed FAQ

A left rail of question anchors beside a right column of open answers; every answer is visible at once, with no expand/collapse.

## Determinations

- The section spans the page-width wrapper (`.u-container`). On the 12-column grid the question rail spans 4 columns and the answer column spans 8, separated by the grid gutter (`foundations/layout.md` §11.6).
- The rail lists each question as an in-page anchor (`<a href>`) pointing at its answer block; selecting one scrolls the answer column to that entry. No disclosure interaction — answers are open by default, which is why the shape carries no script.
- Answer blocks render in the order the content supplies them; each pairs its question heading over its answer body, separated from the next by a 1px hairline (`--border-subtle`) at the card-hairline weight (`foundations/layout.md` §11.9).
- Both rail and answers sit in the left register, matching the reading axis of the long-form answer copy.
- The `sticky-rail` variant pins the question rail within the section as the answer column scrolls; the `static-rail` variant lets the rail scroll away with the page.
- Below the tablet breakpoint (`foundations/responsive.md` §17.1) the rail moves above the answer column and the two stack to a single column; the rail anchors still jump to their answers.
