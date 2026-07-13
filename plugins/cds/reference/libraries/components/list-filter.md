---
kind: component
name: list-filter
family: app
aliases: [search field, list search, filter box, inline filter input]
status: stable
slots:
  - { name: glyph, required: true, accepts: [icon] }
  - { name: input, required: true, accepts: [text-entry] }
  - { name: placeholder, required: true, accepts: [text] }
  - { name: clear, required: false, accepts: [button] }
sizing:
  width: "full container width"
  height: "--control-height"
  radius: "--radius-sm"
behavior:
  - "states: rest | hover | focus | with-value | disabled"
  - "live filtering debounced at --duration-200"
accessibility:
  - "input type=search (implicit role=searchbox)"
  - "visually-hidden label or aria-label matching the placeholder"
  - "Escape clears the focused input"
token_bindings: [--surface-raised, --border-subtle, --border-strong, --focus-ring, --text-primary, --text-tertiary, --typeface-sans]
shell_component: false
composite: false
---

# List filter

A single-line text input with a leading search glyph and a placeholder, used to filter a list rendered elsewhere on the same page. Distinct from the general-purpose search input (`libraries/components/search-input.md`); the list filter is the in-list filter pattern with a wrapper that owns the visual styling and a transparent inner input.

## Slots

- `glyph` (required): leading magnifying-glass SVG icon, left-aligned inside the wrapper (calibrates to 16×16px).
- `input` (required): the text-entry field. Renders transparent with zero padding (visual styling lives on the wrapper).
- `placeholder` (required): instructive placeholder text.
- `clear` (optional): a trailing × clear button visible only when the input has a value.

## Sizing

- Wrapper: full container width; height `--control-height` (calibrates to 36px); padding at the small steps (calibrates to 12px horizontal, 8px vertical); border `1px solid --border-subtle`; radius `--radius-sm` (calibrates to 8px); ground `--surface-raised`; `display: flex` with an internal gap (calibrates to 8px).
- Glyph: icon-glyph geometry (calibrates to 16×16px).
- Input itself: `flex: 1; background: transparent; padding: 0; border: none; outline: none`; font `--typeface-sans` at the caption scale (calibrates to 12px); placeholder ink `--text-tertiary`; input text ink `--text-primary`.

## Behavior

- `hover`: border steps from `--border-subtle` to `--border-strong` via a color transition.
- `focus`: the foundation focus ring applies on the wrapper, painted in `--focus-ring` (`foundations/accessibility.md` §18.2).
- `disabled`: cursor not-allowed; 50% opacity.
- Reduced motion: suppress the border-color transition.

## Accessibility

- `<input type="search">` provides implicit `role="searchbox"`.
- Pair with a visually-hidden `<label>` or `aria-label` matching the placeholder.
- The wrapper `<div>` carries no role.
- Escape clears the input when focused (browser default for `type="search"`).
- Tab focuses the input.

## Structural skeleton

```html
<div class="list-filter"><!-- --surface-raised ground, 1px --border-subtle, --radius-sm, --control-height -->
  <svg class="list-filter__glyph" aria-hidden="true"><!-- magnifying-glass path --></svg>
  <input type="search" placeholder="Search templates" aria-label="Search templates"
         class="list-filter__input"><!-- transparent, flex:1, --text-primary; placeholder --text-tertiary -->
</div>
```

## Clear button mechanics

Because the input is `<input type="search">`, the browser's native clear control renders automatically once a value is present and clears on Escape when focused (HTML spec). When the host needs a custom clear control (e.g., to match the magnifier glyph's visual weight or to suppress the native browser glyph via `::-webkit-search-cancel-button { display: none }`), the custom clear is a trailing `<button type="button" aria-label="Clear search">`, visible only when the input value is non-empty, positioned at the right edge inside the wrapper. On click: clear the input value, restore focus to the input, and emit a synthetic change event so the host's filter logic re-runs.

## Debounce contract

Live filtering debounces input at `--duration-200` (the `foundations/motion.md` §15.2 interaction-scale duration, calibrates to 200ms): the filter callback fires after the user stops typing, with a leading-edge fire on the first keystroke so the first character feels immediate. Clearing the field (native or custom clear) fires the filter immediately with an empty query, bypassing the debounce.
