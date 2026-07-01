#!/usr/bin/env bash
# memory-backend.sh — detect persistent memory backend for this project
#
# Returns "beads" when the project uses bd remember (`.beads/` present, bd on PATH).
# Returns "memory-md" for Claude Code native auto-memory (MEMORY.md).
#
# Usage:
#   source "${CLAUDE_PLUGIN_ROOT}/hooks/lib/memory-backend.sh"
#   BACKEND="$(detect_memory_backend)"
#
# Or from shell:
#   ./hooks/lib/memory-backend.sh          # prints backend name
#   ./hooks/lib/memory-backend.sh --check  # exit 0 if beads, 1 if memory-md

detect_memory_backend() {
    if [ -f "${HOME}/.claude/hooks/lib/bd-guard.sh" ]; then
        # shellcheck source=/dev/null
        source "${HOME}/.claude/hooks/lib/bd-guard.sh"
        if bd_guard 2>/dev/null; then
            echo "beads"
            return 0
        fi
    elif command -v bd >/dev/null 2>&1; then
        local dir="${1:-${PWD}}"
        while [ "$dir" != "/" ] && [ -n "$dir" ]; do
            if [ -d "$dir/.beads" ]; then
                echo "beads"
                return 0
            fi
            dir="$(dirname "$dir")"
        done
    fi

    echo "memory-md"
}

# Session context hint: if instructions say "Use bd remember" and NOT "MEMORY.md",
# prefer beads even when bd_guard is unavailable (e.g. sandbox without bd binary).
detect_memory_backend_from_context() {
    local context="${1:-}"
    if [ -n "$context" ]; then
        if echo "$context" | grep -q "bd remember" && \
           echo "$context" | grep -q "Do NOT use MEMORY.md"; then
            echo "beads"
            return 0
        fi
    fi
    detect_memory_backend
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    backend="$(detect_memory_backend)"
    if [ "${1:-}" = "--check" ]; then
        [ "$backend" = "beads" ] && exit 0 || exit 1
    fi
    echo "$backend"
fi
