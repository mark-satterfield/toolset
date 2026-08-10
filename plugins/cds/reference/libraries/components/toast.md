---
kind: component
name: toast
page_family: shared
aliases: [toast, snackbar, transient notice, auto-dismiss message, flash message]
status: stable
slots:
  - { name: glyph, required: false, accepts: [icon-glyph] }
  - { name: message, required: true, accepts: [text] }
  - { name: action, required: false, accepts: [tertiary-link] }
  - { name: dismiss, required: false, accepts: [icon-button] }
sizing:
  max-width: "--column-field-measure — a toast wider than a comfortable measure is a banner"
  padding: "--sp-0-75"
  radius: "--radius-md"
  stack-gap: "--sp-0-5 between stacked toasts"
  viewport-offset: "--sp-1-5 from the viewport edges the region anchors to"
behavior:
  - "auto-dismisses after its dwell time; hovering or focusing it suspends the timer, and leaving resumes it"
  - "never blocks interaction with the page beneath it"
  - "toasts stack in one region in arrival order; a new toast never displaces one mid-read"
accessibility:
  - "the toast region is a single persistent live region so arrivals are announced without moving focus"
  - "a toast carrying an action does not auto-dismiss — an affordance that vanishes on a timer is unreachable to a slow or assisted reader"
  - "dwell time is at least five seconds and is extended, never shortened, by user preference"
token_bindings: [--surface-raised, --border-subtle, --text-primary, --status-positive-bg, --status-caution-bg, --status-critical-bg, --radius-md, --ease-in-out, --focus-ring, --sp-0-5, --sp-0-75, --sp-1-5]
composite: false
---

# Toast

A short, non-blocking notice that appears at a fixed screen position and dismisses itself. The transient surface of the alert system: it confirms that something happened and gets out of the way.

Severity and the forward-question rule are the alert system's, defined in `libraries/components/inline-alert.md`.

A toast is the right surface only when the user needs no action and losing the message costs nothing. Anything the user must act on, or must be able to re-read, is a banner.

## The toast region

Every toast in a build renders into one region, anchored to the same viewport corner on every page. The region is a fixed-position stack: newest toast at the anchored edge, older ones displaced away from it, `var(--sp-0-5)` apart, `var(--sp-1-5)` from the viewport edges.

Consistency of position is the contract. A toast that appears bottom-right on one page and top-center on another trains the user to watch the whole viewport.

## Variants

- `severity`: `info` (default) | `success` | `warning`. There is no `error` toast — a failure the user should know about does not dismiss itself.
- `action`: `absent` (default) | `present` — one tertiary link. A toast with an action does not auto-dismiss.

## Determinations

- Ground `var(--surface-raised)` with a `1px solid var(--border-subtle)` hairline, `var(--radius-md)`, padding `var(--sp-0-75)`, and the raised elevation from `foundations/layout.md` §11.8. Severity is carried by the glyph, not by a filled ground — a toast is small, and a saturated fill at that size reads as decoration.
- Capped at a comfortable measure; a message needing more is a banner.
- Entrance and exit are an opacity transition over `var(--duration-200)` `var(--ease-in-out)` with no translation, so a stack of toasts never appears to slide past each other. Reduced motion drops the transition entirely.
- Dwell time is at least five seconds, and longer for a longer message. Pointer hover and keyboard focus anywhere within the toast suspend the timer; leaving resumes it from the start rather than from where it stopped.
- The region never blocks the page: it is `pointer-events: none` with each toast re-enabling pointer events for itself, so a click aimed past an empty part of the region reaches the page.
- A toast never covers a fixed control. When the region's anchored corner holds one, the region offsets past it.

## Accessibility

- The region is one persistent live region declared once at page level, `role="status"` with `aria-live="polite"`. Toasts are inserted into it, so arrivals are announced without focus moving and without a new live region being created per message.
- A toast carrying an action does not auto-dismiss, and its action is reachable by Tab. An affordance that disappears on a timer cannot be reached by anyone navigating slowly.
- The dismiss control's accessible name says what it dismisses.
- Auto-dismissal satisfies WCAG 2.2.1 by being pausable on hover and focus; a build that lets a user extend or disable the timer honors that preference here.
- Severity reaches a non-visual reader through the glyph and the wording (WCAG 1.4.1).
