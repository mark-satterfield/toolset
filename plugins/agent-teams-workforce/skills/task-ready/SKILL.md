---
name: task-ready
description: Completeness gate for one issue — decides whether it carries what someone needs in order to work it, and records that verdict on the issue itself. Quality control on a Task's CONTENT, run at Task creation time inside the prd-to-spec workflow. Resolves the issue from Beads (primary) or GitHub (backup), reuses the stored review verdict while the content is unchanged, reruns the review when it is missing or stale, records missing lineage or a missing repository as a note on the verdict rather than as a refusal, stores review_status, review_missing, reviewed_at and ready_content_hash as issue attributes, and emits one fixed contract. It judges content completeness and nothing else — not dependencies, not blockers, not priority. Triggers on /task-ready or "is this ready to implement", "is this issue complete", "prepare this issue".
---

# Task Ready — Content Completeness Gate

Decide whether ONE issue carries what someone needs in order to work it, say what is
missing when it does not, and persist that decision on the issue so the next run is cheap.
The source of truth for an issue's state is **Beads** (primary) or **GitHub** (backup).
Throughout this skill, "the tracker" means whichever one resolved the issue. Anything that
applies to Beads applies to GitHub too, **except** storing attributes on the issue — GitHub
has no custom fields, so it uses the marker-comment fallback described below.

## What this skill is for

**Quality control on a Task's CONTENT, at the moment the Task is created.** Its home is
inside the `prd-to-spec` workflow, where it runs over what the decomposer just emitted and
answers one question: does this Task say enough for someone to work it, and if not, what is
missing. That is its whole purpose, and running it there is what keeps an incomplete Task
from reaching the board in the first place.

**It is NOT an eligibility gate.** Eligibility means dependencies and blockers. This skill
has never consulted either, and both belong entirely to whatever decides eligibility.

**It does NOT score.** WSJF for a Task is computed outside this skill, by the sequencing
capability, under the `wsjf` rubric at Task level — value and time criticality inherited from the
parent Epic, risk-reduction computed from the dependency graph, size judged locally. This
skill neither computes a score, nor reads one, nor backfills one, nor clears one. A Task
with no score simply never appears in the sorted eligible list, so there is nothing here to
fill in and nothing downstream waiting on this skill for a number.

## Output contract — emit this and nothing else

Every invocation, for every outcome, responds to chat with **exactly** this block. Never
add narrative, commentary, or explanation before or after it. A human usually never reads
this; it is a machine contract. The single exception: for a **closed** issue, append one
trailing line — `Issue <id> was closed on <date>.` — as chat-only context. It is never
posted to the tracker, and `Comments posted` stays `0`.

```
Ready: [TRUE / FALSE]
Pipeline result: [READY / INCOMPLETE / MISSING / ERROR]
Issue: [id or title]
Review: [COMPLETE / INCOMPLETE — n dimensions need attention / n/a]
Comments posted: [n]
```

- **`Ready`** is `TRUE` only when **both** hold: `Pipeline result` is `READY` **and** the
  tracker reports the issue in a *ready* state — for Beads that is `bd ready` membership
  (status `open`, no active blockers, not deferred/hooked), for GitHub that is state
  `OPEN`. Status `open` alone is not enough; a blocked or closed issue is never `Ready`.
  In all other cases `Ready` is `FALSE`.
- **`Pipeline result`** describes the review verdict only (it does not fold in blocker or
  closed state):
  - `READY` — the review came back COMPLETE.
  - `INCOMPLETE` — the review found gaps.
  - `MISSING` — no such issue in the tracker.
  - `ERROR` — a `bd`/`gh` call failed or the input could not be resolved.
- A **closed** issue is never recomputed: it reports the verdict already stored on it
  (e.g. a stored `READY` stays `READY`) with `Ready: FALSE`. See Algorithm step 2.
- For `MISSING` / `ERROR`, fill `Review` with `n/a` and `Comments posted: 0`. Never switch
  to a different response shape.

## Be quiet

No preamble, no "let me…", no summary. Post to the tracker only when a step actually ran
(see Audit Trail). Resolve everything you can yourself — never ask clarifying questions.
The only exception is an empty invocation: with no argument, ask once, in one line —
"Provide an issue ID, number, or description." — then stop.

## What gets stored on the issue

The skill persists current-state attributes so a later run can skip work. On **Beads**,
these are first-class metadata (set with `--set-metadata`, read from `bd show --json`):

| Key | Meaning |
| --- | --- |
| `review_status` | `COMPLETE` or `INCOMPLETE` from the last review |
| `review_missing` | on an INCOMPLETE review, what the issue is MISSING — one line, the skill's own words. Empty/omitted when the review was COMPLETE |
| `reviewed_at` | ISO 8601 timestamp of the last review |
| `ready_content_hash` | fingerprint of the issue's content at the last run — the staleness watermark |

**Those four keys are the whole of what this skill writes.** It writes no other metadata,
and it never touches `wsjf` or `wsjf_calculated_at` — reading, writing, or clearing — because
it does not own them. Metadata is overwritten each real run (it is current state, not history).

On **GitHub** (no custom fields) the same keys are written into one machine-readable
marker comment instead:

```
<!-- task-ready:state
review_status=COMPLETE
review_missing=
reviewed_at=2026-06-30T12:00:00Z
ready_content_hash=ab12cd34ef56a7b8
-->
```

**Both spellings are read; only `task-ready:state` is written.** This skill used to be
called `issue-ready`, and markers it wrote then — `<!-- issue-ready:state … -->` — sit in
live GitHub issue bodies today. Accept either header when reading, take the most recent
marker of either spelling, and always write the `task-ready:state` spelling.

Read state from the most recent such marker; write a fresh marker each real run. Every
marker carries `ready_content_hash=$H` — a marker written without it is the same defect as
a Beads write that omits it, and step 7 verifies GitHub by re-reading the marker just as
it verifies Beads by re-reading the metadata.

## Staleness — the reason work is skipped

The concept: **only run the review when it is missing or stale; otherwise return the
verdict already on the issue.** Re-reviewing content nobody has touched costs a whole
session and reaches the identical conclusion off the identical bytes. Freshness is decided
by a content fingerprint, not by the tracker's `updated_at` (which the skill's own writes
would bump, falsely invalidating the cache). See Recipes for the exact hashing command.

**What the fingerprint ACTUALLY covers: `title`, `description`, `issue_type`, `priority`.**
That is four fields, and it is narrower than it looks. The hash is taken over a ten-key object,
but six of those keys — `acceptance`, `design`, `type`, `dependencies`, `deps`, and `labels` —
carry no value: the first five are not returned by `bd show --json` at all, and `labels` is
nulled deliberately (see below). They stay in the object because the digest is over its shape.

**`bd show --json` has no fixed field list.** It OMITS any field the bead does not carry, so a
record carries anywhere from 13 to 18 keys and the union across a whole tracker is larger still.
Never assert a field is absent from the SCHEMA when it is merely absent from one bead; the
`beads-contract` skill documents the census and `beads-contract.py record <id>` reports what a
given bead actually has.

Two consequences follow, and neither is a defect to be fixed here:

- **Acceptance criteria are PROSE, so WHERE they live decides whether they are hashed.**
  Criteria are not a key/value pair on a bead and are not meant to be: they live in the
  issue's description, or in its parent Story or Epic. The requirement is that they exist
  somewhere, not that they occupy a field — so "`bd` exposes no `acceptance` key" says
  nothing about whether criteria are covered.

  Criteria written in the issue's OWN description are inside `description`, which IS hashed.
  Editing them changes the fingerprint and DOES release
  a hold: a Task held on an INCOMPLETE verdict leaves the hold on that edit alone, with no
  title touch needed.

  Criteria that live ONLY on the parent Story or Epic are NOT covered, because the
  fingerprint is computed over this issue's own record and nothing else. Editing a parent's
  criteria does not make this issue stale. That is the real limitation, and it is about where
  the prose sits rather than about the tracker lacking a field — to release such a hold, edit
  this issue's own description or remove the `needs-correction` label.

  Criteria mirrored into an `acceptance_criteria` METADATA key are not covered either, for
  the separate reason that metadata is outside the fingerprint entirely (which is what lets
  this skill store its own verdict without invalidating it). That key is a convenience for
  the build lane, never the evidence that criteria exist.
- **`labels` is nulled ON PURPOSE.** The pipeline itself writes a `needs-correction` label onto
  every held bead. If labels were hashed, the act of RECORDING a hold would change the
  fingerprint, the bead would read as stale on the very next pass, and the skill would re-buy
  the full review it just held to avoid — a fresh session per sweep, forever.

Never metadata, timestamps, status, or comments — so storing a verdict never invalidates it.

**THE RECIPE HAS ONE IMPLEMENTATION: `content_hash` in the `agent-teams-workforce:beads-contract`
skill.** This file carries no copy, and neither does anything else: a host that compares
fingerprints shells out to `beads-contract.py`. Change the recipe in the one place that
implements it.

A recipe stated twice re-invokes this skill forever on every affected bead: the Python reads a
watermark it cannot reproduce, calls the bead stale, and the skill rewrites the same watermark the
Python will reject again on the next pass. That is not hypothetical — it is what the `labels`
disagreement did, on precisely the held beads the rule exists for, and it is why there is now one
implementation and no copies.

- **Fresh** — `ready_content_hash` exists and equals the current content hash → reuse the
  stored verdict; rerun nothing; post nothing.
- **Stale or missing** — no stored hash, or it differs → rerun the review, overwrite the
  stored attributes, post the comments.

**One hash, computed once.** The value compared and the value stored are the same string
from the same command, computed once at step 3 and held in `$H` for the rest of the
invocation. A stored hash that disagrees with the compared hash is worse than none: it
makes a changed issue look fresh. Never recompute after a write, never truncate to a
different length, never hash a different field set.

## Algorithm

1. **Resolve the issue.** Beads ID (e.g. `tst-123`) → `bd show <id> --json`. GitHub number
   → `gh issue view <n> --json ...`. Inline text → assess directly, store nothing, post
   nothing (chat-only result). If the lookup returns "not found" → `Pipeline result:
   MISSING`, emit contract, stop. If a `bd`/`gh` call errors → `Pipeline result: ERROR`,
   emit contract, stop.
2. **Closed → return stored state, recompute nothing.** If the status is `closed`, do not
   run the review and do not check staleness — a closed issue is never recomputed. Report
   the attributes already on the issue: `Review` = stored `review_status` (or `n/a` if it
   was never reviewed); `Pipeline result` = `READY` when the stored review is `COMPLETE`,
   otherwise `INCOMPLETE`. `Ready: FALSE` (a closed issue is never ready).
   `Comments posted: 0`. After the contract block, append one chat-only line — `Issue <id>
   was closed on <closed_at>.` — using the issue's close date; never post it to the
   tracker. Emit, stop.
3. **Read stored state** (`review_status`, `review_missing`, `reviewed_at`,
   `ready_content_hash`) and **compute the current content hash into `$H`** — always,
   before anything else runs, using the Content hash recipe verbatim.

   Compute it even when there is no stored hash to compare against. `$H` is what steps 4
   and 6 **write**; the comparison is its second use, not its only one. Short-circuiting
   on "no stored hash, so obviously stale — skip the hash and go review" is the single
   failure this whole attribute exists to prevent: the run then has nothing to store, the
   next run again finds no hash, and every sweep pays for a full review forever. If you
   took that shortcut, you have broken the skill.
4. **Read the lineage and the repo — as CONTEXT, never as a refusal.** Read the issue's own
   type, walk its parents, and read the `repoPath:` marker off each (Hierarchy recipe).
   Record what you found and carry it into the review as a note. Then continue to step 5 no
   matter what it said.

   **A Story never gates a Task, and a repository is never a dispatch precondition.** Both
   are standing rulings, and this step used to violate both — it refused any Task lacking a
   parent Story, any Story lacking an Epic, and any Task whose chain named no `repoPath`,
   before spending a review on it. A Story is a **roll-up parent for reporting and
   tracking**; it never decides whether a Task can be worked. A recorded repo on a bead is
   at most a **hint** — the repository a piece of work belongs in is ruled when the work is
   dispatched, from the work itself, not read off a field somebody may or may not have
   filled in. Refusing on either of them made this gate unable to clear anything.

   So: missing lineage and a missing repository are **notes on the verdict**, never the
   verdict. Append them to whatever `Review` reports, e.g.
   `COMPLETE (note: no parent Story)` or
   `INCOMPLETE — 2 dimensions need attention (note: no repoPath on the task or its Story)`.
   They never set `Pipeline result` and never skip the review.

   **Provenance is settled upstream, not re-adjudicated here.** A Task with no parent Epic
   or PRD behind it is not legitimate work — that is true, and it is enforced where such a
   Task is CREATED. This gate's job is content completeness: does this Task say enough to
   be worked. Re-litigating where an issue came from, at gate time, on a bead that already
   exists, blocks the queue and repairs nothing.

   **Bugs do not come here.** A bug is a reporting mechanism that a person triages into an
   Epic, a Task, or a closure; it has no acceptance criteria. A caller that sends one is the
   defect. Report `Pipeline result: INCOMPLETE` with
   `Review: INCOMPLETE — a bug is triaged by a person, not gated here` and write nothing.

5. **Decide freshness.** Fresh = stored hash exists and equals `$H`.
   - **Fresh:** reuse the stored verdict. `review_status=COMPLETE` → `Pipeline result:
     READY`; `review_status=INCOMPLETE` → `Pipeline result: INCOMPLETE`, and append the
     stored `review_missing` to the `Review` line so the reused verdict still says what is
     missing. Rerun nothing. `Comments posted: 0`. Go to step 8.
   - **Stale/missing:** go to step 6.
6. **Run review** (the `task-review` skill) against the issue. Post the review comment
   (Audit Trail). Then run the **review write** in Recipes as written — `review_status`,
   `review_missing`, `reviewed_at` and `ready_content_hash=$H` in ONE `bd update`. The keys
   land together or the run has failed; a write that sets the status without the hash is the
   defect, not a partial success.

   `Pipeline result` is then `READY` if `review_status=COMPLETE`, otherwise `INCOMPLETE`.
   Post the ready-declaration comment only when the review was COMPLETE.

   **An INCOMPLETE verdict MUST carry what is missing, in `review_missing`.** This is not
   bookkeeping. The pipeline no longer re-buys an INCOMPLETE verdict: on the next pass it
   reads the stored verdict, sees the content hash unchanged, and HOLDS the bead rather than
   spending a session to reach the identical conclusion. Nothing downstream regenerates the
   reason, so if this write does not carry it, the only record of what to fix is a prose
   comment, and a person is told a Task is blocked without being told why. Summarize the
   review's findings in one line — the missing acceptance criteria, the unresolved
   dependency, the absent scope — and write it. On a COMPLETE review write it empty.
7. **Verify the write landed.** Read the attributes back (the verify recipe) and confirm
   `ready_content_hash` is present and equals `$H`, alongside `review_status` /
   `reviewed_at`. If the hash is absent or different, the write did not land: redo it and
   read back again. Never emit the contract on an unverified write. A run that reports
   `READY` with no stored hash has thrown away everything it just paid for and guarantees
   the next run reruns it.
8. **Compute `Ready`.** `Ready = (Pipeline result == READY) AND tracker-ready-state`.
   Tracker-ready-state: Beads → issue appears in `bd ready`; GitHub → issue state `OPEN`.
9. **Emit the contract block.** Stop.

## Audit Trail

- Post a tracker comment **only for a step that actually ran this invocation.** A fresh,
  reused verdict posts nothing (`Comments posted: 0`).
- Human-readable comments are **append-only** — never edit or delete prior ones. Each
  carries an ISO 8601 timestamp. The comment history is the canonical record of every
  review iteration. (The machine-readable attributes are current-state and *are*
  overwritten — that is separate from the audit trail.)
- Comment templates (post only the ones whose step ran):

  ```
  ## Lineage Note — [ISO 8601 timestamp]

  [what the walk found: no parent Story, a parent Story with no Epic, or no repoPath
  anywhere in the chain]

  Recorded as context, not as a refusal. A Story is a roll-up parent for reporting and
  tracking and never gates whether this can be worked; a recorded repository is a hint,
  and the repository this work lands in is ruled at dispatch from the work itself. The
  review below ran as normal.
  ```

  ```
  ## Issue Review — [ISO 8601 timestamp]

  [full task-review output]
  ```
  ```
  ## Ready for Implementation — [ISO 8601 timestamp]

  Passed completeness review: this issue carries what someone needs in order to work it.
  ```

## Recipes

Beads commands run read-only where possible (`--readonly`); writes use `bd update`. The
`jq` selectors tolerate both array and `{issue:…}`/flat shapes and missing keys.

**Content hash (Beads)** — capture it into `$H`; this is the only place the hash is
computed, and both the freshness comparison and the write use `$H`:
```
H=$(python3 "${CLAUDE_PLUGIN_ROOT}/skills/beads-contract/scripts/beads-contract.py" \
      fingerprint <id> | jq -r .fingerprint)
```

**THE RECIPE IS NOT WRITTEN DOWN HERE, AND THAT IS THE POINT.** A recipe stated twice drifts
in whichever copy is wrong, and a drift on the `labels` line disagrees about precisely the beads
this rule exists for: every bead the pipeline has held carries `needs-correction`.

So `content_hash` in `beads-contract.py` is the single implementation, the
`agent-teams-workforce:beads-contract` skill documents what it covers and why, and
`fingerprint <id> --explain` prints the exact object hashed when you need to see it. Do not
reconstruct the pipeline from this file, and do not paste a `jq` version back in.

The same command also reports the stored watermark and whether it is still fresh, so step 5's
comparison can read `.stored` and `.fresh` from one invocation rather than re-deriving them.

**Content hash (GitHub):** GitHub is the BACKUP tracker with a different record shape, and
nothing downstream reproduces this digest — `readiness.py` reads beads only. So this one stays
inline; it is not half of a joint contract and has nothing to drift against.
```
H=$(gh issue view <n> --json title,body,labels \
  | jq -S '{title,body,labels:[.labels[].name]}' \
  | shasum -a 256 | cut -c1-16)
```

**Read stored state (Beads):**
```
bd show <id> --json --readonly \
  | jq -r 'if type=="array" then .[0] else (.issue // .) end | (.metadata // {})
           | "review_status=\(.review_status//"")\nreview_missing=\(.review_missing//"")\nreviewed_at=\(.reviewed_at//"")\nready_content_hash=\(.ready_content_hash//"")"'
```

**Hierarchy (Beads)** — the issue's own type and its parent chain. Two reads: the issue,
then its parent:
```
bd show <id> --json --readonly \
  | jq -r 'if type=="array" then .[0] else (.issue // .) end
           | "type=\(.issue_type//"")\nparent=\(.parent//"")"'
# then, for a non-empty parent:
bd show <parent> --json --readonly \
  | jq -r 'if type=="array" then .[0] else (.issue // .) end
           | "parent_type=\(.issue_type//"")\ngrandparent=\(.parent//"")"'
# and for a task, one more read of <grandparent> for grandparent_type.
```

The `repoPath:` marker, read from the same records — notes first, then description. It is a
LINE-ANCHORED marker, so read the line, not the whole field:
```
bd show <id> --json --readonly \
  | jq -r 'if type=="array" then .[0] else (.issue // .) end
           | ((.notes // "") + "\n" + (.description // ""))' \
  | grep -iE '^[[:space:]]*[-*>[:space:]]*`?(repoPath|repo|repository)`?[[:space:]]*[:=]' \
  | head -1
```
Absent on the task, read the Story's. **Absent on both, the gate does NOT fail** — it records
"no repoPath on the task or its Story" as a note on the verdict and carries on to the review,
exactly as step 4 says. A recorded repository is a hint; the repository a piece of work lands
in is ruled at dispatch, from the work itself. There is no path in this skill on which a
missing repo sets `Pipeline result`. `repo:` and `repository:` are accepted spellings of the
same marker.

**Status / closed check (Beads):**
```
bd show <id> --json --readonly \
  | jq -r 'if type=="array" then .[0] else (.issue // .) end | .status'
```

**Close date (Beads):** from the same `bd show --json`, read `.closed_at`; if absent, fall
back to `.updated_at`. **GitHub:** `gh issue view <n> --json closedAt`.

**Ready-state membership (Beads):**
```
bd ready --json -n 0 --readonly \
  | jq -e --arg id "<id>" '[.[]?,(.issues[]?)] | any(.id==$id)' >/dev/null && echo ready || echo not-ready
```

**Write attributes after a real run (Beads).** ONE command, carrying `$H` from the
content-hash recipe. Copy it as written — there is no variant that omits
`ready_content_hash`:
```
bd update <id> \
  --set-metadata review_status=<COMPLETE|INCOMPLETE> \
  --set-metadata review_missing=<one-line summary of what is missing, or "" when COMPLETE> \
  --set-metadata reviewed_at=<ISO8601> \
  --set-metadata ready_content_hash=$H
```

`review_missing` is REQUIRED on an INCOMPLETE review and must name what to fix — not the word
INCOMPLETE, not a dimension count. It is the only machine-readable record of the gap: the
pipeline HOLDS a bead against an unchanged INCOMPLETE verdict instead of re-running this
skill, so no later run regenerates the reason. Keep it to one line and avoid newlines and
quotes, which do not survive the attribute round-trip. Metadata is outside the content hash,
so writing it never invalidates the watermark.

`--set-metadata` merges into existing metadata, so this write leaves every other key on the
bead alone — including `wsjf`, which the `wsjf-scoring` workflow owns and this skill must never
touch. Do not reach for `--metadata`: it replaces the whole object and would drop them.

**Verify the write (step 7, Beads):**
```
bd show <id> --json --readonly \
  | jq -r 'if type=="array" then .[0] else (.issue // .) end | (.metadata // {})
           | "ready_content_hash=\(.ready_content_hash//"MISSING")"'
```
`MISSING`, or anything other than `$H`, means the write did not land — redo it.

**Post a comment:** Beads `bd comment add <id> --body "..."` · GitHub `gh issue comment <n> --body "..."`.

**GitHub state read/write:** read the latest `<!-- task-ready:state … -->` marker — or the
legacy `<!-- issue-ready:state … -->` spelling, whichever is more recent — from
`gh issue view <n> --json comments`; issue open/closed from `gh issue view <n> --json state`.
