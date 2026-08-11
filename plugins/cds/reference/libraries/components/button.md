---
kind: component
name: button
aliases: [button, primary button, secondary button, tertiary button, CTA]
status: stable
slots:
  - { name: leading-icon, required: false, accepts: [icon] }
  - { name: label, required: true, accepts: [text] }
sizing:
  min_height: "40px (intrinsic control floor)"
  padding: "8px 16px"
  radius: "--radius-sm (8px) at the body-2 label size (17px); --radius-md at the body-3 label size (14–15px), calibrates to 9.6px at the captured surface (ladder default 12px)"
  icon_gap: "8px when a leading icon is present"
behavior: [hover-shoulder-ring, disabled, loading, shared-transition]
accessibility: [focus-visible-ring, disabled-attribute-choice, icon-only-aria-label, tap-target]
token_bindings:
  - --button-primary-bg
  - --button-primary-text
  - --button-secondary-bg
  - --button-secondary-text
  - --button-tertiary-border
  - --text-tertiary
  - --text-primary
  - --surface-primary
  - --focus-ring
composite: false
---

# Button

The base button contract shared by every button variant, plus the three standard variants. A conversion, commit, or supporting action rendered as a filled, bordered, or quiet control.

## Variants

| Variant | Structure | Theme roles | Interaction behavior | Notes |
|---|---|---|---|---|
| `primary` | Fill + label | `--button-primary-bg`, `--button-primary-text` | Hover paints a 1px outer shoulder ring in the fill color over 200ms. | The dominant button on its surrounding surface. Inverts ground with the page's color-mode (light theme → dark fill; dark theme → light fill). |
| `secondary` | Fill + label | `--button-secondary-bg`, `--button-secondary-text` | Hover shifts fill to `--surface-primary`. | Supporting action peer to a primary button on the same surface. |
| `tertiary` | Border + label | `--button-tertiary-border`, `--text-tertiary` | Hover shifts text color to `--text-primary`; border unchanged. | Quietest affordance; transparent fill, hairline border, link-glyph leading. Used inline or as a link-like control. |

State props: `rest` | `hover` | `disabled` | `loading`.

## Determinations

- `min-height: 40px` (2.5rem); `display: inline-flex; align-items: center; justify-content: center` — label and any leading icon centered on both axes, `gap: 8px` when a leading icon is present.
- `padding: 8px 16px` (0.5rem 1rem).
- `border-radius: var(--radius-sm)` (8px, `foundations/layout.md` §11.7) for the body-2 label size (17px); `var(--radius-md)` for the body-3 label size (14–15px) — calibrates to 9.6px at the captured surface (ladder default 12px).
- Font: Primary Sans, Body 2 size (17px), weight per the type-weight scale in `foundations/implementation.md` §6.4. `line-height: 1`.

## Behavior

- Shared transition: `color 0.1s ease, background-color 0.2s, box-shadow 0.2s`. The leading icon (if any) transitions `color 0.3s ease`.
- Hover: a 1px outer box-shadow ring in the button's fill color — shadow, never a fill change, is the hover affordance.
- Disabled: 50% opacity, `pointer-events: none`, shadow removed.

## Accessibility

- **Disabled-state attribute choice.** Default to the HTML `disabled` attribute on `<button>` so the control is excluded from tab order, form submission, and pointer events at the browser level. Use `aria-disabled="true"` (plus visual styling and a JS click-guard) only when the control must remain focusable so screen reader users can still discover it (e.g., a form-submit button whose disabled state explains *why* on focus). The two forms are mutually exclusive — never set both. (WAI-ARIA + HTML spec.)
- **Focus-visible ring.** `outline: 2px solid var(--focus-ring); outline-offset: 2px` per the foundation focus-ring contract (`foundations/accessibility.md` §18.2) — paints only on `:focus-visible` so pointer-input focus does not light the ring. (WCAG 2.4.7, 2.4.11.)
- **Loading / pending state.** Preserve the button's rest-state width and height (no layout shift); replace the label with a centered spinner inheriting `currentColor`; set `aria-busy="true"`; ignore click events while loading. The `disabled` attribute is not set during loading so screen readers continue to announce the button.
- **Icon-only variant.** A button with no visible label carries an `aria-label` describing the action (e.g., `aria-label="Close"`). Icon-only buttons render at the larger of `min-height: 40px` and `min-width: 40px` so the icon's hit area meets the same target floor as labelled buttons. (WAI-ARIA + WCAG 2.5.5.)
- **Tap target.** The 40px base clears the WCAG 2.2 AA minimum target size (2.5.8, 24×24) with room to spare, assuming desktop placement with adequate inline spacing satisfying 2.5.8's spacing clause. The 44×44 size is the WCAG 2.5.5 **AAA** target size — variants intended for high-pointer-error contexts (mobile, forms) ship at `min-height: 44px`; the authentication primary CTA (`libraries/components/auth-primary-cta.md`) is the 44px conversion variant.
