---
kind: component
name: stepper
aliases: [progress steps, wizard steps, step indicator, numbered steps]
status: stable
slots:
  - { name: step, required: true, accepts: [circle, label, meta] }
  - { name: connector, required: true, accepts: [rule] }
sizing:
  circle: "component geometry"
  connector: "hairline × component geometry"
behavior:
  - "states per step: current | pending | complete"
  - "non-interactive by default; aria-current=step marks the current step"
accessibility:
  - "wrapper <ol> (implicit role=list); connectors aria-hidden"
  - "no navigation landmark — a status indicator"
token_bindings: [--text-primary, --text-tertiary, --text-inverse, --border-subtle, --status-positive-bg, --focus-ring, --typeface-sans, --font-mono]
composite: false
---

# Stepper

A horizontal progress indicator showing a numbered sequence of steps in a multi-step flow. The current step is visually emphasized (high-contrast outline, full-strength ink); pending and complete steps drop to a dim-border + muted-ink treatment. Optional API-endpoint metadata renders inline at very wide viewports.

## Slots

- `step` (repeating, 1 per logical step):
  - `circle` (required): the numbered indicator.
  - `label` (required): the step name.
  - `meta` (optional, current step only by convention): inline secondary text (e.g., the API call this step makes), rendered in the monospace face.
- `connector` (one per step except the first, rendered BEFORE that step's wrapper): a hairline horizontal rule joining adjacent steps. Owned by the step it precedes (inside the same `<li>`).

## Sizing

- Circle: component geometry (calibrates to 20×20px); fully rounded.
- Current-step circle border: an emphasis-weight border in `--text-primary` (calibrates to 1.5px).
- Pending-step circle border: `1px solid --border-subtle`.
- Connector: hairline height × a short run (calibrates to 1×16px) in `--border-subtle`.
- Gap between circle and label/meta inside a step (calibrates to 8px); gap between adjacent step wrappers inside the `<ol>` (calibrates to 12px).
- Circle number: caption scale (calibrates to 12px), weight 500, `--typeface-sans`.
- Label: body compact scale (calibrates to 14px); weight 500 for the current step, 400 for pending.
- Meta: caption scale (calibrates to 12px), `--font-mono`, ink `--text-tertiary`.

## Responsive collapse

- Default viewport: only circles + connectors render. Labels and meta are `display: none`.
- Very wide viewport (calibrates to ≥1400px): labels become inline.
- Widest viewport (calibrates to ≥1536px): meta becomes inline.
- Label and meta use `white-space: nowrap`.

## Behavior

Not interactive by default; the wrapper carries `aria-current="step"` on the current step only. No CSS transitions on the step elements — no reduced-motion fallback required. If a host project's flow needs back-navigation, the pending/complete circle becomes a `<button>` inside the wrapper.

## Accessibility

- Wrapper element: `<ol>` (implicit ARIA role `list`).
- Each step: `<li>` with `display: contents`.
- The current step's inner `<div>` carries `aria-current="step"`.
- Connectors carry `aria-hidden="true"`.
- No `role="navigation"` — it's a status indicator, not a navigation landmark.

## Structural skeleton

```html
<ol class="stepper"><!-- flex row, min-w-0 -->
  <li class="stepper__step"><!-- display: contents -->
    <div aria-current="step" class="stepper__step-body stepper__step-body--current">
      <span class="stepper__circle"><!-- emphasis border in --text-primary; number in --text-primary -->1</span>
      <span class="stepper__label">Create project</span>
      <span class="stepper__meta"><!-- --font-mono, --text-tertiary -->POST /v1/projects</span>
    </div>
  </li>
  <li class="stepper__step">
    <span aria-hidden="true" class="stepper__connector"><!-- hairline in --border-subtle --></span>
    <div class="stepper__step-body">
      <span class="stepper__circle"><!-- 1px --border-subtle; number in --text-tertiary -->2</span>
      <span class="stepper__label">Configure environment</span>
    </div>
  </li>
</ol>
```

## Complete-state visual

A completed step paints a filled circle in `--status-positive-bg` containing a centered checkmark glyph (replacing the step number), inked in `--text-inverse` (calibrates to white over the positive fill at the captured surface — the nearest ink role; no dedicated on-status ink role exists). The circle border drops in favor of the fill; the label shifts to weight 400 at `--text-primary`, matching pending labels but with the filled circle marking completion.

## Interactive back-navigation

When a host enables back-navigation, the complete/pending circle's `<span>` is replaced with a `<button>` carrying an `aria-label` of the step name; it paints the foundation focus ring on `:focus-visible` (`outline: 2px solid var(--focus-ring); outline-offset: 2px`, `foundations/accessibility.md` §18.2). The current step is never a button (you cannot navigate to where you already are).
