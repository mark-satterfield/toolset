---
name: search
description: Find prompts by natural language description. Searches names, descriptions, tags, and body content.
argument-hint: "[query]"
allowed-tools: Read, Bash
---

If no query is provided, ask: "What are you looking for? Describe the prompt you need."

Read all prompt files from `~/.claude/prompts/` and `.claude/prompts/`. Parse each file's frontmatter and body.

Search across these fields for semantic relevance to the query:
- `name`
- `description`
- `tags`
- First 200 characters of the prompt body

Rank results by relevance. Show top matches (up to 10). For each match, show:
- Name and scope badge
- Description
- Why it matched (e.g. "matches tag: coding" or "description mentions code review")
- A short excerpt from the body if the match was in the body text

If no matches are found, say so and suggest `/prompt:create` or `/prompt:import` to add prompts.

After showing results, ask: "Would you like to run or view any of these?" If the user selects one, proceed as `/prompt:show` for that prompt.
