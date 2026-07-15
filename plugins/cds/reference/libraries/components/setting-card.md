---
kind: component
name: setting-card
page_family: app
aliases: [preference card, settings card, settings row]
status: stable
slots:
  - { name: title, required: true, accepts: [heading] }
  - { name: body, required: true, accepts: [paragraphs] }
  - { name: toggle, required: false, accepts: [toggle-switch] }
  - { name: primary-action, required: false, accepts: [primary-button] }
  - { name: pill, required: false, accepts: [badge] }
sizing:
  width: "fills the vacant space"
  padding: "--sp-2"
  radius: "--radius-md"
  slot-gap: "--sp-1-5"
behavior:
  - "control-kind: toggle | primary-action | none"
  - "embedded toggle-switch (regular size) carries the switch contract"
accessibility:
  - "switch aria-labelledby points at the title id"
  - "Space/Enter toggle; Tab focuses the switch"
token_bindings: [--text-primary, --text-tertiary, --border-subtle, --accent-primary, --switch-active-bg, --surface-tertiary, --surface-raised, --focus-ring]
shell_component: false
composite: false
---

# Setting card

A self-contained card representing a single preference: title, 1–2-paragraph explanation, and an inline toggle (or primary action) on the right.

## Slots

- `title` (required): the card heading.
- `body` (required): one or more paragraphs explaining the preference.
- `toggle` (optional): a toggle switch (`libraries/components/toggle-switch.md`, `regular` size variant) on the right edge, vertically centered against the full card height via `row-span-2`.
- `primary-action` (optional): a primary button in the toggle slot's place (mutually exclusive with the toggle).
- `pill` (optional): a small tag adjacent to the title (e.g., "NEW"); renders inline inside the title cell, vertically centered against the title's cap height with a small gap (calibrates to 8px).

## Sizing

- Card outer width: fills the vacant space.
- Card padding: `--sp-2` on all sides (calibrates to 32px).
- Card border: hairline `--border-subtle` (an alpha-thinned 1px per `foundations/layout.md` §11.9; calibrates to the sub-pixel hairline rendering).
- Card border-radius: `--radius-md` (calibrates to 12px).
- Card background: transparent (sits directly on the page ground).
- Card inner layout: `display: flex; flex-direction: column` with a `--sp-1-5` gap (calibrates to 24px).

## Layout pattern

The card's single direct child is a 2-column CSS grid: `grid-template-columns: 1fr auto` with a column gap (calibrates to 20px), full width. Three grid items participate:

1. **Title cell**: heading scale (calibrates to 18px) at a variable-axis medium weight (calibrates to 510 — a custom weight via the variable sans face, per the type-weight scale in `foundations/implementation.md` §6.4), ink `--text-primary`; `inline-flex` with the pill gap. Column 1, row 1.
2. **Toggle cell**: the switch wrapper, `flex; align-items: center; row-span-2`. Column 2, spans both rows, vertically centered against the full title-plus-body height.
3. **Body cell**: body compact scale (calibrates to 14px), weight 400, ink `--text-tertiary`; inline links inherit `--accent-primary`. Column 1, row 2, with a small top margin (calibrates to 4px).

The toggle's `row-span-2` is the key rule: the toggle always centers vertically against the combined title + body block, regardless of how the body wraps.

## Toggle spec

The embedded switch is the toggle switch component at its `regular` size variant (calibrates to a 43×24 track with a 20×20 thumb): `<button role="switch">` containing a `<span>` thumb, track `--surface-tertiary` at rest / `--switch-active-bg` when checked, thumb `--surface-raised` with a small shadow, thumb travel `0.8 × --switch-height`. The slide transition runs at `--duration-200`; suppress under `prefers-reduced-motion: reduce`. Hover steps the track one shade within the same role's theme binding (rest-hover and checked-hover).

## Behavior

- Title ink: `--text-primary`.
- Body ink: `--text-tertiary`; inline links `--accent-primary`.
- Focus ring on the switch: the `--focus-ring` foundation treatment.

## Accessibility

- Switch: `<button role="switch">`; state in both `aria-checked` and a `data-state` mirror.
- Heading-to-switch relationship via `aria-labelledby` on the switch pointing at the title's `id`.
- Space and Enter toggle the switch.
- Tab focuses the switch.

## Structural skeleton

```html
<article class="setting-card"><!-- --radius-md, --sp-2 padding, --border-subtle hairline -->
  <div class="setting-card__grid"><!-- grid-template-columns: 1fr auto -->
    <div class="setting-card__title" id="setting-metrics">
      Allow product metrics logging
      <!-- optional <span class="pill pill--new">NEW</span> sits here -->
    </div>
    <div class="setting-card__control"><!-- row-span-2, vertically centered -->
      <button role="switch" data-state="true" aria-checked="true" aria-labelledby="setting-metrics"
              class="toggle-switch cds-reset"><!-- regular size variant -->
        <span class="toggle-switch__thumb"></span>
      </button>
    </div>
    <div class="setting-card__body"><!-- --text-tertiary; links --accent-primary -->
      Enable metrics collection to track product usage across your organization…
    </div>
  </div>
</article>
```

## Multi-card spacing

When multiple setting cards stack in a column, the inter-card gap is `--sp-1-5` (calibrates to 24px) — matching the intra-card slot gap so the rhythm reads as one consistent vertical scale.

The composition that adds a destructive sub-row beneath the body is its own entry: `libraries/components/setting-card-with-destructive-sub-row.md` — not a property of this Component.
