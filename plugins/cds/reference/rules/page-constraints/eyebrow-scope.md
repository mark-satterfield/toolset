---
kind: page-constraint
name: eyebrow-scope
family: landing
aliases: [eyebrow rule, kicker rule, section label rule]
status: stable
applies_to: { families: [landing], containers: [] }
check: |
  Reject a shape candidate whose rendered output places a section-level
  eyebrow anywhere except the two authorized positions: the optional eyebrow
  slot in heading-strip (T18) and the per-card tag/pill inside
  tagged-card-grid and resource-grid. Outside the landing family an eyebrow
  is valid only where a Section declares it as a slot (E1 subjects line).
---

# Eyebrow scope

Section-level eyebrows are **deny-by-default** on landing pages. A section-level eyebrow — a short label line above a Section's heading — is authorized in exactly two places:

1. The optional eyebrow slot in `heading-strip` (the T18 standalone heading strip).
2. The per-card tag/pill inside `tagged-card-grid` and `resource-grid`.

No other shape carries a section-level eyebrow. A hero (`centered-stack`, `split-text-media`, `centered-affordance`, `sub-hero-split`), a card-grid heading (`card-grid`), a workflow (`numbered-steps`), a CTA panel (`banner-strip`, `cta-panel`, `cta-newsletter`), and every other shape begin directly with the heading — no kicker above it. A label that genuinely must precede a content unit is modeled as its own T18 heading-strip Section, never as decoration on an adjacent Section's heading.

The eyebrow Component itself is one definition, scoped by family: outside the landing family it appears only where a Section declares it as a slot (the editorial article-header's subjects line, E1).
