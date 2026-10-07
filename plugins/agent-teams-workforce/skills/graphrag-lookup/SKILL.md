---
name: graphrag-lookup
description: >-
  Look up what already exists across the project's repositories and documentation in the
  GraphRAG index before designing anything and before changing or refactoring any code.
user-invocable: false
---

# GraphRAG lookup

The GraphRAG server (`mcp__mcp-graphrag-server`) indexes every repository of the project and
its documentation repository. Use it to find what already exists before you create or change
anything.

## Before designing

- Call `search` with the capability or concept across all repositories (no `repo_id`), and
  again with `repo_id` set to the repository that holds the architecture root (its directory
  name), to answer: is this already solved, documented or planned?
- Cite each hit you rely on by repository and path. When nothing relevant is found, say so in
  your result.

## Before any change or refactor

- Call `search` with the symbol or concept across all repositories (no `repo_id`) to find
  every place that uses it.
- Call `get_graph` (direct relationships of one repository) or `find_path` (whether one
  direct edge exists between two nodes) for the repositories the hits name.
- Confirm each dependency the index reports with `git grep` on the repository's `main` before
  acting on it.

## Limits

- Never call `list_indexed_repos`; it fails on an index this size.
- A server that does not answer is a named blocker in your result, never a silently skipped
  step.
