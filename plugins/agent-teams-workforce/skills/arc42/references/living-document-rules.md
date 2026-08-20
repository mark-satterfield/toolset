# Living-document rules

The SAD is a **current-state** document. It describes how the system *is* architected right now, not how it got there. Every sub-skill that writes to the SAD obeys these rules; `arc42-verify` enforces them.

## Current-state only

- A reader who opens any section sees the present truth and nothing else. There is no "previously we used X, now we use Y" prose in the body.
- When a fact changes, **supersede it in place**: replace the old text with the new text. Do not append, do not strike through, do not leave the prior version visible.
- The document carries **no changelog, no revision table, and no "last updated" / "last modified" line**. Version and authorship live in version control (git history, blame, PR records), which is where they belong. Duplicating that into prose creates two sources of truth that immediately diverge.

## Where history actually lives

This project keeps **no** per-decision history. A decision's result is written directly into section 2, 4 or 8 as current state, carrying its own driver and rationale inline. To answer "what is true now?", a reader reads the section. There is no "why did we reject X" trail to follow, by deliberate choice.

## Consequences for the sub-skills

- `arc42-author` writes only present-tense, current-state content.
- `arc42-maintain` overwrites stale content rather than annotating it — it does not narrate the change inside the SAD.
- `arc42-verify` flags any changelog prose, any "last updated"/"last modified" string, and any "we used to…" narrative.

## Quick test

Before committing any SAD edit, ask: *"If a new engineer read only this paragraph, would they believe a false thing about the current system?"* If the paragraph only makes sense as history, it does not belong in the SAD — delete it.
