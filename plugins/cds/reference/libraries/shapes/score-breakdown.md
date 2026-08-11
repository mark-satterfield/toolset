---
kind: shape
name: score-breakdown
aliases: [scorecard, score detail, contribution breakdown, why this score, assessment detail]
status: stable
slots:
  - { name: headline-verdict, required: true, accepts: [score-verdict] }
  - { name: component-rows, required: true, accepts: [text] }
  - { name: gap-report, required: false, accepts: [text] }
variants: [inline, panel]
self_contained: false
content_defaults: {}
---

# score-breakdown — The named parts that produced a score

The headline verdict, then one row per named component of the assessment: what that component is, what it contributed, and why in plain language. The arrangement that makes a score answerable rather than final.

## Determinations

- The headline verdict opens the arrangement as a score-verdict Component (`libraries/components/score-verdict.md`) at its `full` density, with a hairline rule beneath it.
- Each component row is: the component's name at the inline-start, its contribution at the inline-end, and its rationale on a second line spanning the row. The contribution is stated in the same unit as the headline score so the parts visibly relate to the whole.
- Rows are separated by hairline rules and share one column split, so contributions align down the run.
- Every row carries a rationale. A named component with a number and no sentence has moved the black box down a level rather than opening it.
- Rationales are written in the user's terms. A row that names an internal field, a model, or a weight has described the machine instead of the result.
- `gap-report`, when the content supplies one, closes the arrangement beneath a rule: what specifically is missing, and what would close it. It is informational — it states what is absent, never what the user should do about their situation.
- The gap report is present only when there is a genuine gap to state. An arrangement that manufactures one for a strong result has invented a deficiency.
- The `inline` variant renders the rows directly in the surrounding surface; the `panel` variant renders them inside a scrollable pane, for a drawer or a tab where the run may be long. The row contract is identical.

## Scannability

The run is read by scanning, so the rows stay uniform: one line of name and contribution, one line of rationale, no nested lists, no per-row cards, no expand-to-see-the-reason. A rationale long enough to need collapsing is too long for this arrangement.

## Accessibility

- The rows are a description list, so each contribution and rationale is announced with the component name it belongs to.
- The contribution is announced with its unit, never as a bare number.
- The headline verdict keeps its own contract from `libraries/components/score-verdict.md`.
