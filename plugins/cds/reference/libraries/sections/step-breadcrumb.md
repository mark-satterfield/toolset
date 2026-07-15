---
kind: section
name: step-breadcrumb
page_family: app
aliases: [stepper, step indicator, multi-step breadcrumb, wizard steps]
status: stable
shape: step-indicator-row
content_contract:
  step_count: "number of steps in the flow (content-driven)"
  current_step: "index of the active step"
theme: default
composition_notes: []
---

# Step breadcrumb

A numbered step indicator for a multi-step flow, rendered by the stepper component (`libraries/components/`), which carries the full spec. Its layout is the step-indicator-row Shape (`libraries/shapes/step-indicator-row.md`); the stepper fills its stepper slot. The number of steps and the index of the active step come from the flow's content.
