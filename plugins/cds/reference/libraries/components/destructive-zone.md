---
kind: component
name: destructive-zone
aliases: [danger zone, destructive section, delete zone]
status: stable
slots:
  - { name: wrapper, required: true, accepts: [section] }
  - { name: destructive-button, required: true, accepts: [destructive-button] }
sizing:
  wrapper-padding: "--sp-1-5 top only"
  wrapper-border: "1px --border-subtle top hairline"
behavior:
  - "activation opens a confirmation modal; no first-click deletion"
accessibility:
  - "inherits the destructive-button contract, including the destructive focus ring"
token_bindings: [--border-subtle, --button-destructive-bg, --button-destructive-text]
composite: true
---

# Destructive zone

A divider-delimited section that hosts a Destructive button (`libraries/components/destructive-button.md`) — for example a "Delete organization" button (solid destructive fill, inverse label) on its own line beneath a form. The composition is the hairline-top-divider + destructive-button pattern, distinct from the button itself.

## Frame / wrapper zone

The destructive action does NOT sit inside a bordered or tinted card. It sits in a section delimited only by a hairline top divider beneath the preceding form:

- Wrapper layout: `display: block`, full container width.
- Wrapper padding: `--sp-1-5` top only (calibrates to 24px) — the divider provides the visual separation; no left/right/bottom padding.
- Wrapper border: `1px solid --border-subtle` on the TOP edge only.
- Wrapper background: inherits the page surface (no tint, no card styling).

The destructive zone pattern is **divider-delimited, not card-delimited**. A bordered/tinted destructive card is an alternative pattern this system does not use.

## Structural skeleton

```html
<!-- Destructive zone: hairline-divider-delimited section hosting one Destructive button -->
<section class="destructive-zone"><!-- --sp-1-5 top pad, 1px --border-subtle top rule -->
  <button class="btn-destructive">Delete organization</button>
</section>
```

## Confirm-step contract

Activating the destructive button opens a confirmation modal (`libraries/components/modal-with-form.md`) that restates the consequence and requires an explicit confirm before the action runs. The zone itself does not delete on first click — the confirm step lives in the modal.

Every settings page eventually carries a destructive action; the divider-delimited zone visually separates an irreversible action from the editable fields above it, preventing accidental activation while keeping the action discoverable.
