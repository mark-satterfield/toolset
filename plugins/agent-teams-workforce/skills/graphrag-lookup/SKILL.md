---
name: graphrag-lookup
description: >-
  Look up what already exists before designing anything, and understand code before reading,
  changing, reviewing or testing it: the matrix first for what it records, GitNexus for the code
  itself (execution flows, symbol context, callers, blast radius, scope before commit, safe
  renames), and the GraphRAG index for search by meaning across the repositories and the vault.
user-invocable: false
---

# GraphRAG lookup

Three sources answer "what exists, and what does it touch". Each answers a different question,
and they are used together:

- **The matrix** records which features and stacks exist, which repository holds each stack and
  what depends on what. Read it with `atw-matrix`; each command prints one JSON object. It is
  the authority for what it records: go to it first.
- **GitNexus** (`mcp__gitnexus__*`) indexes each code repository's call graph: symbols, callers
  and callees, imports, execution flows, API routes and their consumers. It is the tool for
  understanding and changing code inside a repository, and it is used constantly, not only
  when something looks risky. SkillSpoke's code is spread across more than 60 repositories,
  so reading files and grepping misses callers that GitNexus finds.
- **GraphRAG** (`mcp__mcp-graphrag-server`) indexes every repository and the `skillspoke-docs`
  vault for search by meaning. Use it for a passage in a document, a pattern, or a concept the
  matrix records nothing about and whose repository you do not yet know.

Cite each matrix entry you rely on by its id, each GitNexus result by repository, symbol and
file, and each GraphRAG hit by repository and path. When nothing relevant is found, say so in
your result.

## Before designing

- Ask the matrix first whether the capability exists:
  `atw-matrix find --kinds feature --text "<the behaviour>"` for a feature that provides it, with
  the Epics it serves, and `atw-matrix find --kinds stack --text "<the behaviour>"` for the stack
  that is its home. `atw-matrix node <id>` returns one entry with what realizes it, the stack that
  holds it and the documents that describe it.
- An empty result is the answer: no such feature or stack exists. Do not search the repositories
  to learn whether one does.
- For the stacks the matrix returns, see how the code realises them: `atw-matrix node stack:<id>`
  gives the `repository`; GitNexus `query` with that repository as `repo` returns the execution
  flows for the behaviour, and `context` on a symbol it names shows what calls it and what it
  calls. For an API, `route_map` shows each route, its handler and its consumers.
- Use GraphRAG for what the matrix does not record, such as a passage in a document, a pattern or
  a symbol in code whose repository you do not know: call `search` with the concept across all
  repositories (no `repo_id`), or with `repo_id` set to the repository that holds the
  architecture root (its directory name). Then use GitNexus in the repositories the hits name.

## Reading and exploring code

- To understand unfamiliar code, start with GitNexus `query` (a concept, a symptom or an error
  message as `search_query`, with `goal` and `task_context` filled in). It returns execution
  flows ranked by relevance, with their symbols and files. Prefer it to grepping.
- `context` on a symbol gives its callers, callees, imports, the flows it takes part in and its
  file. Pass `uid` from an earlier result, or `file_path` and `kind`, when a name is ambiguous.
- `trace` answers "how does A reach B" in one call. `cypher` answers a structural question the
  other tools do not, for example every writer of a field.
- For HTTP routes and MCP tools: `route_map`, `tool_map`, and `shape_check` (what a route
  returns against what its consumers read).
- Read the result's `epistemic`, `boundaries` and `causes`: `lower-bound` means callers may be
  missing (an untyped receiver, dependency injection, a callable passed as a value). Confirm
  with `git grep` on the repository before relying on an absence.

## Before any change or refactor

- Ask the matrix first what depends on the entry you change: `atw-matrix deps --on <id>` returns
  every entry and stack that depends on it, to any depth, each with the relationship kind and the
  stack that holds the dependent. `atw-matrix node stack:<id>` returns that stack's `repository`.
- Then, before editing any function, class or method, run GitNexus `impact` on it with
  `direction: "upstream"` in each repository concerned (the one you change and those of the
  stacks the matrix returned). Report the blast radius in your result: the direct callers (d=1,
  which will break and must be updated), the affected execution flows and modules, and the risk
  level.
- When `impact` reports HIGH or CRITICAL risk, state it as a warning in your result, update or
  cover every d=1 dependent, and keep the change to what the task needs. When it reports
  UNKNOWN, no caller was resolved: confirm with `git grep` before treating the symbol as unused.
- Before changing an API route handler, run `api_impact` on the route or the handler file: its
  consumers, the response fields they read and the middleware that protects it.
- Before moving or splitting code, run `context` on what you move and `impact` upstream on it,
  so every external reference moves with it.
- Use GraphRAG for a symbol or concept that neither the matrix nor GitNexus finds: call `search`
  across all repositories (no `repo_id`), then `get_graph` (direct relationships of one
  repository) or `find_path` (whether one direct edge exists between two nodes) for the
  repositories the hits name, and confirm each dependency the index reports with `git grep` on
  the repository's `main`.

## Renaming

- Rename a function, class, method or variable with GitNexus `rename`, never with find-and-
  replace. Run it with `dry_run: true` first and review the preview: `graph` edits are reliable,
  `text_search` edits need checking one by one. Then run it with `dry_run: false`, and run
  `detect_changes` afterwards.
- `rename` edits files. Only agents granted it use it; an agent without it reports the rename
  the work needs.

## Before committing

- Run GitNexus `detect_changes` before every commit (`scope: "staged"` for what you staged,
  `"all"` for the whole working tree, `"compare"` with `base_ref: "main"` for a branch). In a
  linked worktree, pass the worktree's absolute path as `worktree`. Check that the changed
  symbols and affected flows are the ones the task meant to change; a result with
  `partial: true` is not a clean check, so run it again.

## Reviewing and testing code

- Reviewers read a change through GitNexus: `detect_changes` with `scope: "compare"` and
  `base_ref: "main"` for what the branch changed, then `impact` and `context` on the changed
  symbols for what they reach.
- Test writers and testers use `query`, `context` and `impact` to find the flows and callers a
  test must cover, `api_impact` and `shape_check` for API contracts, and `explain` for the taint
  findings of an index built with `--pdg` (sources reaching command, code, path, SQL or HTML
  sinks). An empty `explain` is not proof of safety; its result states what it cannot see.
- `check` reports circular imports between files; `pdg_query` shows what condition guards a
  statement and where a variable flows, on an index built with `--pdg`.

## Across repositories

- Name the repository in every GitNexus call (`repo`): many repositories are indexed, and a call
  without one may answer from the wrong index. `list_repos` returns the indexed repositories
  (page with `offset` while `pagination.hasMore` is true).
- Every SkillSpoke repository is a member of the GitNexus group `skillspoke`, named by its clone
  path under `$SKILLSPOKE_APPS`. `group_list` lists the members. To work across repositories, pass
  `repo: "@skillspoke/<group path>"`, naming the member (for example
  `@skillspoke/personal-agent/SkillSpoke-chat-service`), to `query`, `context`, `impact` or `trace`:
  `impact` then follows cross-repository contracts (HTTP routes, topics) to their consumers, and
  `trace` with no `to` follows a client call to the handler that serves it. A result with
  `truncated: true` is a floor, not a verdict; read its `truncationReason`.
- For a repository that is not a member of the group, run the GitNexus call in that repository, and use
  GraphRAG to find repositories the matrix does not name.
- The matrix says which repositories are related; GitNexus says how their code is connected;
  GraphRAG finds what neither records.

## When the index is stale or missing

- Indexes refresh themselves: a git hook queues a background re-index after every commit, merge,
  checkout and rebase, and every session start queues any repository that is behind. A GitNexus
  tool warns when a repository's index is behind the repository. First run
  `python3 "$SKILLSPOKE_CC/ops/indexing/gitnexus-fleet.py" status`; re-index with
  `"$SKILLSPOKE_CC/ops/indexing/gitnexus-reindex.sh" <repository path>` only when that shows no
  re-index queued for the repository, then repeat the call.
  Run any other GitNexus command through `"$SKILLSPOKE_CC/ops/indexing/gitnexus-pinned.sh"
  <command>`; never start GitNexus another way, because the project pins one version.
- Never rebuild a group's contract registry (`group_sync`) and never change `group.yaml`; a
  missing or stale group is reported in your result.
- A repository that is not indexed, or a GitNexus call that fails, is a named blocker in your
  result. Continue with `git grep` on that repository and say what the gap leaves unchecked.

## Limits

- Never call GraphRAG `list_indexed_repos`; it fails on an index this size. GitNexus
  `list_repos` is paginated and safe.
- A server that does not answer is a named blocker in your result, never a silently skipped
  step.
