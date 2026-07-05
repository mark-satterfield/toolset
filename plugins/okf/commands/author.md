---
description: Create a new Open Knowledge Format (OKF) bundle from scratch — interactive scope, structure, concepts, indexes, and conformance check.
argument-hint: "[target bundle dir]"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion
---

# /okf:author

Invoke the `author-okf-bundle` skill to build a new OKF bundle interactively.

## Process

1. Resolve `$ARGUMENTS` as the target bundle directory. If empty, ask where the
   bundle should live and what knowledge it captures.
2. Load and execute `${CLAUDE_PLUGIN_ROOT}/skills/author-okf-bundle/SKILL.md`.
3. On completion, run `${CLAUDE_PLUGIN_ROOT}/scripts/validate-okf.sh <bundle>`
   and report the tree plus the conformance result.

## Notes

- Greenfield authoring only. To build from an existing source, use
  `/okf:convert`. To review an existing tree, use `/okf:audit`.
- Never invent data — ask when a `type`, column, or URI is unknown.
