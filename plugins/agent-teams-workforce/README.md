# Agentic Workflow Plugin

This plugin packages agents, skills, commands, and supporting assets for an SDLC-focused agent-teams-workforce. The pipeline runs from PRD Creation through a TRD Authoring phase (Phase 2.5) into Specs, with the architecture documentation as the source of truth that feeds both the TRD and the Specs: the effective architecture in its arc42 folder, the targets proposed for a feature, and the deltas between them.

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

- 172 SDLC agents across 13 teams (including the cross-cutting Documentation team and the upstream PRD Creation team) plus a governance group

> [!IMPORTANT]
>
> `sdlc-worforce.md` has been renamed to `AGENT-TEAMS-WORKFORCE.md`
## Check release coherence before evaluating workflow changes

Run the read-only report with the exact plugin root whose workflows will run and the Claude configuration directory the owner launches with:

```sh
node "$ATW_PLUGIN_ROOT/scripts/report-release-coherence.cjs" \
  --workflow-root "$ATW_PLUGIN_ROOT" \
  --config-dir "${CLAUDE_CONFIG_DIR:-$HOME/.claude}" \
  --project "$PWD" \
  --mcp-config "$PWD/.mcp.json"
```

Set these variables for the environment being evaluated; the project and MCP file arguments are optional. The report names registered releases, compares rendered MCP agent copies, flags foreign/missing/different copies, resolves internal skill names in the selected release and reports declarations in the supplied MCP file. Exact content matches cannot prove provenance or what an already-running session loaded. External skills, merged MCP configuration and live server health require owner verification. After publishing, update/reload the intended release before evaluating changed behavior. The report never synchronizes copies, updates installations, starts workflows or changes authentication.


## Dispatch retry policy

The workflow caller can supply `retryPolicy: { maxAttempts, maxWaitMs }`. The existing retrying dispatch wrappers consume it; composite callers forward it to their children. Defaults are three total attempts and at most 300,000 milliseconds of scheduled waiting per dispatch. These are operational retry bounds, not agent token budgets. A host without a timer returns an interruption rather than retrying immediately.

Account/session exhaustion stops immediately with `stage: account-quota-exhausted`; exhausted transport retries stop with `stage: api-unavailable`. Both return `ok: false`, `dispatchFailed`, `paused`, `resumable` and the original error/reset text in `dispatchInterruption`. Subsequent dispatches in that invocation stop, and existing results and saved artifacts remain available. Deterministic schema failures keep their existing failure path. Numeric Retry-After seconds and `retryAfterMs` are honored; an HTTP-date without a clock is handed back as an interruption rather than retried too early. The supervising caller owns waiting and resuming; the workflow does not invent an account reset time.
