# Agentic Workflow Plugin

This plugin packages agents, skills, commands, and supporting assets for an SDLC-focused agent-teams-workforce. The pipeline runs from PRD Creation through a TRD Authoring phase (Phase 2.5) into Specs, with a living arc42 SAD as the architecture source of truth that feeds both the TRD and the Specs.

## Structure

- `agents/` - agent definitions generated from the SDLC roster.
- `commands/` - slash-command style entry points for orchestration and common workflows.
- `skills/` - reusable skill instructions and task-specific workflows.
- `references/` - source documents and inputs used to generate or maintain the plugin.
- `scripts/` - automation for generating, validating, or syncing plugin content.
- `hooks/` - optional lifecycle hooks.
- `assets/` - plugin icons, screenshots, and other static assets.

## Source Roster

The roster is defined by the agent files in `agents/`.

Current roster scope:

- 173 SDLC agents across 13 teams (including the cross-cutting Documentation team and the upstream PRD Creation team) plus a governance group
- 1 standalone specialist: `polyrepo-cartographer`

Workforce rules live in `rules/separation-of-duties.md`.

> [!IMPORTANT]
>
> `sdlc-worforce.md` has been renamed to `AGENT-TEAMS-WORKFORCE.md`