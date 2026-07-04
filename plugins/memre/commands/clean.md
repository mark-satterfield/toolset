---
description: Delete high-confidence process-residue from a deliverable in place
argument-hint: <path-to-file>
---

Use the Bash tool to run:

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/residue_lint.py" --fix $ARGUMENTS

Report which lines it deleted, then list anything still flagged so I can decide on
those myself.
