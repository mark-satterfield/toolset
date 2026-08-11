---
kind: component
name: side-drawer
aliases: [drawer, side panel, detail drawer, slide-over, edge panel, off-canvas panel]
status: stable
slots:
  - { name: header, required: true, accepts: [text, button] }
  - { name: close, required: true, accepts: [icon-button] }
  - { name: body, required: true, accepts: [content] }
  - { name: footer, required: false, accepts: [button] }
  - { name: scrim, required: false, accepts: [overlay] }
sizing:
  desktop-width: "a proportion of the viewport's inline size — the surface names the proportion; the drawer never takes a fixed width, because it exists to leave the surface behind it readable"
  mobile-width: "the full viewport inline size below the tablet breakpoint"
  header-height: "--list-row-standard plus --sp-0-5 block padding"
  body-padding: "--sp-1-5"
behavior:
  - "enters by translating from the edge it is anchored to; it does not fade, scale, or grow from the centre"
  - "the surface behind it stays rendered and in place — opening the drawer is not a navigation"
  - "closing returns focus to the element that opened it"
accessibility:
  - "role=\"dialog\" with aria-modal reflecting whether the scrim blocks the surface behind it, and an accessible name from its header"
  - "focus is trapped within the drawer while it is modal, and Escape closes it"
  - "the drawer's own content scrolls; the surface behind it does not scroll with it"
token_bindings: [--surface-raised, --border-subtle, --text-primary, --ease-out-quart, --focus-ring, --list-row-standard, --sp-0-5, --sp-1-5]
composite: true
---

# Side drawer

A panel anchored to one edge of the viewport, sliding in over the surface without replacing it. The right surface for examining one record while its list stays where it was.

Distinct from the dialog (`libraries/components/dialog.md`), which is centred and interrupts, and from the mobile drawer (`libraries/components/mobile-drawer.md`), which is the narrow-viewport form of the navigation. This drawer carries content, not chrome.

## Entering from the edge is the contract

The drawer translates in from the edge it is anchored to. It does not pop, fade, or scale from the centre — the movement is what tells the user the panel came from beside their list rather than replacing it, and that closing it will put them back.

On a viewport too narrow to show both, the drawer takes the full width. It still enters from the edge, so the gesture and the mental model hold across sizes.

## Variants

- `edge`: `inline-end` (default) | `inline-start` | `block-end`.
- `modality`: `modal` (default — a scrim over the surface, focus trapped, the surface behind inert) | `inline` — no scrim, the surface behind stays interactive, for a drawer the user works alongside.
- `width`: the proportion of the viewport the drawer takes on desktop, named by the surface. Below the tablet breakpoint (`foundations/responsive.md` §17.1) it is always full width.

## Determinations

- `position: fixed`, pinned to its edge, full block size on that axis.
- Ground `var(--surface-raised)` with a `1px solid var(--border-subtle)` hairline on the edge facing the surface, and the modal-lift shadow from `foundations/layout.md` §11.8.
- The header is sticky to the drawer's block-start: identity at the inline-start, the close control at the inline-end. It never scrolls away, because the way out must always be visible.
- The body scrolls within the drawer. The surface behind does not scroll while a modal drawer is open.
- The footer, when present, is sticky to the block-end and holds the drawer's commit actions.
- Entrance is a translation from the anchored edge over `var(--duration-300)` `var(--ease-out-quart)`, with the scrim fading in over the same duration. Exit reverses it. Under reduced motion both are instant, and the drawer simply is or is not there (`foundations/motion.md` §15.5).
- The scrim is a dim over the whole viewport, mixed from the theme's ink per the `foundations/layout.md` §11.8 idiom rather than from an absolute, so it darkens correctly in either colour mode. Clicking it closes a modal drawer.
- Opening the drawer is not a navigation. The surface behind keeps its scroll position, its selection, and its state, so closing returns the user exactly where they were.

## Accessibility

- `role="dialog"` with an accessible name taken from its header. The `modal` modality sets `aria-modal="true"` and makes the surface behind inert; the `inline` modality does neither, because claiming modality while the page stays reachable misreports the surface.
- Focus moves into the drawer on open — to the header, not to the close control, so a screen reader hears what opened before it hears how to leave.
- Focus is trapped within a modal drawer. Escape closes it from anywhere inside.
- Closing returns focus to the element that opened it. A drawer opened from a table row returns focus to that row, so the user resumes where they were.
- Focus paints the foundation ring on `:focus-visible` (`foundations/accessibility.md` §18.2).
