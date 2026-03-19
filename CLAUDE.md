# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

A personal Claude Code plugin and skill monorepo. It publishes reusable extensions to the Claude Code plugin marketplace under the `mark-satterfield` namespace.

- `plugins/` — Claude Code plugins (commands + skills bundled as installable units)
- `skills/` — Standalone behavioral skills not tied to a plugin

## Commands

```bash
npm run list                          # List all plugins and skills
npm run install:plugin <name>         # Install a plugin locally
npm run install:skill <name>          # Install a skill locally
```

No build step. Plugins and skills are Markdown/YAML — no compilation required.

## Plugin Architecture

Each plugin lives in `plugins/<name>/` and follows this structure:

```
plugins/<name>/
├── .claude-plugin/plugin.json   # Claude Code plugin manifest (name, version, description)
├── plugin.json                  # Extended manifest with metadata
├── commands/                    # Slash commands — each .md file = one /name:command
│   └── <command>.md             # YAML frontmatter + Markdown instructions
└── skills/
    └── <skill>/
        └── SKILL.md             # Auto-activating skill with YAML frontmatter
```

Commands are invoked as `/plugin-name:command`. Skills auto-activate based on their `description` frontmatter field — Claude Code matches them via semantic similarity.

## Skill Frontmatter

Both commands and skills use YAML frontmatter. Key fields:

**Commands (`commands/<name>.md`):**
```yaml
---
description: "One-line trigger description for Claude Code"
argument-hint: "[optional-arg]"
allowed-tools: [Read, Write, Bash, ...]
---
```

**Skills (`skills/<name>/SKILL.md`):**
```yaml
---
name: skill-name
description: >-
  Trigger conditions — this is what Claude Code matches against user intent
allowed-tools: [Read, Write, ...]
argument-hint: "[optional-arg]"
---
```

## Design Plugin

The primary plugin under active development. It provides architecture governance: ADRs, specs, drift detection, issue planning, parallel implementation, and Docusaurus doc generation.

- Commands: `plugins/pmo/commands/` — 16 commands (`adr`, `spec`, `init`, `plan`, `work`, `review`, `check`, `audit`, `discover`, `docs`, `list`, `status`, `prime`, `organize`, `enrich`, `discover-more`)
- Skills: `plugins/pmo/skills/` — one SKILL.md per command
- References: `plugins/pmo/references/` — shared templates (`claude-md-template.md`, `shared-patterns.md`)
- Templates: `plugins/pmo/templates/docusaurus/` — full Docusaurus site scaffold; `templates/integration/` — plugin for existing Docusaurus sites

Design plugin configuration per project is stored in `.claude-plugin-pmo.json` at the project root (tracker type, branch conventions, PR settings, worktree config).

## Marketplace Registration

`.claude-plugin/marketplace.json` at repo root registers plugins for marketplace distribution. When adding a new plugin, add an entry here pointing to its source directory.

## npm Workspaces

`package.json` declares `plugins/*` and `skills/**/*` as workspaces. Each plugin/skill that needs its own `package.json` is auto-discovered.
