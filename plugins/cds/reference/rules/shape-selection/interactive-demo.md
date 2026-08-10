---
kind: shape-selection-rule
name: interactive-demo
section: interactive-demo
page_family: landing
status: stable
signals: [demo_format]
table:
  - { when: "demo_format == prompt-artifact", primary: prompt-artifact, alternates: [tabbed-panels] }
  - { when: "demo_format == multi-surface", primary: tabbed-panels, alternates: [alternating-rows] }
default: tabbed-panels
---

# Shape selection — Interactive Demo

The pick follows the demo's format: a prompt-to-artifact demo renders as the prompt-artifact shape; a multi-surface demo (one screenshot per surface) tabs the surfaces. Candidates are tried in order (primary, then alternates, then `default`) against the Page-Level Aesthetic Constraints (`reference/rules/page-constraints/`). This table is rung 1 of the Shape-assignment waterfall; what happens when every candidate is rejected — the library search, the adapted Shape, and only then generation from scratch — is defined once, in `reference/pipeline.md`.
