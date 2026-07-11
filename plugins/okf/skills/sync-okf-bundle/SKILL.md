---
name: sync-okf-bundle
description: >-
  Reconcile an OKF bundle with the source tree(s) it was built from — stamp
  provenance, apply changed files, add new ones, remove (or tombstone) deleted
  ones, then reindex and validate. Use when the user wants to update, refresh,
  or re-sync a bundle after its source changed, or add new/changed source files
  to an existing bundle.
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Agent]
---

# Sync an OKF bundle with its source

Keep a bundle in step with its source tree. Provenance — `source_path` (env-var
form), `source_sha`, `timestamp` — is what makes this incremental and
shareable. Full spec: `${CLAUDE_PLUGIN_ROOT}/design/okf-sync.md`.

## Deterministic core

`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/okf_tools/sync.py <cmd> <bundle> --source-root VAR=/abs/path`

- `plan` — JSON: `new` / `changed` / `deleted` / `unchanged` / `adoptable`.
- `adopt` — stamp provenance on concepts that mirror a source path but have none
  (first-time bootstrap of an already-built bundle).
- `apply-deletions [--tombstone]` — remove (or tombstone) concepts whose source
  is gone.

`--source-root` takes `VAR=/abs/path` or a bare `VAR` resolved from the shell.

## Workflow

1. **Manifest** — ensure the bundle has `sources.md` (`type: Source Manifest`)
   declaring each env var, the tree it points to, and an example. Create it if
   missing. Confirm every referenced var is set; stop with a pointer to
   `sources.md` if not.
2. **Bootstrap (first sync only)** — if concepts lack provenance, run `adopt` to
   stamp them from the source by mirrored path. Report anything unmatched.
3. **Plan** — run `plan`; show the user new / changed / deleted before writing.
4. **Apply:**
   - *new* → convert per `references/conversion-guides.md` (binaries via the
     `to-markdown-util` skill), place by mirroring the source-relative path,
     stamp provenance. Ask only on a filename collision.
   - *changed* → re-derive the body, preserving curation (never shrink
     `# Schema` / `# Citations`; keep hand-added frontmatter). Refresh
     `source_sha` + `timestamp`.
   - *deleted* → `apply-deletions` (add `--tombstone` for posterity).
5. **Finish** — reindex (`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/okf_tools/index.py <bundle>`)
   and validate (`${CLAUDE_PLUGIN_ROOT}/scripts/validate-okf.sh <bundle>`).

## Size / delegate

Under ~15 changed items: inline. Larger: delegate to the `okf-sync` agent (pass
the bundle, source root(s), tombstone preference, and the reference paths).

## Guardrails

- Concepts without `source_path` are hand-authored — never touch them.
- `index.md` is generated; directory prose lives in an `overview.md` concept,
  never folded into an index.
- Never invent data; store `source_path` in env-var form, never machine-absolute.
