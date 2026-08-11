---
kind: component
name: confidence-indicator
aliases: [confidence band, certainty indicator, reliability indicator, confidence level]
status: stable
slots:
  - { name: glyph, required: true, accepts: [icon-glyph] }
  - { name: label, required: true, accepts: [text] }
sizing:
  gap: "--sp-0-25 between the glyph and the label"
  glyph: "--icon-size-inline on the --icon-viewbox-sm drawing grid"
behavior:
  - "static; the indicator reports a value and does not respond to interaction"
accessibility:
  - "the band is carried by the glyph shape and the written label — never by color, position, or fill level alone"
  - "the label names the band in words the user can act on, not a bare number"
  - "the indicator is read as part of the value it qualifies, not as a separate item"
token_bindings: [--text-secondary, --text-tertiary, --status-positive-bg, --status-caution-bg, --icon-size-inline, --sp-0-25]
composite: false
---

# Confidence indicator

How sure the system is about the value it is showing, stated beside that value. A derived value presented without one asserts a certainty the system does not have.

## Bands

Three bands, named once here and used by everything that reports confidence:

| Band | What it means for the user |
|---|---|
| `high` | The value can be relied on as it stands. |
| `medium` | The value is probably right and is worth checking. |
| `low` | The value is a guess; treat it as a prompt, not a fact. |

A band is a range the producing system defines; this entry fixes only how a band is shown, never where its thresholds sit.

## Never color alone

Each band carries a distinct **glyph shape** and a **written label**. Color reinforces, and is never the only difference between two bands. A reader with a color-vision difference, a monochrome print, a high-contrast mode, or a low-quality screen must be able to tell `high` from `low` — and a filled-dot or bar-length treatment fails that test as surely as a color swatch does (WCAG 1.4.1).

This is the constraint the whole entry exists to enforce. An implementation that drops the label to save space has removed the accessibility contract, not compressed it.

## Variants

- `band`: `high` | `medium` | `low`.
- `density`: `full` (default — glyph and label) | `glyph-with-tooltip` — the label moves into a tooltip (`libraries/components/tooltip.md`) where a run of values would otherwise be dominated by repeated words. The tooltip anchor is focusable, so the label stays reachable without a pointer.

## Determinations

- One inline row: glyph at the inline-start, label beside it, `var(--sp-0-25)` apart. The indicator sits on the same line as the value it qualifies, after it.
- Glyph at `--icon-size-inline` on the `--icon-viewbox-sm` grid.
- Label at the caption size in `var(--text-secondary)`; the `low` band drops to `var(--text-tertiary)` so it reads as the quietest thing on the line.
- The indicator never outsizes its value: it is set smaller and quieter, because it qualifies the value rather than competing with it.
- No ground, no border, no pill. A confidence band is an annotation.

## Accessibility

- The glyph carries an accessible name naming the band, so the band survives when the visual label is in a tooltip.
- The indicator is associated with its value — inside the same element, or referenced by it — so a screen reader announces "value, medium confidence" as one unit rather than encountering a stray word.
- In the `glyph-with-tooltip` density the anchor is a `<button>` and the tooltip follows the WCAG 1.4.13 contract in `libraries/components/tooltip.md`.
