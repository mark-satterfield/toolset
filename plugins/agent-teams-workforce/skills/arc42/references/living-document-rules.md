# Living-document rules

Every version of the architecture — effective, target, delta, built — describes itself as it is.
Every sub-skill that writes architecture follows these rules, and `arc42-verify` checks them.

## Each version describes itself as it is

- A reader who opens any view sees the design that version holds, and nothing else. There is no
  "previously we used X, now we use Y" prose.
- When the design changes, the view changes in place: the old text and diagram are replaced, not
  struck through, appended to or kept beside the new content.
- No view carries a changelog, a revision table or a "last updated" line. Version history lives in
  git, which is the one place it can stay accurate.
- A delta describes the change between effective and target as the target states it ("the settings
  service gains a preferences table"), not as a history of how the design was reached.

## Where a design outcome goes

A design's outcome becomes part of the architecture description, in the section and view the MODEL
names for it: a service's structure in section 5, its flows in section 6, its stacks in section 7, a
pattern used across services in section 8, a change of direction in section 4. It is written as a
description of what the design is, with the reason a reader needs stated in the prose around the
view. There are no decision records, no ADRs and no decision logs, and a design outcome is not
written as a rule: the next design follows it as an established pattern unless it states a reason to
change.

Section 2 is the owner's. A design outcome is never written there, because only the owner writes
constraints.

## What does not belong in any version

- Requirements, and anything addressed to one PRD, Epic or bead. Requirements live in PRDs.
- History: what the design used to be, why it changed, who decided.
- Decision records, and decisions written as rules ("services MUST …").
- Open items: questions, TODOs, pending work, referrals to the owner. They are tracked in beads and
  reported to the caller.

## Quick test

Before writing any view, ask: *"If a new engineer read only this paragraph, would they believe a
false thing about the design this version holds?"* A paragraph that only makes sense as history, as a
rule or as an open item does not belong; delete it.
