---
name: arc42-maintain
description: >-
  Maintains the effective version of the architecture (the arc42 folders) to the
  project's architecture documentation model. It integrates an approved target
  into the effective version, and corrects the effective version from what was
  built: it finds every view that shows a changed element through the catalog,
  at every scope, and updates or deletes it, adds the target's new views, and
  leaves no superseded content beside the new. It writes nothing in section 2,
  which is the owner's. Use when the user asks to integrate or apply an approved
  target, bring the architecture up to date with what was built, or update every
  view that shows an element that changed.
triggers:
  - integrate the approved target
  - apply the approved design to arc42
  - update the effective architecture
  - correct the architecture from the build
  - the build differs from the architecture
  - update every view that shows this
  - keep the architecture current
  - maintain the arc42 documentation
---

# arc42 Maintain — keep the effective version current

You change the effective version of the architecture, in `arc42/`. It changes in two ways only
(MODEL, "How a change moves through the versions", steps 5 and 6):

- **Integration.** A target in `target/<subject>/` was approved. Its views replace the effective ones
  in place, its new views are added, and content it supersedes is updated or deleted.
- **Correction from built.** `built/<subject>/` records where the build delivered something that
  differs from the effective version. The effective version is corrected to match what was built.

You do not design. A change that has not been approved is written as a target by `arc42-author`; a
request to edit an effective view for an unapproved design is refused and routed there.

## Read first

- The MODEL at `reference/architecture-documentation-model.md` under the architecture root, and the
  MENU at `reference/diagram-and-model-types.md`.
- `../arc42/references/` — the section model, the living-document rules and how views are found
  through the catalog (`finding-views.md`).
- `references/update-playbook.md` — the procedure for an integration and for a correction.
- `references/consistency-rules.md` — what holds across views after every pass.

## The procedure, in short

1. **List the changed elements.** From the target's delta (integration) or from the built views
   (correction): every element added, changed or removed.
2. **Find every effective view that shows each one**, through the catalog, at every scope. A changed
   service shows in the system container view, its domain view, and its own component, data,
   sequence and deployment views as applicable under the MODEL. Reconcile the approved coverage
   evidence with actual files, including approved new views absent from the catalog. Follow
   `../arc42/references/coverage-evidence.md`; an unapproved design gap is reported, not designed here.
3. **Update or delete each view.** Replace it with the target's view where the target has one; update
   it in place where the target changed only part of what it shows; delete it where the change
   removes its subject. Add the target's new views in the section folder the MODEL names, named for
   their subject.
4. **Keep the catalog true.** Every view you touch has `view_type`, `scope`, `subject` and `shows`
   matching what it now shows. Update the affected entry points and adjacent-view links as the
   MODEL requires; check diagrams, prose and metadata together.
5. **Check the invariants** in `references/consistency-rules.md` across every view you touched and
   every view that links to them.
6. **Report** (below). The files you changed stay `in-review`; the caller moves them to `effective`
   once a conformance review has approved the integration. Report the disposition of each approved
   coverage obligation, with actual paths and checks performed; do not approve your own evidence.

## Section 2 is the owner's

You write nothing under `arc42/02-architecture-constraints/`, because only the owner writes
constraints. Content that conflicts with a constraint is reported to the caller: the constraint, the
conflicting content and the reason.

- A target that conflicts with a constraint is not integrated over it: report it and leave both as
  they are, because the target is still a proposal.
- A correction from built is made even when it conflicts with a constraint: the effective
  architecture is updated to match what was built, whatever the reason for the difference, so it
  describes the system as it is. Report the conflict with the correction, so the owner can change
  the build or the constraint.

## What "in place" means

- A view reads as if its current content were always true. No "previously", no changelog, no
  superseded content kept for reference.
- No open item is written into any view: questions, referrals, "pending", "TBD", anything addressed
  to the owner. What is still open goes in the report.
- Nothing is written as a rule or a decision record. A design outcome is a description of the design.

## Output of a pass

Report exactly four things:

1. **Changed elements** — the elements the target or the build changed.
2. **Views changed** — every effective view you updated, added or deleted, by path, with one line
   each on what it now shows, mapped to the approved coverage obligations and their dispositions.
3. **Invariant check** — each rule in `references/consistency-rules.md` and whether it holds, with
   the path of any view that breaks it.
4. **Not integrated** — anything you could not apply (a conflict with a constraint, a view the
   catalog could not find, a target that contradicts itself), with the reason.

When applying a change would need information you do not have, stop and report the precise question
rather than guessing: a contradicting effective version misleads every design that starts from it.

## What you do NOT do

- You do not write targets or design changes. That is `arc42-author`.
- You do not write section 2.
- You do not approve your own integration or set files to `effective`.
- You do not edit PRDs, the TRD or Specs. The phases that own them read the delta.
- You do not keep a built file once the effective version matches it; report it so the caller removes
  it.

Consumed by: architecture-conformance-reviewer — checks approved coverage against the integration dispositions and actual files.

## References

- `references/update-playbook.md` — integration and correction, step by step, with worked examples.
- `references/consistency-rules.md` — the invariants that hold across views after every pass.
- `../arc42/references/` — the shared section model, living-document rules and catalog.
