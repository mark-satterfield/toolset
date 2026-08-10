---
kind: component
name: chat-composer
page_family: app
aliases: [message input, chat input, prompt box, composer, message box]
status: stable
slots:
  - { name: field, required: true, accepts: [textarea] }
  - { name: source-actions, required: true, accepts: [icon-button, action-menu] }
  - { name: mode-picker, required: false, accepts: [select-menu] }
  - { name: model-picker, required: false, accepts: [select-menu] }
  - { name: voice, required: false, accepts: [voice-input-control] }
  - { name: submit, required: true, accepts: [icon-button] }
sizing:
  min-height: "one text row plus the control row beneath it"
  max-height: "a bounded proportion of the viewport's block size, after which the field scrolls within itself"
  padding: "--sp-0-75"
  radius: "--radius-lg"
  control-row-gap: "--sp-0-5 between adjacent controls"
behavior:
  - "the field grows row by row as the text wraps, up to its cap, then scrolls within itself"
  - "the composer's own box grows with the field, and the transcript above it yields the space"
  - "Enter submits and Shift+Enter inserts a row; a composer whose Enter inserts a row makes every message end in a hunt for the button"
accessibility:
  - "the field carries an accessible name; its placeholder is not that name"
  - "growth is a visual property — the field's value is one string and its row count is never announced"
  - "the submit control states what it does in each state, and the streaming state's stop is a distinct control with its own name"
token_bindings: [--surface-primary, --surface-raised, --border-subtle, --border-strong, --text-primary, --text-tertiary, --accent-primary, --radius-lg, --ease-in-out, --focus-ring, --sp-0-5, --sp-0-75]
composite: true
---

# Chat composer

The input a conversation is written in: a field that grows with what is typed, the controls that decide what the message can draw on, and the control that sends it.

## It grows with the message

The field starts at one row and grows a row at a time as the text wraps, up to a bounded proportion of the viewport, after which it scrolls within itself. The composer's box grows with it and the transcript above yields the space.

This matters because a fixed single-row input makes a paragraph unreviewable — the user writes into a slot showing eight words and cannot read back what they wrote before sending it. Growth is not a nicety; it is what makes a long message editable.

Growing never moves the control row out of reach: the controls stay pinned to the composer's block-end edge, so the send control sits in the same place whether the message is one row or twelve.

## Two control clusters

The controls sit in one row beneath the field, and which side a control belongs to follows from what it does:

- **Leading cluster — what the message can draw on.** Attaching a file, adding a directory or a source, and picking a working mode. These decide the message's inputs, and they are read before the message is sent.
- **Trailing cluster — how it is sent.** Model or profile selection, voice input, and the submit control. These are the last things touched.

A control that changes what the system can see belongs at the start; a control that changes how it responds belongs at the end.

## Adding sources without leaving the field

The leading cluster's primary control opens an action menu (`libraries/components/action-menu.md`) carrying every way to bring material in — files, images, a whole directory, a saved source, a connected service — each with its keyboard shortcut, and toggle-state items for the capabilities a message may draw on.

A frequent source may also take its own direct control beside the menu rather than living one level down, since a source added on most messages should not cost a menu each time.

## Variants

- `submit-state`: `idle` (nothing typed; submit is present but inert) | `ready` (content typed; submit paints its accent fill) | `streaming` (a response is arriving; submit becomes a stop control) — the stop is the same position and a different control, so interrupting is always in the place the user just used.
- `controls`: `minimal` (source actions and submit only) | `full` (adds the mode picker, model picker, and voice control).

## Determinations

- Ground `var(--surface-primary)`, `1px solid var(--border-subtle)`, `var(--radius-lg)`, padding `var(--sp-0-75)`. Focus within the composer shifts the border to `var(--border-strong)` — the whole composer takes focus emphasis, not the inner field, because the box is the control.
- The field carries no border, no ground, and no radius of its own. It sits inside the composer's box, so the composer reads as one object rather than as a field with things around it.
- The control row sits beneath the field, `var(--sp-0-5)` between adjacent controls, pinned to the composer's block-end.
- The submit control is an `--icon-size-marginalia` square. Idle it is `var(--text-tertiary)` on no ground; ready it paints `var(--accent-primary)` with inverse ink; streaming it holds the accent and shows a stop glyph.
- Enter submits; Shift+Enter inserts a row. A composer that reverses this makes every send a hunt for a button.
- The composer is pinned to the block-end of the transcript column and never scrolls away with it.
- Below the tablet breakpoint (`foundations/responsive.md` §17.1) the trailing cluster's pickers collapse into the leading cluster's menu; the voice and submit controls stay in the row.

## Accessibility

- The field has an accessible name of its own. The placeholder is a hint and disappears on input; a field whose only name is its placeholder becomes anonymous the moment it is used.
- Growth is visual. The field's value is one string, its row count is never announced, and a screen reader user typing a long message hears their text, not the layout.
- The submit control's accessible name states what it does in the current state. The streaming state's stop is announced as a distinct control, not as a renamed send.
- Every control in both clusters is reachable by Tab in source order, and none depends on hover.
- Focus paints the foundation ring on `:focus-visible` (`foundations/accessibility.md` §18.2).
