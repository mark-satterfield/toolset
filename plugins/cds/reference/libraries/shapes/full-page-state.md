---
kind: shape
name: full-page-state
aliases: [blocking state, error page, unrecoverable state, full-page error, offline state]
status: stable
slots:
  - { name: pictogram, required: false, accepts: [svg-glyph] }
  - { name: headline, required: true, accepts: [heading] }
  - { name: explanation, required: true, accepts: [text] }
  - { name: primary-action, required: true, accepts: [button] }
  - { name: secondary-action, required: false, accepts: [tertiary-link] }
  - { name: diagnostic, required: false, accepts: [tertiary-link] }
variants: [unrecoverable, blocked, offline]
self_contained: false
content_defaults: {}
---

# full-page-state — A blocking state in place of the content

A centered column replacing the region's whole content: what happened, why, and the one way forward. The blocking surface of the alert system, reserved for a state in which nothing on the page can usefully be interacted with.

Severity and the forward-question rule are the alert system's, defined in `libraries/components/inline-alert.md`. This arrangement is the only alert surface that removes content rather than accompanying it, so the bar for choosing it is that continuing is genuinely impossible — not merely degraded. A degraded state is a banner over content that still works.

## Determinations

- One centered column at the `--column-reading` measure, vertically centered within the region it replaces, so the state occupies the space its content would have.
- The pictogram, when supplied, sits at the column's block-start at the feature icon scale, `--sp-1-5` above the headline. It never depicts the failure literally.
- Headline at the Section's heading role: it names the state in the user's terms, not the system's.
- Explanation beneath it at the body size, one or two sentences, saying why and what it means for what the user was doing.
- `primary-action` is required. A blocking state with no way forward is a dead end, and the alert system forbids one — the action is retry, go back, or go somewhere that works.
- `secondary-action`, when present, is the alternative route.
- `diagnostic`, when present, opens the diagnostic detail (`libraries/shapes/diagnostic-detail.md`) for a user who needs to report the state. It is informational and never the primary action.
- The frame around the region — the Shell's pinned Sections — stays rendered. A state that blocks the content region does not remove the user's way out of it.
- Variants differ only in what they say: `unrecoverable` (the operation cannot complete), `blocked` (the user lacks something required), `offline` (connectivity). The arrangement is identical, because the user's need is identical.

## Accessibility

- The region announces the state on arrival through the page's live region, and focus moves to the headline so a screen-reader user is not left reading the content that is no longer there.
- The headline is the region's heading at the level the surrounding document establishes.
- The primary action is the first tab stop within the state.
