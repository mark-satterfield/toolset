#!/usr/bin/env bash
# PreToolUse hook: blocks dangerous Edit/Write/MultiEdit operations on .gitignore files.
# Prevents accidental removal of sensitive patterns, @protect violations, and overly broad additions.
#
# Exit 0 = allow, Exit 2 = block (stderr sent to Claude as correction)

set -euo pipefail

# Read JSON input from stdin
INPUT=$(cat)

# Extract tool_name, file_path, and content changes using node
set +e
EXTRACTED=$(node -e "
  const d = JSON.parse(process.argv[1]);
  const ti = d.tool_input || {};
  const tool = d.tool_name || '';

  // Get file path
  const filePath = ti.file_path || ti.filePath || '';

  // Only process .gitignore files
  if (!filePath.endsWith('.gitignore') && !filePath.endsWith('/.gitignore')) {
    process.stdout.write(JSON.stringify({ skip: true }));
    process.exit(0);
  }

  // Get old and new content depending on tool type
  let oldContent = '';
  let newContent = '';
  if (tool === 'Write') {
    newContent = ti.content || '';
  } else if (tool === 'Edit') {
    oldContent = ti.old_string || '';
    newContent = ti.new_string || '';
  } else if (tool === 'MultiEdit') {
    const edits = ti.edits || [];
    oldContent = edits.map(e => e.old_string || '').join('\n');
    newContent = edits.map(e => e.new_string || '').join('\n');
  }

  process.stdout.write(JSON.stringify({ skip: false, filePath, oldContent, newContent, tool }));
" "$INPUT" 2>/dev/null)
NODE_EXIT=$?
set -e

if [ $NODE_EXIT -ne 0 ] || [ -z "$EXTRACTED" ]; then
  exit 0
fi

# Check if we should skip (not a .gitignore file)
set +e
SKIP=$(node -e "process.stdout.write(String(JSON.parse(process.argv[1]).skip))" "$EXTRACTED" 2>/dev/null)
set -e

if [ "$SKIP" = "true" ]; then
  exit 0
fi

# Extract fields
set +e
FILE_PATH=$(node -e "process.stdout.write(JSON.parse(process.argv[1]).filePath)" "$EXTRACTED" 2>/dev/null)
OLD_CONTENT=$(node -e "process.stdout.write(JSON.parse(process.argv[1]).oldContent)" "$EXTRACTED" 2>/dev/null)
NEW_CONTENT=$(node -e "process.stdout.write(JSON.parse(process.argv[1]).newContent)" "$EXTRACTED" 2>/dev/null)
TOOL_NAME=$(node -e "process.stdout.write(JSON.parse(process.argv[1]).tool)" "$EXTRACTED" 2>/dev/null)
set -e

VIOLATIONS=""

# --- Check 1: Sensitive pattern removal ---
# These patterns protect secrets and credentials. Removing them is dangerous.
SENSITIVE_PATTERNS=('.env' '*.pem' '*.key' 'credentials*' '*.p12' '*.pfx' '*secret*' '*.keystore' 'service-account*.json')

if [ -n "$OLD_CONTENT" ]; then
  for pattern in "${SENSITIVE_PATTERNS[@]}"; do
    # Check if old_string contains this pattern (being removed) and new_string does not
    if echo "$OLD_CONTENT" | grep -qF "$pattern"; then
      if ! echo "$NEW_CONTENT" | grep -qF "$pattern"; then
        VIOLATIONS="${VIOLATIONS}  - Removing sensitive pattern: '${pattern}'\n"
      fi
    fi
  done
fi

# --- Check 2: @protect annotation violation ---
# Removing or modifying @protect lines is blocked
if [ -n "$OLD_CONTENT" ]; then
  if echo "$OLD_CONTENT" | grep -qE '^#[[:space:]]*@protect:'; then
    if ! echo "$NEW_CONTENT" | grep -qE '^#[[:space:]]*@protect:'; then
      VIOLATIONS="${VIOLATIONS}  - Removing @protect annotation (these are intentionally protected entries)\n"
    fi
  fi
  if echo "$OLD_CONTENT" | grep -qE '^#[[:space:]]*@protect-start'; then
    if ! echo "$NEW_CONTENT" | grep -qE '^#[[:space:]]*@protect-start'; then
      VIOLATIONS="${VIOLATIONS}  - Removing @protect-start block marker\n"
    fi
  fi
  if echo "$OLD_CONTENT" | grep -qE '^#[[:space:]]*@protect-end'; then
    if ! echo "$NEW_CONTENT" | grep -qE '^#[[:space:]]*@protect-end'; then
      VIOLATIONS="${VIOLATIONS}  - Removing @protect-end block marker\n"
    fi
  fi
  # @index annotations are also protected from removal
  if echo "$OLD_CONTENT" | grep -qE '^#[[:space:]]*@index:'; then
    if ! echo "$NEW_CONTENT" | grep -qE '^#[[:space:]]*@index:'; then
      VIOLATIONS="${VIOLATIONS}  - Removing @index annotation (these override IDE exclusion behavior)\n"
    fi
  fi
  if echo "$OLD_CONTENT" | grep -qE '^#[[:space:]]*@index-start'; then
    if ! echo "$NEW_CONTENT" | grep -qE '^#[[:space:]]*@index-start'; then
      VIOLATIONS="${VIOLATIONS}  - Removing @index-start block marker\n"
    fi
  fi
  if echo "$OLD_CONTENT" | grep -qE '^#[[:space:]]*@index-end'; then
    if ! echo "$NEW_CONTENT" | grep -qE '^#[[:space:]]*@index-end'; then
      VIOLATIONS="${VIOLATIONS}  - Removing @index-end block marker\n"
    fi
  fi
fi

# --- Check 3: Overly broad pattern addition ---
# Warn (but don't block) on patterns that would ignore source files
BROAD_PATTERNS=('*' '**' '*.py' '*.ts' '*.tsx' '*.js' '*.jsx' '*.java' '*.go' '*.rs' '*.rb' '*.swift')

if [ -n "$NEW_CONTENT" ]; then
  for pattern in "${BROAD_PATTERNS[@]}"; do
    # Check if new content adds this broad pattern (and old didn't have it)
    if echo "$NEW_CONTENT" | grep -qxF "$pattern"; then
      if [ -z "$OLD_CONTENT" ] || ! echo "$OLD_CONTENT" | grep -qxF "$pattern"; then
        VIOLATIONS="${VIOLATIONS}  - Adding overly broad pattern: '${pattern}' (would ignore source files)\n"
      fi
    fi
  done
fi

# If no violations, allow
if [ -z "$VIOLATIONS" ]; then
  exit 0
fi

# Block with correction message on stderr
cat >&2 <<CORRECTION
BLOCKED: Dangerous .gitignore modification in ${FILE_PATH}

Violations found:
$(echo -e "$VIOLATIONS")
The gitignore-guardian skill protects against accidental changes that could:
  - Expose secrets by removing protective patterns
  - Override intentionally-protected entries (@protect annotations)
  - Ignore source code files with overly broad patterns

To proceed:
  - If removing a sensitive pattern is intentional, explain why and get user confirmation
  - If modifying @protect entries, use 'python3 tools/gitignore_audit.py protect' to manage them
  - If adding broad patterns, use specific paths instead (e.g., '/build/' not '*')

See: .claude/skills/gitignore-guardian/SKILL.md
CORRECTION

exit 2
