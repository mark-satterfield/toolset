---
name: task-ready
description: Completeness gate for one issue — decides whether it carries what someone needs in order to work it, and records that verdict on the issue itself. Quality control on a Task's CONTENT, run before a Task is worked. Resolves the issue from Beads (primary) or GitHub (backup), reuses the stored review verdict while the content is unchanged, reruns the review when it is missing or stale, records missing lineage or a missing stack as a note on the verdict rather than as a refusal, stores the verdict as the readiness gate keys the beads-contract metadata schema defines, and emits one fixed contract. It judges content completeness and nothing else — not dependencies, not blockers, not priority. Triggers on /task-ready or "is this ready to implement", "is this issue complete", "prepare this issue".
---

# Task Ready — Content Completeness Gate

Decide whether ONE issue carries what someone needs in order to work it, say what is
missing when it does not, and persist that decision on the issue so the next run is cheap.
The source of truth for an issue's state is **Beads** (primary) or **GitHub** (backup).
Throughout this skill, "the tracker" means whichever one resolved the issue. Anything that
applies to Beads applies to GitHub too, **except** storing attributes on the issue — GitHub
has no custom fields, so it uses the marker-comment fallback described below.

## What this skill is for

**Quality control on a Task's CONTENT, before the Task is worked.** It
runs over a candidate before anyone works it and answers one question: does this Task say enough for someone to work it,
and if not, what is missing. That is its whole purpose, and running it there is what keeps
an incomplete Task from being dispatched.

**It is NOT an eligibility gate.** Eligibility means dependencies and blockers. This skill
has never consulted either, and both belong entirely to whatever decides eligibility.

**It does NOT score.** WSJF for a Task is computed outside this skill, by the sequencing
capability, under the `agent-teams-workforce:wsjf` skill's Task-level rubric — value and time criticality inherited from the
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
Review: [<review status> / <review status> — n dimensions need attention / n/a]
Comments posted: [n]
```

- **`Ready`** is `TRUE` only when **both** hold: `Pipeline result` is `READY` **and** the
  tracker reports the issue in a *ready* state — for Beads that is `atw-bd ready` membership
  (status `open`, no active blockers, not deferred/hooked), for GitHub that is state
  `OPEN`. Status `open` alone is not enough; a blocked or closed issue is never `Ready`.
  In all other cases `Ready` is `FALSE`.
- **`Pipeline result`** describes the review verdict only (it does not fold in blocker or
  closed state):
  - `READY` — the review status is the schema's `REVIEW_COMPLETE` value.
  - `INCOMPLETE` — the review found gaps (the schema's `REVIEW_INCOMPLETE` value).
- **`<review status>`** is a `ReviewStatus` value from the beads-contract metadata schema
  (`skills/beads-contract/schemas/bead-metadata.schema.json`), as stored on or written to the issue.
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

The skill persists current-state attributes so a later run can skip work: the **readiness
gate keys**. Their one definition — each key's name, value type, allowed values and when it is
required — is the `GATE_KEYS` group of the beads-contract metadata schema,
`skills/beads-contract/schemas/bead-metadata.schema.json` (every property whose `x-groups`
names `GATE_KEYS`). Take key names and values from there; this file does not restate them. In
the schema's terms they hold the review status (a `ReviewStatus` value), the one-line summary of
what is missing (required on an incomplete review, empty on a complete one), the review
timestamp, and the content hash watermark (`CONTENT_HASH_KEY`). On **Beads** they are read and
written through the beads-contract CLI (`metadata get` / `metadata set`, see Recipes).

**The `GATE_KEYS` group is the whole of what this skill writes.** It writes no other metadata,
and it never touches a key of the schema's `WSJF_KEYS` group — reading, writing, or clearing —
because it does not own them. Metadata is overwritten each real run (it is current state, not
history).

On **GitHub** (no custom fields) the same gate keys are written into one machine-readable
marker comment instead, one `key=value` line per `GATE_KEYS` key, exactly the pairs
`metadata set` would write on Beads:

```
<!-- task-ready:state
<GATE_KEYS key>=<value>
...
-->
```

**Both spellings are read; only `task-ready:state` is written.** This skill used to be
called `issue-ready`, and markers it wrote then — `<!-- issue-ready:state … -->` — sit in
live GitHub issue bodies today. Accept either header when reading, take the most recent
marker of either spelling, and always write the `task-ready:state` spelling.

Read state from the most recent such marker; write a fresh marker each real run. Every
marker carries the `CONTENT_HASH_KEY` key set to `$H` — a marker written without it is the same defect as
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
carry no value: the first five are not returned by `atw-bd show --json` at all, and `labels` is
nulled deliberately (see below). They stay in the object because the digest is over its shape.

**`atw-bd show --json` has no fixed field list.** It OMITS any field the bead does not carry, so a
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
  Editing them changes the fingerprint, so the next run reviews the Task again.

  Criteria that live ONLY on the parent Story or Epic are NOT covered, because the
  fingerprint is computed over this issue's own record and nothing else. Editing a parent's
  criteria does not make this issue stale; to have it reviewed again, edit this issue's own
  description.

  Criteria mirrored into the build contract's acceptance-criteria METADATA key (`KEY_ACCEPTANCE_CRITERIA` in the schema) are not covered either, for
  the separate reason that metadata is outside the fingerprint entirely (which is what lets
  this skill store its own verdict without invalidating it). That key is a convenience for
  the build lane, never the evidence that criteria exist.
- **`labels` is nulled.** Adding or removing a label never changes the fingerprint.

Never metadata, timestamps, status, or comments — so storing a verdict never invalidates it.

**THE RECIPE HAS ONE IMPLEMENTATION: `content_hash` in the `agent-teams-workforce:beads-contract`
skill.** This file carries no copy; anything that compares fingerprints runs
`beads-contract.py`. Change the recipe in the one place that implements it.

- **Fresh** — the stored `CONTENT_HASH_KEY` value exists and equals the current content hash → reuse the
  stored verdict; rerun nothing; post nothing.
- **Stale or missing** — no stored hash, or it differs → rerun the review, overwrite the
  stored attributes, post the comments.

**One hash, computed once.** The value compared and the value stored are the same string
from the same command, computed once at step 3 and held in `$H` for the rest of the
invocation. A stored hash that disagrees with the compared hash is worse than none: it
makes a changed issue look fresh. Never recompute after a write, never truncate to a
different length, never hash a different field set.

## Algorithm

1. **Resolve the issue.** Beads ID (e.g. `tst-123`) → `atw-bd show <id> --json`. GitHub number
   → `gh issue view <n> --json ...`. Inline text → assess directly, store nothing, post
   nothing (chat-only result). If the lookup returns "not found" → `Pipeline result:
   MISSING`, emit contract, stop. If a `bd`/`gh` call errors → `Pipeline result: ERROR`,
   emit contract, stop.
2. **Closed → return stored state, recompute nothing.** If the status is `closed`, do not
   run the review and do not check staleness — a closed issue is never recomputed. Report
   the attributes already on the issue: `Review` = the stored review status (or `n/a` if it
   was never reviewed); `Pipeline result` = `READY` when the stored review status is
   `REVIEW_COMPLETE`, otherwise `INCOMPLETE`. `Ready: FALSE` (a closed issue is never ready).
   `Comments posted: 0`. After the contract block, append one chat-only line — `Issue <id>
   was closed on <closed_at>.` — using the issue's close date; never post it to the
   tracker. Emit, stop.
3. **Read stored state** (the `GATE_KEYS` values, `.gate` in `metadata get`) and **compute the current content hash into `$H`** — always,
   before anything else runs, using the Content hash recipe verbatim.

   Compute it even when there is no stored hash to compare against. `$H` is what steps 4
   and 6 **write**; the comparison is its second use, not its only one. Short-circuiting
   on "no stored hash, so obviously stale — skip the hash and go review" is the single
   failure this whole attribute exists to prevent: the run then has nothing to store, the
   next run again finds no hash, and every sweep pays for a full review forever. If you
   took that shortcut, you have broken the skill.
4. **Read the lineage and the stack — as CONTEXT, never as a refusal.** Read the issue's
   own type and its parents (Hierarchy recipe), and the stack the Task states (Stack
   recipe). Record what you found and carry it into the review as a note. Then continue to
   step 5 no matter what it said.

   **The repository comes from the stack the Task states, through the matrix.** A Task
   states what it builds with the matrix's ids, in its `matrix_elements` key: its stack,
   its components and its shared capabilities. The repository is the `repository` of that
   stack, which `atw-matrix node stack:<id>` returns. It is not read from the wording of
   the Task's title, description or notes, and not taken from the parent Story or Epic.

   **A Story never gates a Task, and a stack is not this gate's precondition.** This step
   refuses no Task for lacking a parent Story, no Story for lacking an Epic, and no Task
   that states no stack. A Story is a **roll-up parent for reporting and tracking**; it
   never decides whether a Task can be worked. Whether a Task with no stack can be built
   is ruled where the build opens its workspace. Refusing on either of them here made this
   gate unable to clear anything.

   So: missing lineage, a Task that states no stack, and a stack id the matrix holds no
   entry for are **notes on the verdict**, never the verdict. Append them to whatever
   `Review` reports, e.g. `<review status> (note: no parent Story)` or
   `<review status> — 2 dimensions need attention (note: the Task states no stack)`.
   They never set `Pipeline result` and never skip the review.

   **Provenance is settled upstream, not re-adjudicated here.** A Task with no parent Epic
   or PRD behind it is not legitimate work — that is true, and it is enforced where such a
   Task is CREATED. This gate's job is content completeness: does this Task say enough to
   be worked. Re-litigating where an issue came from, at gate time, on a bead that already
   exists, blocks the queue and repairs nothing.

   **Bugs do not come here.** A bug is a reporting mechanism that a person triages into an
   Epic, a Task, or a closure; it has no acceptance criteria. A caller that sends one is the
   defect. Report `Pipeline result: INCOMPLETE` with
   `Review: <the REVIEW_INCOMPLETE value> — a bug is triaged by a person, not gated here` and
   write nothing.

5. **Decide freshness.** Fresh = stored hash exists and equals `$H`.
   - **Fresh:** reuse the stored verdict. Review status `REVIEW_COMPLETE` → `Pipeline result:
     READY`; review status `REVIEW_INCOMPLETE` → `Pipeline result: INCOMPLETE`, and append the
     stored missing summary to the `Review` line so the reused verdict still says what is
     missing. Rerun nothing. `Comments posted: 0`. Go to step 8.
   - **Stale/missing:** go to step 6.
6. **Run review** (the `task-review` skill) against the issue. Post the review comment
   (Audit Trail). Then run the **review write** in Recipes as written — every `GATE_KEYS`
   key, the content hash watermark set to `$H`, in ONE `metadata set`. The keys land together
   or the run has failed; a write that sets the status without the hash is the defect, not a
   partial success.

   `Pipeline result` is then `READY` if the review status is `REVIEW_COMPLETE`, otherwise
   `INCOMPLETE`. Post the ready-declaration comment only when the review was complete.

   **An incomplete verdict MUST carry what is missing, in the missing-summary gate key.**
   While the content hash is unchanged, step 5 reuses the stored verdict and reruns nothing,
   and the stored missing summary is the only record of what to fix. Summarize the review's
   findings in one line — the missing acceptance criteria, the unresolved dependency, the
   absent scope — and write it. On a complete review write it empty (the schema states both
   rules).
7. **Verify the write landed.** `metadata set` reads the written values back into its
   `verified` object; confirm the `CONTENT_HASH_KEY` value there is present and equals `$H`,
   alongside the review status and timestamp. If the hash is absent or different, the write did not land: redo it and
   read back again. Never emit the contract on an unverified write. A run that reports
   `READY` with no stored hash has thrown away everything it just paid for and guarantees
   the next run reruns it.
8. **Compute `Ready`.** `Ready = (Pipeline result == READY) AND tracker-ready-state`.
   Tracker-ready-state: Beads → issue appears in `atw-bd ready`; GitHub → issue state `OPEN`.
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

  [what was found: no parent Story, a parent Story with no Epic, a Task that states no
  stack, or a stack id the matrix holds no entry for]

  Recorded as context, not as a refusal. A Story is a roll-up parent for reporting and
  tracking and never gates whether this can be worked; the repository this work lands in
  is the repository of the stack the Task states, as the matrix returns it. The review
  below ran as normal.
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

Beads commands run read-only where possible (`--readonly`); writes use `atw-bd update`. The
`jq` selectors tolerate both array and `{issue:…}`/flat shapes and missing keys.

**Content hash (Beads)** — capture it into `$H`; this is the only place the hash is
computed, and both the freshness comparison and the write use `$H`:
```
H=$(python3 "${CLAUDE_PLUGIN_ROOT}/skills/beads-contract/scripts/beads-contract.py" \
      fingerprint <id> | jq -r .fingerprint)
```

The recipe is not written down here. `content_hash` in `beads-contract.py` is the single
implementation, the
`agent-teams-workforce:beads-contract` skill documents what it covers and why, and
`fingerprint <id> --explain` prints the exact object hashed when you need to see it. Do not
reconstruct the pipeline from this file, and do not paste a `jq` version back in.

The same command also reports the stored watermark and whether it is still fresh, so step 5's
comparison can read `.stored` and `.fresh` from one invocation rather than re-deriving them.

**Content hash (GitHub):** GitHub is the BACKUP tracker with a different record shape, and
nothing else computes this digest, so it is stated inline:
```
H=$(gh issue view <n> --json title,body,labels \
  | jq -S '{title,body,labels:[.labels[].name]}' \
  | shasum -a 256 | cut -c1-16)
```

**Read stored state (Beads):** the `.gate` object holds every `GATE_KEYS` key the bead carries
(an absent key was never written):
```
python3 "${CLAUDE_PLUGIN_ROOT}/skills/beads-contract/scripts/beads-contract.py" metadata get <id> \
  | jq '.gate'
```

**Hierarchy (Beads)** — the issue's own type and its parent chain. Two reads: the issue,
then its parent:
```
atw-bd show <id> --json --readonly \
  | jq -r 'if type=="array" then .[0] else (.issue // .) end
           | "type=\(.issue_type//"")\nparent=\(.parent//"")"'
# then, for a non-empty parent:
atw-bd show <parent> --json --readonly \
  | jq -r 'if type=="array" then .[0] else (.issue // .) end
           | "parent_type=\(.issue_type//"")\ngrandparent=\(.parent//"")"'
# and for a task, one more read of <grandparent> for grandparent_type.
```

**Stack and repository (Beads)** — the ids the Task states, then the stack's repository
from the matrix. `matrix_elements` is a `CONTRACT_KEYS` key of the beads-contract metadata
schema, and `contract <id>` returns the contract the Task carries:
```
python3 "${CLAUDE_PLUGIN_ROOT}/skills/beads-contract/scripts/beads-contract.py" contract <id>
# then, for the id among them that begins with stack: —
"${CLAUDE_PLUGIN_ROOT}/bin/atw-matrix" node stack:<id> | jq -r '.entry.repository // ""'
```
A matrix read needs no role. **A Task that states no stack, or a stack id the matrix holds
no entry for, does NOT fail the gate** — it is recorded as a note on the verdict and the
review runs, exactly as step 4 says. There is no path in this skill on which a missing
stack sets `Pipeline result`. Nothing here reads a repository out of the Task's text or off
its parent Story or Epic.

**Status / closed check (Beads):**
```
atw-bd show <id> --json --readonly \
  | jq -r 'if type=="array" then .[0] else (.issue // .) end | .status'
```

**Close date (Beads):** from the same `atw-bd show --json`, read `.closed_at`; if absent, fall
back to `.updated_at`. **GitHub:** `gh issue view <n> --json closedAt`.

**Ready-state membership (Beads):**
```
atw-bd ready --json -n 0 --readonly \
  | jq -e --arg id "<id>" '[.[]?,(.issues[]?)] | any(.id==$id)' >/dev/null && echo ready || echo not-ready
```

**Write attributes after a real run (Beads).** ONE `metadata set` naming every key of the
schema's `GATE_KEYS` group, each as `<key>=<value>` with the key name and value rule the schema
gives it, and the `CONTENT_HASH_KEY` key set to `$H` from the content-hash recipe. There is no
variant that omits the content hash:
```
python3 "${CLAUDE_PLUGIN_ROOT}/skills/beads-contract/scripts/beads-contract.py" metadata set <id> \
  <GATE_KEYS key>=<value> ...
```

The missing summary is REQUIRED on an incomplete review and must name what to fix — not the
review status, not a dimension count. It is the only machine-readable record of the gap: while
the content hash is unchanged the stored verdict is reused and no later run regenerates the
reason. Keep it to one line and avoid newlines and quotes, which do not survive the attribute
round-trip. Metadata is outside the content hash, so writing it never invalidates the watermark.

`metadata set` merges into existing metadata (it writes with `--set-metadata`), so this write
leaves every other key on the bead alone — including the `WSJF_KEYS` group, which the
`wsjf-scoring` workflow owns and this skill must never touch. Never write gate keys with
`atw-bd update --metadata`: it replaces the whole object and would drop them.

**Verify the write (step 7, Beads):** read `.verified` from the `metadata set` result. A
`CONTENT_HASH_KEY` value that is absent, or anything other than `$H`, means the write did not
land — redo it.

**Post a comment:** Beads `atw-bd comment add <id> --body "..."` · GitHub `gh issue comment <n> --body "..."`.

**GitHub state read/write:** read the latest `<!-- task-ready:state … -->` marker — or the
legacy `<!-- issue-ready:state … -->` spelling, whichever is more recent — from
`gh issue view <n> --json comments`; issue open/closed from `gh issue view <n> --json state`.
