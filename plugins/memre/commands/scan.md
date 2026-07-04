---
description: Report process-residue in a deliverable without changing it
argument-hint: <path-to-file>
---

Use the Bash tool to run:

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/residue_lint.py" $ARGUMENTS

Then tell me, in plain terms, which findings are safe to delete outright and which
are judgment calls worth a look. Do not modify the file.
