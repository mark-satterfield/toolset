---
description: Import this project's file-based memories into beads, preserving the markdown (dry run by default)
argument-hint: <path-to-memory-dir> [--project-dir <repo-root>]
---

Use the Bash tool to run:

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/md_to_beads.py" $ARGUMENTS

Show me the plan: the beads key for each memory, its type, size, and any issues
(duplicate keys, missing `name`, dangling `[[links]]`). Change nothing yet.

When I confirm, re-run with `--apply` appended to write the entries with
`bd remember`. Add `--delete-source` only if I ask to remove the original files
after a successful import. The beads project root must be the current directory or
passed with `--project-dir`.
