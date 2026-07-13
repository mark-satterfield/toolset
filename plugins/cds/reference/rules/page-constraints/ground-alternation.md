---
kind: page-constraint
name: ground-alternation
family: landing
status: stable
applies_to: { families: [landing], containers: [] }
---

# Ground alternation

Section grounds follow a strict, position-determined alternation. The alternation index starts at **1 on the first content Section** in document order and increments by 1 for every following content Section. The Shell's persistent Sections (topbar, footer) live in the Shell, not in the Section Container, so they are excluded from the alternation index: the topbar carries the page ground via `--nav-bg` (= `surface-primary`) and the footer uses its named theme island. Every Section in the Section Container counts, including section-header heading strips.

1. Odd-indexed Sections (1, 3, 5, …): `surface-primary`.
2. Even-indexed Sections (2, 4, 6, …): `surface-secondary`.

No shape, content type, or variety choice changes the schedule, and there are **no exceptions**. A Section that must read as a distinct theme (for example a dark Final CTA) is a **named theme island** — declared on the Section Container — applied on top of its scheduled ground, never a per-shape or one-off choice.

## As a validator

This constraint assigns rather than rejects: during per-Section resolution it supplies the scheduled ground to the winning shape. A shape candidate that cannot render on its scheduled ground (a declared incompatibility) is rejected, and the rule engine tries the next candidate.
