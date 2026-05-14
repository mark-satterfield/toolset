# Agentic Workflow Plugin

This plugin packages agents, skills, commands, and supporting assets for an SDLC-focused agent-teams-workforce.

## Structure

- `agents/` - agent definitions generated from the SDLC roster.
- `commands/` - slash-command style entry points for orchestration and common workflows.
- `skills/` - reusable skill instructions and task-specific workflows.
- `references/` - source documents and inputs used to generate or maintain the plugin.
- `scripts/` - automation for generating, validating, or syncing plugin content.
- `hooks/` - optional lifecycle hooks.
- `assets/` - plugin icons, screenshots, and other static assets.

## Source Roster

The initial roster is copied to `references/sdlc-agent-roster.csv`.

Current roster scope:

- 73 agents
- 11 teams
- Command agents: `ss-master-orchestrator`, `ss-iteration-supervisor`, `ss-beads-coordinator`, `ss-repository-manager`, `ss-patrol-agent`

