---
kind: shape
name: modal-over-list
aliases: [creation modal, modal over page, grouped-checkbox form modal]
status: stable
slots:
  - { name: underlying-page, required: true, accepts: [list-page] }
  - { name: modal-header, required: true, accepts: [title, close-action] }
  - { name: modal-body, required: true, accepts: [text-input, textarea, checkbox-tree] }
  - { name: modal-footer, required: true, accepts: [secondary-button, primary-button] }
variants: []
self_contained: false
content_defaults:
  modal_title: "Create webhook endpoint"
  fields: ["Endpoint URL", "Name (optional)", "Description (optional)"]
  checkbox_groups: [{ label: "Session lifecycle", ratio: "4 of 4" }, { label: "Threads", ratio: "3 of 3" }, { label: "Outcomes", ratio: "1 of 1" }, { label: "Vault lifecycle", ratio: "3 of 3" }]
---

# modal-over-list — Form modal with grouped checkboxes over a list page

A list page (typically in its empty state) overlaid with a centered modal carrying a creation form. The modal hosts, top to bottom: a header row (title + close glyph), identifier field groups (URL, name, multi-line description), an events-to-subscribe section — a subhead followed by a vertical stack of parent-and-children checkbox groups — and a footer with the primary actions. The modal itself is the centered-dialog component (`libraries/components/`); this shape is the page-level arrangement of dialog over list.

Each checkbox parent carries a checkbox + label + right-aligned selection-ratio indicator ("4 of 4"); its children render as indented label rows, each with its own checkbox, a human label, and a code-style identifier (`session.status_run_started`) in a smaller dim font.

## HTML skeleton

```html
<div class="modal-overlay">
  <div class="modal" role="dialog" aria-labelledby="modal-title">
    <header class="modal__header">
      <h2 id="modal-title">Create webhook endpoint</h2>
      <button class="modal__close" aria-label="close">×</button>
    </header>
    <form class="modal__body">
      <label>Endpoint URL <input type="url" placeholder="https://example.com/webhooks"></label>
      <label>Name (optional) <input type="text" placeholder="My webhook endpoint"></label>
      <label>Description (optional) <textarea placeholder="Receives session lifecycle events"></textarea></label>
      <fieldset class="event-tree">
        <legend>Events to subscribe</legend>
        <div class="event-tree__group">
          <label class="event-tree__parent">
            <input type="checkbox" checked> Session lifecycle <span class="event-tree__ratio">4 of 4</span>
          </label>
          <label class="event-tree__child"><input type="checkbox" checked> Run started <code>session.status_run_started</code></label>
          <!-- remaining children -->
        </div>
        <!-- remaining groups -->
      </fieldset>
    </form>
    <footer class="modal__footer">
      <button class="btn-secondary">Cancel</button>
      <button class="btn-primary">Create</button>
    </footer>
  </div>
</div>
```

## Determinations

- Modal footer: right-aligned secondary "Cancel" + primary "Create"; the primary commits the form and is disabled until the required URL field is valid.
- Parent indeterminate state: when some but not all children are checked, the parent checkbox renders the indeterminate (dash) glyph and exposes `aria-checked="mixed"`. Checking the parent selects all children; unchecking it clears all.
- Modal sizing: a `--radius-md`-cornered card at `--modal-width` (calibrates to 520px), `max-height: 80vh` with the body scrolling internally while header and footer stay fixed.

Suits creation flows where the user picks a subscription set across enumerated event groups — and any permissions, scope-picker, or feature-gate creation modal that benefits from grouped multi-select.
