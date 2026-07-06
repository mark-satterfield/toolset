---
name: record-decision
description: >-
  Use when a choice has been settled and one road was taken while a live road was
  rejected — record it in the project's decision log (decisions.md). Fires when you
  catch yourself narrating a decision and its rationale into a deliverable, commit,
  or memory instead; when the user says "record this decision", "log why we chose",
  or "add an ADR/decision entry"; and when the record-observation router sends a
  decision here.
allowed-tools: [Read, Bash]
---

<!-- residue-lint:ignore-file (this rule quotes the decision-narration vocabulary to forbid it) -->

# Recording a decision

A decision-log entry is a settled choice written for a reader who was never in the
room — no "as discussed", no pointer to a chat that is now gone. You draft the
content; the script owns the mechanics (the D-id, the date, the shape, and the
`Supersedes` / `Superseded By` back-pointers). Your job is the seven fields and
two rules below, written to **read cold**.

## Steps

1. **Draft the seven fields** against the guidance in *Writing each field*. Each
   field must stand alone for a stranger. Done when every required field has
   content that passes its own test — not a placeholder, not "see above".
2. **Check the two rules** — supersession and read-cold — below. If this reverses
   an earlier decision, note the D-id it supersedes. Done when you have decided
   whether `supersedes` applies and confirmed no field leans on context that lives
   only in this conversation.
3. **Assemble the JSON** payload (contract in
   [`references/decision-log-template.md`](references/decision-log-template.md))
   and pipe it to the script:

   ```bash
   echo '<json>' | python3 "${CLAUDE_PLUGIN_ROOT}/skills/record-decision/scripts/record_decision.py"
   ```

   The script writes `decisions.md` at the project root, assigns the next D-id,
   stamps the date, and — if `supersedes` is set — flips the older entry to
   Superseded and cross-links both.
4. **Read the exit code.** Exit 0 is success: **say nothing, end the turn.** The
   log is the record; there is nothing to announce. On a non-zero exit, surface
   the drafted record and the script's stderr line to the user so the decision is
   not lost, and stop. Done when the turn ends silently on success, or the user
   has the full drafted entry and the reason on failure.

## Writing each field

**Made by.** Who made the call — name and role. Don't guess: you either know who
settled it or you don't. When you're unsure, leave it blank rather than inventing
an attribution.

**Decision.** What was settled, as a present-tense fact — not the discussion.
"The system uses X," not "we weighed it and chose X." One sentence; if it needs
two, split into two decisions.

**Context.** The pressure that forced a choice now: what was true that made
standing still impossible. A reader who wasn't there should finish this field
seeing why doing nothing wasn't an option. Pressure only — keep the reasoning out.

**Options considered.** One line per real option, naming why it lost. Name the
actual disqualifier, not a vague complaint: "slower" is a complaint; "added a
second datastore to keep in sync" is a reason. Test: would this line stop someone
re-proposing the option next quarter? If not, it's too vague. State each losing
option at its real strength; an option written as foolish was never weighed, and
blocks a future reader from reopening it when conditions change.

**Why chosen.** Why the winner won, on the same axis the others lost on. If an
option lost on operational cost, the winner wins on operational cost, not on
elegance. Give the reason that drove the call, not the best-sounding one in
hindsight.

**Consequences.** The price: what was accepted, given up, or taken on. Name a
downside — a field listing only benefits is worthless, since every choice costs
something. If you can't name one, you don't yet understand the trade.

**Revisit conditions.** An observable trigger: a number crossing a line, a
dependency retired, a scale that changes the math. "If monthly users exceed
10,000," not "if requirements change." If you can't state a concrete trigger that
would overturn the decision, say so — that signals the decision rests on
unsurfaced assumptions.

**Impacted repositories.** Reason by reach, not proximity: which repositories must
now behave differently, not which one the conversation happened in. List a
repository if its behavior, contract, or assumptions change, even if no code there
was touched today. Failure to avoid: listing only the repository in front of you
and missing the one that silently inherits the consequence.

## Two rules above the fields

**Supersession.** If this reverses or replaces an earlier decision, set
`supersedes` to that entry's D-id and carry the changed circumstance into Context.
A new decision that quietly contradicts an older one is how the log starts to lie.
Flag the link only — the script wires the identifiers and back-pointers.

**Read cold.** Every field stands alone for someone who was never in the
conversation. No "as discussed," no "per the above," no pointer to context that
lives only in a chat that's now gone. If a phrase makes sense only to someone who
was there, it fails.
