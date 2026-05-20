#!/usr/bin/env bash
#
# introspect.sh — Introspect MCP servers by launching temporary claude -p sessions.
#
# Usage: bash introspect.sh <approved_servers.json> [output_dir]
#
# For each server in approved_servers.json, this script:
#   1. Writes a temporary .mcp.json config for that single server
#   2. Launches `claude -p --mcp-config <tmp> --bare --max-turns 1 --output-format json`
#   3. Parses the response via parse_response.py
#   4. Saves structured result to <output_dir>/<server_name>.json
#
# Environment variables:
#   INTROSPECT_TIMEOUT  — seconds to wait per server (default: 60)
#   INTROSPECT_MODEL    — model to use (default: sonnet)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPROVED_FILE="${1:?Usage: introspect.sh <approved_servers.json> [output_dir]}"
OUTPUT_DIR="${2:-introspect_results}"
INTROSPECT_TIMEOUT="${INTROSPECT_TIMEOUT:-60}"
MODEL="${INTROSPECT_MODEL:-sonnet}"

mkdir -p "$OUTPUT_DIR"

# Verify prerequisites
if ! command -v claude &>/dev/null; then
    echo "ERROR: 'claude' CLI not found in PATH." >&2
    echo "This skill requires Claude Code CLI to be installed." >&2
    exit 1
fi

if ! command -v python3 &>/dev/null; then
    echo "ERROR: 'python3' not found in PATH." >&2
    exit 1
fi

# Count servers
TOTAL=$(python3 -c "
import json
with open('$APPROVED_FILE') as f:
    data = json.load(f)
print(len(data.get('servers', [])))
")

if [ "$TOTAL" -eq 0 ]; then
    echo "No servers to introspect."
    exit 0
fi

echo "Introspecting $TOTAL MCP server(s)..."
echo "  Timeout per server: ${INTROSPECT_TIMEOUT}s"
echo "  Model: $MODEL"
echo "  Output: $OUTPUT_DIR/"
echo ""

# Generate the server iteration data — writes each server config to its own temp file
python3 -c "
import json
with open('$APPROVED_FILE') as f:
    data = json.load(f)
for i, srv in enumerate(data.get('servers', [])):
    config_path = '/tmp/mcp-cat-srv-{}.json'.format(i)
    with open(config_path, 'w') as cf:
        json.dump(srv['config'], cf)
    print('{}\t{}\t{}'.format(i, srv['name'], config_path))
" | while IFS=$'\t' read -r idx name config_path; do
    echo "[$((idx + 1))/$TOTAL] Introspecting: $name"

    # Build temporary mcp config wrapping the single server
    TMP_MCP=$(mktemp /tmp/mcp-catalog-XXXXXX.json)
    python3 -c "
import json
with open('$config_path') as f:
    config = json.load(f)
wrapper = {'mcpServers': {'$name': config}}
with open('$TMP_MCP', 'w') as f:
    json.dump(wrapper, f)
"

    TMP_RAW=$(mktemp /tmp/mcp-cat-raw-XXXXXX.json)
    RESULT_FILE="$OUTPUT_DIR/${name}.json"

    PROMPT="You have exactly one MCP server connected named \"$name\".

List ALL tools that this MCP server provides. For each tool, provide:
1. The tool name (exactly as registered)
2. The description
3. The input_schema (the full JSON schema for the tool's parameters)

Respond with ONLY a JSON object matching this structure:
{
  \"server_name\": \"$name\",
  \"tools\": [
    {
      \"name\": \"tool_name\",
      \"description\": \"what it does\",
      \"input_schema\": {}
    }
  ]
}

If the MCP server failed to connect or has no tools, return:
{\"server_name\": \"$name\", \"tools\": [], \"error\": \"description of what went wrong\"}

Do NOT use any tools. Do NOT search for anything. Just list the MCP tools you see in your context from the $name server."

    # Run claude -p
    set +e
    timeout "$INTROSPECT_TIMEOUT" claude -p "$PROMPT" \
        --mcp-config "$TMP_MCP" \
        --bare \
        --max-turns 1 \
        --model "$MODEL" \
        --output-format json \
        < /dev/null \
        > "$TMP_RAW" 2>/dev/null
    EXIT_CODE=$?
    set -e

    # Clean up temp mcp config and server config
    rm -f "$TMP_MCP" "$config_path"

    if [ $EXIT_CODE -ne 0 ]; then
        echo "  FAILED (exit code: $EXIT_CODE)"
        python3 -c "
import json
result = {
    'server_name': '$name',
    'tools': [],
    'status': 'failed',
    'error': 'claude -p exited with code $EXIT_CODE (timeout=${INTROSPECT_TIMEOUT}s)'
}
with open('$RESULT_FILE', 'w') as f:
    json.dump(result, f, indent=2)
"
        rm -f "$TMP_RAW"
        continue
    fi

    # Parse the response using the standalone parser
    python3 "$SCRIPT_DIR/parse_response.py" "$TMP_RAW" "$name" "$RESULT_FILE"
    rm -f "$TMP_RAW"

    # Report
    TOOL_COUNT=$(python3 -c "
import json
with open('$RESULT_FILE') as f:
    data = json.load(f)
print(len(data.get('tools', [])))
" 2>/dev/null || echo "?")

    STATUS=$(python3 -c "
import json
with open('$RESULT_FILE') as f:
    data = json.load(f)
print(data.get('status', 'unknown'))
" 2>/dev/null || echo "unknown")

    echo "  $STATUS — $TOOL_COUNT tool(s)"
done

echo ""
echo "Introspection complete. Results in: $OUTPUT_DIR/"
