---
kind: component
name: account-row
page_family: app
aliases: [user menu, account menu, profile row, user row]
status: stable
composite: false
slots:
  - { name: avatar, required: true, accepts: [initial, image, icon-glyph] }
  - { name: name, required: true, accepts: [text] }
  - { name: role-or-org, required: false, accepts: [text] }
  - { name: caret, required: false, accepts: [chevron-glyph] }
sizing:
  full-width: "var(--app-shell-rail-width) minus 2 × rail padding; calibrates to 232px at the 256px reference rail"
  full-height: "48px"
  full-padding: "6px vertical × 8px horizontal"
  full-radius: "var(--radius-sm) (8px)"
  avatar: "32×32px, radius var(--radius-xs) (calibrates to 6px), not a circle; inner glyph 20×20px centered"
  compact-button: "32×32px, padding 0, radius var(--radius-sm)"
  footer-strip: "height 40px, padding 0 8px; identity-pill avatar 20×20px"
behavior:
  - "hover fades the background from transparent to the hover stratum (one step above the rail ground) over 150ms --ease-in-out"
  - "menu-open (data-state=\"open\") holds the hover-stratum background; the caret rotates 180° over 150ms with --ease-in-out, suppressed under reduced motion"
accessibility:
  - "wrapper is a <button> carrying aria-haspopup=\"menu\" and aria-expanded"
  - "row carries aria-label joining name and role (e.g. \"Account menu for {name}, {role}\"); avatar SVG is aria-hidden"
  - "Tab focuses the button; Enter/Space open the menu; Escape closes (host menu logic)"
token_bindings: [--surface-raised, --border-subtle, --text-primary, --text-secondary, --text-tertiary, --ease-in-out, --radius-sm, --radius-xs]
---

# Account row

A row anchored to the bottom of the rail (or sidebar) showing the current user's identity, role/org, and an expandable menu trigger for account actions. Fills the left-rail's `account` slot within the Shell's persistent rail Section.

## Variants

- `variant`: `full` (avatar + name + role + caret, standard rail) | `compact` (avatar only, narrow mini-rail) | `footer-strip` (horizontal strip with link + identity pills at the bottom of an app-Shell form sidebar).
- `state`: `rest` | `hover` | `menu-open` (`data-state="open"`).
- The `caret` slot is required in the `full` variant only; the `compact` and `footer-strip` variants have no caret.

The `footer-strip` variant is the form-sidebar placement: it shares the identity slots (avatar, name) and exposes its actions as inline links.

## Determinations — full variant

- Outer button: width fills the rail content — `var(--app-shell-rail-width)` minus 2 × rail padding (calibrates to 232px at the 256px reference rail); height 48px; padding `6px` vertical × `8px` horizontal; border-radius `var(--radius-sm)`; background transparent at rest.
- Layout: `display: flex; align-items: center; gap: 12px`.
- Avatar: 32×32px; border-radius `var(--radius-xs)` (calibrates to 6px) — NOT a circle; border `0.5px solid var(--border-subtle)`; background = the theme's raised ground (`--surface-raised`) at 60% opacity; glyph ink `--text-secondary`. Inner SVG icon: 20×20px centered.
- Name/role stack container: `flex flex-col; align-items: flex-start; min-width: 0; overflow: hidden; padding-right: 16px; flex: 1`.
- Name span: 14px, weight 500; `line-clamp: 2` with `break-words`.
- Role/org line: 12px, weight 400, faint ink stratum (one step below `--text-tertiary`); truncates to 2 lines max with line-clamp.
- Caret: 16×16px SVG chevron in `--text-tertiary` with `aria-hidden="true"`. When the menu opens, the caret rotates 180° over 150ms with `--ease-in-out`; suppress under `prefers-reduced-motion: reduce`.

## Determinations — compact variant

- Button: 32×32px; padding 0; border-radius `var(--radius-sm)`; transparent background at rest; hover paints the hover stratum. Renders the avatar glyph only (no name, role, or caret), centered.
- Avatar inside: the same 32×32px `var(--radius-xs)`-radius avatar spec as the full variant, filling the button.
- Carries an `aria-label` joining the user's name and role so the identity is announced despite the absent visible text.

## Determinations — footer-strip variant

- A horizontal strip at the bottom of a form sidebar: `display: flex; align-items: center; justify-content: space-between; gap: 12px`; height 40px; padding `0 8px`.
- Left: a small identity pill (avatar 20×20px + name at 12px in `--text-secondary`). Right: a Tertiary link (e.g., "Sign out" or "Account") at 12px.
- The footer-strip variant carries no caret and no menu trigger; its actions are the inline links themselves.

## Behavior

- `hover` (pointer): background fades from transparent to the hover stratum (one stratification step above the rail ground) via a color transition over 150ms `var(--ease-in-out)` (calibrates to `cubic-bezier(0.4, 0, 0.2, 1)`).
- `menu-open` (`data-state="open"`): background holds the hover stratum; the caret (if animated) rotates 180°.

## Accessibility

- Wrapper is a `<button>` carrying `aria-haspopup="menu"` and `aria-expanded`.
- The row carries an `aria-label` joining avatar + name + role: e.g., `aria-label="Account menu for {name}, {role}"`. The avatar SVG carries `aria-hidden="true"`.
- Keyboard: Tab focuses the button; Enter or Space opens the menu; Escape closes (host's menu logic).

## Structural skeleton — full variant

```html
<button class="account-row" aria-haspopup="menu" aria-expanded="false"
        aria-label="Account menu for {name}, {role}">
  <div class="account-row-inner"><!-- flex row, 12px gap, min-width 0 -->
    <div class="account-avatar"><!-- 32×32, radius --radius-xs (calibrates 6px), hairline border, --surface-raised at 60% -->
      <svg aria-hidden="true"><!-- avatar glyph (20×20) --></svg>
    </div>
    <div class="account-identity"><!-- column, min-width 0, 16px right padding, flex 1 -->
      <span class="account-name">{name}</span><!-- 14px / 500, line-clamp 2 -->
      <span class="account-role">{role-or-org}</span><!-- 12px / 400, faint ink, truncate -->
    </div>
    <svg class="account-caret" aria-hidden="true"><!-- 16×16 chevron --></svg>
  </div>
</button>
```
