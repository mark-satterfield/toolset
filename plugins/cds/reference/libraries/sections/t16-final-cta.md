---
kind: section
name: final-cta
id: T16
family: landing
aliases: [final CTA, closing CTA, bottom call to action, closing conversion section]
status: stable
mode: dynamic
content_contract:
  has_newsletter_capture: bool
  has_download_upgrade_path: bool
theme: scheduled
composition_notes: []
---

# T16 — Final CTA

Closing conversion attempt — the last content Section of a landing Section Container. The shape pick branches on two T16-only booleans via `rules/shape-selection/t16.md`: `has_newsletter_capture` (the closing form captures email for a newsletter) and `has_download_upgrade_path` (the closing path is a platform download + paid upgrade).

On browse-mode pages (`page_meta.buying_mode == browse`) T16 is omitted entirely; the Section Container declares that omission. A dark rendering is the named `dark` theme island declared on the Section Container, applied on top of the scheduled ground — it is not a shape or a property of this Section.
