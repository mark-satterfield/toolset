---
kind: shape-selection-rule
name: cross-promo
section: cross-promo
family: landing
status: stable
signals: [format]
table:
  - { when: "format == narrow-banner", primary: banner-strip, alternates: [] }
  - { when: "format == event-register-card", primary: banner-strip, alternates: [] }
default: banner-strip
---

# Shape selection — Cross-Promo

Both formats resolve to banner-strip as a standalone Section. An event/register card with thumbnail may instead embed inside trust-detail — a composition choice declared in the cross-promo Section's `composition_notes`, not a Shape this rule can pick. Candidates are tried in order (primary, then alternates, then `default`) against the Page-Level Aesthetic Constraints (`reference/rules/page-constraints/`); if every candidate is rejected, the composer falls back to agent-generated layout and records that in the decisions sidecar.
