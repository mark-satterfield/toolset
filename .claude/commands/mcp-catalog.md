---
description: Discover and catalog all MCP servers and their tools across the project and user environment
user-invocable: true
---

# MCP Catalog

You are running the mcp-catalog skill. Follow these steps exactly.

## Step 1: Discover

Run the discovery script to find all MCP server configurations:

```bash
python3 "$SKILL_DIR/scripts/discover.py" --project-dir "$(pwd)" --output /tmp/mcp-catalog-discovered.json
```

Read the output file and present the results to the user.

## Step 2: Present servers and get user approval

Group the discovered servers by risk classification and present them to the user:

**Ready to introspect (safe):**
List each server name, source file, and transport type.

**Missing environment variables (needs-env):**
List each server name and which env vars are missing. Warn that introspection will fail unless the vars are set.

**Requires interactive login (needs-auth):**
List each server name and URL. Warn that these servers require OAuth or other interactive authentication. Claude cannot complete this in a `claude -p` session.

**Unknown risk:**
List these and let the user decide.

Ask: "Which servers should I skip? Reply with a comma-separated list of names to exclude, or 'none' to introspect everything that's safe."

Default behavior: Skip all `needs-auth` servers unless the user explicitly opts them in. Include all `safe` servers. Ask about `needs-env` and `unknown`.

## Step 3: Write approved list

Based on the user's response, write `/tmp/mcp-catalog-approved.json` containing only the servers the user wants introspected. Use the same JSON structure as `discovered_servers.json` but with the filtered server list.

## Step 4: Introspect

Run the introspection script:

```bash
bash "$SKILL_DIR/scripts/introspect.sh" /tmp/mcp-catalog-approved.json /tmp/mcp-catalog-results
```

This will take time proportional to the number of servers. Each server launches a separate `claude -p` session. Give the user a heads-up on estimated time and token cost.

If a server fails, note it and continue. Do not retry automatically.

## Step 5: Assemble catalog

Run the assembly script:

```bash
python3 "$SKILL_DIR/scripts/assemble.py" \
    --discovered /tmp/mcp-catalog-discovered.json \
    --approved /tmp/mcp-catalog-approved.json \
    --results-dir /tmp/mcp-catalog-results \
    --output mcp-catalog.json
```

## Step 6: Report

Read `mcp-catalog.json` and present a summary:
- Total servers found vs cataloged vs skipped vs failed
- For each cataloged server: name, tool count, and a one-line description of what the server does
- For failed servers: the error

Then tell the user: "The full catalog is in `mcp-catalog.json` in your project root."
