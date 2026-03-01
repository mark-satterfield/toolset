---
name: edit
description: Edit an existing prompt. Updates name, description, tags, variables, body, or pinned status.
argument-hint: "[name]"
allowed-tools: Read, Write, Bash
---

If no name is provided, ask: "Which prompt would you like to edit?"

Find the prompt file (check project-local first, then global). If not found, tell the user and suggest `/prompt:search`.

Display the current content: metadata summary and body.

Ask: "What would you like to change? (name / description / tags / variables / body / pinned / all)"

Based on the answer, prompt the user for only the relevant fields. Do not ask about fields the user did not request to change.

If editing the body:
- Show the current body
- Ask for the new body
- After entry, re-scan for `{{variable}}` patterns
- For any new variables not in the existing frontmatter, ask for their description and optional default
- Remove any variable entries from frontmatter that no longer appear in the body

If editing the name:
- Check the new name does not conflict with an existing prompt
- Rename the file (and directory if namespaced)

Write the updated file, preserving all unchanged fields exactly.

Confirm: "Prompt '[name]' updated." Show a brief diff summary of what changed.
