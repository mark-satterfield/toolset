---
kind: shape-selection-rule
name: final-cta
section: final-cta
page_family: landing
status: stable
signals: [has_newsletter_capture, has_download_upgrade_path]
table:
  - { when: "has_newsletter_capture == true", primary: cta-newsletter, alternates: [cta-panel] }
  - { when: "has_download_upgrade_path == true", primary: cta-panel, alternates: [install-buttons] }
default: cta-panel
---

# Shape selection — Final CTA

The rows key on the explicit `content_contract` booleans, not on an audience facet. The Shapes are cta-newsletter and cta-panel; the ground is not a Shape. Whichever Shape wins renders on the footer ground with the light hairline seam beneath it, per `libraries/sections/final-cta.md`.

When `page_meta.buying_mode == browse` the Page omits final-cta entirely, so this rule never runs on browse-mode pages. Candidates are tried in order (primary, then alternates, then `default`) against the Page-Level Aesthetic Constraints (`reference/rules/page-constraints/`). This table is rung 1 of the Shape-assignment waterfall; what happens when every candidate is rejected — the library search, the adapted Shape, and only then generation from scratch — is defined once, in `reference/pipeline.md`.
