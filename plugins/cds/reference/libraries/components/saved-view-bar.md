---
kind: component
name: saved-view-bar
aliases: [saved views, view switcher, named views, view tabs, viewsets]
status: stable
slots:
  - { name: view-option, required: true, accepts: [text] }
  - { name: dirty-marker, required: false, accepts: [icon-glyph] }
  - { name: view-menu, required: false, accepts: [action-menu] }
  - { name: save-action, required: false, accepts: [button] }
sizing:
  height: "--list-row-standard"
  gap: "--sp-0-25 between adjacent view options"
  option-padding: "--sp-0-5 inline"
  option-radius: "--radius-sm"
behavior:
  - "selecting a view applies its filters, sort, and column configuration in one step"
  - "modifying an applied view marks it changed without altering the stored view until the user saves"
  - "a built-in view can be modified in place and saved as a new view, but cannot itself be renamed or deleted"
accessibility:
  - "the run is a tablist whose selected option carries aria-selected, since the options switch one region's content"
  - "the changed marker is carried by a glyph and the option's accessible name, never by an ink shift alone"
  - "applying a view announces the resulting record count"
token_bindings: [--surface-secondary, --surface-tertiary, --text-primary, --text-secondary, --text-tertiary, --list-row-standard, --radius-sm, --ease-in-out, --focus-ring, --sp-0-25, --sp-0-5]
composite: true
---

# Saved view bar

The named configurations of a table — its filters, sort order, and columns — as a run of options above it. Selecting one applies the whole configuration at once.

## Built-in views are not deletable

A build ships views that always exist. They can be selected, modified in place, and used as the starting point for a new saved view, but they cannot be renamed or deleted — a user who removes the default has no way back to it.

The restriction is expressed by those verbs being absent from a built-in view's menu, not by their presence and failure. An action that is offered and then refused is a worse experience than one that was never offered.

## Changed, but not yet saved

Modifying the filters or sort while a view is applied does not alter the stored view. The bar marks the applied option as changed and offers to save. This keeps two things separate that a user needs separate: what they are looking at now, and what they will see next time.

The marker is a glyph and a word, not an italic or a dot, so it survives a monochrome rendering.

## Variants

- `management`: `read-only` (default — select among views) | `full` — each user-created view carries a menu with rename, duplicate, and delete, and the bar carries a save action.

## Determinations

- The bar is a single horizontal run at `var(--list-row-standard)`, sitting directly above the surface it configures.
- Each option is a pill at `var(--radius-sm)` with `var(--sp-0-5)` of inline padding, `var(--sp-0-25)` apart. The selected option paints `var(--surface-tertiary)` with `var(--text-primary)` ink; the rest are transparent with `var(--text-secondary)`.
- The changed marker sits after the selected option's label with its own glyph.
- The per-view menu opens from a trailing glyph on the option, shown on hover, `:focus-visible`, and while that option is selected — so the selected view's verbs are always reachable without a pointer.
- Beyond the bar's width the run scrolls horizontally rather than wrapping; a wrapped run changes the surface's height as views are added.
- Deleting a user-created view confirms first and falls back to the first built-in view, never to an unnamed state.

## Accessibility

- The run is a `role="tablist"` with each option a `role="tab"` carrying `aria-selected`, since the options switch the content of one region.
- The changed state is part of the selected option's accessible name, not an ink or weight difference alone (WCAG 1.4.1).
- Applying a view announces the resulting record count through a polite live region.
- Focus paints the foundation ring on `:focus-visible` (`foundations/accessibility.md` §18.2).
