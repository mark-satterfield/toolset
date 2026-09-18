---
name: epic-ready
description: Readiness gate for one EPIC — decides whether it is dispatchable to elaboration. An Epic is ready when its PRD resolves and its elaboration_state is ready or in_progress, and nothing else. It never demands acceptance criteria and never demands a repository scope, because an Epic carries neither. Triggers on /epic-ready or "is this epic ready to elaborate", "can this PRD be dispatched".
---

# Epic Ready — Dispatchability Gate

Decide whether ONE Epic can be dispatched to elaboration. That is the whole job.

**This is not `task-ready`, and the two judgments are different on purpose.** `task-ready`
rules on a Task about to be BUILT: it demands a verifiable pass condition, because the Red
phase encodes acceptance criteria into failing tests, and it stores a WSJF score so the
build lane can sort. An Epic is a container paired with a PRD. It carries no acceptance
criteria, it carries no repository — a PRD may span several, and which repositories it
lands in is ruled by `repo-scoping` during the run this gate is deciding whether to start.
A gate that demands either of those off an Epic returns INCOMPLETE forever, on every Epic,
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

2. **`elaboration_state` is `ready` or `in_progress`.** This is the `elaboration_state`
   metadata attribute on the Epic bead, and it is a different axis from `bd` status — an
   Epic stays `open` right through its whole life.
   - **absent** → the PRD is still being AUTHORED. Absence is the state on purpose: a bead
     created by hand carries no attribute, so the default is the safe one. Not ready.
   - **`ready`** → authoring is finished. Ready.
   - **`in_progress`** → a run started and did not finish. **Ready** — an Epic stays a
     candidate across failed runs, and nothing here consults how many there have been.
     Live ownership is a separate question: `prd-to-spec` settles it at its start from the
     `elaboration_state_owner` token.
   - **`done`** → the Tasks were written and they are the workable items now. Not ready.
     Only a person puts a `done` Epic back.

Nothing else is consulted. Not child counts, not whether Stories or Tasks already exist,
not the Epic's age, not its history.

This gate answers a person's question. What decides whether an Epic IS elaborated is
`prd-to-spec`'s own start check, `depscore.py elaboration-start`, which every door into
elaboration passes through: it requires the state rule above and also that the Epic is
scored, that every Epic it depends on has `elaboration_state=done`, and that no other run
owns it.

## Output contract — emit this and nothing else

Every invocation, for every outcome, responds with **exactly** this block. No preamble, no
summary, no commentary before or after it. A human usually never reads it; it is a machine
contract.

```
Ready: [TRUE / FALSE]
Epic: [id or title]
PRD: [path / "unresolved" / "conflict: <a> vs <b>"]
Elaboration state: [ready / in_progress / done / authoring (absent)]
Reason: [one line — why, whichever way it went]
```

- `Ready: TRUE` only when both conditions hold. Otherwise `FALSE`, and `Reason` names the
  one that failed (the PRD first, if both did).
- No such Epic in the tracker, or the bead is not an Epic → `Ready: FALSE`, `Reason` says
  which. A Task or a Story sent here is a caller defect: say so and rule nothing.
- A `bd` call that errors → `Ready: FALSE` with the error in `Reason`.

## This gate writes nothing

No metadata, no comments, no labels. It reads and it rules. `elaboration_state` is written
by `prd-to-spec` — `in_progress` at its start, `done` when its Tasks are written — and by a
person setting `ready`; writing it from a readiness check would let a gate claim progress no
run made.

## Recipes

**The Epic's type, status and elaboration state:**
```
bd show <id> --json --readonly \
  | jq -r 'if type=="array" then .[0] else (.issue // .) end
           | "type=\(.issue_type//"")\nstatus=\(.status//"")\nstate=\((.metadata//{}).elaboration_state//"")"'
```

**The Epic's `prd:` label:**
```
bd show <id> --json --readonly \
  | jq -r 'if type=="array" then .[0] else (.issue // .) end
           | (.labels//[])[] | select(startswith("prd:"))'
```

**PRDs naming this Epic** — the other pointer, read from the documents:
```
grep -rlE '^\*\*Epic:\*\*[[:space:]]*<id>\b' <prd-dir>
```

Both empty → unresolved. Both present and disagreeing → conflict. One present → that is
the PRD.
