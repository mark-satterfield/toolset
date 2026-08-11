---
kind: section
name: final-cta
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

On browse-mode pages (`page_meta.buying_mode == browse`) final-cta is omitted entirely; the Page declares that omission.

## Ground

final-cta is the last content Section, so it meets the Shell's footer. It takes the footer's ground: the Section paints `--footer-bg` and its ink resolves through the same theme island the footer wears. The closing conversion moment and the footer read as one terminal block rather than two competing dark bands, and neither the Page nor the Shell names a colour to achieve it — both consume the same role.

The two are separated by a single hairline in `--border-strong` on the Section's bottom edge — the light border role, which resolves to a high-tone neutral on every dark island. A seam painted in a dark border role disappears into the ground and reads as one undifferentiated mass; the light hairline marks where the conversion moment ends and the site frame begins.

This is a property of the Section, not a Shape and not a per-Page choice: any Shape final-cta receives renders on the footer ground with the hairline beneath it.
