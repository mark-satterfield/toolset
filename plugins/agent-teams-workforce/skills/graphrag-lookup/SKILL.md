---
name: graphrag-lookup
description: >-
  Look up what already exists before designing anything and before changing or refactoring any
  code: in the matrix first, for what it records, and in the GraphRAG index for what it does not.
user-invocable: false
---

# GraphRAG lookup

The matrix records which features and stacks exist and what depends on what. Read it with
`atw-matrix`; each command prints one JSON object. The GraphRAG server
(`mcp__mcp-graphrag-server`) indexes every repository of the project and its documentation
repository, for search by meaning. Go to the matrix first for what it records, and use GraphRAG
for what it does not.

## Before designing

- Ask the matrix first whether the capability exists:
  `atw-matrix find --kinds feature --text "<the behaviour>"` for a feature that provides it, with
  the Epics it serves, and `atw-matrix find --kinds stack --text "<the behaviour>"` for the stack
  that is its home. `atw-matrix node <id>` returns one entry with what realizes it, the stack that
  holds it and the documents that describe it.
- An empty result is the answer: no such feature or stack exists. Do not search the repositories
  to learn whether one does.
- Use GraphRAG for what the matrix does not record, such as a passage in a document, a pattern or
  a symbol in code: call `search` with the concept across all repositories (no `repo_id`), or
  with `repo_id` set to the repository that holds the architecture root (its directory name).
- Cite each matrix entry you rely on by its id, and each GraphRAG hit by repository and path.
  When nothing relevant is found, say so in your result.

## Before any change or refactor

- Ask the matrix first what depends on the entry you change: `atw-matrix deps --on <id>` returns
  every entry and stack that depends on it, to any depth, each with the relationship kind and the
  stack that holds the dependent. `atw-matrix node stack:<id>` returns that stack's `repository`.
- Then look inside the repositories of the stacks returned, and only those: GitNexus for the
  callers of a symbol, and `git grep` on the repository's `main` to confirm each use before
  acting on it.
- Use GraphRAG for a symbol or concept the matrix holds no entry for: call `search` across all
  repositories (no `repo_id`), then `get_graph` (direct relationships of one repository) or
  `find_path` (whether one direct edge exists between two nodes) for the repositories the hits
  name, and confirm each dependency the index reports with `git grep` on the repository's `main`.

## Limits

- Never call `list_indexed_repos`; it fails on an index this size.
- A server that does not answer is a named blocker in your result, never a silently skipped
  step.
