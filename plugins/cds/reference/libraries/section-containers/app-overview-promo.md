---
kind: section-container
name: app-overview-promo
family: app
aliases: [product overview screen, feature overview, tier overview, promo dashboard]
status: stable
default_shell: rail-main
sections:
  - { section: page-header, required: true, notes: "title variant with a period picker in the right cluster" }
  - { section: hero-promo, required: true }
  - { section: kpi-summary, required: true, notes: "tile size variant; typical content: 2 stat tiles" }
  - { section: chart-panels, required: true, notes: "typical content: 2 chart cards side by side, each with a legend" }
  - { section: info-note, required: false }
constraints: []
register:
  motion_register: application-shell
---

# App overview with promo

A product-tier or feature-specific overview screen that combines a promotional card (CTA to onboard or upgrade) with at-a-glance metrics: page heading with a period picker, a full-width hero promo card, a stat-tile pair, a chart-card pair, and an info-note footer strip. Fills the main pane of an app Shell (default rail-main).

## Determinations

- The stat-tile pair spans the full main width split into two equal columns (`1fr 1fr`, `--sp-1-5` gap); the chart pair below uses the **same** two-column track so the tile and chart columns align vertically.
