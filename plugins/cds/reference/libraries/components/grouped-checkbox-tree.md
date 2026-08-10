---
kind: component
name: grouped-checkbox-tree
page_family: app
aliases: [event tree, permission picker, checkbox group tree, scope selector]
status: stable
slots:
  - { name: group, required: true, accepts: [fieldset] }
  - { name: parent, required: true, accepts: [checkbox, label, ratio-indicator] }
  - { name: child, required: true, accepts: [checkbox, label, code-identifier] }
sizing:
  child-indent: "--sp-1-5"
  ratio-indicator: "caption scale, right-aligned in the parent row"
behavior:
  - "parent state: checked | indeterminate | unchecked, driven by the children"
  - "clicking the parent toggles all children; groups are collapsible"
accessibility:
  - "parent aria-checked=mixed when partially checked"
  - "child accessible name joins human label + code identifier"
token_bindings: [--text-primary, --text-tertiary, --font-mono]
composite: true
---

# Grouped checkbox tree

A two-level checkbox group where each parent represents a category and each child is a leaf option; the parent shows a "checked count over total" indicator on the right; parent state is `checked` / `indeterminate` / `unchecked` driven by the children. A collapsible-group composition assembled from checkbox Components.

## Component references

Checkbox primitives (the host project's checkbox Component), label primitives. The indeterminate-state visual treatment for the parent checkbox is a Component-level concern; this composition is the parent + children + ratio-indicator pattern.

## Slots

- `group` (repeating): a fieldset for each category.
- `parent` (required per group): checkbox + label + right-aligned ratio indicator ("4 of 4").
- `child` (repeating per group): checkbox + human label + a code-style identifier in a smaller, dimmer font.

State props per parent: `checked` | `unchecked` | `indeterminate`. State props per child: `checked` | `unchecked`.

## Sizing

- Children are indented `--sp-1-5` (calibrates to 24px) relative to their parent.
- The ratio indicator is right-aligned within the parent row, caption-size text.
- The code-style identifier renders in `--font-mono` at the caption scale (calibrates to 12px), one step dimmer (`--text-tertiary`) than the human label.

## Structural skeleton

```html
<fieldset class="event-tree">
  <legend>Events to subscribe</legend>
  <div class="event-tree__group">
    <label class="event-tree__parent">
      <input type="checkbox" checked>
      <span class="event-tree__parent-label">Session lifecycle</span>
      <span class="event-tree__ratio">4 of 4</span>
    </label>
    <label class="event-tree__child">
      <input type="checkbox" checked>
      <span class="event-tree__child-label">Run started</span>
      <code class="event-tree__child-id">session.status_run_started</code>
    </label>
    <label class="event-tree__child">…</label>
    <label class="event-tree__child">…</label>
    <label class="event-tree__child">…</label>
  </div>
  <div class="event-tree__group">…</div>
</fieldset>
```

## Interaction contracts

- The parent checkbox renders the indeterminate (dash) glyph and exposes `aria-checked="mixed"` when some-but-not-all children are checked.
- Clicking the parent toggles all of its children at once (check-all when not fully checked, clear-all when fully checked).
- Each group is collapsible via its `<summary>` (`aria-expanded`, `aria-controls`) and ships expanded by default.
- The accessible name for each child joins the human label and the code identifier (e.g., "Run started, session.status_run_started") so screen-reader users hear both.

Permission pickers, event-subscription pickers, scope selectors, capability pickers — anywhere a user picks subsets across enumerated categories — use this stable two-level pattern.
