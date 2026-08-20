# Source-of-truth map

The SAD is the upstream source of truth for two downstream document families: the **Technical Requirements Document (TRD)** and the **Specs** (per-feature or per-component specifications). This file defines the feed contract — exactly which sections are exported, what each export carries, and who consumes it. `arc42-extract` implements this contract; nothing else in the toolkit reads sections on behalf of downstream authors.

## The exported sections

Only four arc42 sections are part of the feed. Sections 1, 3, 5, 6, 7, 10, 11, and 12 are *not* exported as source — they are read for orientation, but they do not flow downstream as binding inputs.

| Section | Export name | What it carries | Primary consumer |
|---|---|---|---|
| 2 — Architecture Constraints | `constraints` | Mandated tech, regulatory/compliance rules, org conventions, platform and licensing limits | **TRD author** (sets the boundary conditions the TRD cannot violate) and **spec authors** (per-feature constraint inheritance) |
| 4 — Solution Strategy | `solution-strategy` | Fundamental technology choices, decomposition style, how top quality goals are met | **TRD author** (the high-level approach the TRD elaborates into requirements) |
| 8 — Crosscutting Concepts | `crosscutting-concepts` | System-wide concepts: domain model, persistence, security, error handling, logging, i18n, transactions, applied patterns | **Spec authors** (each spec inherits these instead of re-deriving them) |

## Direction of the feed

```
                        SAD (arc42)
                   §2  §4  §8  (SOURCE sections only)
                          │
                  arc42-extract
                          │
            ┌─────────────┴──────────────┐
            ▼                             ▼
       TRD author                   Spec authors
   (constraints,                (crosscutting-concepts,
    solution-strategy,           constraints,
    decisions-index)             decisions-index)
```

The feed is **one-directional and read-only**. Downstream authors never write back into the SAD. If a spec or TRD reveals that a constraint, strategy, concept, or decision is wrong or missing, that change is made *in the SAD first* (via `arc42-maintain`), and only then re-extracted. This keeps the SAD as the single upstream source and prevents downstream documents from forking the architecture.

## Contract guarantees

- **Stable export names.** `constraints`, `solution-strategy`, `crosscutting-concepts`, and `decisions-index` are the contract keys downstream tooling depends on. They do not change with the SAD's file layout (single-file vs. one-file-per-section).
- **Current-state payload.** Because the SAD is a living document (see `living-document-rules.md`), every extraction returns present truth. There is no historical payload; rationale and rejected alternatives are stated inline with the decision in §2, §4 or §8.
- **Source-only.** `arc42-extract` reads sections 2, 4, 8, and 9 and refuses to export any other section as source, even if asked — non-source sections are orientation, not feed.
