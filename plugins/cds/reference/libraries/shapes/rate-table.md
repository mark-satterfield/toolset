---
kind: shape
name: rate-table
family: landing
aliases: [rates table, usage pricing table, rate card]
status: stable
slots:
  - { name: column-headers, required: true, accepts: [rate-category-label] }
  - { name: rate-rows, required: true, accepts: [row-header, rate-value] }
variants: []
self_contained: false
content_defaults:
  columns: [Input, Output, Cache write, Cache read]
---

# rate-table — Rate table

Rows of usage rates in tabular form: one row per priced unit, one column per rate category.

## Determinations

- Rendered as a semantic `<table>` with `<th scope>` on the row and column headers. Rate values are right-aligned; the leading row-header column is left-aligned.
- Rates display with an explicit currency symbol and per-unit suffix in each cell. Rows render in the order the content supplies them (no automatic re-sort).
- The column set is content: it is extensible, and additional rate categories append as further columns. The declared defaults in `content_defaults` are the drafted-mode scaffold; supplied content overrides them.
- Below the tablet breakpoint (`foundations/responsive.md` §17.1) the table scrolls horizontally within its container; cells do not reflow.
