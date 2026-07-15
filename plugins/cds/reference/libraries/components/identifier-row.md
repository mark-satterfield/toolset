---
kind: component
name: identifier-row
page_family: app
aliases: [read-only identifier row, copyable ID, ID row, UUID row]
status: stable
slots:
  - { name: label, required: true, accepts: [text] }
  - { name: value, required: true, accepts: [code] }
  - { name: copy, required: true, accepts: [icon-button] }
sizing:
  row: "inline-flex, content-driven, no visual styling of its own"
  gap: "component geometry"
  copy-button: "icon-button geometry, radius --radius-xs"
  value-max-width: "--column-field-measure"
behavior:
  - "states: rest | copied (transient confirmation)"
  - "copy writes the full value to the clipboard"
accessibility:
  - "copy button aria-label joins action + identifier name"
  - "value wrapped in <code>; aria-live=polite copy announcement"
token_bindings: [--text-primary, --text-secondary, --font-mono, --focus-ring]
shell_component: false
composite: false
---

# Identifier row

A small inline row exposing a system-generated identifier (UUID, slug, key prefix) the user cannot edit but may need to copy. Renders as label + monospaced value + copy icon button.

## Slots

- `label` (required): the identifier name (e.g., "Organization ID"), ink `--text-secondary` (one step dimmer than primary body text).
- `value` (required): the identifier itself, in the monospaced face for visual distinction from labels and prose.
- `copy` (required): a copy-to-clipboard icon button positioned immediately after the value.

## Sizing

- Row container: `display: inline-flex; align-items: center` with a gap (calibrates to 8px). No background, no border, no padding — the row inherits the surrounding section's surface.
- Value: `--font-mono` (falls back through `ui-monospace, SFMono-Regular, Menlo, monospace`); body compact scale (calibrates to 14px); ink `--text-primary`; `letter-spacing: 0`.
- Copy button (inherits the icon-button base): icon-button geometry (calibrates to 32×32px); padding `0`; radius `--radius-xs` (calibrates to 6px); transparent background; inline-flex centered; SVG glyph at icon-glyph geometry (calibrates to 16×16px). Host-project implementations targeting WCAG 2.5.5 AAA should ship at ≥44×44px.

## Truncation rule

- Default: render on a single line at natural width.
- Long IDs (>48 chars): apply `overflow: hidden; text-overflow: ellipsis; white-space: nowrap` to the value's container, capped at `max-width: var(--column-field-measure)` (`foundations/layout.md` §11.2; the same measure the field-group-form 2-col row uses). The copy button always copies the FULL value via the clipboard payload, not the truncated display.
- Never wrap — wrapping a UUID across two lines defeats visual scan/verification.

## Behavior

Click on the copy button writes the full value to the clipboard and triggers the `copied` state — an inline checkmark swap on the same icon button (1.5s timeout) rather than a toast, since the action is local and the row is small. The swap is an instantaneous icon replacement; if a fade or scale is added at the host level, suppress it under `prefers-reduced-motion: reduce` and show the new icon instantly. (WCAG 2.3.3.) When the copy succeeds, also announce the result via an `aria-live="polite"` region (a visually-hidden `<span>` reading "Copied") so screen-reader users get parity with the visual checkmark.

## Accessibility

- The copy button carries an `aria-label` joining the action and the identifier name (e.g., `aria-label="Copy Organization ID"`).
- The value MUST be wrapped in `<code>` for semantic distinction from labels and prose; the monospaced face alone is not a substitute for the element.

## Structural skeleton

```html
<p class="identifier-row"><!-- inline-flex, no styling of its own -->
  <span class="identifier-row__label"><!-- --text-secondary -->Organization ID:</span>
  <code class="identifier-row__value"><!-- --font-mono, --text-primary, --column-field-measure cap -->00000000-0000-4000-8000-000000000000</code>
  <button class="identifier-row__copy" aria-label="Copy Organization ID"><!-- icon-button base -->
    <svg aria-hidden="true"><!-- clipboard glyph --></svg>
  </button>
</p>
```

## Narrow-viewport behavior

At and above the mobile-wide breakpoint (≥480px, `foundations/responsive.md` §17.1) the row stays inline (label, value, copy on one line). Below 480px the label moves above the value/copy pair (a two-line stack) so the monospaced value retains its full single-line width without wrapping; the copy button stays on the value's line.
