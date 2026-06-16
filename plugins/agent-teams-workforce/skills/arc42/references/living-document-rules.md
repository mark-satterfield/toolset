# Living-document rules

The SAD is a **current-state** document. It describes how the system *is* architected right now, not how it got there. Every sub-skill that writes to the SAD obeys these rules; `arc42-verify` enforces them.

## Current-state only

- A reader who opens any section sees the present truth and nothing else. There is no "previously we used X, now we use Y" prose in the body.
- When a fact changes, **supersede it in place**: replace the old text with the new text. Do not append, do not strike through, do not leave the prior version visible.
- The document carries **no changelog, no revision table, and no "last updated" / "last modified" line**. Version and authorship live in version control (git history, blame, PR records), which is where they belong. Duplicating that into prose creates two sources of truth that immediately diverge.

## Where history actually lives

Per-decision history is real and valuable — it just does not live in the SAD body. It lives in **Architecture Decision Records (ADRs)**: dated, immutable, append-only records, one per significant decision, each stating context, the decision, status, consequences, and rejected alternatives. When a decision is reversed, a *new* ADR supersedes the old one (status `Superseded by ADR-NNNN`); the old ADR is never edited.

Section 9 (Architecture Decisions) is the **link layer** between the living SAD and the immutable ADR log. Section 9 holds a current index — decision title, status, and a pointer to the ADR — and nothing more. To answer "why is it this way and what did we reject?", a reader follows the link to the ADR. To answer "what is true now?", a reader stays in the SAD section.

## Consequences for the sub-skills

- `arc42-author` writes only present-tense, current-state content and creates the section-9 index as links, never inline decision logs.
- `arc42-maintain` overwrites stale content rather than annotating it, and adds a section-9 link when a new ADR is created — it does not narrate the change inside the SAD.
- `arc42-verify` flags any changelog prose, any "last updated"/"last modified" string, any "we used to…" narrative, and any section-9 entry that inlines a full decision record instead of linking an ADR.

## Quick test

Before committing any SAD edit, ask: *"If a new engineer read only this paragraph, would they believe a false thing about the current system?"* If the paragraph only makes sense as history, it does not belong in the SAD — move it to an ADR and leave a link.
