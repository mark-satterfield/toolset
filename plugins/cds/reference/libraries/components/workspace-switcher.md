---
kind: component
name: workspace-switcher
page_family: app
aliases: [workspace picker, org switcher, team switcher]
status: stable
composite: false
slots:
  - { name: wrapper, required: true, accepts: [trigger, collapse-toggle] }
  - { name: trigger, required: true, accepts: [color-dot, name, caret] }
  - { name: name, required: true, accepts: [text] }
  - { name: caret, required: true, accepts: [chevron-glyph] }
  - { name: collapse-toggle, required: false, accepts: [button] }
  - { name: color-dot, required: false, accepts: [color-swatch] }
  - { name: panel, required: true, accepts: [search-input, workspace-row, create-workspace-action] }
sizing:
  wrapper-width: "var(--app-shell-rail-width) minus 2 × rail padding (var(--sp-0-75) per side); calibrates to 232px at the 256px reference rail"
  wrapper-height: "32px"
  wrapper-padding: "0 5px 0 0"
  wrapper-radius: "var(--radius-xs) (calibrates to 6px)"
  trigger-width: "wrapper width minus the wrapper's 5px trailing padding and 2px gap; calibrates to 225px at the 232px reference wrapper"
  trigger-height: "30px"
  trigger-padding: "0 0 0 8px"
  compact-button: "32×32px, padding 0, radius var(--radius-xs) (calibrates to 6px)"
behavior:
  - "closed: trigger carries aria-expanded=\"false\"; open: aria-expanded=\"true\" and the panel becomes visible"
  - "compact-variant hover transitions ink from the faint stratum to --text-primary; transition duration 300ms cubic-bezier(0.165, 0.85, 0.45, 1) plus color transition"
  - "compact ↔ full keys off the rail's collapsed/expanded runtime state, not a media query"
accessibility:
  - "trigger: <button type=\"button\" role=\"combobox\" aria-haspopup=\"dialog\" aria-expanded> — combobox + dialog popup, NOT menu or listbox"
  - "wrapper <div> carries no ARIA role"
  - "Space/Enter open; arrow keys, Escape, and focus trap are dialog-pattern responsibilities"
  - "reduced motion suppresses both transitions for instant color swaps"
token_bindings: [--border-subtle, --surface-secondary, --text-primary, --text-tertiary, --radius-xs, --sp-0-25]
---

# Workspace switcher

A control at the top of the rail letting the user switch between workspaces in the current organization. Fills the left-rail's `workspace-switcher` slot within the Shell's persistent rail Section.

## Variants

- `variant`: `compact` (32×32 icon-only, rail collapsed) | `full` (named trigger, rail expanded).
- `state`: `closed` | `open`.

## Determinations — full variant

- Wrapper: width = `var(--app-shell-rail-width)` minus 2 × rail padding (calibrates to 232px at the 256px reference rail); height 32px; padding `0 5px 0 0`; border `1px solid var(--border-subtle)` (hairline at low alpha against the dark rail surface); border-radius `var(--radius-xs)` (calibrates to 6px); background transparent (the rail's `--surface-secondary` shows through); layout `display: flex; gap: 2px; align-items: center`.
- Trigger: width = wrapper width minus the trailing 5px padding and 2px gap (calibrates to 225px); height 30px; padding `0 0 0 8px`; internal gap 4px.
- Trigger children: the `name` span is `flex: 1; min-width: 0` with truncation, 12px, weight 400, ink `--text-primary`; the `caret` is a 12×12px chevron in the faint ink stratum (one step below `--text-tertiary`), `flex-shrink: 0`, with a trailing margin of `calc(0.75 × var(--sp-0-25))` (calibrates to 3px) separating it from the wrapper's trailing edge.

## Determinations — compact variant

- Button: 32×32px; padding 0; border-radius `var(--radius-xs)` (calibrates to 6px); transparent background; faint-stratum ink at rest, `--text-primary` on hover.
- Single child: 16×16 icon glyph; color inherited via `currentColor`.

## Behavior

- `closed` (rest): trigger carries `aria-expanded="false"`.
- `open`: trigger carries `aria-expanded="true"`; panel becomes visible.
- `hover` (compact variant): ink transitions from the faint stratum to `--text-primary` via a color transition.
- `focus`: the inner button suppresses its own ring; the wrapper carries `outline-offset: 2px` so the focus indicator paints on the wrapper. The actual focus ring is the global `:focus-visible` foundation.
- Compact-variant transition: 300ms `cubic-bezier(0.165, 0.85, 0.45, 1)` plus the color transition.
- Under `prefers-reduced-motion: reduce`, suppress both transitions for instant color swaps.
- Variant switching: the `compact` ↔ `full` switch keys off the rail's collapsed/expanded runtime state (the rail's own collapse toggle), not a media query — when the rail collapses, the switcher renders `compact`.

## Accessibility

- Trigger: `<button type="button" role="combobox" aria-haspopup="dialog" aria-expanded="false">`. The combobox role + dialog popup is the pattern (NOT `<menu>` or `<listbox>`); `aria-haspopup="dialog"` means screen readers announce "opens a dialog."
- Wrapper `<div>` carries no ARIA role.
- Keyboard: standard button activation (Space/Enter to open). Arrow keys, Escape, and dialog focus-trap behavior are dialog-pattern responsibilities.

## Structural skeleton — full variant

```html
<div class="workspace-switcher"><!-- hairline border, radius --radius-xs (calibrates 6px), flex row, 2px gap, 5px right padding -->
  <button type="button" role="combobox" aria-haspopup="dialog" aria-expanded="false">
    <span class="workspace-name">{workspace name}</span><!-- flex-1, min-width 0, truncate -->
    <div class="workspace-caret"><!-- 12×12 caret SVG; trailing margin calc(0.75 × --sp-0-25), calibrates 3px --></div>
  </button>
  <!-- optional sibling: collapse-rail toggle -->
</div>
```

## Structural skeleton — compact variant

```html
<button type="button" aria-label="{open workspace switcher}" class="workspace-switcher--compact">
  <!-- 16×16 icon glyph -->
</button>
```

## Panel contents

The popover is a `role="dialog"` listing the organization's workspaces. Its layout, top to bottom: a search-input component (shown only when more than ~7 workspaces exist), a list of workspace rows (the rows are a vertical-menu Component, `libraries/components/vertical-menu.md`, carrying `aria-current="true"` on the active workspace), and a "Create workspace" row pinned to the bottom rendered as a Tertiary button with a leading plus glyph. The panel follows the dropdown-panel lift-and-scale open vocabulary and the modal-dialog focus-trap contract.

## Leading workspace-color dot

An optional `color-dot` slot precedes the workspace name in both trigger and panel rows: an 8px circle painted in the workspace's identity color, supplied per workspace by the host. When no color is supplied the dot is omitted and the name sits flush left.
