---
description: Report process-residue in a deliverable without changing it
argument-hint: <path-to-file>
---

<!-- residue-lint:ignore-file (this command quotes the residue vocabulary to define it) -->

Read the file at $ARGUMENTS in full and judge it yourself. The decision here is
semantic, not lexical: a deliverable states only what is true now, and any text
that describes the *making* of the file — change history, decision or rationale
narration, deferrals and TODOs, or anything named only to be ruled out — is
process-residue that does not belong.

1. Read the whole file. Load the `canonical-output` skill and apply its definition
   of residue, so this matches what the rest of the plugin enforces.
2. Judge by meaning. Read every sentence, heading, and parenthetical as a stranger
   who never saw the conversation that produced the file. A passage is residue if
   it only makes sense to someone who watched the file being built, or if it points
   at something not otherwise present. This is what catches what a keyword scan
   cannot — a section titled "Decisions," a "why this is better" rationale block, a
   parenthetical that exists to explain a choice.
3. A keyword pass is a backstop, never the boundary. You may run
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/residue_lint.py" --json $ARGUMENTS`
   to catch purely mechanical shapes (a bare `TODO:`, a struck-through line). Treat
   any hit as a hint you still judge: discard the ones that are legitimate
   present-state prose — for example "no longer" describing the current design —
   and never assume its silence means the file is clean.
4. Report, grouped, and change nothing:
   - **Residue — safe to remove:** unambiguously making-of.
   - **Judgment calls:** could read either way; say why, and what it would become
     rewritten as present-state.
   Give each item a line number and the quote. If the file is clean, say so plainly.

Do not modify the file. Where the residue records a real decision, history, or open
action worth keeping, note that its home is an outlet reached through
`/record-observation` — a decision log, an issue, or chat — not the deliverable.
