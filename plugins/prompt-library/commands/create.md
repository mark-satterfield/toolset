---
name: create
description: Create a new prompt interactively. Supports --global to save to the global library, --pin to mark as favorite, and category namespacing via path-style names.
argument-hint: "[name] [--global] [--pin]"
allowed-tools: Read, Write, Bash
---

Determine save location:
- Default: `.claude/prompts/` (project-local). Create directory if it does not exist.
- If `--global` flag: `~/.claude/prompts/`. Create directory if it does not exist.

If a name was provided as an argument, use it. Otherwise ask: "What should this prompt be called? (Use `category/name` for namespacing, e.g. `coding/review`)"

Check if a prompt with that name already exists in the target location. If it does, tell the user and suggest `/prompt:edit` instead.

Ask the following questions one at a time, waiting for each answer:
1. "Description: What does this prompt do? (one sentence)"
2. "Tags: Any tags for organizing? (comma-separated, or press Enter to skip)"
3. "Body: Enter your prompt text. Use `{{variable}}` for placeholders and `{{variable|default}}` for optional ones with defaults."

After the body is entered, scan it for `{{variable}}` patterns. For each unique variable found, ask:
- "Describe the `{{variableName}}` variable:" (one line description)
- "Default value for `{{variableName}}`? (press Enter to make it required)"

Determine `pinned` value: `true` if `--pin` flag was passed, `false` otherwise.

Construct the `.md` file with YAML frontmatter:

```
---
name: [name]
description: [description]
tags: [tags array]
variables:
  - name: [var]
    description: [desc]
    default: [default or omit if required]
pinned: [true|false]
---

[prompt body]
```

Write the file to the appropriate directory. If the name contains a path (e.g. `coding/review`), create subdirectories as needed.

Confirm: "Prompt '[name]' created in [scope] library." Then tell the user the commands available: `/prompt:run`, `/prompt:show`, `/prompt:edit`.
