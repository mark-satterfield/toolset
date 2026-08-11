---
kind: component
name: inline-alert
aliases: [field error, validation message, inline message, field-level alert, form error]
status: stable
slots:
  - { name: glyph, required: true, accepts: [icon-glyph] }
  - { name: message, required: true, accepts: [text] }
  - { name: action, required: false, accepts: [tertiary-link] }
sizing:
  gap: "--sp-0-5 between the glyph and the message"
  offset: "--sp-0-25 between the field and the alert beneath it"
  glyph: "--icon-size-inline on the --icon-viewbox-sm drawing grid"
behavior:
  - "appears adjacent to the control it concerns and moves with it; it never relocates to a page-level surface"
  - "static once shown — no entrance animation, because a message about the field under the cursor must be readable immediately"
accessibility:
  - "the message is referenced by the control's aria-describedby, and aria-invalid is set on the control for the error severity"
  - "the alert lives in a live region so a message appearing after submission is announced without moving focus"
  - "severity is carried by the glyph and the wording, never by color alone"
token_bindings: [--error-text, --status-positive-bg, --status-caution-bg, --status-critical-bg, --text-secondary, --text-tertiary, --icon-size-inline, --sp-0-25, --sp-0-5]
composite: false
---

# Inline alert

A single line of feedback about one control, rendered directly beneath or beside it. The field-level surface of the alert system: it says what is wrong with *this* input, where the user is already looking.

## The severity vocabulary

Four tiers, defined here once and referenced by every other alert surface (`libraries/components/page-banner.md`, `libraries/components/toast.md`, `libraries/shapes/full-page-state.md`):

| Severity | What it reports | Ground role |
|---|---|---|
| `info` | Something the user should know that changes nothing they have done. | `--surface-secondary` |
| `success` | An action completed. | `--status-positive-bg` |
| `warning` | A condition that will cost the user something if left alone. | `--status-caution-bg` |
| `error` | Something failed or is invalid and blocks progress until resolved. | `--status-critical-bg` |

**A user's input mistake is a validation state, not an error tier.** A required field left blank, a malformed entry, a value out of range — these are `warning` at most, and their wording says what to type rather than that something failed. Reserve `error` for a failure the user did not cause and cannot fix by retyping.

**An edge case is guidance, not an error.** An empty result set, a boundary condition, a state the flow did not anticipate — these are `info`, phrased as what to do next.

## Every alert answers a forward question

An alert that only reports a state is incomplete. Each one answers at least one of: what happened, why, or what to do now — and the `action` slot carries the affordance when the answer is something the user can act on.

## Variants

- `severity`: `info` | `success` | `warning` | `error` (default).
- `action`: `absent` (default) | `present` — one tertiary link naming the forward step.

## Determinations

- The alert is a single flex row: glyph at the inline-start, message beside it, optional action after the message.
- Glyph at `--icon-size-inline` on the `--icon-viewbox-sm` grid, `var(--sp-0-5)` from the message, aligned to the message's first line rather than to the block's center.
- The alert sits `var(--sp-0-25)` beneath its control, inset to the control's inline-start edge so the two read as one unit.
- Message at the caption size. The `error` severity paints `var(--error-text)`; the other severities paint `var(--text-secondary)` and carry their tier in the glyph.
- The alert has no ground, no border, and no radius. It is a line of type beneath a field, not a box — a filled box at field level competes with the field it describes.
- The message wraps to the field's own measure rather than extending past it.
- Showing the alert does not resize the field. Space for one line is reserved beneath the control so its appearance does not shift the form.

## Accessibility

- The message carries an `id` referenced by the control's `aria-describedby`. For the `error` severity the control also carries `aria-invalid="true"`.
- The alert's container is a live region (`role="status"` for `info`, `success`, and `warning`; `role="alert"` for `error`), so a message that appears after a submit attempt is announced without stealing focus.
- Severity reaches a non-visual reader through the glyph's accessible name and the message's own wording. Color is confirmation, never the carrier (WCAG 1.4.1).
- The action, when present, is a real link or button with an accessible name stating its verb.
