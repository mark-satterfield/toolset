---
kind: shape-selection-rule
name: final-cta
section: final-cta
family: landing
status: stable
signals: [has_newsletter_capture, has_download_upgrade_path]
table:
  - { when: "has_newsletter_capture == true", primary: cta-newsletter, alternates: [cta-panel] }
  - { when: "has_download_upgrade_path == true", primary: cta-panel, alternates: [install-buttons] }
default: cta-panel
---

# Shape selection — Final CTA

The rows key on the explicit `content_contract` booleans, not on an audience facet. The Shapes are cta-newsletter and cta-panel; darkness is not a Shape. A dark cta-panel is the `dark` theme island directive declared on the Section Container, applied on top of the scheduled ground; a light cta-panel is cta-panel on its scheduled ground with no island.

When `page_meta.buying_mode == browse` the Section Container omits final-cta entirely, so this rule never runs on browse-mode pages. Candidates are tried in order (primary, then alternates, then `default`) against the Page-Level Aesthetic Constraints (`reference/rules/page-constraints/`); if every candidate is rejected, the composer falls back to agent-generated layout and records that in the decisions sidecar.
