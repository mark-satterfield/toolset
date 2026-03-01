---
name: list
description: List all available prompts showing scope, tags, variable count, and pinned status. Supports filtering by scope or tag.
argument-hint: "[--pinned] [--global] [--local] [--tag <tag>]"
allowed-tools: Read, Bash
---

Read prompts from both `~/.claude/prompts/` (global) and `.claude/prompts/` relative to the current working directory (project-local). If either directory does not exist, skip it silently.

For each `.md` file found, parse the YAML frontmatter to extract: `name`, `description`, `tags`, `variables`, and `pinned`.

Count the number of `{{variable}}` placeholders in the prompt body (excluding variables that have defaults via `{{var|default}}`).

Apply filters based on flags:
- `--pinned`: show only prompts where `pinned: true`
- `--global`: show only prompts from `~/.claude/prompts/`
- `--local`: show only prompts from `.claude/prompts/`
- `--tag <tag>`: show only prompts whose tags array contains the specified tag

Display results as a formatted list. Sort: pinned prompts first (marked with ★), then alphabetical by name.

For each prompt show:
- `★` if pinned
- Name (including category path if namespaced, e.g. `coding/review`)
- `[global]` or `[local]` scope badge
- Description (truncated to 60 chars if longer)
- Tags (if any)
- Variable count: `(2 vars)` or `(no vars)`

If no prompts are found after filtering, tell the user and suggest `/prompt:create` to get started.

If no prompts exist at all in either directory, tell the user the library is empty and suggest `/prompt:create`.
