---
kind: shape-selection-rule
name: hero
section: hero
status: stable
signals: [visual_type]
table:
  - { when: "visual_type == video", primary: centered-stack, alternates: [sub-hero-split] }
  - { when: "visual_type == screenshot", primary: split-text-media, alternates: [centered-stack] }
  - { when: "visual_type == code-or-install-snippet", primary: centered-affordance, alternates: [centered-stack] }
  - { when: "visual_type == chat-or-live-affordance", primary: centered-affordance, alternates: [] }
default: centered-stack
---

# Shape selection — Hero

The hero's pick is driven entirely by the visual the content supplies. Candidates are tried in order (primary, then alternates, then `default`) against the Page-Level Aesthetic Constraints (`reference/rules/page-constraints/`). This table is rung 1 of the Shape-assignment waterfall; what happens when every candidate is rejected — the library search, the adapted Shape, and only then generation from scratch — is defined once, in `reference/pipeline.md`.
