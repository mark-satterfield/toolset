---
kind: component
name: select-menu
aliases: [picklist, select, single-select, option list, listbox, chooser, group-by picker]
status: stable
slots:
  - { name: option, required: true, accepts: [label, check-glyph] }
  - { name: group-label, required: false, accepts: [text] }
sizing:
  panel-min-width: "matches the trigger's width at minimum, growing to its longest option"
  panel-padding: "--sp-0-5"
  panel-radius: "--radius-md"
  option-height: "--list-row-standard"
  option-padding: "--sp-0-5 inline"
  option-radius: "--radius-xs"
behavior:
  - "exactly one option is selected at a time; selecting an option commits it and closes the panel"
  - "the selected option carries a trailing check glyph and holds the hover stratum at rest so it reads as current with the pointer elsewhere"
  - "opens from its trigger, closes on selection, on Escape, and on pointer-down outside the panel"
accessibility:
  - "panel is role=\"listbox\"; options are role=\"option\" with aria-selected on exactly one"
  - "the trigger carries aria-haspopup=\"listbox\", aria-expanded, and an accessible name joining the facet and its current value"
  - "arrow keys move the active option, Enter/Space commit, Escape closes without committing and returns focus to the trigger"
token_bindings: [--surface-raised, --surface-tertiary, --border-subtle, --text-primary, --text-secondary, --accent-primary, --list-row-standard, --radius-md, --radius-xs, --ease-in-out, --focus-ring, --sp-0-5]
composite: false
---

# Select menu

The single-select option list a picker opens: one option is current, choosing another replaces it. The value the user picks is the point, so the panel shows which option is in force at rest and never leaves it ambiguous.

Its trigger is a filter chip (`libraries/components/filter-chip.md`) when the picker states a facet and its value, or a button when the label alone is enough. This entry owns the panel; the trigger owns its own contract.

Distinct from the action menu (`libraries/components/action-menu.md`), whose rows fire commands and hold no persistent state.

## Variants

- `grouping`: `flat` (default) | `grouped` — options divided by non-interactive group labels above each run.
- `selection-marker`: `check` (default — a trailing check glyph on the selected option) | `check-and-fill` — the selected option additionally holds the hover stratum at rest.

## Determinations

- Panel: ground `var(--surface-raised)`, `1px solid var(--border-subtle)`, `var(--radius-md)`, padding `var(--sp-0-5)`, raised elevation per `foundations/layout.md` §11.8.
- The panel is at least as wide as its trigger, so the value the user is changing stays under the pointer.
- Option: height `var(--list-row-standard)`, inline padding `var(--sp-0-5)`, radius `var(--radius-xs)`. Label at the compact body size, ink `var(--text-primary)`.
- The selected option carries a trailing check glyph in `var(--accent-primary)` at the trailing edge. Selection is never signalled by ink weight or color alone — the glyph is the marker, so the state survives a monochrome or high-contrast rendering.
- Hover paints the theme's hover stratum over `var(--duration-100)` `var(--ease-in-out)`.
- Group labels sit above the run they introduce, at the caption size in `var(--text-secondary)`, and paint no hover state.
- When the option list exceeds the available height the panel scrolls, the selected option is scrolled into view on open, and the group labels scroll with their runs.

## Accessibility

- The panel is `role="listbox"` and options are `role="option"`; exactly one option carries `aria-selected="true"` at all times.
- The trigger carries `aria-haspopup="listbox"` and `aria-expanded`, and an accessible name that joins the facet to its current value, so the control announces what it selects and what is selected now.
- Arrow keys move the active option, Home and End jump to the ends, typing a character moves to the next option starting with it. Enter and Space commit the active option and close. Escape closes without committing and returns focus to the trigger.
- Grouped options use `role="group"` with the group label as its accessible name, so the grouping is announced rather than merely drawn.
- Focus paints the foundation ring on `:focus-visible` (`foundations/accessibility.md` §18.2).
