---
kind: component
name: filter-builder-panel
aliases: [filter builder, advanced filter, condition builder, query builder, filter panel]
status: stable
slots:
  - { name: natural-language-input, required: false, accepts: [text-input] }
  - { name: condition-row, required: true, accepts: [select-menu, text-input, filter-chip] }
  - { name: add-condition, required: true, accepts: [button] }
  - { name: apply-actions, required: true, accepts: [button] }
sizing:
  panel-padding: "--sp-1"
  row-gap: "--sp-0-5 between adjacent condition rows"
  field-gap: "--sp-0-5 between the field, operator, and value controls within a row"
behavior:
  - "each condition row is field, operator, value, and a remove control; rows combine with one joining rule stated once above them"
  - "an incomplete row is inert — it neither filters nor blocks the rows that are complete"
  - "applying updates the result set and announces the new count"
accessibility:
  - "each row is a group whose accessible name states its position, since the three controls repeat identically down the panel"
  - "the remove control names the condition it removes, not its position"
  - "the result count after applying is announced through a live region"
token_bindings: [--surface-raised, --border-subtle, --text-primary, --text-secondary, --text-tertiary, --radius-md, --focus-ring, --sp-0-5, --sp-1]
composite: true
---

# Filter builder panel

Explicit, per-field conditions over a result set: one row per condition, each naming a field, an operator, and a value, with an optional plain-language input above that writes rows for the user.

Composes the select menu (`libraries/components/select-menu.md`) for field and operator, and a text input or filter chip for the value. Distinct from the list filter (`libraries/components/list-filter.md`), which is a single free-text match, and from the filter chip, which is one facet.

## Plain language writes rows; it does not replace them

The natural-language input, when present, converts a typed sentence into condition rows and shows them. The rows are the state — the sentence is an input method for producing them.

This matters because the user must be able to see and correct what was understood. A query that silently becomes an opaque filter cannot be verified, adjusted, or trusted, and a misread sentence produces a result set the user has no way to explain.

A conversion that cannot be expressed as rows is reported as not understood, with the rows left as they were. Partially applying a misunderstood sentence is worse than applying none of it.

## Variants

- `natural-language`: `absent` (default) | `present`.
- `join`: `all` (default — every condition must hold) | `any` — stated once above the rows in words, not as a per-row operator. A per-row join produces precedence questions the panel has no way to answer.

## Determinations

- The panel is a column: the optional plain-language input, the join statement, the condition rows, the add control, then the apply actions beneath a hairline rule.
- Each condition row is a flex row: field select, operator select, value control, and a remove control at the inline-end, `var(--sp-0-5)` apart. Rows are `var(--sp-0-5)` apart.
- The operator set offered depends on the chosen field's type, so a text field never offers a numeric comparison. Until a field is chosen the operator and value controls are disabled rather than absent, so the row's shape is legible before it is filled.
- An incomplete row is inert: it is neither applied nor treated as an error while the user is still building it. It reports as incomplete only when the user applies.
- The remove control is available on every row including the last. Removing the last row leaves an empty panel, which is a valid state meaning no conditions.
- Ground `var(--surface-raised)`, `1px solid var(--border-subtle)`, `var(--radius-md)`, padding `var(--sp-1)`.
- Applying is explicit. Filtering on every keystroke of a value makes a partially-typed value into a query and destroys the result set the user was reading.

## Accessibility

- Each condition row is a `<fieldset>` or a `role="group"` whose accessible name states its ordinal, since three identical controls repeat down the panel.
- The remove control's accessible name names the condition it removes.
- The join rule is a real control, not a label, and changing it announces the change.
- The result count after applying is announced through a polite live region.
- Focus paints the foundation ring on `:focus-visible` (`foundations/accessibility.md` §18.2).
