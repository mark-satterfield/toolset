# @mark-satterfield/toolset

A curated collection of Claude Code plugins and skills, organized by capability.

## Structure

- `plugins/` — Extend Claude Code with new commands and integrations
- `skills/` — Behavioral instructions organized by capability category

## Namespacing

All packages follow the pattern:

```
@mark-satterfield/plugin-<name>
@mark-satterfield/skill-<name>
```

## Installation

### Install a plugin

Copy the plugin directory into `~/.claude/plugins/` to make it available globally:

```bash
cp -r plugins/prompt-library ~/.claude/plugins/
```

Or for project-local installation, copy into `.claude/plugins/` at your project root.

Then enable the plugin in Claude Code settings.

### Install a skill

Copy the desired skill's `SKILL.md` into your global Claude skills directory:

```bash
cp skills/skill-management/gitignore-manager/SKILL.md ~/.claude/skills/gitignore-manager/
```

Or into your project's `.claude/skills/` directory for project-local scope.

## Plugins

| Name | Description |
|------|-------------|
| [prompt-library](./plugins/prompt-library) | Full-featured prompt management — create, search, run, compose, and orchestrate prompt templates |

## Skills

### Skill Management

| Name | Description |
|------|-------------|
| [gitignore-manager](./skills/skill-management/gitignore-manager) | Manage `.gitignore` files across projects |
| [ide-index-manager](./skills/skill-management/ide-index-manager) | Manage IDE indexing configuration (pairs with gitignore-manager) |
| [skill-manager](./skills/skill-management/skill-manager) | Manage custom skills — deduplicate, promote to global, publish to marketplace |

### Project Management

| Name | Description |
|------|-------------|
| *(coming soon)* | — |

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md).
