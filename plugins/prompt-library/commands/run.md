---
name: run
description: Run a stored prompt with variable substitution. Inline values are used first; missing variables are filled interactively. Use --preview to inspect the assembled prompt before sending.
argument-hint: "[name] [var=value ...] [--preview]"
allowed-tools: Read, Write, Bash
---

If no name is provided, ask: "Which prompt would you like to run?"

Find the prompt file (check project-local first, then global). If not found, suggest `/prompt:search`.

Parse the prompt body for all `{{variable}}` and `{{variable|default}}` placeholders.

Build the variable values map:
1. Apply any inline `var=value` arguments provided in the command
2. For variables with defaults (`{{var|default}}`): use the default if no inline value was provided
3. For remaining unresolved variables: ask the user interactively, one at a time: "Value for {{variableName}} ([description]):"

Assemble the final prompt by substituting all variable placeholders with their resolved values.

If `--preview` flag:
- Display the fully assembled prompt text
- Ask: "Send this prompt? (yes/no)"
- If no, stop here

If not `--preview` (or user confirmed after preview):
- Record this run in `~/.claude/prompts/.history.json`: `{ name, timestamp, variables_used }`
- Submit the assembled prompt text as a message to continue the conversation

Do not show the variable substitution process to the user — just show the final result.
