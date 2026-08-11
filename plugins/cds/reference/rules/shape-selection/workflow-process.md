---
kind: shape-selection-rule
name: workflow-process
section: workflow-process
status: stable
signals: [step_count]
table:
  - { when: "step_count == 3", primary: numbered-steps, alternates: [] }
  - { when: "step_count != 3", primary: tabbed-panels, alternates: [numbered-steps] }
default: numbered-steps
---

# Shape selection — Workflow / Process

Three steps is the canonical horizontal numbered-steps read; any other count tabs the steps instead, with numbered-steps in its vertical variant as the alternate (a vertical numbered list reads at any count). A step set that fits neither candidate may instead split into two consecutive workflow-process Sections — that is a composition note on the workflow-process Section, not a Shape in this table. Candidates are tried in order (primary, then alternates, then `default`) against the Page-Level Aesthetic Constraints (`reference/rules/page-constraints/`). This table is rung 1 of the Shape-assignment waterfall; what happens when every candidate is rejected — the library search, the adapted Shape, and only then generation from scratch — is defined once, in `reference/pipeline.md`.
