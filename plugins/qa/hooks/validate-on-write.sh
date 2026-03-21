#!/usr/bin/env bash
# PreToolUse hook: warn on writes to plugin.json, SKILL.md, or commands/*.md
# that produce invalid components. Does not block — prints warnings to stderr.

set -euo pipefail

# Read tool use JSON from stdin
INPUT=$(cat)

# Extract file_path from the tool input
if command -v jq &>/dev/null; then
    FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null || true)
else
    # Fallback: use python3 to parse JSON
    FILE_PATH=$(python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get('tool_input', {}).get('file_path', ''))
except Exception:
    print('')
" <<< "$INPUT" 2>/dev/null || true)
fi

# If no file path extracted, exit without blocking
if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Find repo root by walking up from the file's directory looking for .claude-plugin/marketplace.json
find_repo_root() {
    local dir
    dir=$(dirname "$1")
    # Resolve to absolute path
    dir=$(python3 -c "import os; print(os.path.realpath('$dir'))" 2>/dev/null || echo "$dir")
    local max_depth=10
    local depth=0
    while [ "$dir" != "/" ] && [ $depth -lt $max_depth ]; do
        if [ -f "$dir/.claude-plugin/marketplace.json" ]; then
            echo "$dir"
            return 0
        fi
        dir=$(dirname "$dir")
        depth=$((depth + 1))
    done
    return 1
}

REPO_ROOT=$(find_repo_root "$FILE_PATH" 2>/dev/null || true)
if [ -z "$REPO_ROOT" ]; then
    exit 0
fi

SCRIPTS_DIR="$REPO_ROOT/plugins/qa/scripts"

# Helper: run a validator and print failures to stderr
run_and_warn() {
    local script="$1"
    local target="$2"

    if [ ! -f "$script" ]; then
        return 0
    fi

    local output
    output=$(python3 "$script" "$target" 2>/dev/null || true)
    local exit_code=$?

    if [ "$exit_code" -eq 1 ]; then
        echo "[qa hook] Validation failures detected in: $target" >&2
        echo "$output" >&2
    fi
}

BASENAME=$(basename "$FILE_PATH")
DIR=$(dirname "$FILE_PATH")
DIR_BASENAME=$(basename "$DIR")

# SKILL.md: validate parent skill directory
if [ "$BASENAME" = "SKILL.md" ]; then
    run_and_warn "$SCRIPTS_DIR/validate_skill.py" "$DIR"
fi

# plugin.json in .claude-plugin/ dir: validate grandparent plugin directory
if [ "$BASENAME" = "plugin.json" ] && [ "$DIR_BASENAME" = ".claude-plugin" ]; then
    PLUGIN_DIR=$(dirname "$DIR")
    run_and_warn "$SCRIPTS_DIR/validate_plugin.py" "$PLUGIN_DIR"
fi

# commands/*.md: validate the command file directly
if [ "$BASENAME" != "${BASENAME%.md}" ] && [ "$DIR_BASENAME" = "commands" ]; then
    run_and_warn "$SCRIPTS_DIR/validate_command.py" "$FILE_PATH"
fi

# Always exit 0 — never block the write
exit 0
