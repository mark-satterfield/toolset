---
name: epic-ready
description: Readiness gate for one EPIC — decides whether it is dispatchable to elaboration. An Epic is ready when its PRD resolves and its elaboration state (the beads-contract metadata schema's ElaborationState) is the ready or in-progress value, and nothing else. It never demands acceptance criteria and never demands a repository scope, because an Epic carries neither. Triggers on /epic-ready or "is this epic ready to elaborate", "can this PRD be dispatched".
---

# Epic Ready — Dispatchability Gate

Decide whether ONE Epic can be dispatched to elaboration. That is the whole job.

**This is not `task-ready`, and the two judgments are different on purpose.** `task-ready`
rules on a Task about to be BUILT: it demands a verifiable pass condition, because the Red
phase encodes acceptance criteria into failing tests, and it stores a WSJF score so the
build lane can sort. An Epic is a container paired with a PRD. It carries no acceptance
criteria, it carries no repository — a PRD may span several, and which repositories it
lands in is ruled by `repo-scoping` during the run this gate is deciding whether to start.
A gate that demands either of those off an Epic rules not-ready forever, on every Epic,
and nothing a person can write on the bead would ever clear it.

So this skill demands exactly two things, and adds nothing to them.

## The two conditions

1. **The PRD resolves.** Exactly one PRD document pairs with this Epic. The pairing is
   carried by two canonical pointers, both authoritative:
   - the Epic's own `prd:<stem>` label, and
   - the PRD's own `**Epic:** <bead-id>` line.

   When both are present they must name the same document. **A disagreement resolves to
   nothing** — it is a conflict to report, never to settle by preferring a side — so it
   reports `Ready: FALSE` naming both candidates. No PRD at all, or two PRDs naming this
   Epic with no label saying which, is the same answer for the same reason.

2. **The elaboration state is `ELABORATION_READY` or `ELABORATION_IN_PROGRESS`.** The key,
   its values and the owner-token key are defined once, in the `LANE_KEYS` group of the
   beads-contract metadata schema, `skills/beads-contract/schemas/bead-metadata.schema.json`
   (`KEY_ELABORATION_STATE`, whose values are `ElaborationState` or `ELABORATION_AUTHORING`;
   `KEY_ELABORATION_STATE_OWNER`). Take the names and values from there; this file does not
   restate them. The elaboration state is a different axis from `bd` status — an Epic stays
   `open` right through its whole life. Ruling on each value:
   - **`ELABORATION_AUTHORING` (absent or empty)** → the PRD is still being AUTHORED.
     Absence is the state on purpose: a bead created by hand carries no attribute, so the
     default is the safe one. Not ready.
   - **`ELABORATION_READY`** → authoring is finished. Ready.
   - **`ELABORATION_IN_PROGRESS`** → a run started and did not finish. **Ready** — an Epic
     stays a candidate across failed runs, and nothing here consults how many there have
     been. Live ownership is a separate question: `prd-to-spec` settles it at its start from
     the `KEY_ELABORATION_STATE_OWNER` token.
   - **`ELABORATION_DONE`** → the Tasks were written and they are the workable items now.
     Not ready. Only a person puts a done Epic back.

Nothing else is consulted. Not child counts, not whether Stories or Tasks already exist,
not the Epic's age, not its history.

This gate answers a person's question. What decides whether an Epic IS elaborated is
`prd-to-spec`'s own start check, `depscore.py elaboration-start`, which every door into
elaboration passes through: it requires the state rule above and also that the Epic is
scored, that every Epic it depends on is in the `ELABORATION_DONE` state, and that no other run
owns it.

## Result

Every invocation, for every outcome, rules on the five fields below and nothing else. When the
caller supplies a response schema, the schema carries them. When it does not, respond with
**exactly** this block: no preamble, no summary, no commentary before or after it.

```
Ready: [TRUE / FALSE]
Epic: [id or title]
PRD: [path / "unresolved" / "conflict: <a> vs <b>"]
Elaboration state: [<the stored ElaborationState value> / authoring (absent)]
Reason: [one line — why, whichever way it went]
```

- `Ready: TRUE` only when both conditions hold. Otherwise `FALSE`, and `Reason` names the
  one that failed (the PRD first, if both did).
- No such Epic in the tracker, or the bead is not an Epic → `Ready: FALSE`, `Reason` says
  which. A Task or a Story sent here is a caller defect: say so and rule nothing.
- A `bd` call that errors → `Ready: FALSE` with the error in `Reason`.

## This gate writes nothing

No metadata, no comments, no labels. It reads and it rules. The elaboration state is written
by `prd-to-spec` — `ELABORATION_IN_PROGRESS` at its start, `ELABORATION_DONE` when its Tasks
are written — and by a person: `ELABORATION_READY` when a new PRD is finished,
`ELABORATION_IN_PROGRESS` to hand back an Epic that was already started, so it resumes from
its persisted artifacts rather than starting over; writing it from a readiness check would let
a gate claim progress no run made.

## Recipes

**The Epic's type and status:**
```
atw-bd show <id> --json --readonly \
  | jq -r 'if type=="array" then .[0] else (.issue // .) end
           | "type=\(.issue_type//"")\nstatus=\(.status//"")"'
```

**The Epic's elaboration state** — the `.lane` object holds the `LANE_KEYS` keys the bead
carries; the state is its `KEY_ELABORATION_STATE` value, absent while authoring:
```
python3 "${CLAUDE_PLUGIN_ROOT}/skills/beads-contract/scripts/beads-contract.py" metadata get <id> \
  | jq '.lane'
```

**The Epic's `prd:` label:**
```
atw-bd show <id> --json --readonly \
  | jq -r 'if type=="array" then .[0] else (.issue // .) end
           | (.labels//[])[] | select(startswith("prd:"))'
```

**PRDs naming this Epic** — the other pointer, read from the documents:
```
grep -rlE '^\*\*Epic:\*\*[[:space:]]*<id>\b' <prd-dir>
```

Both empty → unresolved. Both present and disagreeing → conflict. One present → that is
the PRD.
