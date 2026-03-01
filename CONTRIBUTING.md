# Contributing to toolset

## Adding a Plugin

1. Create a directory under `plugins/<your-plugin-name>/`
2. Add a `package.json` with name `@mark-satterfield/plugin-<your-plugin-name>`
3. Add a `.claude-plugin/plugin.json` manifest
4. Add a `README.md` documenting commands and usage
5. Add command files as `commands/<command-name>.md` (markdown, not TypeScript)
6. Submit a PR

## Adding a Skill

1. Identify the appropriate capability category under `skills/`
2. Create a directory under `skills/<category>/<your-skill-name>/`
3. Add a `SKILL.md` following the standard skill format
4. Add a `README.md` with usage instructions
5. Submit a PR

## Naming Conventions

- Plugins: `@mark-satterfield/plugin-<name>`
- Skills: `@mark-satterfield/skill-<name>`
- Directories: kebab-case
- No abbreviations unless universally understood

## Plugin Command Format

Commands are markdown files with YAML frontmatter:

```markdown
---
name: command-name
description: What this command does
argument-hint: "[name] [--flag]"
allowed-tools: Read, Write, Bash
---

Instructions for Claude about how to execute this command...
```

## Categories

Current skill categories:

- `skill-management` — Tools for managing skills themselves
- `project-management` — Project lifecycle and organization (expanding)
