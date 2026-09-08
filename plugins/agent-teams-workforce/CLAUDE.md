# agent-teams-workforce — Claude Code Instructions

@README.md

## Working in this plugin

This is the primary, actively-developed plugin. Its detailed specifications are large — open them on demand rather than loading everything at once:

- `AGENT-TEAMS-WORKFORCE.md` — full workforce and SDLC pipeline specification
- `Project Delivery Agentic Workforce Doctrine.md` — governance doctrine (bounded authority, maker-checker, no self-approval)
- `rules/separation-of-duties.md` — separation-of-duties rules every agent must honor
- `AGENT-INSTRUCTIONS.md` — how the agent roster is authored and generated
- `agents-file.md` — agent roster source notes

Agents live in `agents/` (auto-discovered), skills in `skills/`, commands in `commands/`.

## Shipping a change

A commit to this plugin is not a shipped fix — the marketplace resolves plugins by version, so a change with no version bump never reaches a running session. Bump with `/version` (the `version-plugins` skill), never by hand-editing the manifests: it moves `.claude-plugin/marketplace.json` and this plugin's `.claude-plugin/plugin.json` together in one commit, and a version that moves in only one of them ships nothing. Push, then tell Mark the new version number so he can run `/plugin marketplace update mark-satterfield` and `/reload-plugins`.
