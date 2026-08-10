---
kind: component
name: chat-activity-row
page_family: app
aliases: [tool call row, activity summary, work summary, collapsed detail, process row]
status: stable
slots:
  - { name: summary, required: true, accepts: [text] }
  - { name: disclosure, required: true, accepts: [icon-glyph] }
  - { name: detail, required: false, accepts: [text, code-block] }
sizing:
  height: "--list-row-standard for the collapsed row"
  gap: "--sp-0-25 between the summary and its disclosure glyph"
  detail-padding: "--sp-0-75"
behavior:
  - "collapsed by default; the summary alone is what most readers need"
  - "expanding reveals the detail in place and pushes the transcript below it down"
  - "several rows may be expanded at once"
accessibility:
  - "the row is a <button> carrying aria-expanded and aria-controls"
  - "the summary states what was done and how much of it, so the collapsed row is informative on its own"
  - "the row is not announced as it arrives — it is process, not content"
token_bindings: [--text-secondary, --text-tertiary, --surface-secondary, --list-row-standard, --radius-sm, --ease-in-out, --focus-ring, --sp-0-25, --sp-0-75]
composite: false
---

# Chat activity row

A quiet line between turns reporting work the system did rather than said: what it read, ran, or produced. Collapsed to one line by default, expandable to the detail.

## The summary must stand alone

The collapsed row states what happened and how much — the action and its count. A row that says only "working" or "used tools" has told the reader nothing and forces every one of them to expand it to find out whether anything relevant occurred.

## Variants

- `state`: `idle` (default — the work is finished) | `active` — the work is still running, with the row's glyph animating and the summary in the present tense.
- `detail`: `absent` (the summary is the whole of it, and the row does not disclose) | `present`.

## Determinations

- The row is a single line at `var(--list-row-standard)`, ink `var(--text-secondary)` at the caption size — quieter than either kind of turn, because it is not what the user came to read.
- The disclosure glyph sits `var(--sp-0-25)` after the summary and rotates on expansion over `var(--duration-150)` `var(--ease-in-out)`.
- The row carries no ground at rest; hover paints the theme's hover stratum at `var(--radius-sm)`.
- Expanded detail sits beneath the row on `var(--surface-secondary)` at `var(--radius-sm)` with `var(--sp-0-75)` of padding, inset to the row's inline offset.
- Several rows may be expanded at once, and expanding never collapses another — a reader comparing two steps needs both.
- An `active` row's glyph animates; under reduced motion it holds a static state and the summary's present tense carries the fact that work is ongoing (`foundations/motion.md` §15.5).
- Rows sit between turns at the transcript's own turn gap, never inside a turn.

## Accessibility

- The row is a `<button>` carrying `aria-expanded` and `aria-controls` referencing its detail.
- The row is not announced through the transcript's live region as it arrives. It is process rather than content, and announcing every step would bury the response the user is waiting for.
- An `active` row's completion is not announced either; the response that follows is the announcement.
- Focus paints the foundation ring on `:focus-visible` (`foundations/accessibility.md` §18.2).
