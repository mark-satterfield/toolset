---
kind: shape
name: centered-affordance
family: landing
aliases: [hero with chat input, hero with install command, interactive hero]
status: stable
slots:
  - { name: heading-block, required: true, accepts: [headline, subhead, cta-group] }
  - { name: affordance, required: true, accepts: [chat-input, install-snippet, code-snippet, prompt-chips] }
variants: [chat-input, install-or-code-snippet, prompt-chips]
self_contained: false
content_defaults: {}
---

# centered-affordance — Centered text + embedded affordance

Centered headline; an interactive element (chat input, install/code snippet, prompt chips) sits where the visual would. Vertical stack, centered — text above the affordance. The subhead and CTAs in the heading block are optional.

## Determinations

- Exactly one affordance per Shape instance. When more than one affordance is needed, repeat the Shape as separate Sections rather than stacking affordances.
- CTAs, when present, sit below the affordance — the affordance is the Section's primary action.
- The affordance is centered in a `--column-medium` reading column inside the page-width section, with `--sp-3` between the heading block and the affordance.
