---
kind: component
name: sticky-header
page_family: editorial
aliases: [hide-on-scroll header, auto-hiding header, scroll-away nav]
status: stable
shell_component: true
composite: false
slots:
  - { name: header, required: true, accepts: [topbar] }
sizing:
  dimensions: "inherits the topbar dimension contract (var(--topbar-height) and its mobile_floor)"
behavior:
  - "hides on downward scroll (transform: translateY(-100%) over 0.3s ease) and reappears on upward scroll"
  - "hide threshold: 8px cumulative downward scroll past the header height; reveal on ≥4px upward scroll; detection debounced to one evaluation per animation frame"
accessibility:
  - "hide is suppressed while focus is inside the header (WCAG 2.4.11 Focus Not Obscured, AA)"
  - "prefers-reduced-motion: reduce drops the transition so the header snaps between states"
token_bindings: []
---

# Sticky header

A header that hides on downward scroll and reappears on upward scroll. Optional; applies only to editorial surfaces. A behavioral modifier over the Shell's persistent top-nav Section (the topbar), inheriting its dimension contract.

## Variants

- `state`: rest | `is-hidden` (translated off-screen).
- `motion-mode`: `animated` (default) | `reduced` (under `prefers-reduced-motion: reduce`, no transition).

## Determinations

```css
.header.is-hide-on-scroll {
  transition: transform 0.3s ease;
}
.header.is-hide-on-scroll.is-hidden {
  transform: translateY(-100%);
}
@media (prefers-reduced-motion: reduce) {
  .header.is-hide-on-scroll { transition: none; }
}
```

- The `is-hidden` class is added via JavaScript on downward scroll past the header height and removed on upward scroll.
- Scroll-direction detection threshold: apply a hide threshold of 8px of cumulative downward scroll past the header height before adding `is-hidden`, and reveal on any upward scroll of 4px or more. Debounce scroll handling to one evaluation per animation frame (`requestAnimationFrame`) so the detection cost stays off the main scroll path.

## Accessibility

- Reduced-motion override drops the transition entirely so the header snaps between states.
- Focus during hide: while focus is inside the header (e.g., the user has Tab-walked into a nav link or CTA), the `is-hidden` class is NOT applied — the hide is suppressed until focus leaves the header. This prevents the keyboard user's focused control from being scrolled off-screen. (WCAG 2.4.11 Focus Not Obscured, AA.)
- If the header hides while focus is elsewhere, focus is untouched; the next Tab moves into the next sequential focusable element in the document, which may be off-screen until the user scrolls up to reveal the header. (HTML default focus order.)
