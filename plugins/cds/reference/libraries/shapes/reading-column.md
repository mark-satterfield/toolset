---
kind: shape
name: reading-column
aliases: [reading column, prose column, centered reading column, long-form column]
status: stable
slots:
  - { name: prose, required: true, accepts: [flowing long-form prose] }
  - { name: sidebar, required: false, accepts: [in-page anchor links] }
variants: [centered, with-sidebar]
self_contained: false
content_defaults: {}
---

# reading-column — Centered column of flowing long-form prose

A single reading column for flowing long-form content, with an optional sticky sidebar beside it. The `prose` slot holds the running text; the `sidebar` slot, when filled, holds in-page anchor links.

## Determinations

- The `prose` slot sits in a `--column-reading` reading column (calibrates to 640px) inside the container: centered when the `sidebar` slot is empty (the `centered` variant), left-aligned with the sidebar to the right when it is filled (the `with-sidebar` variant).
- The sidebar is sticky and sits to the right of the reading column.
- Below the tablet breakpoint (`foundations/responsive.md` §17.1) the column takes the full container width.
