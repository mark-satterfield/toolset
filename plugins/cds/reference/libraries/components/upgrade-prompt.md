---
kind: component
name: upgrade-prompt
page_family: shared
aliases: [paywall prompt, gated feature, plan prompt, upsell, entitlement prompt]
status: stable
slots:
  - { name: feature-name, required: true, accepts: [text] }
  - { name: explanation, required: true, accepts: [text] }
  - { name: tier-name, required: true, accepts: [text] }
  - { name: primary-action, required: true, accepts: [button] }
  - { name: comparison-link, required: false, accepts: [tertiary-link] }
  - { name: dismiss, required: true, accepts: [icon-button] }
sizing:
  padding: "--sp-1"
  radius: "--radius-md"
  stack-gap: "--sp-0-75 between the explanation and the action row"
behavior:
  - "appears in the place the gated action was attempted, not as an interruption elsewhere"
  - "dismissing returns the user to what they were doing with nothing else changed"
  - "it never blocks the surrounding surface"
accessibility:
  - "the prompt is announced when it replaces the gated affordance, and focus moves to it so the reason is reached"
  - "the dismiss control is reachable by keyboard and by Escape, and returns focus to the affordance that was gated"
  - "the tier comparison it links to is navigable by keyboard and by screen reader"
token_bindings: [--surface-secondary, --border-subtle, --text-primary, --text-secondary, --radius-md, --focus-ring, --sp-0-75, --sp-1]
composite: true
---

# Upgrade prompt

What appears where a gated feature would have been: the feature's name, why it is unavailable, which tier includes it, and one way forward.

## It appears where the user was

The prompt renders in the place the user tried to act — inline, in the affordance's own position. It does not take over the page, does not open a modal over unrelated work, and does not appear later somewhere else. A user who clicks a gated control needs the explanation at that control.

## Dismissal costs nothing

The dismiss control returns the user to exactly what they were doing. Nothing else changes, nothing is remembered as a rejection, and the gated affordance is still there to try again. A prompt that penalises dismissal — by navigating away, collapsing the surrounding work, or refusing to reappear — makes the user avoid the feature rather than consider the tier.

## Variants

- `placement`: `inline` (default — in the gated affordance's own position) | `adjacent` — beside the affordance where replacing it would collapse the layout.
- `comparison-link`: `absent` (default) | `present` — a link to the full tier comparison (`libraries/shapes/comparison-matrix.md`).

## Determinations

- Ground `var(--surface-secondary)`, `1px solid var(--border-subtle)`, `var(--radius-md)`, padding `var(--sp-1)`.
- The feature's name leads at the compact body size, weight 700, in `var(--text-primary)`. The explanation follows at the compact body size in `var(--text-secondary)`, naming the tier that includes the feature.
- The action row sits `var(--sp-0-75)` beneath: the primary action at the inline-start, the comparison link after it, the dismiss control at the inline-end.
- The prompt takes the inline size of the affordance it replaces, so the surrounding layout does not shift.
- It carries no imagery, no price, and no countdown. The user is mid-task; the prompt's job is to name the gate and offer the route past it.
- It never dims, blocks, or overlays the surrounding surface.

## Accessibility

- The prompt is announced when it replaces the gated affordance, and focus moves to it, so a screen-reader user learns why the thing they activated did not happen.
- The dismiss control is reachable by Tab and by Escape, and returns focus to the affordance that was gated.
- The tier comparison it links to carries the comparison matrix's own accessibility contract, including its real table semantics.
- Focus paints the foundation ring on `:focus-visible` (`foundations/accessibility.md` §18.2).
