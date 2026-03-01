---
name: demote
description: Move a global prompt to the project-local library, scoping it to the current project only.
argument-hint: "[name]"
allowed-tools: Read, Write, Bash
---

If no name is provided, ask: "Which global prompt would you like to demote to project-local?"

Look for the prompt in `~/.claude/prompts/` (global). If not found there, check if it exists in `.claude/prompts/` (project-local). If it is already local, tell the user: "That prompt is already in the project-local library."

If not found at all, tell the user and suggest `/prompt:search`.

Verify there is a current project directory with a `.claude/` folder. If not, ask the user to confirm the current working directory before proceeding.

Check for a naming conflict in `.claude/prompts/`. If a local prompt with the same name already exists, ask: "A project-local prompt named '[name]' already exists. Overwrite it?" If no, cancel.

Move the file: copy to `.claude/prompts/` (creating subdirectories if namespaced), then delete from `~/.claude/prompts/`. Clean up empty directories.

Confirm: "Prompt '[name]' demoted to project-local library. It is now only available in this project."
