---
kind: page
name: app-overview-promo
page_family: app
aliases: [product overview screen, feature overview, tier overview, promo dashboard]
status: stable
sections:
  - { section: page-header, required: true, notes: "title variant with a period picker in the right cluster" }
  - { section: hero-promo, required: true }
  - { section: kpi-summary, required: true, notes: "tile size variant; typical content: 2 stat tiles" }
  - { section: chart-panels, required: true, notes: "typical content: 2 chart cards side by side, each with a legend" }
  - { section: info-note, required: false }
constraints: []
---

# App overview with promo

A product-tier or feature-specific overview screen that combines a promotional card (CTA to onboard or upgrade) with at-a-glance metrics: page heading with a period picker, a full-width hero promo card, a stat-tile pair, a chart-card pair, and an info-note footer strip. Nests in the vacant space of the user's Shell.

## Determinations

- The stat-tile pair spans the full Page width split into two equal columns (`1fr 1fr`, `--sp-1-5` gap); the chart pair below uses the **same** two-column track so the tile and chart columns align vertically.
