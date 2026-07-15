---
kind: component
name: code-block
page_family: shared
aliases: [code block, code snippet, terminal block]
status: stable
slots:
  - { name: mono-body, required: true, accepts: [monospaced-text] }
  - { name: language-picker, required: false, accepts: [picker] }
  - { name: copy-action, required: false, accepts: [tertiary-button] }
  - { name: docs-action, required: false, accepts: [tertiary-button] }
sizing:
  radius: "--radius-md (12px)"
behavior: [copy-success-state]
accessibility: [aria-live-copy-announcement, reduced-motion]
token_bindings:
  - --surface-primary
  - --surface-secondary
  - --text-primary
shell_component: false
composite: false
---

# Code block

A monospaced text block on a dark ground with an optional language picker and Copy / View Docs actions. The language picker sits top-left; "Copy" and "View Docs" tertiary actions sit top-right. Static at rest.

## Determinations

- Theme roles resolve through the `code` theme: `--surface-primary` to a fixed dark neutral (with `--surface-secondary` as the inner stratification) and `--text-primary` to a light text neutral. The `code` theme is color-mode-invariant — it stays dark in both light and dark mode.
- `var(--radius-md)` radius (12px, `foundations/layout.md` §11.7).
- Syntax highlighting: muted accent for keywords and strings, light tone for identifiers, dim tone for comments.

## Copy success state

On copy, the Copy action swaps its label to "Copied" with a checkmark glyph for 1.5s, then reverts — an inline confirmation, not a toast, since the action is local to the block. Announce the result via an `aria-live="polite"` visually-hidden span ("Copied to clipboard"). Suppress any fade/scale on the swap under `prefers-reduced-motion: reduce` (`foundations/motion.md` §15.5).

## View Docs target

The "View Docs" action is a tertiary button (`libraries/components/button.md`) linking to the documentation URL supplied by the host's `data-docs-href` attribute on the block; when no target is supplied, the block omits the action.
