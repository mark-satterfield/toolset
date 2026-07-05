#!/usr/bin/env bash
# OKF Bundle Validator (v0.1 conformance)
# Usage: validate-okf.sh [bundle-path]
#
# Checks the three OKF v0.1 conformance rules and reports non-blocking
# warnings. Exit codes: 0 = conformant, 1 = conformance failure(s),
# 2 = usage/path error.
#
#   E1: every non-reserved .md file has a YAML frontmatter block
#   E2: every frontmatter block has a non-empty `type` field
#   E3: reserved files (index.md, log.md) follow their structure rules
#
# Warnings never affect the exit code — the spec forbids rejecting a
# bundle for any of them.

set -euo pipefail

BUNDLE="${1:-.}"
ERRORS=0
WARNINGS=0
TOTAL=0

if [ -t 1 ]; then
  RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[0;33m'; NC=$'\033[0m'
else
  RED=''; GREEN=''; YELLOW=''; NC=''
fi

if [ ! -d "$BUNDLE" ]; then
  echo "${RED}Error: '$BUNDLE' is not a directory${NC}" >&2
  exit 2
fi

echo "Validating OKF bundle: $BUNDLE"
echo "---"

while IFS= read -r -d '' file; do
  TOTAL=$((TOTAL + 1))
  relative="${file#"$BUNDLE"/}"
  base=$(basename "$file")

  # --- Reserved files (E3) -------------------------------------------
  if [[ "$base" == "index.md" || "$base" == "log.md" ]]; then
    if [[ "$base" == "index.md" ]]; then
      # index.md must not carry frontmatter, except the bundle-root
      # index.md which may declare okf_version.
      if head -1 "$file" | grep -q "^---[[:space:]]*$"; then
        if [[ "$relative" == "index.md" ]]; then
          fm=$(sed -n '2,/^---[[:space:]]*$/p' "$file" | sed '$d')
          if ! echo "$fm" | grep -qE "^okf_version:"; then
            echo "${RED}E3: $relative — root index.md frontmatter must declare okf_version${NC}"
            ERRORS=$((ERRORS + 1))
          fi
        else
          echo "${RED}E3: $relative — index.md must not have frontmatter${NC}"
          ERRORS=$((ERRORS + 1))
        fi
      fi
    fi
    if [[ "$base" == "log.md" ]]; then
      if [ -s "$file" ] && ! grep -qE "^## [0-9]{4}-[0-9]{2}-[0-9]{2}" "$file"; then
        echo "${YELLOW}W5: $relative — log.md has no ISO 8601 (YYYY-MM-DD) date headings${NC}"
        WARNINGS=$((WARNINGS + 1))
      fi
    fi
    continue
  fi

  # --- Concept files (E1, E2) ----------------------------------------
  if ! head -1 "$file" | grep -q "^---[[:space:]]*$"; then
    echo "${RED}E1: $relative — no YAML frontmatter${NC}"
    ERRORS=$((ERRORS + 1))
    continue
  fi

  fm=$(sed -n '2,/^---[[:space:]]*$/p' "$file" | sed '$d')

  type_value=$(echo "$fm" | grep -E "^type:" | head -1 | sed 's/^type:[[:space:]]*//' | tr -d "\"'" | xargs || true)
  if [ -z "$type_value" ]; then
    echo "${RED}E2: $relative — missing or empty 'type' field${NC}"
    ERRORS=$((ERRORS + 1))
    continue
  fi

  # --- Recommended-field warnings ------------------------------------
  echo "$fm" | grep -qE "^title:"       || { echo "${YELLOW}W1: $relative — missing recommended 'title'${NC}"; WARNINGS=$((WARNINGS + 1)); }
  echo "$fm" | grep -qE "^description:" || { echo "${YELLOW}W1: $relative — missing recommended 'description'${NC}"; WARNINGS=$((WARNINGS + 1)); }

done < <(find "$BUNDLE" -name "*.md" -type f -print0 | sort -z)

echo "---"
echo "Files scanned: $TOTAL"
if [ "$ERRORS" -eq 0 ]; then
  echo "${GREEN}PASS — bundle is OKF v0.1 conformant${NC}"
else
  echo "${RED}FAIL — $ERRORS conformance error(s)${NC}"
fi
[ "$WARNINGS" -gt 0 ] && echo "${YELLOW}$WARNINGS warning(s) (non-blocking)${NC}"

[ "$ERRORS" -eq 0 ] || exit 1
exit 0
