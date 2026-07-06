---
kind: section
name: workflow-process
id: T5
family: landing
aliases: [how it works, steps, process, workflow, getting started steps]
status: stable
mode: dynamic
content_contract:
  step_count: int
theme: scheduled
composition_notes:
  - "A workflow whose step_count does not fit one shape cleanly may split into two consecutive T5 Sections, each carrying a contiguous range of the steps — a composition decision on the Section Container, not a shape pick."
---

# T5 — Workflow / Process

How the product is used, step by step. Each item is one step in an ordered sequence; `step_count` is the section's item count.

The shape pick branches on `step_count` via `rules/shape-selection/t5.md`.
