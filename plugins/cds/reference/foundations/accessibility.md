# Accessibility Requirements

## §18.1 Contrast

- Body text on every page ground must meet WCAG AAA: minimum contrast ratio 7:1 against the surrounding `--surface-primary`.
- Tertiary text (meta, dates, placeholders) must meet WCAG AA: minimum contrast ratio 4.5:1.
- Icon-only buttons must carry an `aria-label`.
- The required-field asterisk is `aria-hidden="true"`; the `required` attribute on the input carries semantics.

## §18.2 Focus rings

Provide three distinct focus-ring styles. Use `:focus-visible` so that mouse-click focus does not paint the ring.

| Surface | Focus Style |
|---|---|
| Default | `outline: 2px solid var(--focus-ring); outline-offset: 1px;` Ring color resolves to a mid-neutral on light themes via the active theme's `focus-ring` binding. |
| Inside a button or item with a 4px or smaller radius | `outline-offset: -2px` (ring sits inside the element edge). |
| Conversion input | `outline: 2px solid var(--input-focus-ring); outline-offset: 2px;` Chromatic ring; the `input-focus-ring` role is constrained `from_palette: signals`. |

Tokens for focus:

```css
:root {
  --focus-width: 2px;
  --focus-offset-inner: -2px;
  --focus-offset-outer: 4px;
}
```

## §18.3 Keyboard navigation

- Skip links at the top of `<body>` per the navigation system's skip-link rules.
- Tab order: nav links → CTAs → page content.
- Dropdown triggers use `aria-haspopup="menu"` and `aria-expanded`.
- Accordion rows use `aria-expanded` and `aria-controls`.
- Tab buttons use `aria-selected`.
- Mobile menu trigger uses `aria-label="Open menu"` and `"Close menu"` paired with `aria-expanded`.
- Use `tabindex="-1"` only for actions that are duplicated or non-essential for keyboard users.

## §18.4 Reduced motion

Respect `prefers-reduced-motion: reduce` globally per motion.md §15.5. Override specific animations to `none` inside the media query. The framework already lists reduced-motion overrides for the topbar entrance animation, card-stagger entrance, tab-panel swap, and the mobile drawer footer.

## §18.5 Color and weight floor for readable text

Apply a three-axis floor on color, weight, and size for any text that must be read:

- Color must meet at least WCAG AA against its surface.
- Weight must be at least 600 for text below 14px.
- Size must be at least 12px (or 13px for tracked-caps caption).

Decorative glyphs are exempt. Body, caption, meta, and form labels are not.

## §18.6 Form validation

Prefer browser-native validation for required fields and email format. Render error messages in `--error-text` below the input, with `aria-live="polite"` on the message container.
