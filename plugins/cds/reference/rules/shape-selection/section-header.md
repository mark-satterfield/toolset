---
kind: shape-selection-rule
name: section-header
section: section-header
page_family: landing
status: stable
signals: [position, has_pictogram]
table:
  - { when: "position == interstitial", primary: divider-label, alternates: [heading-strip] }
  - { when: "has_pictogram", primary: pictogram-headline, alternates: [heading-strip] }
  - { when: "always", primary: heading-strip, alternates: [] }
default: heading-strip
---

# Shape selection — Section Header / Eyebrow

A `lead` header (and any unset position) opens a content run as heading-strip, the left-aligned standalone heading. An `interstitial` header sits between two content runs and picks divider-label, a centered label breaking a hairline rule. A header whose content supplies a mark picks pictogram-headline, the centered column that sets the mark above the heading — the mark is why the register is centered, so a header with no mark never takes it. The inline kicker (a short label above the heading) is heading-strip's `with-eyebrow` variant, not a separate Shape. Candidates are tried in order (primary, then alternates, then `default`) against the Page-Level Aesthetic Constraints (`reference/rules/page-constraints/`). This table is rung 1 of the Shape-assignment waterfall; what happens when every candidate is rejected — the library search, the adapted Shape, and only then generation from scratch — is defined once, in `reference/pipeline.md`.
