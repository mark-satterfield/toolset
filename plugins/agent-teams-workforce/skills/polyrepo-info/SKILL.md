---
name: polyrepo-info
description: >-
  Create, update, deprecate, list, or search information about the repositories that lives
  OUTSIDE the manifest's structural core — derived facts and tribal knowledge, much of it
  "where to find things." Answers questions like "what's the naming convention?", "which
  repos have no code?", "which contain a DynamoDB table?" by searching LIVE (never by
  pre-storing every answer), and curates a small store of durable, hard-won pointers. First
  token may be a CUDLS verb (create | update | delete | deprecate | list | search); if
  absent, infer.
---

# Polyrepo Info

You handle everything a caller wants to *know* about the repositories that isn't the manifest's
structural spine. You have two jobs: **search** (answer questions live) and **curate** (keep a
small, high-value knowledge store).

## What you do NOT do

You do not pre-answer and pre-store every possible question. "Which repos have no code" and
"which contain a DynamoDB table" are **searched on demand** — you are expected to *find* the
answer, not to have cached it. Store only what is genuinely worth keeping close.

## Search — always by precedence

Every search follows `references/search-recipes.md`, in order: **(1)** the project's
CLAUDE.md / AGENTS.md instructions first (they say where data lives and how to reach it);
**(2)** the project's second-brain tools for the data type — Obsidian CLI for the vault,
GraphRAG for cross-repo semantics, GitNexus for code intelligence, NotebookLM / vector DBs
where provided; **(3)** generic search (ripgrep → git grep → gh) only as a last resort. Do not
reach for ripgrep just because a recipe lists it.

## The knowledge store

You own `.polyrepo/knowledge.yaml` — durable, non-structural facts, heavily *where to find
things*. Entry shape:

```yaml
schema_version: 1
knowledge:
  - id: <slug>
    topic: <subject, e.g. "repository naming convention">
    kind: location | fact | pointer
    value: <the fact, or where/how to find it, e.g. "vault: docs/.../repository-naming.md">
    source: <how it was learned>
# No date field — git history is the audit trail for when an entry changed.
```

## Operations (CUDLS)

- **search** — answer the question via the precedence ladder. If the answer is a durable
  "where to find it" fact, offer to record it so the next lookup is instant.
- **create / update** — add or revise a knowledge entry.
- **delete / deprecate** — retire an entry (keep a tombstone with the reason where it matters).
- **list** — enumerate knowledge entries by topic or kind.

## Recording

Curation changes follow the learning protocol (`../polyrepo-repo/references/learning-protocol.md`):
update `.polyrepo/knowledge.yaml` **and** append `.polyrepo/changelog.md`. Read non-obvious
facts back before storing.

## Boundaries

Structural questions (repos, owners, dependencies, groups, deploy waves) belong to
**polyrepo-repo**, not here. Bulk scanning to populate the store is **polyrepo-tribal-knowledge**.
The project's own scripts/tools/procedures registry is **polyrepo-governance**.
