---
name: promote
description: Move a project-local prompt to the global library, making it available in all projects.
argument-hint: "[name]"
allowed-tools: Read, Write, Bash
---

If no name is provided, ask: "Which prompt would you like to promote to global?"

Look for the prompt in `.claude/prompts/` (project-local). If not found there, check if it exists in `~/.claude/prompts/` (global). If it is already global, tell the user: "That prompt is already in the global library."

If not found at all, tell the user and suggest `/prompt:search`.

Check for a naming conflict in `~/.claude/prompts/`. If a global prompt with the same name already exists, ask: "A global prompt named '[name]' already exists. Overwrite it?" If no, cancel.

Move the file: copy to `~/.claude/prompts/` (creating subdirectories if namespaced), then delete from `.claude/prompts/`. Clean up empty directories.

Confirm: "Prompt '[name]' promoted to global library. It is now available in all projects."
