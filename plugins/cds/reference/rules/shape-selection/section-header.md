---
kind: shape-selection-rule
name: section-header
section: section-header
page_family: landing
status: stable
signals: [position]
table:
  - { when: "position == interstitial", primary: divider-label, alternates: [heading-strip] }
  - { when: "always", primary: heading-strip, alternates: [] }
default: heading-strip
---

# Shape selection — Section Header / Eyebrow

A `lead` header (and any unset position) opens a content run as heading-strip, the left-aligned standalone heading. An `interstitial` header sits between two content runs and picks divider-label, a centered label breaking a hairline rule. The inline kicker (a short label above the heading) is heading-strip's `with-eyebrow` variant, not a separate Shape. Candidates are tried in order (primary, then alternates, then `default`) against the Page-Level Aesthetic Constraints (`reference/rules/page-constraints/`); if every candidate is rejected, the composer falls back to agent-generated layout and records that in the decisions sidecar.
