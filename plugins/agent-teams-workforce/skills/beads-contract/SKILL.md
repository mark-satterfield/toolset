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

The recipes for how beads stores work live in `scripts/beads-contract.py`, and this document
does not restate them. Acceptance criteria are PROSE: they may live in the issue's own
description, or in its parent Story or Epic, and the requirement is that they EXIST somewhere,
not that they occupy a field. Where a fact has a canonical implementation, this document names
it and stops.

## Which database: always the central one

Pipeline beads — every Epic, Story and Task the pipeline files, and every bead an agent reads
or writes for its work — live in ONE database: the central beads database of the control
repository (its environment variable is defined by the `DriverEnvironment` of
`schemas/driver-surface.schema.json` in the `agent-teams-workforce:pipeline-contracts` skill;
read it there). It is read and written there wherever the actor runs. A
build or bug session runs inside a Task's own repository or worktree, and a plain `bd` there
reaches THAT repository's database, where the central bead does not exist.

So every `bd` command goes through **`atw-bd`**, the plugin's command on the Bash tool's
`PATH`: `atw-bd show <id> --json`, `atw-bd update <id> --claim`, `atw-bd close <id>`,
`atw-bd note <id> "..."`, `atw-bd dep add <a> <b>`, `atw-bd create ...`. It takes `bd`'s own
arguments, runs them against the central database, and refuses `-C`, `--db` and the other
flags that would name another. A script runs it as `beads-contract.py bd <arguments>`; every
other command of this CLI uses the central database too. Never run a plain `bd` for a
pipeline bead.

**A bead is edited in the database it was filed in.** A bead filed in a fleet repository's
own database is copied into the central one by the fleet sync (`bd repo sync`), which is
one-way and copies the fleet copy over the central one every time it runs: a central edit to
that bead is overwritten (title, status, notes). `atw-bd` and this CLI apply the rule
themselves — a write to a fleet-filed bead runs in its own repository's database — so the
caller names only the bead.

## Reading beads

Beads is read live through `bd`, and only through `bd`. `.beads/issues.jsonl` is never read:
`bd` auto-exports only after a state-changing command, at most once per `export.interval`
(60 s), and the export can be blocked, so it lags the tracker. A live read that fails is
retried with backoff.

## Run it

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/beads-contract/scripts/beads-contract.py" <command> ...
```

Every command prints ONE JSON object on stdout and reads `bd show --json --readonly` unless it
is a `metadata set`, a `cds-audit` or `bd`. `-C <path>` names the central repository when
it is not the control repository the `pipeline-contracts` driver environment names. Exit status: `0` fine, `2` the command refused (the object
carries `error`).

| Command | Answers |
| --- | --- |
| `contract <id>` | The whole build contract a Task carries, plus resolved criteria, the gate keys, and what is `missing`. `bead` in the result is the build composite's `bead` argument — id, title, description, the contract and the Task's `story` (id, title), whose branch the Task is built on — passed as-is. |
| `criteria <id>` | The acceptance criteria and, critically, `sourceId` / `sourceField` / `searched` — WHERE each was found and everywhere that was looked. |
| `fingerprint <id>` | The content fingerprint, the stored readiness fingerprint (the schema's `CONTENT_HASH_KEY`), and whether they agree. `--scope` picks one of the schema's `HashScope` values; `--explain` prints the exact object hashed. |
| `fingerprint-batch [id ...]` | The same answer, in either `--scope`, for MANY beads in one invocation. With `--records -` it fingerprints a sweep the caller already holds, costing no tracker call; otherwise it makes ONE `bd list` call, never one per bead. |
| `ancestors <id>` | The parent chain, nearest first, cycle-safe. |
| `record <id>` | The normalized record and the field names it ACTUALLY carries. |
| `metadata get <id> [key ...]` | Metadata, split by owning lane, with unrecognized keys named rather than hidden. |
| `metadata set <id> k=v ...` | Writes via `bd update --set-metadata`, then reads the values back into `verified`. |
| `bd <bd arguments ...>` | Runs any `bd` command against the central database (a write to a fleet-filed bead against its own) and prints what `bd` prints. `atw-bd` is this command. |
| `cds-audit <id> '<cdsAudit JSON>'` | Writes a `web-ui` Task's cds audit keys (the schema's `CDS_AUDIT_KEYS` group) from `task-to-deploy`'s `cdsAudit` result, refusing a verdict outside the schema's `CdsAuditVerdict` values; reads them back like `metadata set`. `metadata get` shows them under `cdsAudit`. |

`--records <file>` makes any read command work from a JSON array of records instead of the
tracker — how the parent and prose paths are exercised when no live bead has them. `--records -`
reads that array from **stdin**, which is how a caller hands over a sweep it already fetched.

### Fingerprinting a whole sweep

A caller assessing every bead in a pass already holds the records from its own `bd list`. It
should hand them over rather than have them fetched again:

```bash
atw-bd list --json | python3 "${CLAUDE_PLUGIN_ROOT}/skills/beads-contract/scripts/beads-contract.py" \
  --records - fingerprint-batch
```

Stdout carries `fingerprints` — a plain `{id: fingerprint}` map — alongside the full per-bead
`results` (`found`, `fingerprint`, `stored`, `fresh`), `missing`, and `trackerCalls`. Naming ids
as arguments narrows it to those beads; naming none fingerprints every record supplied.

A caller holding `bd list` records hashes those; a re-fetch inside this script would hash `bd show`
records instead, which differ in some fields. Batch mode calls the same
`content_hash` as `fingerprint`, through the same `fingerprint_of` entry point — there is no
parallel implementation and no second recipe.

Because this is a command, it works for an agent with `tools: Bash` and no `Read`. **No agent should need to read a file or hand-roll `jq` to learn any of
this.**

## What `bd show --json` returns

**There is no fixed field list, and any number you have been told is wrong.** `bd` OMITS a
field the bead does not carry. Observed across a tracker of 252 beads: a single record carries **13 to 18 keys**, and the
union across all of them is 23.

Always present (on all 252): `id`, `title`, `status`, `priority`, `issue_type`, `revision`,
`created_at`, `updated_at`, `comment_count`, `dependency_count`, `dependent_count`.

Present only when set — the count is how many of the 252 carried it: `description` (250),
`metadata` (226), `owner` (181), `created_by` (181), `labels` (163), `notes` (154),
`external_ref` (78), `started_at` (8), `assignee` (6), **`parent` (4)**, `dependencies` (4),
`comments_omitted` (3), **the schema's `ACCEPTANCE_FIELD` (3)**, `defer_until` (1).

Two consequences worth stating outright:

- **The schema's `ACCEPTANCE_FIELD` IS a real top-level record field**, written by `bd create/update
  --acceptance`. It is a STRING, not an array. It is neither metadata nor description prose,
  and anything that looks only at those two is blind to it.
- **`parent` is absent on a bead with no parent**, so "no `parent` key" and "`parent` is empty"
  are the same fact. Never infer anything else from its absence.

Do not hard-code this list. `record <id>` reports what a given bead actually carries.

## Acceptance criteria are PROSE

This is the rule that WP-2 and WP-3 got wrong. Criteria are not a key/value pair and are not
meant to be. **The requirement is that they exist somewhere.** They are searched in the order
of the schema's three criteria sources (`SOURCE_METADATA`, `SOURCE_ACCEPTANCE`,
`SOURCE_DESCRIPTION` in `x-constants`) on the Task, then on each ancestor in turn, **nearest
first**, through the same three homes; `criteria <id>` reports which one answered in
`sourceField`. The metadata source is a convenience for the build lane, never the evidence that
criteria exist. A Story or Epic that states the criteria for the work beneath it has stated them
for this Task.

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

The ONE definition of every metadata key the pipeline writes on a bead — its group, its value
type, when it is required, its allowed values, and the build-contract projection `contract`
returns — is the JSON Schema `schemas/bead-metadata.schema.json` in this skill. Read it there;
this page does not restate it. Python producers and consumers import the generated
`scripts/bead_metadata.py` (`scripts/generate_bead_metadata.py` writes it from the schema and
`scripts/check_bead_metadata_generated.py` fails when it is stale); the driver loads both files
from the installed plugin through its `beadmeta.py`.

`bd` metadata is flat `key=value` TEXT, so **every value is a string**: lists and objects are
compact JSON. The build-contract keys are inside the READINESS fingerprint and outside the
JUDGING one; every other group is outside both, which is what lets each consumer store its own
verdict without invalidating it.

**The schema's `UNKNOWN` literal is not `[]`, and the difference is the whole point.** For a
contract key whose kind (the schema's `ContractKind`) admits it, `UNKNOWN` means nobody ruled and
reads as null, so the phase falls back to its own lead; `[]` means somebody checked and the work
crosses no boundary, which SKIPS the phase outright. Never write `[]` for a question no one
settled.

`metadata get` shows a bead's keys split by the schema's groups and lists every key outside the
schema under `unrecognized`. `metadata set` writes whatever `key=value` pairs it is given and
refuses only an argument with no `=`; a typo'd key is written as given and is invisible to every
reader, so take key names from the schema.

**Always `--set-metadata` (merges), never `--metadata` (replaces the whole object and drops every
key the write did not name).** `metadata set` uses the right one and reads back to verify.

## The content fingerprints

The staleness watermark, in TWO SCOPES. A fingerprint answers "has the thing this consumer reads
changed?", and two consumers read different things, so one fingerprint cannot answer for both.
Both scopes have ONE implementation, `content_hash` in `scripts/beads-contract.py`;
`fingerprint <id> --scope <scope> --explain` prints the exact object hashed. Do not reproduce
either recipe in prose, in `jq`, or in a second language.

The scopes are the schema's `HashScope` values, and which record fields each covers is the
schema's `x-field-sets` (`CONTENT_HASH_FIELDS` / `CONTENT_HASH_PRESENT` for readiness,
`JUDGING_HASH_FIELDS` / `JUDGING_HASH_PRESENT` for judging); the readiness scope also covers the
build-contract keys (`CONTRACT_HASHED_WHEN_PRESENT` only on a bead that carries them). The
readiness scope is what `task-ready` rules on, stored under the schema's `CONTENT_HASH_KEY`. The
judging scope is what a WSJF judging session is handed and what the SEQUENCING assessment reads,
each stored under its own key in the schema's WSJF and sequencing groups. **Pass the scope that
matches the key you store the answer under**, or you will compare a watermark against a
fingerprint of something else.

What matters to a caller:

- Rehoming a Task or changing the spec it builds against makes it stale for readiness, because it
  changes what a reviewer would rule on; it does not change the judging fingerprint, because the
  build contract has no bearing on business value, time criticality or size.
- A field set's key outside its `*_PRESENT` set hashes as null, so writing a label, an edge, a
  score or a verdict never changes the fingerprint, and no metadata key outside the build
  contract is hashed.
- Timestamps, status and comments are outside it, so storing a verdict never invalidates it.
- Criteria in the Task's OWN description ARE covered, because `description` is. Criteria on a
  PARENT are NOT — the fingerprint is over this bead's own record. Editing a parent's criteria
  does not make this Task stale; that is a real limitation, and it is about where the prose sits.

Anything that fingerprints beads calls this script rather than carrying its own recipe.
`fingerprint-batch` takes a `bd list` sweep on stdin and answers for every bead in one
invocation.

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

An agent that sends a bug to `task-ready`, a decomposition pass, or a build lane is itself the
defect. Report it and stop.

## Rules for the agent using this skill

- **Ask the CLI; do not reconstruct the answer.** No `bd show ... | jq` pipelines, no hand-written
  hashing, no assumptions about which fields exist.
- **Report provenance.** When you say criteria are missing, quote `searched`. When you use
  criteria, quote `sourceId` and `sourceField`.
- **Never restate a recipe from this document into another document.** Cite the script. The
  duplicate is what drifts, and it drifts in whichever copy is wrong.
- **Read-only unless the task is a write.** Every command except `metadata set` and `cds-audit` changes nothing.
