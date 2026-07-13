---
kind: section
name: activity-card
family: app
aliases: [usage card, token volume card, activity summary card]
status: stable
mode: deterministic
content_contract:
  action: "present | absent"
theme: default
composition_notes: []
---

# Activity card

A single full-width card summarizing recent volume or activity: a small label, a sparkline visualization of the recent series, and an optional right-side action. Spans the full width of the main pane; card inner padding is `--sp-2`.
