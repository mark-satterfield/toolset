---
description: Validate an OKF bundle for v0.1 conformance and report warnings. Prefers okflint when installed; falls back to the bundled conformance script.
argument-hint: "[bundle dir]"
allowed-tools: Read, Bash, Glob, Grep
---

# /okf:validate

Invoke the `validate-okf-bundle` skill to check OKF v0.1 conformance.

## Process

1. Resolve `$ARGUMENTS` as the bundle directory (default: current directory).
2. Load and execute `${CLAUDE_PLUGIN_ROOT}/skills/validate-okf-bundle/SKILL.md`.
3. Prefer `okflint` if installed; otherwise run
   `${CLAUDE_PLUGIN_ROOT}/scripts/validate-okf.sh <bundle>`.
4. Report the verdict, errors (with paths), then non-blocking warnings.

## Notes

- Three conformance rules only: frontmatter present, non-empty `type`, reserved
  files well-formed. Everything else is soft guidance.
- Never reject a bundle for missing optional fields, unknown types, unknown
  keys, broken links, or missing indexes.
