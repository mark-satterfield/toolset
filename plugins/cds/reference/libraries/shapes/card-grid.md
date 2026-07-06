---
kind: shape
name: card-grid
family: landing
aliases: [feature grid, icon card grid, three-up cards]
status: stable
slots:
  - { name: cards, required: true, accepts: [icon, title, blurb, cta] }
variants: [with-card-cta, without-card-cta, with-icon, without-icon, default-fill, colored]
self_contained: false
content_defaults: {}
---

# card-grid — Static card grid

N cards in M columns with identical card structure (icon / title / blurb / optional CTA). Grid of M columns by ⌈N/M⌉ rows; uniform cell structure.

## Determinations

- Default column count is 3 (M = 3) at desktop, dropping to 2 columns below the tablet breakpoint and 1 column below the mobile-narrow breakpoint (`foundations/responsive.md` §17.1). N is content-driven; the last row left-aligns any remainder.
- Grid gap is the grid gutter (`foundations/layout.md` §11.6) on both axes. Cards use the Full promo card or Feature card spec from the components library (`--radius-xl` outer; inner padding per the card component's sizing contract).
- Default fill is transparent on `--surface-primary`. A colored card-grid is a first-class variant: each card may take a saturated `.ground--N` — the shared `tile-ground-*` role set (`from_palette: panels`), emitted one `.ground--N` per declared ground. Pick a ground number per the Section, never a color; grounds are theme-bound. A colored grid uses `.ground--N`, never ad-hoc `panel-N` roles.
- Cards animate in with the `--card-index` stagger (`foundations/motion.md` §15.4), suppressed under `prefers-reduced-motion: reduce`.
