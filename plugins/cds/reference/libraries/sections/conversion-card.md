---
kind: section
name: conversion-card
family: auth
aliases: [auth card, sign-in card, login card, sign-up card]
status: stable
mode: deterministic
content_contract: {}
theme: default
composition_notes: []
---

# Conversion card

The single-action surface of a conversion page: a centered floating card carrying one prominent input and its supporting actions.

## Slots

- `input` — one prominent text field, the text-input Component (`libraries/components/text-input.md`). Sizing calibrates to 44px height, 9.6px radius, 12px horizontal padding at the reference viewport. The label is hidden via CSS with the placeholder as the visible label; the required asterisk is a separate `<span aria-hidden="true">` at `--field-required` with a `--sp-0-25` left margin (calibrates to 4px).
- `primary-cta` — the primary conversion button with bloom hover.
- `divider` — an OR-divider at the OR-divider role (authentication card scale, `foundations/typography.md` §13.6), uppercase via CSS, `--text-secondary`. Typography only — no rules, no decorative line work.
- `secondary-ctas` — 2–3 secondary actions with 0.5px-feeling border and transparent fill. Relevant ones carry a provider-specific 16×16 logo with a `--sp-0-5` gap to the label (calibrates to 8px); the single SSO-style secondary action takes `tabindex="-1"` to skip the keyboard tab order.
- `legal` — legal blurb at the Legal-blurb role (§13.6), with an underlined inline link at 40% opacity at rest and 100% on hover.

## Determinations

- The card centers on the mapped principal light ground with a transparent surface against the page ground.
- Max-width is `--container-conversion-card` (calibrates to 448px) and holds at every breakpoint; the surrounding ground reflows.
- Inner padding is `--sp-2` at its floor (calibrates to 28px).
- Radius is `--radius-2xl` at the top of its clamp — the one place in the system that uses it (calibrates to 32px).
- Border is a 0.5px-feeling `1px solid` ink at 15% opacity; the shadow is the soft-floating 4-layer low-opacity stack (`foundations/layout.md` §11.8).
- Button labels use the Button-label role (§13.6).
- Hover motion: scale 1.005 × 1.015 on the primary CTA with a 200ms `::after` radial-gradient highlight bloom; 100ms color and border transitions on the secondary buttons.
- No avatar or hero illustration on the card, and no green or yellow state color anywhere on it.
