---
kind: component
name: voice-input-control
aliases: [microphone button, voice mode, dictation control, speech input, mic]
status: stable
slots:
  - { name: mic-trigger, required: true, accepts: [icon-button] }
  - { name: level-meter, required: false, accepts: [icon-glyph] }
  - { name: stop, required: false, accepts: [icon-button] }
sizing:
  trigger: "--icon-size-marginalia square hit area"
  meter-width: "--icon-size-button — the meter replaces the trigger's footprint plus one step, so the cluster grows predictably when it activates"
  gap: "--sp-0-25 between the trigger and the meter"
behavior:
  - "idle shows the microphone glyph; capturing replaces it with a live level meter and a stop control"
  - "the meter reflects captured audio level, so silence is visibly distinguishable from a failed microphone"
  - "capture never begins without an explicit activation"
accessibility:
  - "the trigger is a toggle button carrying aria-pressed, and its accessible name states what starting and stopping do"
  - "capture start and stop are announced through a live region, because a user who cannot see the meter has no other confirmation"
  - "the meter is decorative and aria-hidden; the announced state carries the fact that capture is running"
token_bindings: [--text-tertiary, --text-primary, --accent-primary, --surface-tertiary, --icon-size-marginalia, --icon-size-button, --radius-sm, --ease-in-out, --focus-ring, --sp-0-25]
composite: false
---

# Voice input control

Speech as an input method for a text field: a microphone that starts capture and a live level meter that shows it is working.

## The meter is the honesty

An idle microphone glyph and a running one look identical if the only difference is a tint. The level meter — a small run of bars responding to captured audio — distinguishes three states a static glyph cannot: not capturing, capturing silence, and capturing speech. A user whose microphone is muted at the operating system level sees a flat meter rather than an unresponsive interface.

## Variants

- `state`: `idle` (default — the microphone glyph alone) | `capturing` (the level meter and a stop control) | `unavailable` (no capture device or permission; the trigger is disabled and says why).

## Determinations

- Idle: the microphone glyph in an `--icon-size-marginalia` square, ink `var(--text-tertiary)`, rising to `var(--text-primary)` on hover.
- Capturing: the glyph is joined by the level meter, a run of short bars whose heights track the captured level, painted `var(--accent-primary)`. The stop control takes the trigger's position.
- The cluster reserves the capturing footprint at rest, so activating it does not shift the controls beside it.
- The meter animates continuously while capturing. Under reduced motion the bars hold a static mid-level and the announced state carries the fact that capture is running (`foundations/motion.md` §15.5) — the meter's purpose is confirmation, and a static confirmation is still a confirmation.
- Capture never begins on focus, on hover, or on page load. It begins on an explicit activation and ends on an explicit one or on the field losing focus.
- `unavailable` disables the trigger and states the reason in a tooltip (`libraries/components/tooltip.md`) rather than removing the control, so the absence of the feature is explained rather than mysterious.

## Accessibility

- The trigger is a toggle button carrying `aria-pressed`, with an accessible name stating what activating it does in each state.
- Starting and stopping capture are announced through a polite live region. A user who cannot see the meter has no other way to know whether the microphone is live, and a microphone the user believes is off is a privacy failure rather than a usability one.
- The meter carries `aria-hidden="true"`; the announced state carries the information.
- Transcribed text lands in the field as ordinary editable text the user can correct before submitting. Speech that submits itself removes the correction step that speech input most needs.
- Focus paints the foundation ring on `:focus-visible` (`foundations/accessibility.md` §18.2).
