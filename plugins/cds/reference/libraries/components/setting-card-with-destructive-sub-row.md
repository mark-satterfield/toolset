---
kind: component
name: setting-card-with-destructive-sub-row
page_family: app
aliases: [setting with delete row, preference card with destructive action]
status: stable
slots:
  - { name: setting-card, required: true, accepts: [setting-card] }
  - { name: destructive-sub-row, required: true, accepts: [sentence, destructive-button] }
sizing:
  sub-row-divider: "1px --border-subtle hairline above the sub-row"
  sub-row-button: "destructive-inline variant at --control-height-compact"
behavior:
  - "sub-row dims and its button disables while the card's toggle is off"
accessibility:
  - "inherits the setting-card and destructive-button contracts"
token_bindings: [--border-subtle, --button-destructive-bg, --button-destructive-text, --text-tertiary]
composite: true
---

# Setting card with toggle + destructive sub-row

A composition that pairs a setting card Component (with its inline toggle) with an inline destructive sub-row beneath the body — for example an "Allow product metrics logging" card with a "Delete all collected metrics data" sub-row for the associated irreversible action. The destructive sub-row keeps the irreversible action visibly attached to the preference it belongs to rather than placed in a global destructive zone.

## Component references

`libraries/components/setting-card.md` (host), `libraries/components/toggle-switch.md` (the embedded toggle), `libraries/components/destructive-button.md` (the button inside the sub-row).

## Slot composition

- `setting-card` (host): see the setting card Component for slots, dimensions, and role-token bindings.
- `destructive-sub-row` (added composition slot): an inline row beneath the body carrying a destructive sentence + a Destructive button.

## Structural skeleton (composition delta over the base setting card)

```html
<article class="setting-card"><!-- --radius-md, --sp-2 padding, --border-subtle hairline -->
  <!-- standard setting-card body (title cell + toggle cell + body cell) -->
  <div class="setting-card__grid">…</div>
  <!-- destructive sub-row appended beneath the standard card body -->
  <div class="setting-card__destructive-sub-row"><!-- 1px --border-subtle divider above -->
    <span>Delete all collected metrics data. This action cannot be undone.</span>
    <button class="btn-destructive btn-destructive--inline">Delete data</button>
  </div>
</article>
```

## Determinations

- **Destructive sub-row visual treatment** — the sub-row sits beneath the card body, separated by a `1px --border-subtle` hairline divider, on the same card ground (no separate tint). When the card's toggle is `off`, the sub-row dims to a disabled appearance and its button is disabled, since the data it would delete is no longer being collected.
- **`destructive-inline` button-size variant** — the inline sub-row's destructive button uses the compact control size (`--control-height-compact`, calibrates to 32px — one step down from the destructive button's primary height `--control-height`, which calibrates to 36px) so it reads as a scoped, secondary-weight action within the card rather than a page-level destructive action.

When an irreversible action is tightly scoped to one preference, embedding it inside the preference's card keeps the action's context visible. This pattern is preferred over a global destructive zone for setting-specific delete actions.
