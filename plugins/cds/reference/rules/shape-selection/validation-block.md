---
kind: shape-selection-rule
name: validation-block
section: validation-block
page_family: landing
status: stable
signals: [item_count, has_metric_per_item, logos_presence]
table:
  - { when: "item_count == 1 and has_metric_per_item", primary: feature-quote, alternates: [stacked-quotes] }
  - { when: "item_count == 3 and not has_metric_per_item", primary: stacked-quotes, alternates: [] }
  - { when: "item_count >= 5 and has_metric_per_item and logos_presence", primary: quote-swiper, alternates: [stacked-quotes] }
default: stacked-quotes
---

# Shape selection — Validation Block

The pick scales with the quote set: a single big-metric quote leads as a feature, a small qualitative set stacks, and a large metric-and-logo set swipes. Candidates are tried in order (primary, then alternates, then `default`) against the Page-Level Aesthetic Constraints (`reference/rules/page-constraints/`); if every candidate is rejected, the composer falls back to agent-generated layout and records that in the decisions sidecar.
