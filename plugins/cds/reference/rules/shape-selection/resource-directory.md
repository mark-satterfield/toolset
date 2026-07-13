---
kind: shape-selection-rule
name: resource-directory
section: resource-directory
family: landing
status: stable
signals: [has_source_tag_per_item]
table:
  - { when: "has_source_tag_per_item == true", primary: resource-grid, alternates: [tagged-card-grid] }
default: resource-grid
---

# Shape selection — Resource Directory

Items carrying source-type tags resolve to resource-grid, with tagged-card-grid as the alternate. Candidates are tried in order (primary, then alternates, then `default`) against the Page-Level Aesthetic Constraints (`reference/rules/page-constraints/`); if every candidate is rejected, the composer falls back to agent-generated layout and records that in the decisions sidecar.
