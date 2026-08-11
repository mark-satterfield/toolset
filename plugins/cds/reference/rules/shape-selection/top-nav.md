---
kind: shape-selection-rule
name: top-nav
section: top-nav
status: stable
signals: [carries_mark, nav_item_count, conversion_action_count]
table:
  - { when: "carries_mark && nav_item_count > 0 && conversion_action_count > 0", primary: bar-mark-nav-cta, alternates: [] }
  - { when: "carries_mark && nav_item_count > 0 && conversion_action_count == 0", primary: bar-mark-nav, alternates: [] }
  - { when: "carries_mark && nav_item_count == 0 && conversion_action_count > 0", primary: bar-mark-cta, alternates: [] }
  - { when: "carries_mark && nav_item_count == 0 && conversion_action_count == 0", primary: bar-mark-only, alternates: [] }
  - { when: "!carries_mark && nav_item_count > 0 && conversion_action_count > 0", primary: bar-nav-cta, alternates: [] }
  - { when: "!carries_mark && nav_item_count > 0 && conversion_action_count == 0", primary: bar-nav-only, alternates: [] }
default: bar-mark-only
---

# Shape selection — Top nav

The bar's arrangement is determined by what the frame actually offers: whether it carries the mark, how many top-level navigational items it exposes, and how many conversion actions it offers. Every combination the model admits has its own named Shape, so the bar is never rendered with an arrangement that leaves a position open.

A frame that offers a conversion action and no mark and no navigational set is not a navigation bar; it falls to `default` and renders the mark-only arrangement, and the conversion action belongs in the content region.

Candidates are tried in order (primary, then alternates, then `default`) against the Page-Level Aesthetic Constraints (`reference/rules/page-constraints/`). This table is rung 1 of the Shape-assignment waterfall; what happens when every candidate is rejected — the library search, the adapted Shape, and only then generation from scratch — is defined once, in `reference/pipeline.md`.
