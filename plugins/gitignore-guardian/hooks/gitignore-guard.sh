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
# Split on newlines and tabs as well as spaces: a multi-line `git add a \<newline> b`
# left every continuation line glued together and produced bogus "paths".
FILES=$(echo "$COMMAND" | sed -E 's/^\s*git\s+add\s+//' | tr ' \t\n' '\n\n\n' | grep -vE '^-' | grep -vE '^\s*$' | grep -vE '^\\$')
set -e

# Evaluate ignore rules IN THE REPO THE COMMAND ACTUALLY TARGETS. This hook runs in the
# session's working directory, so a compound command like `cd <repo> && git add <file>`
# was being checked against the SESSION repo's .gitignore, not the target repo's.
# In this fleet the orchestration repo carries a bare `package.json` rule — correct there,
# since it is not a package repo — which meant `git add apps/web/package.json` inside ANY
# of the sibling service repos was blocked as "intentionally excluded" when the file was
# tracked and matched no rule in its own repo. Honor a leading `cd` so paths resolve
# against the repo they belong to.
set +e
WORKDIR=$(echo "$COMMAND" | sed -nE "s/.*(^|[;&|[:space:]])cd[[:space:]]+(\"([^\"]+)\"|'([^']+)'|([^;&|[:space:]]+)).*/\3\4\5/p" | head -1)
set -e
if [ -n "$WORKDIR" ] && [ -d "$WORKDIR" ]; then
  cd "$WORKDIR" || true
fi

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
  # A file git ALREADY TRACKS cannot be "intentionally excluded from version control" —
  # git itself does not apply .gitignore to tracked files, so staging a change to one is
  # always legitimate. check-ignore still pattern-matches such a path and reports it as
  # ignored, which made this guard block ordinary edits to tracked files. Skip them.
  # (The guard's real job — catching a NEW file that a rule excludes — is unaffected.)
  if git ls-files --error-unmatch "$file" >/dev/null 2>&1; then
    continue
  fi
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
