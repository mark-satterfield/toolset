---
kind: shape-selection-rule
name: news-updates
section: news-updates
family: landing
status: stable
signals: [item_count, has_emphasis_item]
table:
  - { when: "has_emphasis_item == true", primary: lead-plus-carousel, alternates: [card-carousel, card-grid] }
  - { when: "item_count == 3", primary: card-grid, alternates: [card-carousel] }
  - { when: "item_count >= 4", primary: card-carousel, alternates: [lead-plus-carousel] }
default: card-grid
---

# Shape selection — News / Updates

Rows are ordered most-specific first: an emphasis item (one featured leading secondary cards) takes precedence over the count thresholds. In the emphasis row, the `card-grid` alternate is its 3-card strip variant. Candidates are tried in order (primary, then alternates, then `default`) against the Page-Level Aesthetic Constraints (`reference/rules/page-constraints/`); if every candidate is rejected, the composer falls back to agent-generated layout and records that in the decisions sidecar.
