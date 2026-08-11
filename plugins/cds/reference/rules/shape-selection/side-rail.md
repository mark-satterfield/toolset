---
kind: shape-selection-rule
name: side-rail
section: side-rail
status: stable
signals: [carries_mark, carries_account]
table:
  - { when: "carries_mark && carries_account", primary: rail-mark-nav-account, alternates: [] }
  - { when: "carries_mark && !carries_account", primary: rail-mark-nav, alternates: [] }
  - { when: "!carries_mark && carries_account", primary: rail-nav-account, alternates: [] }
  - { when: "!carries_mark && !carries_account", primary: rail-nav-only, alternates: [] }
default: rail-nav-only
---

# Shape selection — Side rail

The rail always carries a menu; what varies is whether the mark sits at its block-start edge and whether an account row anchors its block-end edge. Both signals are frame-level facts — a frame whose mark lives in a pinned block-start Section reports `carries_mark: false` here, so the mark is never rendered twice.

Every combination has its own named Shape, so the rail is never rendered with an arrangement that leaves a position open.

Candidates are tried in order (primary, then alternates, then `default`) against the Page-Level Aesthetic Constraints (`reference/rules/page-constraints/`). This table is rung 1 of the Shape-assignment waterfall; what happens when every candidate is rejected — the library search, the adapted Shape, and only then generation from scratch — is defined once, in `reference/pipeline.md`.
