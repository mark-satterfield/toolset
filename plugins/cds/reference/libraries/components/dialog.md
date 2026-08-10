---
kind: component
name: dialog
page_family: shared
aliases: [dialog, modal, centered dialog, modal card]
status: stable
slots:
  - { name: card, required: true, accepts: [content-stack] }
  - { name: backdrop, required: true, accepts: [dimmed-wash] }
  - { name: close-glyph, required: true, accepts: [icon-button] }
sizing:
  width: "~600px at and above the 700px breakpoint; full-screen below (100vw × 100dvh)"
  radius: "--radius-lg (16px); 0 in the full-screen collapse"
behavior: [display-toggle-mount, scroll-lock]
accessibility: [modal-dialog-pattern, focus-trap, escape-close]
token_bindings:
  - --surface-raised
  - --text-primary
composite: false
---

# Dialog

A modal card centered on a dimmed-light backdrop: modal card + backdrop + close glyph.

## Determinations

- ~600px wide, `var(--radius-lg)` radius (16px, `foundations/layout.md` §11.7). The close glyph sits upper-right, sticky to the top-left of the scroll container.
- Backdrop is the mapped absolute-black neutral at 50% opacity, with no blur.
- Mounts via display toggle; no entrance keyframe.

## Accessibility

- Renders as `<div role="dialog" aria-modal="true">` with `aria-labelledby` pointing at the dialog title (or `aria-label` when no visible title is present).
- On open, focus moves to the first focusable element in the dialog (typically the close glyph or the first form field). Tab cycles forward within the dialog; Shift+Tab cycles backward; both wrap at the boundaries — focus cannot escape to background content.
- Escape closes the dialog and returns focus to the element that invoked it.
- While open, the underlying page is scroll-locked (typically `overflow: hidden` on `<body>`, accounting for scrollbar width to prevent layout shift). (WAI-ARIA APG modal-dialog pattern.)

## Small-viewport collapse

Below the mobile-wide breakpoint (`< 700px`, `foundations/responsive.md` §17.1) the dialog becomes full-screen: `inset: 0`, `width: 100vw`, `height: 100dvh`, `border-radius: 0`, and the close glyph pins to the top-right of the viewport. At and above 700px it renders as the ~600px centered card. The backdrop and focus-trap contract are unchanged across breakpoints.
