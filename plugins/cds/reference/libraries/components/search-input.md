---
kind: component
name: search-input
family: shared
aliases: [search input, search box, search bar]
status: stable
slots:
  - { name: magnifier-icon, required: true, accepts: [icon] }
  - { name: field, required: true, accepts: [single-line-text] }
sizing:
  min_height: "44px"
  padding: "8px 16px 8px 40px (40px left padding reserves the icon column)"
behavior: [focus-border-shift, focus-visible-ring, native-clear]
accessibility: [searchbox-semantics, tap-target]
token_bindings:
  - --surface-raised
  - --border-subtle
  - --focus-ring
shell_furniture: false
composite: false
---

# Search input

A general-purpose text input with a leading magnifier icon used in search contexts: hairline border + leading magnifier icon + input field.

## Determinations

- 44px min-height. Padding `8px 16px 8px 40px` — the 40px left padding reserves the icon column.
- The 44px height satisfies the WCAG 2.5.5 (AAA) target size — comfortably above the WCAG 2.2 AA minimum (2.5.8, 24×24).

## Behavior

- The border on focus shifts to the mapped mid-tone neutral. The global `:focus-visible` contract paints the 2px foundation focus ring.

## Clear affordance / keyboard

- The input is `<input type="search">`, which provides the browser's native clear control once a value is present and clears the value on Escape when the input has focus (HTML spec).
- When the input is inside a `<form>`, Enter submits the form (HTML spec).
- When used as an inline filter with no form submission, the parent host suppresses the default submit and emits change events as the user types (host responsibility).
