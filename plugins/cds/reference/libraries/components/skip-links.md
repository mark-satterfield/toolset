---
kind: component
name: skip-links
page_family: shared
aliases: [skip to content, skip navigation, bypass links]
status: stable
composite: false
slots:
  - { name: skip-link, required: true, accepts: [in-page-anchor] }
sizing:
  padding: "12px 24px"
  radius: "0 0 var(--radius-md) var(--radius-md)"
  offscreen-position: "top: -1000px; left: 50%; transform: translateX(-50%)"
behavior:
  - "hidden off-screen at rest; snaps to top: 0 on focus so the first Tab from the document reveals it"
accessibility:
  - "semantic <a> elements with in-page hash anchors (WCAG 2.4.1 Bypass Blocks)"
  - "focused link stacks at z-index 101 — one step above the topbar's z-index 100 — so it is never occluded"
  - "state change keys on :focus (not :focus-visible) and pairs with the foundation focus ring"
token_bindings: [--surface-primary, --text-primary, --radius-md, --focus-ring]
---

# Skip links

Keyboard-accessible jump targets at the top of the body that snap into view on focus. It realizes one of the Shell's persistent Sections.

## Variants

- `state`: rest (off-screen) | `:focus` (snapped into view).

## Determinations

```html
<a href="#main-content" class="skip-link">Skip to main content</a>
<a href="#footer" class="skip-link">Skip to footer</a>
```

```css
.skip-link {
  position: absolute;
  top: -1000px;
  left: 50%;
  transform: translateX(-50%);
  padding: 12px 24px;
  background: var(--surface-primary);
  color: var(--text-primary);
  border-radius: 0 0 var(--radius-md) var(--radius-md);
  font-weight: 700;
  text-decoration: none;
}
.skip-link:focus {
  top: 0;
}
```

- Font-weight 700; no text decoration.

## Accessibility

- Hidden off-screen at rest; snaps to `top: 0` on focus so the first Tab from the document reveals it.
- Uses semantic `<a>` elements with in-page hash anchors.
- Stacking: focused skip links use `z-index: 101`, one step above the fixed topbar's `z-index: 100`, so the link is never visually occluded when it snaps into view. (WCAG 2.4.1 — Bypass Blocks.)
- Focus styling: the skip-link state change is `:focus` (not `:focus-visible`) because keyboard users are the sole population that surfaces this control — the positional snap IS the focus indicator, and it must paint for every focus event regardless of input modality. Pair with the foundation focus ring (`outline: 2px solid var(--focus-ring); outline-offset: 2px`) so the focused link is visually distinct against any page ground. (WCAG 2.4.7, 2.4.11, 2.4.13.)
