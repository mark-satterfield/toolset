---
kind: section
name: left-rail
page_family: app
aliases: [sidebar, rail, nav rail, app rail, left nav, side nav, app shell left rail]
status: stable
shell_edge: inline-start
content_contract:
  carries_mark: "true | false"
  carries_account: "true | false"
theme: default
composition_notes: []
variants: []
sizing:
  rail-width: "var(--app-shell-rail-width); calibrates to 256px at the reference desktop viewport"
  rail-padding: "var(--sp-0-75) on all sides; calibrates to 12px"
  mark-height: "var(--topbar-logo-height) when the received Shape places a mark in the rail, so a mark in a rail and a mark in a bar read at one size across the build"
behavior:
  - "the rail surface is static: it paints, it clips its overflow, and it does not animate"
accessibility:
  - "landmark: <nav aria-label=\"Main navigation\"> wrapping the rail; the rail element it wraps does not redeclare a role"
  - "the rail contributes no keyboard semantics of its own — each piece the Shape places carries its own contract"
token_bindings: [--surface-secondary, --border-subtle, --text-primary, --app-shell-rail-width, --topbar-logo-height, --sp-0-75]
---

# Left rail

The Shell Section pinned to the inline-start edge of the canvas: a fixed column holding whatever navigational pieces the frame offers beside a fluid content region.

**This entry fixes the surface; the Shape fixes the arrangement.** Width, padding, ground, hairline, shadow, overflow, and landmark are the rail's own properties and live here. What the rail holds and in what order is the contract of the Shape this Section receives from the ShapeLibrary (`libraries/shapes/`, the `rail-*` arrangements) — a rail carrying a mark, a menu, and an account row is one arrangement; a rail carrying a menu alone is another. A rail with different contents is a different Shape over this one Section, never an optional slot on a Component.

The pieces a `rail-*` Shape places carry their own contracts: `libraries/components/logo.md`, `libraries/components/vertical-menu.md`, `libraries/components/account-row.md`, `libraries/components/workspace-switcher.md`.

## Shape assignment

Lazy by default: the Shape resolves at build time from `carries_mark` and `carries_account` via `rules/shape-selection/left-rail.md`. A ShellDefinition that names a `rail-*` Shape up front is assigned eagerly and the rule does not run.

## Determinations

- Rail outer container: `position: fixed`, pinned to the inline-start and block-start edges; width `var(--app-shell-rail-width)`; `height: 100vh`.
- Rail padding: `var(--sp-0-75)` on all sides.
- Rail ground: `var(--surface-secondary)` — the elevated rail ground.
- Rail border on the inline-end edge: `0.5px solid var(--border-subtle)` — a hairline at low alpha (`foundations/layout.md` §11.9); the alpha is encoded in the role binding for dark themes.
- Rail box-shadow: `inset -4px 0px 6px -4px color-mix(in srgb, var(--text-primary) 4%, transparent)` at the `lg` breakpoint and above — the §11.8 shadow idiom, mixed from the theme's ink rather than from an absolute; below `lg` the inset is replaced by the §11.8 modal-lift stack.
- Rail `overflow: hidden`; a scrolling region within the received Shape handles its own overflow.
- The rail is a flex column, so a Shape may anchor a piece to either end.
- A mark placed in the rail renders at `var(--topbar-logo-height)`. An app Shell whose Shape carries the mark here needs no top-nav Section at all — the content region then runs to the block-start edge of the frame.

## Accessibility

- The rail is wrapped in `<nav aria-label="Main navigation">`. The nav element carries the landmark; the rail element it wraps does NOT redeclare a role.
- The rail exposes no keyboard semantics of its own: Tab order follows the received Shape's source order, and each piece supplies its own activation contract. A rail is a navigation landmark, not a `role="menu"` — arrow-key composite-widget semantics are never introduced at the rail level.
