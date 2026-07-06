---
kind: section
name: step-breadcrumb
id: AS7
family: app
aliases: [stepper, step indicator, multi-step breadcrumb, wizard steps]
status: stable
mode: deterministic
content_contract:
  step_count: "number of steps in the flow (content-driven)"
  current_step: "index of the active step"
theme: default
composition_notes: []
---

# AS7 — Step breadcrumb

A numbered step indicator anchored at the top of the main pane (`--sp-1-5` from the top edge), rendered by the stepper component (`libraries/components/`), which carries the full spec.

Width adapts to the viewport: at narrow viewports the stepper compresses to icons only (width fits the step circles and gaps; calibrates to ~200px); at wide viewports it grows to fit the step labels (calibrates to labels showing at ≥ 1400px).

## Determinations

- Active-step visual: the current step's circle uses `--text-primary` for both its border and its numeral; completed steps use a filled accent circle with a check glyph; future steps use `--text-tertiary` ink on a transparent circle with a `--border-subtle` ring.
