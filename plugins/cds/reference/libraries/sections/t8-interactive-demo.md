---
kind: section
name: interactive-demo
id: T8
family: landing
aliases: [demo, interactive demo, try it, product preview, see it in action]
status: stable
mode: dynamic
content_contract:
  demo_format: "prompt-artifact | multi-surface"
theme: scheduled
composition_notes: []
---

# T8 — Interactive Demo

Lets the visitor see or try the product output. The demo comes in one of two formats: `prompt-artifact` (a prompt producing an artifact) or `multi-surface` (one screenshot per product surface).

The shape pick branches on `demo_format` via `rules/shape-selection/t8.md`. No other content signal branches T8.
