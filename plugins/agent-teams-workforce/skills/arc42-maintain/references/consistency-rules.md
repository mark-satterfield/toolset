# Consistency rules — cross-section invariants

These invariants must hold **after every maintenance edit** to the arc42 SAD.
They are what keeps the document internally coherent and keeps the C4 and UML
views in sync with the structural decisions that drive them. Each rule states
the invariant, why it exists, and how to detect a violation.

The structural source sections are **2 Constraints**, **4 Solution Strategy**,
**8 Crosscutting Concepts**, and **9 Architecture Decisions**. The *view*
sections — **3 Context** (C4 System Context), **5 Building Block** (C4
Container/Component), **6 Runtime** (UML sequence/activity), **7 Deployment**
(C4 Deployment) — render those decisions and must follow them.

## INV-2 — Every pattern-bearing decision is reflected in section 8

**Invariant.** If a section-9 decision establishes a project-wide pattern
(authentication model, authorization model, retry/backoff policy, idempotency
strategy, logging/tracing contract, error taxonomy, persistence approach,
validation strategy), section 8 Crosscutting Concepts describes that pattern as
the now-current standard.

**Why.** Crosscutting concerns are applied in many building blocks; section 8
is the one place they are defined so each block does not redefine them. A
pattern adopted by decision but missing from section 8 will be implemented
inconsistently.

**Violation signal.** A decision that says "all services will use structured
JSON logging with a correlation id" while section 8's logging concept still
describes the old free-text approach (or has no logging concept).

**Repair.** Update or add the section-8 concept so it matches the decision.

## INV-3 — Every changed section-2 constraint is propagated forward

**Invariant.** When a constraint in section 2 changes, every section whose
content was valid only under the *old* constraint is re-examined and brought
into line in the same edit. Constraints bound the solution space; sections 4,
8, 9 (and the 5/6/7 views) live inside those bounds.

**Why.** A constraint change can silently invalidate a strategy, a pattern, a
decision, or a deployment topology. Leaving the dependent content unexamined
produces a SAD that documents a solution its own constraints forbid.

**Violation signal.** A new constraint (e.g. EU-only data residency, a banned
library, a latency budget, a single-region mandate) that contradicts an
existing section-4 statement, section-8 concept, section-9 outcome, or
section-7 region map.

**Repair.** Tighten or relax the dependent content to satisfy the new
constraint. If a decision must change as a result, rewrite the decision in §4
as current state.

## INV-4 — No orphaned cross-references

**Invariant.** Every in-document pointer resolves. References by section number
or by named building block must point at content that still exists under that
identifier.

**Why.** Downstream artifacts (TRD, Specs) and human readers navigate the SAD by
these references. A dangling pointer is an inconsistency and a broken trail into
and out of the document.

**Violation signal.** A reference to a section that was renumbered or removed; a
mention of a building block that section 5 no longer contains; a "see section X"
that no longer covers the cited topic.

**Repair.** Update the reference to the new id/target, or remove it if the
target was intentionally deleted. Never silently leave it.

## INV-6 — Views (3/5/6/7) match the live structural decisions

**Invariant.** The C4 and UML view sections render only the *current* structure
and behaviour. The System Context (3), Building Block View (5, C4
Container/Component), Runtime View (6, UML sequence/activity), and Deployment
View (7, C4 Deployment) must depict the structure implied by the live decisions
in 4/8/9 and the constraints in 2.

**Why.** A view is a projection of the decisions. If the decision changed but
the diagram did not, the diagram lies — and diagrams are what most readers trust
first.

**Violation signal.** A container in the section-5 C4 diagram that a superseded
decision introduced; a section-6 sequence that calls a removed service
synchronously after a decision moved it to async; a section-7 node in a region
the new residency constraint forbids.

**Repair.** Redraw the affected view. Diagram *sources* (which may use mermaid)
live in the view sections and in `../arc42/references/`; this skill's own
reference files keep to plain sketches.

## INV-7 — The SAD states only current state

**Invariant.** No section contains changelog, history, or "what changed"
narrative. The document describes the system as it is now. No history is carried
anywhere: this project keeps no ADRs, no decision log, and no section 9.

**Why.** A living architecture document is read for *what is true*, not for an
archaeology of what used to be true. Mixed history bloats sections and creates
contradictions (current prose vs. retained old prose).

**Violation signal.** Phrases like "previously", "we used to", "as of the last
revision", "changed from X to Y" in any section body.

**Repair.** Delete the historical prose; keep only the current statement. If the
*reason* for the current state matters, state it inline as the decision's driver
in 2/4/8 — never as narrative about what changed.

## Post-edit checklist

Run all seven before declaring the maintenance pass done:

- [ ] INV-1 every accepted decision summarized in section 4
- [ ] INV-2 every pattern-bearing decision reflected in section 8
- [ ] INV-3 every changed constraint propagated into 4/8/9 and 5/6/7
- [ ] INV-4 no orphaned references anywhere
- [ ] INV-5 decision statuses single-valued and current
- [ ] INV-6 views (3/5/6/7) redrawn to match live decisions
- [ ] INV-7 no changelog/history prose; current-state only
