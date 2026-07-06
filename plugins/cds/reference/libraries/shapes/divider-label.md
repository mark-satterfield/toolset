---
kind: shape
name: divider-label
family: landing
aliases: [labeled divider, section divider, hairline label]
status: stable
slots:
  - { name: label, required: true, accepts: [h2] }
variants: [rule-both-sides, rule-trailing]
self_contained: false
content_defaults: {}
---

# divider-label — Hairline divider with centered label

A hairline rule spanning the section, interrupted by a centered label; a transition marker between two content runs, with no content beneath.

## Determinations

- The rule spans the page-width section wrapper (`.u-container`) as a 1px hairline (`--border-subtle`) at the card-hairline weight (`foundations/layout.md` §11.9), with a centered H2 label breaking it at the horizontal center.
- The label and its rule sit in the centered register as one symmetric row; the gap between the label and each rule segment is `--sp-1`.
- Vertical padding uses `--section-pad-small`, matching the narrow rhythm of a section label.
- The `rule-both-sides` variant runs the hairline to the left and right of the centered label; the `rule-trailing` variant left-aligns the label with a single hairline running to its right.
- The label carries no section-level eyebrow; the standalone-heading eyebrow site is heading-strip's, per `rules/page-constraints/eyebrow-scope.md`.
