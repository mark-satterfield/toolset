---
kind: page
name: conversion-auth
page_family: auth
aliases: [conversion page, authentication page, sign-in page, sign-up page, login page]
status: stable
sections:
  - { section: conversion-headline, required: true, notes: "always first" }
  - { section: conversion-card, required: true, notes: "always last" }
constraints: []
---

# Conversion / Authentication Page

A single-action conversion surface: one prominent input and two-to-three secondary actions. This Page is content Sections only, in the fixed order above: marketing headline → card. Any top-nav or site-footer Section belongs to the user's Shell.

## Theme

`default` for the surround; the card renders a transparent surface against the page ground. Any footer treatment belongs to the user's Shell.

## Register rules

### Layout

- Card: `--container-conversion-card` max-width (calibrates to 448px), centered; inner padding `--sp-2` at its floor (calibrates to 28px).
- Card radius: `--radius-2xl` at the top of its clamp (calibrates to 32px).
- Card border: 0.5px-feeling — `1px solid` ink at 15% opacity.
- Card shadow: the soft-floating 4-layer low-opacity stack (`foundations/layout.md` §11.8).

### Typography (authentication card scale, `foundations/typography.md` §13.6)

- Marketing headline: the Marketing-headline-outside-card role (Serif, weight 330, `--lh-120`; calibrates to 56px desktop).
- Input label: the Input-label role, visually hidden via CSS; the placeholder is the visible label.
- Required asterisk: separate `<span aria-hidden="true">` at the Required-asterisk role, ink at `--field-required`, with a `--sp-0-25` left margin (calibrates to 4px).
- Button label: the Button-label role.
- OR-divider: the OR-divider role, uppercase via CSS, `--text-secondary` — typography only, no line work.
- Legal blurb: the Legal-blurb role, with its underlined inline link at 40% opacity at rest, 100% on hover.

### Components

- One prominent standard text input (calibrates to 44px height, 9.6px radius, 12px horizontal padding).
- Primary CTA with bloom hover.
- 2–3 secondary CTAs with 0.5px-feeling border and transparent fill; provider-specific 16×16 logo on relevant ones with a `--sp-0-5` gap to the label (calibrates to 8px).
- The single SSO-style secondary action takes `tabindex="-1"` to skip the keyboard tab order.

### Motion (conversion register, `foundations/motion.md` §15.3)

- Hover transforms: scale 1.005 × 1.015 on the primary CTA.
- 200ms `::after` radial-gradient highlight bloom on hover.
- 100ms color and border on secondary buttons.

### Responsive

- Card width holds at `--container-conversion-card` on every breakpoint.
- Marketing headline scales down to a 36px mobile calibration.

### Do not

- No avatar or hero illustration on the card.
- No "Welcome back" or "Sign in to continue" greeting.
- No green or yellow state color on the card.
