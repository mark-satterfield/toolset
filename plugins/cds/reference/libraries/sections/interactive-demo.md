---
kind: section
name: interactive-demo
aliases: [demo, interactive demo, try it, product preview, see it in action]
status: stable
content_contract:
  demo_format: "prompt-artifact | multi-surface"
theme: scheduled
composition_notes: []
---

# Interactive Demo

Lets the visitor see or try the product output. The demo comes in one of two formats: `prompt-artifact` (a prompt producing an artifact) or `multi-surface` (one screenshot per product surface).

The Shape pick branches on `demo_format` via `rules/shape-selection/interactive-demo.md`. No other content signal branches interactive-demo.
