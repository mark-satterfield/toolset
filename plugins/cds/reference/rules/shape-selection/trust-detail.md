---
kind: shape-selection-rule
name: trust-detail
section: trust-detail
status: stable
signals: [item_count, has_visual_per_item]
table:
  - { when: "item_count >= 2 and has_visual_per_item == true", primary: pictogram-subcards, alternates: [card-grid] }
  - { when: "item_count >= 3 and has_visual_per_item == false", primary: labeled-detail-rows, alternates: [card-grid] }
default: pictogram-subcards
---

# Shape selection — Trust Detail

The pick keys on the composite signal: multiple controls (`item_count >= 2`) with a visual per control resolve to pictogram-subcards. Three or more controls with no visual are a specification rather than a showcase, and resolve to labeled-detail-rows — the rule-separated run that lets a reader scan the titles as one column. Candidates are tried in order (primary, then alternates, then `default`) against the Page-Level Aesthetic Constraints (`reference/rules/page-constraints/`). This table is rung 1 of the Shape-assignment waterfall; what happens when every candidate is rejected — the library search, the adapted Shape, and only then generation from scratch — is defined once, in `reference/pipeline.md`.
