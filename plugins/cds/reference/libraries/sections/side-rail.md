---
kind: section
name: side-rail
aliases: [sidebar, rail, nav rail, app rail, left nav, right nav, side nav, left rail, right rail]
status: stable
pins_to: [inline-start, inline-end]
extent:
  size: "var(--app-shell-rail-width)"
  min: "the collapsed extent — one glyph column plus its padding"
  max: "a bounded proportion of the viewport inline size, so the rail can never crowd out the content region"
  resizable: true
content_contract:
  carries_mark: "true | false"
  carries_account: "true | false"
theme: default
composition_notes: []
variants: [presentation, width]
sizing:
  rail-width: "var(--app-shell-rail-width); calibrates to 256px at the reference desktop viewport"
  rail-padding: "var(--sp-0-75) on all sides; calibrates to 12px"
behavior:
  - "the rail surface is static: it paints, it clips its overflow, and it does not animate"
accessibility:
  - "landmark: <nav aria-label=\"Main navigation\"> wrapping the rail; the rail element it wraps does not redeclare a role"
  - "the rail contributes no keyboard semantics of its own — each piece the Shape places carries its own contract"
token_bindings: [--surface-secondary, --surface-tertiary, --text-primary, --app-shell-rail-width, --sp-0-75]
---

# Side rail

A Section pinned to one of the canvas's inline edges: a column holding whatever navigational pieces the frame offers beside a fluid content region.

**There is no such entity as a rail.** This is a Section with attributes — an inline edge to pin to, an extent on its fixed axis, a ground, and a Shape. The word is shorthand for that combination, and this entry is the preset carrying the system's answers for it. A rail on the inline-end edge is this same Section with a different `pins_to` value chosen by the Shell, not a second entry.

**This entry fixes the surface; the Shape fixes the arrangement.** Width, padding, ground, hairline, shadow, overflow, and landmark are the rail's own properties and live here. What the rail holds and in what order is the contract of the Shape this Section receives from the ShapeLibrary (`libraries/shapes/`, the `rail-*` arrangements) — a rail carrying a mark, a menu, and an account row is one arrangement; a rail carrying a menu alone is another. A rail with different contents is a different Shape over this one Section, never an optional slot on a Component.

The pieces a `rail-*` Shape places carry their own contracts: `libraries/components/logo.md`, `libraries/components/vertical-menu.md`, `libraries/components/account-row.md`, `libraries/components/workspace-switcher.md`.

## Shape assignment

Lazy by default: the Shape resolves at build time from `carries_mark` and `carries_account` via `rules/shape-selection/side-rail.md`. A ShellDefinition that names a `rail-*` Shape up front is assigned eagerly and the rule does not run.

## Determinations

- Rail outer container: `position: fixed`, pinned to the inline edge the Shell chose and to the block-start edge; inline size from `extent`; `height: 100vh`.
- Rail padding: `var(--sp-0-75)` on all sides.
- Rail ground: `var(--surface-secondary)` — the elevated rail ground.
- Rail border on the edge facing the content region: `1px solid var(--surface-tertiary)` — the same role the vertical menu's current item paints its ground with (`libraries/components/vertical-menu.md`), so the seam between the rail and the content region and the selected row in the menu read as one decision rather than two. It is a surface role, not an ink role: the edge is a change of stratum, never a drawn line, and a rail edge dark enough to read as a rule has overstated a boundary the ground change already makes.
- Rail box-shadow: `inset -4px 0px 6px -4px color-mix(in srgb, var(--text-primary) 4%, transparent)` at the `lg` breakpoint and above — the §11.8 shadow idiom, mixed from the theme's ink rather than from an absolute; below `lg` the inset is replaced by the §11.8 modal-lift stack.
- Rail `overflow: hidden`; a scrolling region within the received Shape handles its own overflow.
- The rail is a flex column, so a Shape may anchor a piece to either end.
- Every determination here is written about the rail's own edges rather than about "left", so pinning to `inline-end` mirrors it without restating anything.
- A mark placed in the rail takes its height from the placing `rail-*` Shape's `sizing`, not from this entry. An app Shell whose Shape carries the mark here needs no pinned block-start Section at all — the content region then runs to the block-start edge of the frame — which is exactly why a rail's mark height can never be a bar's: in that Shell there is no bar to take it from.

## Presentation

- `expanded` (default) — the rail sits at `extent.size`, and the pieces its Shape places show their glyphs and their labels.
- `collapsed` — the rail sits at `extent.min`, one glyph column wide. Labels are removed rather than truncated, and each item's label becomes its accessible name and its tooltip (`libraries/components/tooltip.md`), so nothing becomes unreachable by collapsing. An account row takes its `compact` variant (`libraries/components/account-row.md`) at this extent.
- `hidden` — the rail is removed from the frame and the content region takes its inline space. The control that restores it lives outside the rail, in a pinned block-start Section, because a control inside a hidden Section cannot be reached.

The content region offsets to the rail's current extent in every presentation, so the frame reflows rather than the rail overlaying content.

## Resizing

- When `extent.resizable` is true, the rail's content-facing edge carries a drag handle bounded by `extent.min` and `extent.max`.
- The handle is a keyboard control as well as a pointer target: focused, it resizes by a documented step, with Home and End going to the bounds.
- Dragging below the midpoint between `min` and `size` snaps to `collapsed`, so the collapsed state is reachable by the same gesture that resizes.
- The chosen extent persists for the surface. A rail that resets on every navigation is not resizable in any useful sense.

## Accessibility

- The rail is wrapped in `<nav aria-label="Main navigation">`. The nav element carries the landmark; the rail element it wraps does NOT redeclare a role.
- The rail exposes no keyboard semantics of its own: Tab order follows the received Shape's source order, and each piece supplies its own activation contract. A rail is a navigation landmark, not a `role="menu"` — arrow-key composite-widget semantics are never introduced at the rail level.
- Collapsing removes labels from view, never from the accessibility tree: each item keeps its label as its accessible name, so a collapsed rail reads identically to an expanded one.
- The collapse, restore, and resize controls each carry an accessible name stating what they do, and a presentation change is announced through a polite live region.
- A rail that expands on hover also expands on focus, so the labels are reachable without a pointer.
