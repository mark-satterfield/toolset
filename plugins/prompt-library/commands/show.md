---
name: show
description: Display the full content of a named prompt, including its metadata and body, without running it.
argument-hint: "[name]"
allowed-tools: Read, Bash
---

If no name is provided, ask the user: "Which prompt would you like to view?"

Search for the prompt file by name:
1. Check `.claude/prompts/` first (project-local takes precedence)
2. Then check `~/.claude/prompts/` (global)
3. Support category paths: `coding/review` maps to `coding/review.md`

If not found in either location, tell the user the prompt does not exist and suggest `/prompt:search` to find it by description.

Display the prompt with clear sections:

**Metadata:**
- Name, description, scope, tags, pinned status
- Variables: list each variable with its description and default (if any)
- Last run: from history if available

**Body:**
Show the raw prompt body with `{{variables}}` highlighted so the user can see what will be substituted at runtime.

Do not run the prompt. Do not substitute variables. This command is read-only.
