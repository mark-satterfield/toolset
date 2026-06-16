---
name: arc42-maintain
description: >-
  Maintains and updates an existing arc42 Software Architecture Document (SAD)
  in place — applies current-state changes to a SAD that already exists, keeps
  the structural sections (2 Constraints, 4 Solution Strategy, 8 Crosscutting
  Concepts, 9 Architecture Decisions) mutually consistent, and flags the
  downstream TRD/Spec consumers that must be reconciled when a source section
  changes. It edits a living document so the feed into requirements and specs
  stays valid; it never appends changelog narrative or rewrites history. Use
  when the user asks to update the SAD, edit the architecture document, change
  a constraint or decision in an existing arc42 doc, reconcile sections after a
  design change, keep the SAD current, or propagate an architectural change
  into the TRD/Spec.
triggers:
  - update the SAD
  - edit the architecture document
  - change a constraint in the SAD
  - revise an architecture decision
  - keep the SAD current
  - reconcile arc42 sections
  - propagate this change into the TRD
  - the architecture changed
  - fix the solution strategy section
  - maintain the arc42 document
  - the SAD is out of date
  - apply this change to section 9
---

# arc42 SAD — maintain in place

You edit an **existing** arc42 Software Architecture Document. The document is
the single upstream source for the project's Technical Requirements Document
(TRD) and feature Specs; your job is to keep it accurate to the *current* state
of the system and to keep its internal cross-references consistent, so that the
downstream feed never goes stale or contradictory.

This is a single task: editing a SAD that already exists. You do not author a
new SAD from scratch, you do not assess or grade architecture, and you do not
write requirements or specs yourself — you keep the SAD that feeds them honest.

The arc42 section model and the canonical SAD layout live in
`../arc42/references/`. Read those for the meaning and intended content of each
of the twelve sections before editing; this skill governs only how you *change*
an existing one.

## What "in place" means

A SAD is a **living document that states only the current state**. When the
architecture changes, you rewrite the affected sections to describe the new
reality. You do not:

- append a "Changelog", "History", or "What changed" narrative to any section;
- keep superseded prose alongside the new prose "for reference";
- leave a decision in section 9 marked accepted while section 4 still describes
  the option it replaced.

Decision *supersession* is captured by the status field of the section-9
decision record itself (e.g. an ADR moving to `superseded by ADR-0042`), not by
prose archaeology in the body. The rest of the document reads as if the new
decision were always true.

## The locate → edit → reconcile loop

Every maintenance edit runs the same three-phase loop. The full procedure with
worked examples is in `references/update-playbook.md`; the short form:

1. **Locate.** Identify the *primary* section the change belongs in. A changed
   external requirement or technology mandate is a section-2 (Constraints) edit;
   a new "how we will build it" choice is section-4 (Solution Strategy); a
   project-wide pattern (logging, error handling, security, persistence) is
   section-8 (Crosscutting Concepts); a specific, dated, rationale-bearing
   choice is a section-9 (Architecture Decision) record. Edit the primary
   section first, completely.

2. **Edit.** Apply the current-state change to the primary section. Replace
   stale prose; do not annotate it. Keep the section's arc42 intent intact —
   section 2 lists constraints, it does not justify them; section 9 records a
   decision with context/options/rationale/consequences, it is not a design
   essay.

3. **Reconcile.** Walk the cross-section invariants in
   `references/consistency-rules.md` and repair every dependent section the
   primary edit touched. A section-9 decision must be reflected in the
   section-4 strategy and, if it introduces a pattern, in section-8. A changed
   section-2 constraint must be propagated to every section whose content
   assumed the old constraint.

## Cross-section invariants (must hold after every edit)

These are the load-bearing relationships between the structural sections. The
exhaustive list is in `references/consistency-rules.md`; the ones you check on
every edit:

- **Every section-9 decision is reflected in section 4.** Solution Strategy is
  the executive summary of the accepted decisions. If ADR-0041 picks event
  sourcing, section 4 says the system uses event sourcing. No accepted decision
  may be invisible in the strategy.
- **Every pattern-bearing decision is reflected in section 8.** If a decision
  establishes a crosscutting concern (a standard for auth, retries, idempotency,
  observability), section 8 must describe that concern as now-current.
- **Every changed section-2 constraint is propagated forward.** Constraints
  bound the solution space. If a constraint changes, any section-4 / 8 / 9
  content that was valid only under the old constraint is now suspect and must
  be re-examined in the same edit.
- **No orphaned references.** If you remove or renumber a decision, every
  in-document pointer to it (in 4, 8, or another section-9 record) is updated or
  removed. A SAD with a dangling "see ADR-0037" reference is inconsistent.

## Flagging downstream impact

The SAD feeds the TRD and Specs. When you change a *source* section, the change
may invalidate something a downstream consumer already derived. You do not edit
the TRD or Specs — that is another role — but you **must surface** which
consumers are now stale so they can be reconciled. Use the mapping in
`references/source-section-impact.md`:

- A **section-2** change can invalidate TRD non-functional requirements and any
  Spec acceptance criteria that quantified the old constraint.
- A **section-4** change can invalidate the TRD's system-decomposition and any
  Spec whose scope assumed the old structure.
- A **section-8** change can invalidate crosscutting TRD requirements (security,
  logging, error-handling contracts) referenced across many Specs.
- A **section-9** change can invalidate whichever TRD/Spec items cite that
  decision by id.

Emit the impact as an explicit, itemized **reconciliation flag list** — each
item naming the source section that changed, the downstream artifact at risk,
and the specific claim to re-check. Do not silently assume downstream is fine.

## Output of a maintenance pass

When you finish, report exactly three things:

1. **Primary edit** — which section you changed and the current-state result.
2. **Reconciled sections** — every dependent section you updated to satisfy the
   invariants, with a one-line note per section.
3. **Reconciliation flags** — the itemized list of downstream TRD/Spec consumers
   that must be re-checked, derived from
   `references/source-section-impact.md`.

If you cannot satisfy an invariant without information you do not have, stop and
ask one precise question rather than guessing — an inconsistent SAD is worse
than a paused edit.

## What you do NOT do

- You do **not** author a new SAD from an empty template. That is a separate
  arc42 authoring role.
- You do **not** score, grade, or review architecture quality.
- You do **not** edit the TRD or the Specs. You flag them for reconciliation;
  someone else reconciles them.
- You do **not** append changelog or history narrative to the document.
- You do **not** invent constraints or decisions; you only record changes the
  user or the system has actually made.

## References

- `references/update-playbook.md` — the locate → edit → reconcile procedure for
  an in-place SAD update, with worked examples and a non-mermaid flow sketch.
- `references/consistency-rules.md` — the full set of cross-section invariants
  that must hold after any edit.
- `references/source-section-impact.md` — when sections 2/4/8/9 change, which
  TRD/Spec consumers must be re-flagged for reconciliation.
- `../arc42/references/` — the canonical arc42 section model and SAD layout
  this skill maintains.
