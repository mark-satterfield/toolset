---
kind: shape-selection-rule
name: path-fork
section: path-fork
page_family: landing
status: stable
signals: [item_count, emphasis]
table:
  - { when: "item_count == 2 and emphasis == contrast", primary: comparison-fork, alternates: [two-path-fork] }
  - { when: "item_count == 2 and emphasis == sequential", primary: split-banner-fork, alternates: [two-path-fork] }
  - { when: "item_count == 2", primary: two-path-fork, alternates: [] }
default: two-path-fork
---

# Shape selection — Path Fork

`item_count` is 2 by definition for this section type; `emphasis` selects among three fork layouts. An attribute-by-attribute `contrast` picks comparison-fork; a `sequential` reading of one path after another picks split-banner-fork; `balanced` peers (and any unset emphasis) fall to the two-path-fork default. Candidates are tried in order (primary, then alternates, then `default`) against the Page-Level Aesthetic Constraints (`reference/rules/page-constraints/`); if every candidate is rejected, the composer falls back to agent-generated layout and records that in the decisions sidecar.
