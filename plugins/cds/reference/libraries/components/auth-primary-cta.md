---
kind: component
name: auth-primary-cta
family: auth
aliases: [authentication primary CTA, sign-up button, bloom button, conversion CTA]
status: stable
slots:
  - { name: host, required: true, accepts: [transparent-element] }
  - { name: label, required: true, accepts: [text] }
sizing:
  height: "44px"
  min_width: "6rem"
  padding: "0 20px"
  fill_radius: "--radius-md (::before fill layer; calibrates to 9.6px at the captured surface, ladder default 12px)"
behavior: [bloom-hover, transform-transition, reduced-motion]
accessibility: [focus-visible-ring, disabled-inherited]
token_bindings:
  - --accent-primary
  - --focus-ring
shell_furniture: false
composite: false
---

# Authentication primary CTA

The conversion primary CTA on authentication / sign-up surfaces — a richer hover treatment than the standard primary button (the "bloom hover"). A transparent host element whose `::before` paints the mapped dark fill at full width and height with `var(--radius-md)` radius, and whose `::after` carries a radial-gradient highlight that fades in on hover.

State props: `rest` | `hover`.

## Determinations

- `height: 44px`; `min-width: 6rem`; `padding: 0 20px`; `::before` radius `var(--radius-md)` — calibrates to 9.6px at the captured surface (ladder default 12px, `foundations/layout.md` §11.7).
- The 44px height meets the WCAG 2.5.5 (AAA) target size — this is the high-pointer-error conversion variant of the button base (`libraries/components/button.md`).

## Behavior

- Default transition: `transform 0.15s cubic-bezier(0.165, 0.85, 0.45, 1)`.
- Hover: `transform: scale(1.005, 1.015)` plus a `::after` radial-gradient highlight whose opacity fades 0 → 1 over 200ms.
- No box-shadow, no outline ring at rest.
- **Radial-gradient highlight.** The `::after` highlight is `radial-gradient(circle at 50% 0%, color-mix(in srgb, var(--accent-primary) 40%, transparent) 0%, transparent 70%)` — a soft accent bloom seated at the button's top edge that fades from transparent toward the accent color and back out by 70% of the radius. It binds to the `--accent-primary` role (`foundations/motion.md` §15.6) so the bloom carries the active theme's accent without per-surface authoring.

## Accessibility

- Inherits primary button keyboard semantics (`libraries/components/button.md`).
- **Focus-visible.** Since the variant suppresses the outline ring at rest, the focus indicator paints on `:focus-visible` only, as the foundation focus ring (`outline: 2px solid var(--focus-ring); outline-offset: 2px`). The bloom hover is decorative — it must not double as the focus indicator. (WCAG 2.4.7, 2.4.11.)
- **Reduced motion.** Honor `prefers-reduced-motion: reduce` by suppressing both the `transform: scale(...)` transition and the `::after` opacity fade; the button paints its rest state on hover instead. (WCAG 2.3.3.)
- **Disabled state.** Inherits the button-base disabled contract: HTML `disabled` attribute, `opacity: 0.5`, `cursor: not-allowed`, `pointer-events: none`. The bloom transform and `::after` highlight do not paint while disabled.
