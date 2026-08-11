---
kind: section
name: conversion-card
aliases: [auth card, sign-in card, login card, sign-up card]
status: stable
shape: centered-card
content_contract: {}
theme: default
composition_notes: []
---

# Conversion card

The single-action surface of a conversion page: one prominent input and its supporting actions on a floating card. Its layout is the `centered-card` Shape (`libraries/shapes/centered-card.md`); this entry carries the content.

## Content

- `input` — one prominent text field, the text-input Component (`libraries/components/text-input.md`). The label is hidden via CSS with the placeholder as the visible label; the required asterisk is a separate `<span aria-hidden="true">` at `--field-required`.
- `primary-cta` — the primary conversion button with bloom hover.
- `divider` — an OR-divider at the OR-divider role (authentication card scale, `foundations/typography.md` §13.6), uppercase via CSS, `--text-secondary`. Typography only — no rules, no decorative line work.
- `secondary-ctas` — 2–3 secondary actions. Relevant ones carry a provider-specific logo; the single SSO-style secondary action takes `tabindex="-1"` to skip the keyboard tab order.
- `legal` — legal blurb at the Legal-blurb role (§13.6), with an underlined inline link at 40% opacity at rest and 100% on hover.

## Content-driven behaviors

- The card sits on the mapped principal light ground.
- Button labels use the Button-label role (§13.6).
- No avatar or hero illustration on the card, and no green or yellow state color anywhere on it.
