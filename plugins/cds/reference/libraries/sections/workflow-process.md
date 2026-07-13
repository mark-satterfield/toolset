---
kind: section
name: workflow-process
family: landing
aliases: [how it works, steps, process, workflow, getting started steps]
status: stable
mode: dynamic
content_contract:
  step_count: int
theme: scheduled
composition_notes:
  - "A workflow whose step_count does not fit one Shape cleanly may split into two consecutive workflow-process Sections, each carrying a contiguous range of the steps — a composition decision on the Section Container, not a Shape pick."
---

# Workflow / Process

How the product is used, step by step. Each item is one step in an ordered sequence; `step_count` is the section's item count.

The Shape pick branches on `step_count` via `rules/shape-selection/workflow-process.md`.
