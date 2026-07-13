---
kind: component
name: cds-reset
family: app
aliases: [style reset, reset utility, control reset]
status: stable
slots: []
sizing: {}
behavior:
  - "no behavior of its own — a style-neutralization utility class"
accessibility:
  - "removes no focus affordance; the foundation :focus-visible ring still applies"
token_bindings: []
shell_component: false
composite: false
---

# cds-reset

A utility class that neutralizes user-agent and host-cascade styling on interactive primitives (`button`, `input`, `a`, and wrapper `div`s) inside app-surface components, so the component's own contract fully determines rendering. App-surface structural skeletons apply it to wrappers and inner triggers whose visual styling is owned by the component (filter chip, period picker, toggle switch, and peers).

## Declaration

```css
.cds-reset {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  line-height: inherit;
  letter-spacing: inherit;
  text-align: inherit;
  appearance: none;
  -webkit-tap-highlight-color: transparent;
}
```

## Determinations

- The reset neutralizes box, ground, and type inheritance only. It does NOT set `outline: none` — focus indication remains governed by the foundation focus-ring contract (`foundations/accessibility.md` §18.2), which paints on `:focus-visible`.
- Components re-declare their own styling (ground, ring, radius, padding) on top of the reset; the reset guarantees the starting point is the same in a standalone mock and inside a host application's cascade.
- Emitted once in `components.css` by `generate-stylesheets`; a page never re-declares it.
