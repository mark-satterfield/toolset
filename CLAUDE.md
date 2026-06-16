# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

A personal Claude Code plugin and skill monorepo. It publishes reusable extensions to the Claude Code plugin marketplace under the `mark-satterfield` namespace.

- `plugins/` — Claude Code plugins (commands + skills bundled as installable units)
- `skills/` — Standalone behavioral skills not tied to a plugin

## Commands

No build step and no npm scripts. Plugins and skills are plain Markdown/YAML — no compilation required. They are distributed via the marketplace manifest (`.claude-plugin/marketplace.json`); install one by copying or symlinking its `plugins/<name>/` (or `skills/<name>/`) directory into your Claude config.

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

## Primary Plugin: agent-teams-workforce

The plugin under active development and the center of gravity for agentic SDLC work. It packages bounded-specialist agents, skills, and commands that run a phase-gated SDLC pipeline under a maker-checker, no-self-approval doctrine.

- Agents: `plugins/agent-teams-workforce/agents/` — bounded specialists (one task category each), auto-discovered; adding `agents/<name>.md` needs no central roster edit.
- Skills: `plugins/agent-teams-workforce/skills/` — reusable playbooks, including the `arc42` router + sub-skills (`arc42-author` / `-maintain` / `-extract` / `-verify`) and `c4-diagramming` / `uml-diagramming` (Mermaid-first; keep mermaid fences in `references/`, never in a `SKILL.md` body).
- Commands: `plugins/agent-teams-workforce/commands/`.
- Pipeline (workflow 1): PRD Creation → PRD Validation → Architecture Analysis (Gate 2) → **TRD Authoring (Phase 2.5 / Gate 2b)** → Spec Authoring (Gate 3) → Task Decomposition → … → Deployment. A living **arc42 SAD**, consolidated by `sad-maintainer` at the tail of Phase 2, is the architecture source of truth; its §2/§4/§8/§9 source-extract feeds the TRD and the Specs.
- Governance: `Project Delivery Agentic Workforce Doctrine.md` and `rules/separation-of-duties.md` — bounded authority, no self-approval (every maker has a distinct checker), read-only coordination for leads, decider ≠ analyst.

Skill quality is gated by `plugins/qa/scripts/validate_skill.py` (REQUIRED: frontmatter present, description ≥ 50 chars, body ≥ 200 chars, no `last updated/modified` text, no mermaid code fence in the body).

## Marketplace Registration

`.claude-plugin/marketplace.json` at repo root registers plugins for marketplace distribution. When adding a new plugin, add an entry here pointing to its source directory.

## npm Workspaces

`package.json` declares `plugins/*` and `skills/**/*` as workspaces. Each plugin/skill that needs its own `package.json` is auto-discovered.
