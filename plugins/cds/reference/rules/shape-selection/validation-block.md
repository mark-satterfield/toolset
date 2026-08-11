---
kind: shape-selection-rule
name: validation-block
section: validation-block
status: stable
signals: [item_count, has_metric_per_item, logos_presence]
table:
  - { when: "item_count == 1 and has_metric_per_item", primary: feature-quote, alternates: [stacked-quotes] }
  - { when: "item_count == 3 and not has_metric_per_item", primary: stacked-quotes, alternates: [] }
  - { when: "item_count >= 12 and logos_presence", primary: logo-text-pair-marquee, alternates: [quote-swiper] }
  - { when: "item_count >= 12 and not logos_presence", primary: text-pair-marquee, alternates: [stacked-quotes] }
  - { when: "item_count >= 5 and has_metric_per_item and logos_presence", primary: quote-swiper, alternates: [stacked-quotes] }
default: stacked-quotes
---

# Shape selection — Validation Block

The pick scales with the quote set: a single big-metric quote leads as a feature, a small qualitative set stacks, a mid-sized metric-and-logo set swipes one quote at a time, and a set too large to page through scrolls past as a marquee — carrying its source marks when the content supplies them and its statements alone when it does not. Candidates are tried in order (primary, then alternates, then `default`) against the Page-Level Aesthetic Constraints (`reference/rules/page-constraints/`). This table is rung 1 of the Shape-assignment waterfall; what happens when every candidate is rejected — the library search, the adapted Shape, and only then generation from scratch — is defined once, in `reference/pipeline.md`.
