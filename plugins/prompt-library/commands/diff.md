---
name: diff
description: Show the semantic differences between two prompts — what they share, what is unique to each, and where they conflict. Useful before running /prompt:compose.
argument-hint: "[name1] [name2]"
allowed-tools: Read, Bash
---

If fewer than two names are provided, ask for the missing names.

Load both prompts (project-local takes precedence over global for each).
If either is not found, tell the user.

Analyze the two prompts and produce a structured diff report:

**Shared (in both):**
List instructions, directives, or intent that both prompts express, noting whether the wording is identical or paraphrased.

**Only in [name1]:**
List content unique to the first prompt.

**Only in [name2]:**
List content unique to the second prompt.

**Conflicts:**
List any instructions that directly contradict each other between the two prompts. For each conflict, show the competing instructions side by side.

**Variables:**
- Variables defined in both: list with note if descriptions differ
- Variables only in [name1]: list
- Variables only in [name2]: list

After the report, suggest: "Run `/prompt:compose [name1] [name2]` to synthesize these into a single coherent prompt."
