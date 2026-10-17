---
name: polyrepo-info
description: >-
  Create, update, deprecate, list, or search information about the repositories that lives
  OUTSIDE the manifest and the matrix — derived facts and tribal knowledge about procedures
  and non-architecture documents. Answers questions like "what's the naming convention?" or
  "where is the deployment order kept?" by searching LIVE (never by pre-storing every
  answer), and curates a small store of durable, hard-won pointers. Where functionality
  lives and which repository owns it are not here: they are the matrix's. First
  token may be a CUDLS verb (create | update | delete | deprecate | list | search); if
  absent, infer.
---

# Polyrepo Info

You handle everything a caller wants to *know* about the repositories that isn't the manifest's
structural spine or the matrix's record of stacks. You have two jobs: **search** (answer questions live) and **curate** (keep a
small, high-value knowledge store).

## What you do NOT do

You do not pre-answer and pre-store every possible question. They are **searched on demand**
— you are expected to *find* the answer, not to have cached it. Store only what is genuinely
worth keeping close.

You do not search for where functionality lives, which repository owns it, or which
repositories hold a resource type, and you store no pointer to any of them. The matrix
answers them: `atw-matrix find --kinds stack --text "<words>"`, then `node stack:<id>` for the
repository, and `stacks --resource-type <type>` (see **polyrepo-repo**, *The matrix*).

## Search — always by precedence

Every search for a procedure or a non-architecture document follows `references/search-recipes.md`, in order: **(1)** the project's
CLAUDE.md / AGENTS.md instructions first (they say where data lives and how to reach it);
**(2)** the project's second-brain tools for the data type — Obsidian CLI for the vault,
GraphRAG for cross-repo semantics, GitNexus for code intelligence, NotebookLM / vector DBs
where provided; **(3)** generic search (ripgrep → git grep → gh) only as a last resort. Do not
reach for ripgrep just because a recipe lists it.

## The knowledge store

You own `.polyrepo/knowledge.yaml` — an index of common questions about procedures and
non-architecture documents and *where their answers are*. It holds no pointer to where
functionality lives. Entry shape:

```yaml
schema_version: 1
knowledge:
  - id: <slug>
    topic: <the question or subject, e.g. "repository naming convention">
    kind: location | fact | pointer
    value: <where/how to find the answer, e.g. "vault: docs/tech/architecture/arc42/08-crosscutting-concepts/resource-naming-standard.md">
    resolves: <for a location or pointer: the path it points at; environment variables allowed>
    source: <how it was learned>
# No date field — git history is the audit trail for when an entry changed.
```

What the store may hold follows the owner's storage rule (the steward's instructions, *What
you store*, carry it in the owner's words): pointers to the canonical source are the default
storage, and indexes of common questions with where their answers are, caches, relationships
and information that exists nowhere else are welcome.

- **`location` and `pointer`** — the default. The entry names where the answer is (a path or
  a vault document) and carries no copy of the answer.
- **`fact`** — only for information that exists nowhere else, or that is extremely costly to
  collect: it would take a really long time, or a ton of tokens, to fetch, read, collect and
  keep updated. For such an entry the store is the official source, and `source` says how it was
  collected. Any information that has a canonical home elsewhere is a `pointer` to that home,
  never a `fact` holding a copy of its value, and no entry calls a copy canonical.
- A value copied into an entry for speed must have a way to stay updated, in sync and fresh:
  it names its canonical source in `resolves`, and it is checked against that source each time
  it is used (below). A value with no such way is stored as a pointer instead.
- When you do not know where something is documented, ask the `filing-clerk` and store the
  pointer it gives you.

## Operations (CUDLS)

- **search** — answer the question via the precedence ladder. If the answer is a durable
  "where to find it" fact about a procedure or a non-architecture document, record it so the
  next lookup is instant.
- **create / update** — add or revise a knowledge entry.
- **delete / deprecate** — retire an entry (keep a tombstone with the reason where it matters).
- **list** — enumerate knowledge entries by topic or kind.

## Every entry is verified against reality

An entry is a claim until it is checked, and it is checked every time it is used:

- **Before storing** an entry, confirm it: the file, folder or vault document it names exists
  (vault documents through `obsidian-cli vault="skillspoke-docs"`), the command it names runs, and
  the fact it states is what the code, the repo or the canonical document says now. A
  location or pointer carries `resolves`, the path it points at; `polyrepo doctor` checks
  every one on each run and reports the ones that no longer exist.
- **Before answering from** an entry, confirm it the same way. An entry that no longer holds
  is corrected (find where the thing lives now) or retired with the reason, in the same
  invocation, and the answer comes from what you found, not from the entry.
- Repository facts (which repos exist, their state) are never stored here; they come from the
  `polyrepo` tool (see **polyrepo-repo**). What a repository holds and why it exists are the
  matrix's stacks and their purposes, never stored here.

## Recording

Curation changes follow the learning protocol (`../polyrepo-repo/references/learning-protocol.md`):
update `.polyrepo/knowledge.yaml`, then run the tool's `commit --message "<what changed and
why>"`. There is no read-back or approval step; verification
replaces it.

## Boundaries

Structural questions (repos, groups, repo state) belong to **polyrepo-repo** and the
`polyrepo` tool, and questions of what a repository holds or which one owns a piece of
functionality to the matrix, not here. Deployment order lives in
`$SKILLSPOKE_CC/deployment/waves*.yaml`. Bulk scanning to populate the store is **polyrepo-tribal-knowledge**.
The project's own scripts/tools/procedures registry is **polyrepo-governance**. Every change
to a vault document goes to the `filing-clerk`.
