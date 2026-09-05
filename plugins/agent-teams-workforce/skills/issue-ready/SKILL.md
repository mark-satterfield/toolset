---
name: issue-ready
description: Readiness gate for any issue — decides whether it is ready to implement and records the verdict on the issue itself. Resolves the issue from Beads (primary) or GitHub (backup), reuses the stored review status and WSJF score when fresh, reruns review then scoring only when missing or stale, stores wsjf, wsjf_calculated_at, review_status, reviewed_at as issue attributes, and emits one fixed contract. Triggers on /issue-ready or "is this ready to implement", "run the pipeline", "prepare this issue".
---

# Issue Ready — Readiness Gate

Decide whether one issue is ready to implement, and persist that decision on the issue
so the next run is cheap. The source of truth for an issue's state is **Beads** (primary)
or **GitHub** (backup). Throughout this skill, "the tracker" means whichever one resolved
the issue. Anything that applies to Beads applies to GitHub too, **except** storing
attributes on the issue — GitHub has no custom fields, so it uses the marker-comment
fallback described below.

This skill does two things the old version did not: it returns a hard `Ready` boolean,
and it **only does work when work is needed** — when the review or score is missing or
stale. When the stored values are current, it reuses them and reruns nothing.

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
WSJF: [score / "not scored — incomplete" / n/a]
Comments posted: [n]
```

- **`Ready`** is `TRUE` only when **both** hold: `Pipeline result` is `READY` **and** the
  tracker reports the issue in a *ready* state — for Beads that is `bd ready` membership
  (status `open`, no active blockers, not deferred/hooked), for GitHub that is state
  `OPEN`. Status `open` alone is not enough; a blocked or closed issue is never `Ready`.
  In all other cases `Ready` is `FALSE`.
- **`Pipeline result`** describes the review+score verdict only (it does not fold in
  blocker or closed state):
  - `READY` — review COMPLETE and a WSJF score exists.
  - `INCOMPLETE` — review found gaps; not scored.
  - `MISSING` — no such issue in the tracker.
  - `ERROR` — a `bd`/`gh` call failed or the input could not be resolved.
- A **closed** issue is never recomputed: it reports the verdict already stored on it
  (e.g. a stored `READY` stays `READY`) with `Ready: FALSE`. See Algorithm step 2.
- For `MISSING` / `ERROR`, fill `Review` and `WSJF` with `n/a` and `Comments posted: 0`.
  Never switch to a different response shape.

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
| `reviewed_at` | ISO 8601 timestamp of the last review |
| `wsjf` | numeric WSJF score (absent until review is COMPLETE) |
| `wsjf_calculated_at` | ISO 8601 timestamp of the last scoring |
| `ready_content_hash` | fingerprint of the issue's content at the last run — the staleness watermark |

Metadata is overwritten each real run (it is current state, not history). WSJF lives here
now, **not** as a note — nothing else consumes the old `wsjf_score` note.

On **GitHub** (no custom fields) the same keys are written into one machine-readable
marker comment instead:

```
<!-- issue-ready:state
review_status=COMPLETE
reviewed_at=2026-06-30T12:00:00Z
wsjf=8.75
wsjf_calculated_at=2026-06-30T12:00:00Z
ready_content_hash=ab12cd34ef56a7b8
-->
```

Read state from the most recent such marker; write a fresh marker each real run. Every
marker carries `ready_content_hash=$H` — a marker written without it is the same defect as
a Beads write that omits it, and step 7 verifies GitHub by re-reading the marker just as
it verifies Beads by re-reading the metadata. On the score-only path, carry the stored
`review_status` / `reviewed_at` forward into the new marker unchanged rather than
restamping them.

## Staleness — the reason work is skipped

The concept: **only run review and scoring when missing or stale; otherwise return the
values already on the issue.** Freshness is decided by a content fingerprint, not by the
tracker's `updated_at` (which the skill's own writes would bump, falsely invalidating the
cache). The fingerprint covers only substantive content (title, description, acceptance,
design, type, priority, labels, dependencies) — never metadata, timestamps, status, or
comments. See Recipes for the exact hashing command.

- **Fresh** — `ready_content_hash` exists and equals the current content hash → reuse the
  stored verdict; rerun nothing; post nothing.
- **Stale or missing** — no stored hash, or it differs → rerun (review, then score if the
  review is COMPLETE), overwrite the stored attributes, post the comments.

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
   run review or scoring and do not check staleness — a closed issue is never recomputed.
   Report the attributes already on the issue: `Review` = stored `review_status` (or `n/a`
   if it was never reviewed); `WSJF` = stored `wsjf` (or `not scored`); `Pipeline result`
   = `READY` when the stored review is `COMPLETE` and `wsjf` is present, otherwise
   `INCOMPLETE`. `Ready: FALSE` (a closed issue is never ready). `Comments posted: 0`.
   After the contract block, append one chat-only line — `Issue <id> was closed on
   <closed_at>.` — using the issue's close date; never post it to the tracker. Emit, stop.
3. **Read stored state** (`review_status`, `reviewed_at`, `wsjf`, `wsjf_calculated_at`,
   `ready_content_hash`) and **compute the current content hash into `$H`** — always,
   before anything else runs, using the Content hash recipe verbatim.

   Compute it even when there is no stored hash to compare against. `$H` is what steps 5
   and 6 **write**; the comparison is its second use, not its only one. Short-circuiting
   on "no stored hash, so obviously stale — skip the hash and go review" is the single
   failure this whole attribute exists to prevent: the run then has nothing to store, the
   next run again finds no hash, and every sweep pays for a full review and a full
   scoring session forever. If you took that shortcut, you have broken the skill.
4. **Decide freshness.** Fresh = stored hash exists and equals `$H`.
   - **Fresh:** reuse stored values. If `review_status=COMPLETE` and `wsjf` present →
     `Pipeline result: READY`. If `review_status=INCOMPLETE` → `Pipeline result:
     INCOMPLETE`. Rerun nothing. `Comments posted: 0`.
   - **Fresh but `review_status=COMPLETE` with NO `wsjf`:** do not reuse — **go to step
     6** and score. The review is current, so rerunning it would buy nothing; the score
     is the only thing missing. This state is reachable and it is not rare: step 5 writes
     `review_status` and the hash, step 6 writes `wsjf`, and a session that dies between
     them — a spend or session limit, most often — leaves exactly this. Reusing it would
     report a verdict with no score, the caller would find the attributes still
     incomplete and dispatch this skill again, and it would reuse again: a permanent loop
     costing a full session every sweep and never able to end.
   - **Stale/missing:** go to step 5.
5. **Run review** (the `issue-review` skill) against the issue. Post the review comment
   (Audit Trail). Then run the **review write** in Recipes as written — `review_status`,
   `reviewed_at` and `ready_content_hash=$H` in ONE `bd update`. The three keys land
   together or the run has failed; a write that sets the status without the hash is the
   defect, not a partial success.
   - If review is **INCOMPLETE** → `Pipeline result: INCOMPLETE`; do not score. Skip to
     step 7.
   - If review is **COMPLETE** → continue.
6. **Run scoring** (the `wsjf` skill) against the issue. Post the WSJF comment and the
   ready-declaration comment. Then run the **score write** in Recipes — `wsjf`,
   `wsjf_calculated_at` and `ready_content_hash=$H` in one `bd update`. Re-setting the
   hash to the same value is idempotent; it is what leaves a complete attribute set on
   the step-4 path where the review was already fresh and only the score was missing.
   `Pipeline result: READY`.
7. **Verify the write landed.** Read the attributes back (the verify recipe) and confirm
   `ready_content_hash` is present and equals `$H`, alongside `review_status` /
   `reviewed_at` — and `wsjf` / `wsjf_calculated_at` when step 6 ran. If the hash is
   absent or different, the write did not land: redo it and read back again. Never emit
   the contract on an unverified write. A run that reports `READY` with no stored hash
   has thrown away everything it just paid for and guarantees the next run reruns it.
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
  ## Issue Review — [ISO 8601 timestamp]

  [full issue-review output]
  ```
  ```
  ## WSJF Score — [ISO 8601 timestamp]

  [full wsjf output]
  ```
  ```
  ## Ready for Implementation — [ISO 8601 timestamp]

  Passed completeness review and scored. WSJF: [score] (CoD [CoD] / Size [size]).
  ```

## Recipes

Beads commands run read-only where possible (`--readonly`); writes use `bd update`. The
`jq` selectors tolerate both array and `{issue:…}`/flat shapes and missing keys.

**Content hash (Beads)** — capture it into `$H`; this is the only place the hash is
computed, and both the freshness comparison and every write use `$H`:
```
H=$(bd show <id> --json --readonly \
  | jq -S 'if type=="array" then .[0] else (.issue // .) end
           | {title,description,acceptance,design,type,issue_type,priority,labels,dependencies,deps}' \
  | shasum -a 256 | cut -c1-16)
```

**Content hash (GitHub):**
```
H=$(gh issue view <n> --json title,body,labels \
  | jq -S '{title,body,labels:[.labels[].name]}' \
  | shasum -a 256 | cut -c1-16)
```

**Read stored state (Beads):**
```
bd show <id> --json --readonly \
  | jq -r 'if type=="array" then .[0] else (.issue // .) end | (.metadata // {})
           | "review_status=\(.review_status//"")\nreviewed_at=\(.reviewed_at//"")\nwsjf=\(.wsjf//"")\nwsjf_calculated_at=\(.wsjf_calculated_at//"")\nready_content_hash=\(.ready_content_hash//"")"'
```

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

**Write attributes after a real run (Beads).** Two commands, neither optional in its
step, both carrying `$H` from the content-hash recipe. Copy them as written — there is no
variant of either that omits `ready_content_hash`.

Review write (step 5 — the whole write when the review is INCOMPLETE):
```
bd update <id> \
  --set-metadata review_status=<COMPLETE|INCOMPLETE> \
  --set-metadata reviewed_at=<ISO8601> \
  --set-metadata ready_content_hash=$H
```

Score write (step 6):
```
bd update <id> \
  --set-metadata wsjf=<score> \
  --set-metadata wsjf_calculated_at=<ISO8601> \
  --set-metadata ready_content_hash=$H
```

`--set-metadata` merges into existing metadata, so the score write leaves `review_status`
and `reviewed_at` alone — never bump `reviewed_at` for a review that did not rerun. Do
not reach for `--metadata`: it replaces the whole object and would drop the other keys.

**Verify the write (step 7, Beads):**
```
bd show <id> --json --readonly \
  | jq -r 'if type=="array" then .[0] else (.issue // .) end | (.metadata // {})
           | "ready_content_hash=\(.ready_content_hash//"MISSING")"'
```
`MISSING`, or anything other than `$H`, means the write did not land — redo it.

**Post a comment:** Beads `bd comment add <id> --body "..."` · GitHub `gh issue comment <n> --body "..."`.

**GitHub state read/write:** read the latest `<!-- issue-ready:state … -->` marker from
`gh issue view <n> --json comments`; issue open/closed from `gh issue view <n> --json state`.
