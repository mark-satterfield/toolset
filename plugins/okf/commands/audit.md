---
description: Review a directory tree against OKF and produce a ranked recommendation report — conformance, structure, indexes, cross-links, type hygiene. Read-only.
argument-hint: "[bundle/dir path] [optional report output path]"
allowed-tools: Read, Bash, Glob, Grep, Agent
---

# /okf:audit

Review an existing directory tree against OKF and report how it should change.
Read-only — recommends, never modifies.

## Process

1. Resolve `$ARGUMENTS` — first token is the tree to audit, second (optional) is
   where to write the report. If the path is missing, ask for it.
2. Delegate to the `okf-auditor` agent via the `Agent` tool
   (`subagent_type: okf-auditor`). Pass it the tree path, the report output
   path, and the paths to `${CLAUDE_PLUGIN_ROOT}/references` and
   `${CLAUDE_PLUGIN_ROOT}/scripts/validate-okf.sh`.
3. Relay the agent's verdict and ranked recommendations. Offer `/okf:convert` or
   `/okf:enrich` to act on them.

## Notes

- The auditor fans out over the whole tree in its own context, so a large tree
  won't overflow this session.
- Conformance failures are must-fix; everything else is ranked, non-blocking
  guidance.
