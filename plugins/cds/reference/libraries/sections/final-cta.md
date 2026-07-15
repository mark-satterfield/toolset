---
kind: section
name: final-cta
page_family: landing
aliases: [final CTA, closing CTA, bottom call to action, closing conversion section]
status: stable
content_contract:
  has_newsletter_capture: bool
  has_download_upgrade_path: bool
theme: scheduled
composition_notes: []
---

# Final CTA

Closing conversion attempt — the last content Section of a landing Page. The Shape pick branches on two final-cta-only booleans via `rules/shape-selection/final-cta.md`: `has_newsletter_capture` (the closing form captures email for a newsletter) and `has_download_upgrade_path` (the closing path is a platform download + paid upgrade).

On browse-mode pages (`page_meta.buying_mode == browse`) final-cta is omitted entirely; the Page declares that omission. A dark rendering is the named `dark` theme island declared on the Page, applied on top of the scheduled ground — it is not a Shape or a property of this Section.
