---
name: mcp-catalog
description: >
  Discover and catalog all MCP servers and their tools across a Claude Code project and user environment.
  Scans config files (.mcp.json, .claude/settings.json, .claude/settings.local.json, ~/.claude.json,
  ~/.claude/settings.json, ~/.claude/settings.local.json), installed plugins, and Claude Desktop configs.
  For each discovered MCP server, introspects available tools using `claude -p --mcp-config` and produces
  a structured JSON catalog. Use when the user asks to "list all MCPs", "catalog MCP tools",
  "what MCP servers do I have", "inventory my tools", "audit MCP config", "show me all available tools",
  or any variant of discovering what MCP integrations exist. Also triggers on "mcp catalog",
  "mcp inventory", "mcp audit", or "tool catalog".
---

# MCP Catalog

Discovers every MCP server configured across the user's Claude Code environment and catalogs their tools
into a single JSON file.

## How it works

1. **Discovery** — The `scripts/discover.py` script scans all known config locations for MCP server
   definitions. It merges and deduplicates servers found across scopes (project, local, user, plugins,
   Claude Desktop).

2. **Risk classification** — Each server is classified before introspection:
   - `safe` — stdio servers with no env vars or only non-secret env vars
   - `needs-env` — stdio servers referencing env vars that aren't set in the current shell
   - `needs-auth` — HTTP/SSE servers requiring OAuth or interactive login
   - `unknown` — anything that can't be classified

3. **User confirmation** — Before introspecting, present the user with the list of discovered servers
   grouped by risk. Servers classified as `needs-auth` or `needs-env` are flagged. Ask the user which
   servers to skip. Respect their choices.

4. **Introspection** — For each approved server, `scripts/introspect.sh` launches a temporary
   `claude -p --mcp-config <temp-config> --bare --max-turns 1 --output-format json` session that asks
   Claude to list all tools from that MCP server. The response is parsed and tools are extracted.

5. **Catalog assembly** — `scripts/assemble.py` merges all results into a single JSON catalog.

## Running the skill

Execute the orchestrator script:

```bash
python3 scripts/discover.py --project-dir "$(pwd)"
```

This produces `discovered_servers.json` in the working directory.

Then present the servers to the user for confirmation. After confirmation, run:

```bash
bash scripts/introspect.sh discovered_servers.json approved_servers.json
```

Where `approved_servers.json` is the filtered list after user opt-outs.

Finally, assemble the catalog:

```bash
python3 scripts/assemble.py --output mcp-catalog.json
```

## Output format

The catalog JSON has this structure:

```json
{
  "generated_at": "2026-04-27T12:00:00Z",
  "project_dir": "/Users/msat1971/git/my-project",
  "servers": [
    {
      "name": "github",
      "source": ".mcp.json",
      "scope": "project",
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "risk": "safe",
      "status": "cataloged",
      "tools": [
        {
          "name": "create_issue",
          "description": "Create a new GitHub issue",
          "input_schema": { "type": "object", "properties": { "..." : "..." } }
        }
      ],
      "error": null
    },
    {
      "name": "notion",
      "source": "~/.claude/settings.json",
      "scope": "user",
      "transport": "http",
      "url": "https://mcp.notion.com/mcp",
      "risk": "needs-auth",
      "status": "skipped",
      "tools": [],
      "error": "User opted out (requires interactive OAuth)"
    }
  ],
  "summary": {
    "total_servers": 12,
    "cataloged": 8,
    "skipped": 3,
    "failed": 1,
    "total_tools": 47
  }
}
```

## Important notes

- The `--mcp-config` flag loads servers for a single session without modifying the user's config.
  No servers are permanently added or removed.
- Introspection uses `--bare` to skip hooks, skills, plugins, and CLAUDE.md for fast startup.
- `--max-turns 1` prevents runaway sessions.
- Servers that fail to start within the MCP_TIMEOUT (default 30s) are marked as `failed`.
- The prompt sent to `claude -p` asks for JSON output with a `--json-schema` constraint when possible.
- Each introspection session costs tokens. For a project with 15 MCP servers, expect roughly
  $0.50-$1.00 in API usage on Sonnet.
