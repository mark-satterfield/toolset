---
kind: component
name: toggle-chip
aliases: [filter toggle, chip toggle, facet toggle, tag filter, multi-select chip]
status: stable
slots:
  - { name: label, required: true, accepts: [text] }
  - { name: leading-glyph, required: false, accepts: [icon-glyph] }
  - { name: count, required: false, accepts: [text] }
sizing:
  height: "--list-row-compact"
  padding: "--sp-0-5 inline"
  radius: "--radius-sm"
  gap: "--sp-0-25 between the glyph, the label, and the count"
behavior:
  - "toggles on and off in place; several may be on at once and they do not exclude each other"
  - "the on state carries a filled ground and a check glyph, not a ground alone"
accessibility:
  - "a toggle button carrying aria-pressed — not a link, and not a tab"
  - "the on state is carried by the check glyph and aria-pressed, never by ground alone"
  - "toggling announces the resulting count through the run's live region"
token_bindings: [--surface-secondary, --surface-tertiary, --text-primary, --text-secondary, --border-subtle, --list-row-compact, --radius-sm, --ease-in-out, --focus-ring, --sp-0-25, --sp-0-5]
composite: false
---

# Toggle chip

A compact on/off control in a run of peers: each one includes or excludes a category, and any number may be on at once.

Distinct from the filter chip (`libraries/components/filter-chip.md`), which states a facet and its current value and opens a popover to change it. This chip *is* the value — activating it changes state immediately with no panel between.

Distinct from the pill-tab strip (`libraries/components/pill-tab-strip.md`), where exactly one option is active. These do not exclude each other.

## Variants

- `state`: `off` (default) | `on`.
- `count`: `absent` (default) | `present` — how many records the category holds, so the user can tell an empty category from a full one before toggling it.

## Determinations

- Height `var(--list-row-compact)`, inline padding `var(--sp-0-5)`, radius `var(--radius-sm)`.
- `off`: transparent ground, `1px solid var(--border-subtle)`, ink `var(--text-secondary)`.
- `on`: ground `var(--surface-tertiary)`, ink `var(--text-primary)`, and a leading check glyph. The glyph is what carries the state — a ground shift alone is invisible in a high-contrast rendering and ambiguous in a monochrome one.
- The chip's inline size changes when the check glyph appears, so a run reserves the glyph's width at rest and the row does not reflow as chips are toggled.
- The count sits after the label at the caption size in `var(--text-secondary)`, in both states.
- Transitions run over `var(--duration-100)` `var(--ease-in-out)`; reduced motion swaps instantly.
- A run of chips is arranged by chip-row (`libraries/shapes/chip-row.md`) or by whatever Shape places it; this entry supplies no run spacing.

## The all-off state

A run with every chip off means no category is excluded, not that nothing matches. A surface using these chips states that in its empty region rather than showing zero results, since "all filters off" and "no results" look identical and mean opposite things.

## Accessibility

- The chip is a `<button>` carrying `aria-pressed`. It is not a link, and not a tab — both would misreport what activating it does.
- The on state reaches a non-visual reader through `aria-pressed` and the check glyph (WCAG 1.4.1).
- Toggling announces the resulting record count through the run's polite live region, so the effect of the toggle is knowable without inspecting the results.
- Focus paints the foundation ring on `:focus-visible` (`foundations/accessibility.md` §18.2).
