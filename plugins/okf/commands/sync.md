---
description: Reconcile an OKF bundle with its source tree(s) — apply changed files, add new ones, drop deleted ones — using env-var source paths so the bundle stays shareable.
argument-hint: "[source root or VAR=path] [bundle dir]"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent, AskUserQuestion
---

# /okf:sync

Invoke the `sync-okf-bundle` skill to reconcile a bundle against the source it
was built from.

## Process

1. Resolve `$ARGUMENTS` — first token is the source root (or a `VAR=path`),
   second is the bundle directory. If the bundle already has a `sources.md`
   manifest, the source may be omitted.
2. Load and execute `${CLAUDE_PLUGIN_ROOT}/skills/sync-okf-bundle/SKILL.md`.
3. Show the plan (new / changed / deleted) first; apply after confirmation, then
   reindex and validate.

## Notes

- Provenance is stored in env-var form (`$VAR/path`) so bundles stay shareable;
  the required vars are declared in the bundle's `sources.md`.
- Deleted sources are **removed** by default; pass tombstone to keep a
  deprecated stub for posterity.
- Large diffs delegate to the `okf-sync` agent.
