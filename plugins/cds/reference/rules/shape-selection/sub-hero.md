---
kind: shape-selection-rule
name: sub-hero
section: sub-hero
family: landing
status: stable
signals: [visual_type]
table:
  - { when: "visual_type == video", primary: sub-hero-split, alternates: [centered-stack] }
default: sub-hero-split
---

# Shape selection — Sub-Hero

The composition signal is video + text + CTA: a video visual resolves to sub-hero-split with centered-stack as the alternate. Candidates are tried in order (primary, then alternates, then `default`) against the Page-Level Aesthetic Constraints (`reference/rules/page-constraints/`); if every candidate is rejected, the composer falls back to agent-generated layout and records that in the decisions sidecar.
