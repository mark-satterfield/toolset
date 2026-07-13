---
kind: shape-selection-rule
name: trust-detail
section: trust-detail
family: landing
status: stable
signals: [item_count, has_visual_per_item]
table:
  - { when: "item_count >= 2 and has_visual_per_item == true", primary: pictogram-subcards, alternates: [card-grid] }
default: pictogram-subcards
---

# Shape selection — Trust Detail

The pick keys on the composite signal: multiple controls (`item_count >= 2`) with a visual per control. Candidates are tried in order (primary, then alternates, then `default`) against the Page-Level Aesthetic Constraints (`reference/rules/page-constraints/`); if every candidate is rejected, the composer falls back to agent-generated layout and records that in the decisions sidecar.
