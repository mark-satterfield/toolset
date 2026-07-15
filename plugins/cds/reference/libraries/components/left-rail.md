---
kind: component
name: left-rail
page_family: app
aliases: [sidebar, rail, nav rail, app rail, left nav, app shell left rail]
status: stable
shell_component: true
composite: false
slots:
  - { name: outer-rail, required: true, accepts: [workspace-switcher, section-header, item-row, account-row] }
  - { name: workspace-switcher, required: false, accepts: [workspace-switcher] }
  - { name: section-header, required: false, accepts: [label] }
  - { name: item-row, required: true, accepts: [icon, label] }
  - { name: account, required: false, accepts: [account-row] }
  - { name: detail-viewport, required: true, accepts: [page] }
sizing:
  rail-width: "var(--app-shell-rail-width); calibrates to 256px at the reference desktop viewport"
  rail-padding: "var(--sp-0-75) on all sides; calibrates to 12px"
  nav-row-height: "var(--list-row-compact) (36px)"
  nav-row-padding: "8px horizontal (rows with a leading icon inflate left padding to 40px to reserve the icon column)"
  nav-row-gap: "var(--sp-0-75) between icon and label; calibrates to 12px"
  nav-row-radius: "var(--radius-sm) (8px)"
behavior:
  - "active row paints a filled pill: --surface-tertiary ground, --text-primary ink; no left bar, no border indicator — the fill alone marks the selection"
  - "inactive rows are transparent at rest; hover paints the hover stratum (one step above the rail ground, one below the active pill) with --text-primary ink over 150ms --ease-in-out"
  - "rows are <a> anchors because they navigate — not <button>"
accessibility:
  - "rail wrapped in <nav aria-label=\"Main navigation\">; the rail <div> does not redeclare a role"
  - "active row carries aria-current=\"page\""
  - "sequential Tab order — not arrow-key composite-widget semantics"
  - "foundation focus ring on :focus-visible; reduced motion suppresses the hover transition"
token_bindings: [--surface-secondary, --surface-tertiary, --border-subtle, --text-primary, --text-secondary, --text-tertiary, --always-black, --list-row-compact, --radius-sm, --ease-in-out]
---

# App shell left rail

Navigation for app Shells combining the Shell's rail-and-list Sections: the icon-rail and list-column collapse into a single rail column, with a fluid detail viewport filling the remaining width. It realizes the Shell's persistent navigation rail Section.

## Variants

- `row-state`: rest | `active` (filled-pill selection).

## Determinations

- Rail outer container: `position: fixed; left: 0; top: 0`; width = `var(--app-shell-rail-width)` (calibrates to 256px); `height: 100vh`.
- Rail padding: `var(--sp-0-75)` (calibrates to 12px) on all sides.
- Rail background: `var(--surface-secondary)` (elevated rail ground).
- Rail border-right: `0.5px solid var(--border-subtle)` — a hairline at low alpha against the dark surface; alpha is encoded in the role binding for dark themes.
- Rail box-shadow: `inset -4px 0px 6px -4px hsl(var(--always-black) / 4%)` at the `lg` breakpoint and above; a plain large drop shadow below `lg`.
- Rail `overflow: hidden`.
- Nav-row height: `var(--list-row-compact)` (36px — the dense list-row step); horizontal padding 8px; icon-to-label gap `var(--sp-0-75)` (calibrates to 12px); border-radius `var(--radius-sm)`.
- Nav-row font: `font-ui`, 14px, weight 400.
- Active-row pill: paints the full row at radius `var(--radius-sm)` with background `var(--surface-tertiary)` (deepest stratification within the theme) and ink `var(--text-primary)`. The active row carries `aria-current="page"`.
- Inactive-row rest: transparent ground, ink `var(--text-secondary)`.
- Inactive-row hover: ground at the theme's hover stratum — one stratification step above the rail's `--surface-secondary` and one below the active pill's `--surface-tertiary` — ink `var(--text-primary)`.
- Hover transition (inactive): color, background-color, border-color, text-decoration-color, fill, and stroke over 150ms `var(--ease-in-out)` (calibrates to `cubic-bezier(0.4, 0, 0.2, 1)`).
- Section headers sit above grouped rows in tertiary ink (`--text-tertiary`).
- Account slot: an account-row component anchors at the bottom edge of the rail — the rail is a flex column and the account slot takes `margin-top: auto`, sitting below the scrolling nav rows.
- Icon-slot reservation: rows that prefix an icon glyph inflate left padding to 40px to reserve the icon column; the icon-to-label gap stays `var(--sp-0-75)`. Rows without an icon use the base 8px horizontal padding. The reservation is a per-row modifier, not a change to the base row contract — apply it consistently to every row in a section so the labels align.

## Accessibility

- Rail outer is wrapped in `<nav aria-label="Main navigation">`. The nav element carries the landmark; the rail `<div>` it wraps does NOT redeclare a role.
- Active row carries `aria-current="page"`.
- Focus contract: nav rows expose focus via the foundation focus ring on `:focus-visible` (`outline: 2px solid var(--focus-ring); outline-offset: 2px`). The ring paints only for keyboard focus.
- Keyboard: rows are `<a>` anchors inside a `<nav>` landmark, not a `role="menu"` — the contract is standard sequential Tab order, NOT arrow-key navigation. Tab moves to the next focusable row; Shift+Tab to the previous; Enter activates. (WAI-ARIA APG: navigation landmarks do not use arrow-key composite-widget semantics.)
- Reduced motion: honor `prefers-reduced-motion: reduce` by suppressing the hover transition; the hover state swaps instantly. (WCAG 2.3.3.)
