---
kind: component
name: kanban-card
aliases: [board card, pipeline card, draggable card, stage card]
status: stable
slots:
  - { name: title, required: true, accepts: [text] }
  - { name: subtitle, required: true, accepts: [text] }
  - { name: verdict, required: false, accepts: [score-verdict] }
  - { name: aging-indicator, required: false, accepts: [status-badge] }
sizing:
  padding: "--sp-0-75"
  radius: "--radius-md"
  stack-gap: "--sp-0-5 between the title block and the meta row"
behavior:
  - "the whole card is the drag handle; there is no separate grip"
  - "while dragging, the card lifts one elevation step and the position it left holds open as a gap"
  - "the card shows the same fields in every column — its column is its state, so restating it on the card is redundant"
accessibility:
  - "the card is a button, so it is reachable and activatable without a pointer"
  - "drag has a keyboard equivalent: the card announces its current column and the move commands available"
  - "the aging state is carried by the badge's text, never by a card tint alone"
token_bindings: [--surface-raised, --border-subtle, --text-primary, --text-secondary, --radius-md, --ease-out-quart, --focus-ring, --sp-0-5, --sp-0-75]
composite: true
---

# Kanban card

One record on a board: what it is, who it is with, how it scored, and whether it has sat too long. Compact enough that a column of them is scannable, complete enough that the user rarely needs to open one.

## The same fields in every column

A card carries identical content wherever it sits. Its column already states its state, so repeating that on the card wastes the only space the card has. Varying the fields per column would also make the board unscannable across columns, which is the one thing a board is for.

## Variants

- `verdict`: `present` (default) | `absent` — a record whose assessment has not been computed renders without the slot. There is no placeholder figure and no error treatment; an assessment in progress is not a failure.
- `aging`: `absent` (default) | `present` — the record has exceeded its aging threshold.

## Determinations

- Ground `var(--surface-raised)`, `1px solid var(--border-subtle)`, `var(--radius-md)`, padding `var(--sp-0-75)`.
- Title at the compact body size, weight 700, ink `var(--text-primary)`, wrapping to at most two lines then truncating.
- Subtitle directly beneath at the caption size in `var(--text-secondary)`, one line.
- The meta row sits `var(--sp-0-5)` beneath the title block: the verdict at the inline-start, the aging indicator at the inline-end.
- The aging indicator is a status badge (`libraries/components/status-badge.md`) at its caution state, naming the condition in words. A card that only tints or outlines to show aging has hidden the signal from a monochrome rendering and from a colour-blind reader.
- While dragging, the card lifts one elevation step (`foundations/layout.md` §11.8) and rotates not at all — a tilt is decoration that costs legibility at the moment the user most needs to read the card.
- The gap the card left holds open at the card's own height, so the column does not reflow under the pointer.

## Accessibility

- The card is a `<button>`: reachable by Tab, activatable by Enter, and announced as a control rather than as a decorated block.
- Dragging has a keyboard equivalent. A focused card announces its current column and the commands that move it, and each move announces the destination column and the card's new position within it. A board whose only re-ordering mechanism is a pointer drag is unusable without one.
- The aging state is part of the card's accessible name so it is heard, not only seen (WCAG 1.4.1).
- Focus paints the foundation ring on `:focus-visible` (`foundations/accessibility.md` §18.2).
