---
kind: component
name: suggested-value-row
aliases: [inferred field, suggested field, review row, accept or reject row, extracted value]
status: stable
slots:
  - { name: label, required: true, accepts: [text] }
  - { name: value, required: true, accepts: [text] }
  - { name: status-badge, required: true, accepts: [outline-pill-badge] }
  - { name: confidence, required: false, accepts: [confidence-indicator] }
  - { name: provenance, required: false, accepts: [provenance-note] }
  - { name: review-actions, required: true, accepts: [button] }
sizing:
  row-padding: "--sp-0-75 block"
  label-column: "--column-field-measure caps the label and value column"
  action-gap: "--sp-0-5 between adjacent review actions"
behavior:
  - "a suggested value is inert until reviewed — it displays, and nothing downstream consumes it"
  - "accepting an auto-applied value is not required; undoing one is always available while the row is in view"
accessibility:
  - "the suggested status is carried by the badge's text, not by a tint on the value"
  - "each review action names its verb and the field it acts on, since the actions repeat down a list"
  - "accepting or rejecting announces the outcome through a live region and leaves focus on the row"
token_bindings: [--surface-secondary, --border-subtle, --text-primary, --text-secondary, --text-tertiary, --sp-0-5, --sp-0-75, --focus-ring]
composite: true
---

# Suggested value row

One field a system inferred, presented for a decision: what it thinks the value is, how sure it is, where it came from, and the controls to accept, correct, or reject it.

Composes the confidence indicator (`libraries/components/confidence-indicator.md`) and the provenance note (`libraries/components/provenance-note.md`); each keeps its own contract.

## Suggested values are inert

A row in the `suggested` state displays and does nothing else. Nothing downstream reads its value until a human has accepted it. The visual treatment says so — the value is set in the secondary ink, not the primary — because a suggestion styled identically to a confirmed fact is indistinguishable from one.

An `applied` row is the exception the system made deliberately: a value confident enough to apply without asking. It reads as confirmed, and it carries an undo for as long as the row is on screen. Applying without asking and applying without recourse are different things.

## Variants

- `state`: `suggested` (default — awaiting a decision, inert) | `applied` (auto-applied, undoable) | `confirmed` (a human accepted it) | `rejected` (a human declined it; the row persists so the decision is visible and reversible).
- `correction`: `absent` (default — accept or reject) | `present` — an edit control so the user can supply the right value instead of only refusing the wrong one.

## Determinations

- The row is a two-part flex layout: the label, value, confidence, and provenance stacked at the inline-start; the review actions grouped at the inline-end via `margin-inline-start: auto`.
- Label at the caption size in `var(--text-tertiary)`; value at the body size. A `suggested` value paints `var(--text-secondary)`; `applied` and `confirmed` values paint `var(--text-primary)`.
- The status badge sits inline after the value, naming the state in words.
- Confidence sits on the value's line; provenance sits beneath it — the order established in `libraries/components/provenance-note.md`.
- Rows stack with a `1px solid var(--border-subtle)` rule between them and `var(--sp-0-75)` of block padding each.
- A `rejected` row keeps its position and drops its value to `var(--text-tertiary)` with a strikethrough on the value only. Removing the row would hide the decision.
- Review actions are quiet: they repeat on every row, and a column of filled buttons would out-weigh the values they act on.

## Accessibility

- The state is carried by the badge's text. A tint on the value is reinforcement (WCAG 1.4.1).
- Each action's accessible name joins its verb to the field, since a screen reader user encounters many identical action labels down a list.
- Acting on a row announces the outcome through a polite live region and leaves focus on the row, so the user can work down a list without re-finding their place.
- An `applied` row's undo is reachable by Tab for as long as it is offered; an undo that exists only in a toast that has already dismissed is not offered.
