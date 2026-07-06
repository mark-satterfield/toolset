---
kind: section
name: cross-promo
id: T14
family: landing
aliases: [cross-promo, promo banner, product plug, inline promotion]
status: stable
mode: dynamic
content_contract:
  format: "narrow-banner | event-register-card"
theme: scheduled
composition_notes:
  - "When format == event-register-card (an event/register card with thumbnail), T14 may embed inside T10 Trust Detail instead of rendering as a standalone Section; the embedding is a composition choice recorded in the decisions sidecar, not a shape pick"
---

# T14 — Cross-Promo

Surfaces another product or feature inline. The shape pick branches on `format` — narrow banner vs. event/register card with thumbnail — via `rules/shape-selection/t14.md`. The event/register format may alternatively embed inside T10 per the composition notes.
