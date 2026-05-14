# @mark-satterfield/plugin-prompt-library

A Claude Code plugin for managing a full-featured prompt library. Create,
search, run, compose, and orchestrate prompt templates with variable
substitution, scope control, and semantic synthesis.

## Commands

| Command | Description |
|---------|-------------|
| `/prompt:list` | List all prompts with scope, tags, and variable count |
| `/prompt:show [name]` | Display prompt content without running it |
| `/prompt:search [query]` | Find a prompt by natural language description |
| `/prompt:create [name]` | Create a new prompt interactively |
| `/prompt:edit [name]` | Edit an existing prompt |
| `/prompt:delete [name]` | Delete a prompt |
| `/prompt:clone [source] [new-name]` | Duplicate a prompt as a starting point |
| `/prompt:run [name] [var=val...]` | Run a prompt with variable substitution |
| `/prompt:exec [n1] [n2] ... [--sequential\|--parallel]` | Run multiple prompts in sequence or parallel |
| `/prompt:compose [n1] [n2] ...` | Semantically synthesize multiple prompts into one |
| `/prompt:diff [name1] [name2]` | Show overlaps and conflicts between two prompts |
| `/prompt:import [path\|url]` | Import prompts from a file or URL |
| `/prompt:export [name\|--all]` | Export prompts to `.md` or `.json` |
| `/prompt:promote [name]` | Move a project-local prompt to global |
| `/prompt:demote [name]` | Move a global prompt to project-local |
| `/prompt:history` | Show recently run prompts |

## Storage

Prompts are stored as individual Markdown files with YAML frontmatter.

- **Global** (available everywhere): `~/.claude/prompts/`
- **Project-local** (overrides global): `.claude/prompts/`

Project-local prompts take precedence over global prompts with the same name.

## Prompt Format

```markdown
---
name: my-prompt
description: A brief description of what this prompt does
tags: [coding, review]
variables:
  - name: language
    description: Programming language to target
    default: Python
  - name: context
    description: Additional context for the task
pinned: false
---

You are an expert {{language}} developer.

Context: {{context}}

Your task is to...
```

## Variable Syntax

Variables use `{{variable}}` syntax. Default values use `{{variable|default}}`:

```
{{role|engineer}}       — uses "engineer" if no value provided
{{language}}            — required; user will be prompted if not supplied inline
```

## Categories

Organize prompts into categories using path-style names:

```
coding/review
coding/refactor
writing/email
writing/summary
```

## Features

- **Scope control**: `--global` / `--local` flags on create, edit, import
- **Pin/favorite**: `--pin` flag to mark prompts for quick access
- **Variable defaults**: `{{var|default}}` syntax for optional variables
- **Dry run**: `--preview` flag on `run` to inspect assembled prompt before sending
- **Auto-suggest**: Surfaces relevant stored prompts based on conversation context (opt-in)
- **Run history**: Tracks recently used prompts with timestamps
