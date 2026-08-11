---
kind: section
name: cross-promo
aliases: [cross-promo, promo banner, product plug, inline promotion]
status: stable
content_contract:
  format: "narrow-banner | event-register-card"
theme: scheduled
composition_notes:
  - "When format == event-register-card (an event/register card with thumbnail), cross-promo may embed inside the trust-detail Section instead of rendering as a standalone Section; the embedding is a composition choice recorded in the decisions sidecar, not a Shape pick"
---

# Cross-Promo

Surfaces another product or feature inline. The Shape pick branches on `format` — narrow banner vs. event/register card with thumbnail — via `rules/shape-selection/cross-promo.md`. The event/register format may alternatively embed inside trust-detail per the composition notes.
