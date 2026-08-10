---
kind: component
name: modal-with-form
page_family: app
aliases: [creation modal, form dialog, modal form]
status: stable
slots:
  - { name: overlay, required: true, accepts: [dim-layer] }
  - { name: dialog, required: true, accepts: [centered-card] }
  - { name: header, required: true, accepts: [title, close-button] }
  - { name: body, required: true, accepts: [form-fields] }
  - { name: footer, required: true, accepts: [secondary-button, primary-button] }
sizing:
  dialog-width: "--modal-width, capped at calc(100vw - 2 × --sp-1)"
  dialog-radius: "--radius-md"
  body-max-height: "80vh with internal vertical scroll"
behavior:
  - "states: closed | open; submit: idle | submitting | error"
  - "overlay click and Escape both close (equivalent to Cancel)"
accessibility:
  - "role=dialog aria-modal aria-labelledby; focus trap per foundations/accessibility.md §18.3"
  - "aria-live=polite error surface in the body"
token_bindings: [--surface-raised, --text-primary, --focus-ring]
composite: true
---

# Modal with form

A centered overlay dialog that holds a form for creating a new item, with a header (title + close), a scrollable body (fields), and a footer (cancel + primary CTA). The dialog itself is the centered dialog Component (`libraries/components/dialog.md`); this composition is the dialog + form-field-group + footer-actions pattern.

## Component references

Centered dialog (host), text inputs (`libraries/components/text-input.md`, `libraries/components/textarea.md`), grouped checkbox tree (`libraries/components/grouped-checkbox-tree.md`), primary + secondary buttons (`libraries/components/button.md`).

## Slots

- `overlay` (required): full-viewport dim layer beneath the dialog.
- `dialog` (required): the centered card.
- `header` (required): title + close button (×).
- `body` (required): vertically scrollable content area holding the form.
- `footer` (required): cancel and primary CTA buttons.

## Sizing

- Dialog width is `--modal-width` (calibrates to 520px), capped at `calc(100vw - 2 × --sp-1)` on narrow viewports (calibrates to 100vw − 32px).
- Dialog corners use `--radius-md` (calibrates to 12px) and carry the modal-lift shadow from `foundations/layout.md` §11.8 above the dimmed underlying page.
- The body has internal vertical scroll if content exceeds available height; `max-height: 80vh`.

## Structural skeleton

```html
<div class="modal-overlay" role="presentation">
  <div class="modal" role="dialog" aria-labelledby="modal-title" aria-modal="true">
    <header class="modal__header">
      <h2 id="modal-title">Create webhook endpoint</h2>
      <button class="modal__close" aria-label="close">×</button>
    </header>
    <form class="modal__body">
      <label>Endpoint URL <input type="url" placeholder="https://example.com/webhooks"></label>
      <label>Name (optional) <input type="text" placeholder="My webhook endpoint"></label>
      <label>Description (optional) <textarea placeholder="Receives session lifecycle events"></textarea></label>
      <!-- event-tree fieldset; see libraries/components/grouped-checkbox-tree.md -->
    </form>
    <footer class="modal__footer">
      <button class="btn-secondary" type="button">Cancel</button>
      <button class="btn-primary" type="submit">Create</button>
    </footer>
  </div>
</div>
```

## Interaction contracts

- Focus moves to the dialog on open and is trapped within it (Tab cycles inside the dialog) per `foundations/accessibility.md` §18.3.
- Clicking the overlay closes the dialog and so does Escape, both equivalent to Cancel.
- The open/close transition fades and lifts over 200ms and reduces to an instant swap under `prefers-reduced-motion: reduce` (`foundations/motion.md` §15.5).
- The primary CTA shows a spinner and is disabled while `submit` is `submitting`, and surfaces an `aria-live="polite"` error message in the body on `error`.

Creation flows that would otherwise need a full route navigation stay inline as a modal, preserving context.
