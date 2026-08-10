---
kind: component
name: row-expansion-panel
page_family: app
aliases: [inline expand, row detail, expanded row, preview panel, row disclosure]
status: stable
slots:
  - { name: disclosure, required: true, accepts: [icon-button] }
  - { name: preview, required: false, accepts: [text] }
  - { name: tags, required: false, accepts: [outline-pill-badge] }
  - { name: quick-actions, required: false, accepts: [button] }
sizing:
  panel-padding: "--sp-1"
  stack-gap: "--sp-0-75 between the preview, the tag run, and the actions"
  disclosure: "--icon-size-marginalia square hit area in the row's leading cell"
behavior:
  - "the panel opens beneath its row, inside the table, and pushes subsequent rows down rather than overlaying them"
  - "several rows may be expanded at once; expanding one never collapses another"
  - "the panel closes on its disclosure control and on Escape while focus is inside it"
accessibility:
  - "the disclosure is a <button> carrying aria-expanded and aria-controls pointing at the panel"
  - "the panel is a row of the table spanning every column, so the grid's row model stays intact"
  - "collapsing returns focus to the disclosure that opened the panel"
token_bindings: [--surface-secondary, --border-subtle, --text-primary, --text-secondary, --icon-size-marginalia, --ease-in-out, --focus-ring, --sp-0-75, --sp-1]
composite: true
---

# Row expansion panel

A preview of one record shown in place, beneath its own row: enough of the record to decide whether to open it, without leaving the table.

The panel is for deciding, not for working. A record the user wants to act on properly opens in the side drawer (`libraries/components/side-drawer.md`); this panel exists so they can tell which record that is.

## Variants

- `content`: `preview` (default — a text excerpt) | `preview-with-tags` | `full` — excerpt, tags, and quick actions.

## Determinations

- The disclosure control sits in the row's leading cell, an `--icon-size-marginalia` square whose glyph rotates on expansion over `var(--duration-150)` `var(--ease-in-out)`.
- The panel is a table row spanning every column, grounded `var(--surface-secondary)` — one stratum from the table's ground, so it reads as belonging to the row above it rather than as a floating object.
- Padding `var(--sp-1)`, inset to the leading cell's inline offset so the panel visibly hangs from its row.
- The excerpt is capped at a few lines and truncates; it is a preview, and a panel that grows to hold a whole record has become the record.
- The tag run wraps with `var(--sp-0-25)` between tags.
- Quick actions sit at the panel's block-end as secondary buttons, `var(--sp-0-75)` beneath the content.
- Expanding pushes subsequent rows down. The panel never overlays the rows beneath it, because a user comparing two records needs both visible.
- Several rows may be expanded at once. Auto-collapsing a previously-opened row makes comparison impossible, which is the panel's whole purpose.
- Expansion state is not persisted: a re-sorted or re-filtered table opens with every row collapsed, since the rows are no longer the same set.

## Accessibility

- The disclosure is a `<button>` carrying `aria-expanded` and `aria-controls` referencing the panel's id.
- The panel is a real table row so the grid's row model, `aria-rowindex` sequence, and keyboard navigation stay intact.
- Escape collapses the panel while focus is inside it, returning focus to the disclosure.
- Focus paints the foundation ring on `:focus-visible` (`foundations/accessibility.md` §18.2).
