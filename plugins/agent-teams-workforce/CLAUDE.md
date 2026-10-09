# agent-teams-workforce — Claude Code Instructions

@README.md

## Working in this plugin

This is the primary, actively-developed plugin. Its detailed specifications are large — open them on demand rather than loading everything at once:

- `AGENT-TEAMS-WORKFORCE.md` — full workforce and SDLC pipeline specification
- `AGENT-INSTRUCTIONS.md` — how the agent roster is authored and generated
- `agents-file.md` — the Agent Teams Workforce block that `polyrepo agents-sync` writes into each repository's `AGENTS.md`

Agents live in `agents/` (auto-discovered), skills in `skills/`, commands in `commands/`.

## Retries

Retry when there is a reasonable expectation that the retry will succeed. Don't retry when there isn't.

- **Reasonable:** the next attempt carries clarified instructions or specific feedback on what was missing and how to correct it; contention or a collision that clears with time (`bd`/Dolt locks and timeouts, git locks), retried with backoff; the owner's handling of Anthropic API and quota errors.
- **Not reasonable:** running the same step again with nothing changed. It repeats the same failure, so it is diagnosed instead.
- Work that already succeeded is never redone.
- Errors are caught where they happen and recorded with a structured cause, never swallowed.

## Shipping a change

A commit to this plugin is not a shipped fix — the marketplace resolves plugins by version, so a change with no version bump never reaches a running session. Bump with `/version` (the `version-plugins` skill), never by hand-editing the manifests: it moves `.claude-plugin/marketplace.json` and this plugin's `.claude-plugin/plugin.json` together in one commit, and a version that moves in only one of them ships nothing. Push, then tell the plugin owner the new version number so they can run `/plugin marketplace update mark-satterfield` and `/reload-plugins`.
