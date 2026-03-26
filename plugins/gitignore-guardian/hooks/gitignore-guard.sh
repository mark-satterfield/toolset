#!/usr/bin/env bash
# PreToolUse hook: blocks git add/commit on gitignored files.
# Prevents the common Auto-Claude error loop where agents repeatedly try to
# commit files inside .auto-claude/ or other gitignored directories.
#
# Exit 0 = allow, Exit 2 = block (stderr sent to Claude as correction)

set -euo pipefail

INPUT=$(cat)

# Extract command from Bash tool input
set +e
COMMAND=$(node -e "
  const d = JSON.parse(process.argv[1]);
  const ti = d.tool_input || {};
  process.stdout.write(ti.command || '');
" "$INPUT" 2>/dev/null)
NODE_EXIT=$?
set -e

if [ $NODE_EXIT -ne 0 ] || [ -z "$COMMAND" ]; then
  exit 0
fi

# Only check git add commands
if ! echo "$COMMAND" | grep -qE '^\s*git\s+add\b'; then
  exit 0
fi

# Extract file paths from git add command (skip flags like -A, -u, --all, -f, -p)
# Parse out the actual file arguments
set +e
FILES=$(echo "$COMMAND" | sed -E 's/^\s*git\s+add\s+//' | tr ' ' '\n' | grep -vE '^-' | grep -vE '^\s*$')
set -e

if [ -z "$FILES" ]; then
  # git add with only flags (like git add -A or git add .) -- check for broad adds
  if echo "$COMMAND" | grep -qE 'git\s+add\s+(-A|--all|\.)'; then
    # Warn but don't block -- the CLAUDE.md already says to avoid git add -A
    cat >&2 <<CORRECTION
WARNING: Using 'git add -A' or 'git add .' is discouraged.
Stage specific files by name instead to avoid accidentally including gitignored files.
CORRECTION
    # Don't block, just warn (exit 0)
    exit 0
  fi
  exit 0
fi

# Check each file against .gitignore
IGNORED_FILES=""
while IFS= read -r file; do
  [ -z "$file" ] && continue
  # git check-ignore returns 0 if the file IS ignored
  if git check-ignore -q "$file" 2>/dev/null; then
    IGNORED_FILES="${IGNORED_FILES}  - ${file}\n"
  fi
done <<< "$FILES"

if [ -z "$IGNORED_FILES" ]; then
  exit 0
fi

cat >&2 <<CORRECTION
BLOCKED: These files are intentionally excluded from version control.
$(echo -e "$IGNORED_FILES")
CORRECTION

exit 2
