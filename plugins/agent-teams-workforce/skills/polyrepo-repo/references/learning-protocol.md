# Learning Protocol

The steward is a *learning* skill. The manifest is only useful if it
stays accurate, and reality changes constantly: repos get added,
renamed, archived; new dependencies appear; conventions evolve; rules
get added or relaxed. This file defines what counts as a learning
event and how to capture it.

The principle: **the manifest is the project's living memory, and you
are its custodian.** Every fact you learn that affects how the project
should be cared for must be written down — promptly, with reasoning,
and without silently dropping anything that came before.

## What counts as a learning event

Any of the following triggers a learning event. The list is not
exhaustive — when in doubt, capture it.

### Repo-level changes

- A new repo joined the project.
- A repo was renamed.
- A repo's role changed (e.g., a library became a service).
- A repo's owner changed.
- A repo was deprecated, archived, or extracted into a separate
  project.
- A repo's primary language, default branch, or remote URL changed.
- A repo that was previously not cloned locally is now cloned (or
  vice versa).

### Relationship changes

- A new dependency between two repos.
- A removed dependency.
- A new shared contract (proto, openapi, schema, types) crossed
  multiple repos.
- A change in deploy ordering (see *Group and deploy-wave changes*).
- A newly observed circular dependency, or one that was resolved.

### Group and deploy-wave changes

- A new group was defined, or an existing one removed.
- A repo joined or left a group's `members`.
- A new deploy wave (stage) was added, or one removed or reordered.
- A repo joined or left a wave, or a wave repo's `gate` or `deploy_task`
  changed.
- A rule or dependency's scope changed because it was retargeted to (or
  away from) a `group:<name>`.

Each of these updates the manifest (`groups`, `relationships.deploy_waves`,
or the affected dependency/rule) **and** appends a changelog entry, like
any other learning event.

### Convention or rule changes

- A new naming convention, or a change to an existing one.
- A new branching, commit, PR, or release rule.
- A new architectural rule (e.g., "no direct DB access from frontend").
- A new security or compliance rule.
- A relaxation of an existing rule (record this carefully — relaxations
  are easy to forget about).

### Documentation, search, ownership

- A new documentation location.
- A new cross-repo search recipe.
- A new owner or contact for a topic.
- A change in how documentation is organized.

### Topology changes

- The shape of the project changed (a meta repo was added; a monorepo
  was extracted into pieces; repos were consolidated).

### Steward self-changes

- A new field was added to the manifest schema.
- A new reference file was added or updated.
- A new search recipe was added.

## How to capture a learning event

Every learning event has the same shape:

1. **Update the manifest.** Find the right field in
   `manifest.yaml` and edit it. If the field does not yet exist, add
   it (and increment `schema_version` if the addition is structural).
   Do not stamp a date on it — git history records when it changed.

2. **Append to the changelog.** Add an entry to
   `.polyrepo/changelog.md` of the form:

   ```markdown
   ## YYYY-MM-DD — <short title>
   - **What:** the fact, stated plainly.
   - **Why:** why this matters, or what motivated the change.
   - **Source:** how the steward learned this — "user mentioned",
     "PR review", "scan reconciled drift", etc.
   - **Affected:** repo names, rule IDs, or fields touched.
   ```

3. **Resolve any related drift entries.** If this learning resolves
   an open entry in `topology.drift_log` or elsewhere, mark it
   `resolved` and link the changelog date.

4. **Confirm with the human if the fact is non-obvious.** If you are
   recording something the human told you in passing, briefly read
   it back: "I'm going to remember that <fact>. Sound right?" This
   prevents the manifest from accumulating misheard or misremembered
   facts.

5. **Speak in outcomes, not internals.** When you tell the human
   you've captured something, do not narrate the file mechanics. "I
   updated `manifest.yaml` and appended the changelog" is internals.
   "Got it — I'll remember that" is outcome.

## Append-only, never destructive

The changelog is append-only. The manifest is editable, but never
silently destructive: when something is removed (a repo archived, a
rule retired), record the removal explicitly rather than deleting the
entry. The schema supports this through `lifecycle` on repos, and
through tombstone-style entries on rules:

```yaml
- id: no-fe-to-db
  category: architectural
  statement: Frontend never talks to the database directly.
  reason: Maintained the API as the single integration point.
  status: retired
  retired_reason: >-
    Replaced by per-feature service-mesh policies that enforce the
    same boundary at the network layer.
```

A future steward, agent, or human reading the manifest learns *why*
the rule went away, not just that it is gone.

## Reconciling drift

Periodically — when invoked with a refresh intent, or when you notice
something that does not match the manifest — run a reconcile pass.
Things to check:

- Do the local clones still exist at the recorded paths?
- Do the remote URLs still resolve?
- Do the `CODEOWNERS` files match the recorded owners?
- Are there `.git` directories under the project's parent folder that
  are not in the manifest? (a possible new repo)
- Are there manifest entries with no corresponding repo on disk or
  remote? (a possible archived/renamed/deleted repo)

For each piece of drift you cannot resolve immediately, append a
`drift_log` entry with `status: open`. The next time the human is
available, surface the open drift entries and ask. Do not invent
answers.

## Audit trail

**Git history is the audit trail** — it records what changed, when, and
why, and never goes stale. The changelog complements it with the human
narrative. Two things should be true at all times:

- Every change to `manifest.yaml` has a corresponding changelog entry.
- Every changelog entry has enough information that someone reading it a
  year later can understand *what* changed and *why*.

Do not add or maintain manual metadata date fields (`last_updated` and the
like) to "track" currency — they go stale and lie; git already knows. A
provenance date the human states inside an `origin` string is fine.

## When the steward learns something about itself

Sometimes the human teaches the steward how to do its job better, not
something about the project. Examples: "stop asking about CODEOWNERS
files — we don't use them"; "always check Confluence before saying
docs don't exist". These are *steward-tuning* facts, and they belong
in the manifest's `steward_preferences` section (add it if it does
not exist):

```yaml
steward_preferences:
  - preference: Do not ask about CODEOWNERS files; this team does
      not use them.
    reason: Team uses Slack-based ownership, not git-based.
```

These get logged to the changelog like any other learning event.
