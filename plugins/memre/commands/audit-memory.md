---
description: Audit auto-memory files and flag any that store a change instead of a current fact
argument-hint: <path-to-memory-file-or-dir>
---

Use the Bash tool to run:

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/residue_lint.py" --memory $ARGUMENTS

For each flagged memory, tell me the current fact it should hold in place of the
change it currently records, so I can overwrite or prune it. This audit never
edits memory files; overwriting is a decision I make per record.
