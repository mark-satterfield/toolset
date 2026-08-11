---
kind: page-constraint
name: ground-alternation
status: stable
applies_to: { page_families: [landing], pages: [] }
check: |
  For every content Section of the Page, indexed from 1 in document order: an
  odd-indexed Section renders on surface-primary and an even-indexed Section on
  surface-secondary. Shell Sections are excluded from the index. A candidate
  shape with a declared incompatibility with its scheduled ground is rejected.
  A named theme island declared on the Page applies on top of the scheduled
  ground and does not alter the index.
---

# Ground alternation

Section grounds follow a strict, position-determined alternation. The alternation index starts at **1 on the first content Section** in document order and increments by 1 for every following content Section. The Shell's Sections (`top-nav`, `site-footer`) live in the Shell, not in the Page, so they are excluded from the alternation index: the top-nav carries the page ground via `--nav-bg` (= `surface-primary`) and the site-footer uses its named theme island. Every Section of the Page counts, including section-header heading strips.

1. Odd-indexed Sections (1, 3, 5, …): `surface-primary`.
2. Even-indexed Sections (2, 4, 6, …): `surface-secondary`.

No shape, content type, or variety choice changes the schedule, and there are **no exceptions**. A Section that must read as a distinct theme (for example a dark Final CTA) is a **named theme island** — declared on the Page — applied on top of its scheduled ground, never a per-shape or one-off choice.

## As a validator

This constraint assigns rather than rejects: during per-Section resolution it supplies the scheduled ground to the winning shape. A shape candidate that cannot render on its scheduled ground (a declared incompatibility) is rejected, and the rule engine tries the next candidate.
