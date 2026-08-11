---
kind: component
name: score-verdict
aliases: [match score, fit verdict, score badge, assessment result, rating verdict]
status: stable
slots:
  - { name: score, required: false, accepts: [text] }
  - { name: verdict, required: true, accepts: [text] }
  - { name: reason, required: false, accepts: [text] }
  - { name: breakdown-action, required: false, accepts: [tertiary-link] }
sizing:
  score-type: "the display-small role, weight 700, tabular figures so scores align down a column"
  verdict-type: "the compact body size, weight 700"
  gap: "--sp-0-5 between the score and the verdict label"
  reason-offset: "--sp-0-25 beneath the verdict"
behavior:
  - "static; the verdict reports an assessment and does not respond to interaction beyond its optional breakdown link"
accessibility:
  - "the tier is carried by the written verdict label — never by the number's color or by a bar's fill alone"
  - "score and verdict are announced as one unit so a number is never heard without the words qualifying it"
  - "a score with no reachable breakdown is a black box and is not a valid configuration"
token_bindings: [--text-primary, --text-secondary, --status-positive-bg, --status-caution-bg, --status-critical-bg, --surface-secondary, --sp-0-25, --sp-0-5]
composite: false
---

# Score verdict

An assessment stated as the user reads it: a figure, the plain-language verdict that figure amounts to, and a one-line reason. The verdict — not the number — is the primary content, because a number alone tells a user nothing about what to do.

## No black box

A score is never terminal. Wherever this Component appears, the per-component breakdown that produced the score is reachable from it — inline, through the `breakdown-action` link, or in the surface that contains it. The breakdown's arrangement is `libraries/shapes/score-breakdown.md`.

A configuration that shows a score with no route to its reasoning is not a compact variant of this Component; it is a different thing, and this entry does not describe it.

## Plain language is not optional

The verdict label and the reason are written in the user's terms — what the assessment means for them, and why. A label that restates the number in words adds nothing. A reason that cites the model, the algorithm, or an internal field name has explained the system rather than the result.

## Variants

- `tier`: `strong` | `partial` | `weak` | `disqualified` — the verdict's band. Each tier has its own written label; the ground role reinforces it and never carries it alone.
- `density`: `full` (default — score, verdict, reason) | `compact` — score and verdict only, for a table cell or a card, with the reason reachable in the surface that holds it.
- `score`: `present` (default) | `absent` — a verdict with no numeric figure is valid, and is correct where a number would imply a precision the assessment does not have.

## Determinations

- The score is set at the display-small role with tabular figures, so a column of scores aligns on the decimal.
- The verdict label sits `var(--sp-0-5)` after the score at the compact body size, weight 700, in `var(--text-primary)`.
- The reason sits `var(--sp-0-25)` beneath both at the caption size in `var(--text-secondary)`, one line, wrapping to the container's measure.
- The tier's ground role tints the verdict label's own pill only; it never grounds the whole component. A saturated block behind an assessment reads as an alarm rather than a result.
- A score that has not been computed renders the component without the score slot and without an error treatment. An assessment in progress is not a failure, and a placeholder figure would be a fabricated one.
- `disqualified` carries the same geometry as the other tiers. A knockout result is stated, not shouted.

## Accessibility

- The score and the verdict are one announced unit, so a screen reader never reports a bare number.
- The tier is carried by the verdict's written label. Color, ground, and any bar or ring are reinforcement (WCAG 1.4.1).
- The breakdown action is a real link or button whose accessible name says what it opens and for which subject.
