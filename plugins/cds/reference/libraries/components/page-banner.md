---
kind: component
name: page-banner
aliases: [banner, page alert, persistent notice, system banner, notification bar]
status: stable
slots:
  - { name: glyph, required: true, accepts: [icon-glyph] }
  - { name: message, required: true, accepts: [text] }
  - { name: action, required: false, accepts: [button, tertiary-link] }
  - { name: dismiss, required: false, accepts: [icon-button] }
sizing:
  padding: "--sp-0-75 block, --sp-1 inline"
  radius: "--radius-sm"
  gap: "--sp-0-75 between the glyph and the message"
  glyph: "--icon-size-inline on the --icon-viewbox-md drawing grid"
behavior:
  - "persists until dismissed or until the condition it reports is resolved; it never auto-dismisses"
  - "spans the full inline width of the content region it heads"
accessibility:
  - "role=\"status\" for info, success, and warning; role=\"alert\" for error"
  - "the dismiss control carries an aria-label naming what it dismisses"
  - "severity is carried by the glyph and the wording, never by color alone"
token_bindings: [--surface-secondary, --status-positive-bg, --status-caution-bg, --status-critical-bg, --text-primary, --text-secondary, --border-subtle, --radius-sm, --icon-size-inline, --focus-ring, --sp-0-75, --sp-1]
composite: false
---

# Page banner

A persistent notice at the head of a page or a region, reporting a condition that outlives a single interaction. The page-level surface of the alert system.

Severity, the input-mistake rule, the edge-case rule, and the forward-question rule are the alert system's, defined in `libraries/components/inline-alert.md` and binding here unchanged.

A banner is the right surface when the condition persists and the user may act on it later. A condition that resolves on its own belongs in a toast; a condition the user must resolve before continuing belongs in a modal.

## Variants

- `severity`: `info` (default) | `success` | `warning` | `error`.
- `dismissible`: `true` (default — the user can close it) | `false` — the banner clears only when its condition resolves, which is correct when dismissing would hide something still true.

## Determinations

- The banner is a flex row spanning the full inline width of the region it heads: glyph at the start, message beside it, action and dismiss grouped at the end via `margin-inline-start: auto`.
- Padding `var(--sp-0-75)` block and `var(--sp-1)` inline; radius `var(--radius-sm)`; a `1px solid var(--border-subtle)` hairline.
- Ground resolves from the severity table in `inline-alert.md`. Message ink is `var(--text-primary)`; a supporting second line, when present, is `var(--text-secondary)`.
- Glyph at `--icon-size-inline`, `var(--sp-0-75)` from the message, aligned to the message's first line.
- The banner sits at the block-start of the region it concerns, above that region's heading, so it is read before the content it qualifies.
- It holds its position in the document flow — it does not float, overlay, or pin to the viewport. A notice that scrolls away with its region has correctly scoped itself to that region.
- Message wraps freely; the action and dismiss hold the end of the first line and never wrap beneath it.

## Accessibility

- The banner is `role="status"` for `info`, `success`, and `warning`, and `role="alert"` for `error`, so its arrival is announced at a politeness matching its severity.
- The dismiss control is a `<button>` whose accessible name says what it dismisses, not merely "close".
- Dismissing returns focus to the element that preceded the banner in the tab order, never to the top of the document.
- Severity reaches a non-visual reader through the glyph and the wording (WCAG 1.4.1).
- Focus paints the foundation ring on `:focus-visible` (`foundations/accessibility.md` §18.2).
