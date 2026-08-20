# Update playbook — locate → edit → reconcile

The procedure for applying a current-state change to an existing arc42 Software
Architecture Document (SAD) without breaking its internal consistency or its
downstream feed into the TRD and Specs.

## The arc42 section model (reference)

arc42 fixes twelve sections. The four this skill treats as *structural source*
sections — the ones whose edits ripple — are highlighted:

| # | Section | Holds |
|---|---------|-------|
| 1 | Introduction and Goals | Top quality goals, stakeholders, requirements overview |
| **2** | **Constraints** | **Technical, organizational, and convention constraints that bound the solution** |
| 3 | Context and Scope | Business context and technical context (the C4 System Context) |
| **4** | **Solution Strategy** | **The fundamental decisions and the executive summary of how goals are met** |
| 5 | Building Block View | Static decomposition (C4 Container/Component levels) |
| 6 | Runtime View | Key scenarios (UML sequence / activity behaviour) |
| 7 | Deployment View | Infrastructure mapping (C4 Deployment) |
| **8** | **Crosscutting Concepts** | **Project-wide patterns: domain model, security, persistence, logging, error handling** |
| 10 | Quality Requirements | Quality tree and scenarios |
| 11 | Risks and Technical Debt | Known risks and accepted debt |
| 12 | Glossary | Domain and technical terms |

A maintenance edit usually starts in one of 2/4/8/9 and then reconciles the
others (and often 3/5/6/7, which *render* the structural decisions as C4 and UML
views).

## Phase 1 — Locate the primary section

Classify the change before touching the document. The section it primarily
belongs in determines the reconciliation that follows.

| The change is… | Primary section |
|----------------|-----------------|
| A new or altered external mandate (regulation, mandated tech, org rule, team-topology rule, budget/runtime limit) | **2 Constraints** |
| A fundamental "how we will build it" choice that summarizes direction | **4 Solution Strategy** |
| A new or revised project-wide pattern (auth model, retry policy, logging contract, persistence approach, error taxonomy) | **8 Crosscutting Concepts** |
| A specific, rationale-bearing choice with consequences | **4 Solution Strategy** (stated as current state, with its driver) |

Tie-breakers:

- **Section 4 is the decision record.** There is no section 9 and no ADR. A
  decision's driver, chosen option, rejected alternatives and consequences are
  stated inline in §4 as current state.
- A pattern introduced *by* a decision lives in **8**, but the decision to adopt
  it is recorded in **9**. Both get touched; 9 is primary.
- A constraint is never "decided" in the arc42 sense — it is imposed. If you
  find yourself writing rationale and alternatives, it belongs in 9, not 2.

## Phase 2 — Edit the primary section

Apply the change so the section reads as the **current state**.

- **Replace, do not annotate.** Delete the stale sentence; write the true one.
  Do not leave "previously we used X" prose. A superseded decision is simply
  overwritten by the new one; nothing records that it ever existed.
- **Stay within the section's arc42 intent.** Section 2 enumerates constraints;
  it does not argue them. Section 4 summarizes; it does not enumerate every
  component — though a §4 decision does state its driver, rejected alternatives
  and consequences inline. Section 8
  describes a concept as a standing rule, not as a one-off.
- **Preserve identifiers.** Keep `D-` decision ids stable, because downstream
  artifacts cite them. If a decision is replaced, overwrite its row with the new
  choice; do not reuse a retired id for an unrelated decision.

## Phase 3 — Reconcile dependent sections

Walk `consistency-rules.md` and repair every section the primary edit affects.
The common ripples:

- Edited **4 (new decision)** → if it introduces a pattern, update **8**; if it changes the static structure,
  update the **5** Building Block View (C4 Container/Component) and any **6**
  Runtime sequence that exercised the old structure; if it moves a deployment
  node, update **7**.
- Edited **4 (direction change)** → update **5/6/7** views that drew the old
  direction.
- Edited **8 (pattern change)** → update every view in **5/6/7** that rendered
  the old pattern, and confirm a decision in **9** authorizes the pattern.
- Edited **2 (constraint change)** → re-examine **4/8/9** for content that was
  valid only under the old constraint; tighten or relax as the new constraint
  requires.

Then produce the **downstream reconciliation flags** from
`source-section-impact.md`. The SAD edit is not complete until those flags are
emitted.

## Non-mermaid flow sketch

(Diagram source files in `../arc42/references/` may use mermaid fences; this
playbook keeps to a plain sketch so it states the loop without a renderer.)

```text
            classify change
                  |
                  v
        +---------------------+
        |  LOCATE primary     |   2 Constraints / 4 Strategy /
        |  section (2/4/8/9)  |   8 Concepts / 9 Decision
        +----------+----------+
                   |
                   v
        +---------------------+
        |  EDIT primary as    |   replace stale prose;
        |  CURRENT STATE      |   not changelog narrative
        +----------+----------+
                   |
                   v
        +---------------------+   9 -> 4 -> 8 -> 5/6/7 views;
        |  RECONCILE dependent|   2 -> re-examine 4/8/9;
        |  sections (invariants)|  fix orphaned refs
        +----------+----------+
                   |
                   v
        +---------------------+   per source-section-impact.md:
        |  FLAG downstream    |   name TRD/Spec items now stale,
        |  TRD / Spec items   |   the claim each must re-check
        +----------+----------+
                   |
                   v
        report: primary edit + reconciled sections + flags
```

## Worked example A — a new architecture decision

> "We're switching the order service from synchronous REST calls to an
> event-driven outbox so we stop losing writes during downstream outages."

1. **Locate:** rationale-bearing, expensive → **section 4**. Primary.
2. **Edit:** write a `D-` row adopting a transactional outbox for order events
   (driver: lost writes during downstream outages; over: 2PC, sync retry;
   consequences: eventual consistency, new relay process). Overwrite the old
   sync-call decision rather than annotating it.
3. **Reconcile:** section 4 now states the system is event-driven via an outbox;
   section 8 gains/updates the "asynchronous integration & idempotency" concept;
   section 5 Building Block View adds the relay component; a section-6 runtime
   sequence for "place order" is redrawn.
4. **Flag:** TRD reliability requirement on write durability must be re-checked;
   any Spec with synchronous-confirmation acceptance criteria is flagged.

## Worked example B — a changed constraint

> "Legal now requires all PII at rest in the EU only."

1. **Locate:** imposed external mandate, no alternatives to weigh → **section 2**.
   Primary.
2. **Edit:** add/replace the data-residency constraint to state EU-only PII at
   rest as current.
3. **Reconcile:** section 7 Deployment View region mapping is re-examined;
   section 8 persistence concept updated; any section-4 region decision is
   overwritten to reflect the forced change.
4. **Flag:** TRD compliance and data-residency NFRs re-checked; any Spec naming
   a non-EU store flagged.
