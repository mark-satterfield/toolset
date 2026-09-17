---
name: beads-contract
description: >-
  The one authority on how this pipeline stores work on a Beads issue — what `bd show --json`
  actually returns, where acceptance criteria live (they are PROSE, and may sit on a parent
  Story or Epic), which metadata keys the pipeline owns, how to resolve a parent, and how the
  content fingerprint is computed. Ships a working CLI: resolve a Task's build contract with
  the provenance of every value, compute the fingerprint, and read or write the pipeline's
  metadata keys. Use whenever an agent reads or writes a bead — before asserting that a field
  exists, that criteria are missing, that a bead is stale, or that a metadata key is the right
  one. Never hand-roll `jq` against `bd`, and never restate the recipes below.
allowed-tools: [Bash]
---

# Beads Contract

Two defects reached production because agents each guessed how beads stores things.

1. **The content-hash recipe was written twice** — once as `jq` prose in
   `skills/task-ready/SKILL.md`, once in `ops/sdlc-automation/readiness.py`. The two copies
   disagreed about `labels`, so they disagreed about exactly the beads the rule existed for.
2. **Two work packages assumed acceptance criteria are a metadata key.** They are PROSE. They
   may live in the issue's own description, or in its parent Story or Epic. The requirement is
   that they EXIST somewhere — not that they occupy a field.

Prose read by a model is not deterministic. A script is. So the recipes live in
`scripts/beads-contract.py` and this document does not restate them — restating is what caused
defect 1. Where a fact has a canonical implementation, this document names it and stops.

## Run it

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/beads-contract/scripts/beads-contract.py" <command> [-C <repoPath>] ...
```

Every command prints ONE JSON object on stdout and reads `bd show --json --readonly` unless it
is a `metadata set`. `-C <repoPath>` runs `bd` from another repository. Exit status: `0` fine,
`2` the command refused (the object carries `error`), `3` only for `contract --require` when a
required part is missing.

| Command | Answers |
| --- | --- |
| `contract <id>` | The whole build contract a Task carries, plus resolved criteria, the gate keys, and what is `missing`. Add `--require` to exit 3 rather than report. |
| `criteria <id>` | The acceptance criteria and, critically, `sourceId` / `sourceField` / `searched` — WHERE each was found and everywhere that was looked. |
| `fingerprint <id>` | The content fingerprint, the stored `ready_content_hash`, and whether they agree. `--explain` prints the exact object hashed. |
| `fingerprint-batch [id ...]` | The same answer for MANY beads in one invocation. With `--records -` it fingerprints a sweep the caller already holds, costing no tracker call; otherwise it makes ONE `bd list` call, never one per bead. |
| `ancestors <id>` | The parent chain, nearest first, cycle-safe. |
| `record <id>` | The normalized record and the field names it ACTUALLY carries. |
| `metadata get <id> [key ...]` | Metadata, split by owning lane, with unrecognized keys named rather than hidden. |
| `metadata set <id> k=v ...` | Writes via `bd update --set-metadata`, refusing an unknown key or a malformed value, then reads back to verify. |
| `selftest` | Exercises the parent, prose, `--acceptance`-field and metadata paths against synthesised records. Changes nothing. |

`--records <file>` makes any read command work from a JSON array of records instead of the
tracker — how the parent and prose paths are exercised when no live bead has them. `--records -`
reads that array from **stdin**, which is how a caller hands over a sweep it already fetched.

### Fingerprinting a whole sweep

A caller assessing every bead in a pass already holds the records from its own `bd list`. It
should hand them over rather than have them fetched again:

```bash
bd list --json | python3 "${CLAUDE_PLUGIN_ROOT}/skills/beads-contract/scripts/beads-contract.py" \
  --records - fingerprint-batch
```

Stdout carries `fingerprints` — a plain `{id: fingerprint}` map — alongside the full per-bead
`results` (`found`, `fingerprint`, `stored`, `fresh`), `missing`, and `trackerCalls`. Naming ids
as arguments narrows it to those beads; naming none fingerprints every record supplied.

**Feeding the caller's own records back in is the correctness argument, not just the cheap one.**
`readiness.py` hashes `bd list` records; a re-fetch inside this script would hash `bd show`
records instead. Those payloads differ in exactly the fields that caused defect 1, so re-fetching
would reintroduce a second source of truth by the back door. Batch mode calls the same
`content_hash` as `fingerprint`, through the same `fingerprint_of` entry point — there is no
parallel implementation and no second recipe.

Because this is a command, it works for an agent with `tools: Bash` and no `Read` — `bead-writer`
is exactly that agent. **No agent should need to read a file or hand-roll `jq` to learn any of
this.**

## What `bd show --json` returns

**There is no fixed field list, and any number you have been told is wrong.** `bd` OMITS a
field the bead does not carry. Verified read-only across all 252 beads in the SkillSpoke
tracker: a single record carries **13 to 18 keys**, and the union across all of them is 23.

Always present (all 252): `id`, `title`, `status`, `priority`, `issue_type`, `revision`,
`created_at`, `updated_at`, `comment_count`, `dependency_count`, `dependent_count`.

Present only when set — the count is how many of the 252 carried it: `description` (250),
`metadata` (226), `owner` (181), `created_by` (181), `labels` (163), `notes` (154),
`external_ref` (78), `started_at` (8), `assignee` (6), **`parent` (4)**, `dependencies` (4),
`comments_omitted` (3), **`acceptance_criteria` (3)**, `defer_until` (1).

Two consequences worth stating outright:

- **`acceptance_criteria` IS a real top-level record field**, written by `bd create/update
  --acceptance`. It is a STRING, not an array. It is neither metadata nor description prose,
  and anything that looks only at those two is blind to it.
- **`parent` is absent on a bead with no parent**, so "no `parent` key" and "`parent` is empty"
  are the same fact. Never infer anything else from its absence.

Do not hard-code this list. `record <id>` reports what a given bead actually carries.

## Acceptance criteria are PROSE

This is the rule that WP-2 and WP-3 got wrong. Criteria are not a key/value pair and are not
meant to be. **The requirement is that they exist somewhere.** They are searched in this order,
and `criteria <id>` reports which one answered:

1. `metadata.acceptance_criteria` on the Task — a JSON array. A convenience for the build lane,
   never the evidence that criteria exist.
2. The `acceptance_criteria` record field on the Task — what `bd update --acceptance` writes.
3. The Task's own `description` prose.
4. Each ancestor in turn, **nearest first**, through the same three homes. A Story or Epic that
   states the criteria for the work beneath it has stated them for this Task.

Prose recognition is implemented in `criteria_in_text` and is not restated here: an
`Acceptance Criteria` heading (markdown or a bare labelled line) taking the bullets or prose
lines beneath it, and otherwise Given/When/Then sentences anywhere in the text.

**A Task is held for missing criteria only when all four came back empty.** `criteria <id>`
returns `searched` for exactly this reason — a hold has to say where it looked, or the person
reading it cannot tell a missing criterion from a missing lookup. Never report criteria as
missing without that list.

When criteria came from anywhere other than the Task's own metadata key, `inherited` is true
and the source travels with them, so a downstream phase can cite what it built against rather
than appearing to invent criteria.

## The metadata key namespace

`bd` metadata is flat `key=value` TEXT, so **every value is a string**: lists and the strategy
object are compact JSON. Metadata sits OUTSIDE the content fingerprint, which is what lets the
gate store its own verdict without invalidating it.

Build contract, written by the decomposition phase onto each Task, read back by
`ops/sdlc-automation/buildinput.py`:

| Key | Shape | Standing |
| --- | --- | --- |
| `spec_path` | one root-relative path | Either this or `spec_paths` is REQUIRED — with no spec there is no contract to build against |
| `spec_paths` | JSON array of paths | as above |
| `spec_sections` | JSON array of strings | navigation |
| `acceptance_criteria` | JSON array of strings | one home among several; never required, see above |
| `definition_of_done` | JSON array of strings | judged at the gates, which read the spec |
| `requirement_ids` | JSON array of strings | traceability |
| `surfaces` | JSON array, **or the literal `unknown`** | never required |
| `test_strategy` | JSON object, **or the literal `unknown`** | never required |

**`unknown` is not `[]`, and the difference is the whole point.** A null `surfaces` means nobody
ruled, and the phase falls back to its own lead; `[]` means somebody checked and the work crosses
no boundary, which SKIPS the phase outright. Handing `[]` to a Task whose spec never settled the
question skips a phase on a statement no one made. The exact literal, and only it, becomes null.

Readiness gate, written by `task-ready`: `review_status`, `review_missing`, `reviewed_at`,
`wsjf`, `wsjf_calculated_at`, `ready_content_hash`. Build lane: `build_state`. Elaboration lane:
`elaboration_state`, `elaboration_state_at`, `elaboration_state_cause`, `artifact_spec_path`,
`elab_key`, `elab_follows`, `decision_ids`.

**`elab_key` is the identity a re-elaboration matches on**, written once at the create and never
recomputed. A Story is keyed by the repository it covers, a Task by its repository and the slug
of its title. Without it a second run of the same Epic has nothing to match against and writes a
complete second set of Stories and Tasks beside the first. `elab_follows` names the Task a
follow-up Task replaces — set when the original was already built and therefore was not
rewritten. **`decision_ids` is the SAD entry tags the item was designed against**, as a compact
JSON list; it is how a changed architecture decision finds the work resting on it, and it holds
the SAD's own per-entry tags because those survive a rewording while a statement-derived id
does not.

WSJF rubrics (`epic-wsjf`, `task-wsjf`): the dimensions a score was built from —
`wsjf_rubric`, `wsjf_ubv`, `wsjf_tc`, `wsjf_rroe`, `wsjf_unblocks`, `wsjf_cod`, `wsjf_size`,
`wsjf_size_source`, `wsjf_size_task_days`, `wsjf_confidence`, `wsjf_value_from`. They are what
lets a Task INHERIT its Epic's value and an Epic roll its size up from its Tasks without
either one re-judging anything. Sequencing (`work-sequencing`): `seq_owned_blockers`, a
comma-separated id list of the blocking edges that pass created on the bead, and
`seq_owned_blockers_at`. The pass only ever withdraws an edge that list names, which is how a
hand-made edge survives it.

The script is the list: `metadata set` names every key it accepts when it refuses one.

`metadata set` refuses any key outside that namespace. A typo'd key is not a small mistake — it
is silently invisible to every reader, and the bead looks unset forever.

**Always `--set-metadata` (merges), never `--metadata` (replaces the whole object and drops every
key the write did not name).** `metadata set` uses the right one and reads back to verify.

## The content fingerprint

The staleness watermark. Its ONE implementation is `content_hash` in
`scripts/beads-contract.py`; `fingerprint <id> --explain` prints the exact object hashed. Do not
reproduce the recipe in prose, in `jq`, or in a second language.

What matters to a caller:

- It covers `title`, `description`, `issue_type` and `priority`, and nothing else. Six of the ten
  keys in the hashed object are null on every bead because `bd show` does not return them; they
  stay in the object because the digest is over its shape.
- **`labels` is nulled deliberately.** The pipeline writes `needs-correction` onto every held
  bead. If labels were hashed, RECORDING a hold would change the fingerprint, the bead would read
  as stale on the very next pass, and the sweep would re-buy the review it just held to avoid.
- Metadata, timestamps, status and comments are outside it, so storing a verdict never
  invalidates it.
- Criteria in the Task's OWN description ARE covered, because `description` is. Criteria on a
  PARENT are NOT — the fingerprint is over this bead's own record. Editing a parent's criteria
  does not make this Task stale; that is a real limitation, and it is about where the prose sits.

`ops/sdlc-automation/readiness.py` in the SkillSpoke repo holds the second copy that caused
defect 1. Until it calls this script, the two are a joint contract: **change it on both sides or
on neither.** Parity is verified, not assumed — `fingerprint` agrees with `readiness.content_hash`
byte for byte on live beads, labelled and unlabelled alike.

`fingerprint-batch` is what lets that copy go. `readiness.assess` runs per bead over an index
built from one `bd list` sweep, so per-bead `fingerprint` was never an option — it would have
added a subprocess and a `bd show` round-trip per bead to a pass that makes one tracker call.
Batch mode takes that sweep on stdin and answers for every bead at once, which removes the only
reason the second copy had to exist.

## Resolving a parent

`ancestors <id>` walks the record's own `parent` field upward, nearest first, stopping at a cycle.
That is the whole mechanism; there is no separate parent index and no dependency edge to consult.
`parent` is absent on a bead with no parent.

**A Story never gates a Task.** A Story is a roll-up parent for reporting and tracking; it is
never a dispatch precondition, and a Task with no parent is workable. Missing lineage is a note on
a verdict, never the verdict.

## Bug rules — standing, not negotiable

- **A bug is a REPORTING MECHANISM, not development work.** It records that something is wrong.
- **A bug is never parented**, so nothing walks its ancestor chain looking for criteria, a spec,
  or an Epic. It has no acceptance criteria and is not expected to.
- **A bug is never dispatched to a build composite.** `route-build` skips it by name rather than
  force-fitting it into `bug-fix`.
- **A bug is triaged by a PERSON** into an Epic, a Task, or a closure. That is a judgment call, not
  a routing rule, and no agent makes it. There is no triage composite to hand it to.

An agent that sends a bug to a readiness gate, a decomposition pass, or a build lane is itself the
defect. Report it and stop.

## Rules for the agent using this skill

- **Ask the CLI; do not reconstruct the answer.** No `bd show ... | jq` pipelines, no hand-written
  hashing, no assumptions about which fields exist.
- **Report provenance.** When you say criteria are missing, quote `searched`. When you use
  criteria, quote `sourceId` and `sourceField`.
- **Never restate a recipe from this document into another document.** Cite the script. The
  duplicate is what drifts, and it drifts in whichever copy is wrong.
- **Read-only unless the task is a write.** Every command except `metadata set` changes nothing.
