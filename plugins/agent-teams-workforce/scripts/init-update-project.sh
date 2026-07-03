#!/usr/bin/env bash
# init-update-project.sh
# Called from SessionStart hook (hooks.json in plugin root):
#   bash "${CLAUDE_PLUGIN_ROOT}/scripts/init-update-project.sh" "${CLAUDE_PLUGIN_ROOT}"
#
# Writes/updates a versioned block in CLAUDE.md and/or AGENTS.md, sourced
# from agents-file.md. Any literal occurrence of the string
# ${CLAUDE_PLUGIN_ROOT} inside agents-file.md is replaced with the
# resolved plugin root path before the block is written. Authors can
# reference any file or directory in the plugin this way — the script makes
# no assumptions about what agents-file.md contains or points to.
#
# When CLAUDE.md and AGENTS.md are symlinked to each other, writes once to
# the real file. No-ops when neither file exists.

set -euo pipefail

PLUGIN_ROOT="${1:?CLAUDE_PLUGIN_ROOT must be passed as first argument}"
PLUGIN_JSON="${PLUGIN_ROOT}/.claude-plugin/plugin.json"
INSTRUCTIONS_FILE="${PLUGIN_ROOT}/agents-file.md"

LABEL="AGENT TEAMS WORKFORCE"

# ---------------------------------------------------------------------------
# Read version from plugin.json
# ---------------------------------------------------------------------------
if [[ ! -f "$PLUGIN_JSON" ]]; then
  echo "[init-update-project] ERROR: ${PLUGIN_JSON} not found" >&2
  exit 1
fi

VERSION=$(python3 -c "import json,sys; d=json.load(open('${PLUGIN_JSON}')); print(d['version'])")
if [[ -z "$VERSION" ]]; then
  echo "[init-update-project] ERROR: version field missing in plugin.json" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Read the hash key from the yaml front matter of agents-file.md
# ---------------------------------------------------------------------------
if [[ ! -f "$INSTRUCTIONS_FILE" ]]; then
  echo "[init-update-project] ERROR: agents-file.md not found at ${INSTRUCTIONS_FILE}" >&2
  exit 1
fi

HASH=$(awk '
  NR==1 && $0=="---" { infm=1; next }
  infm && $0=="---" { exit }
  infm && /^hash:[[:space:]]*/ { sub(/^hash:[[:space:]]*/, ""); print; exit }
' "$INSTRUCTIONS_FILE")

# ---------------------------------------------------------------------------
# Build instruction body: every line of agents-file.md after the closing
# front-matter delimiter. The "hash: <sha>" key lives inside the front matter,
# so it is naturally excluded from the body. Literal ${CLAUDE_PLUGIN_ROOT}
# occurrences are then substituted for the resolved plugin root path — a plain
# string replace, so agents-file.md is free to use ${CLAUDE_PLUGIN_ROOT}
# anywhere: in @-imports, markdown links, table cells, prose, etc.
# ---------------------------------------------------------------------------
INSTRUCTIONS_BODY=$(awk '
  NR==1 && $0=="---" { infm=1; next }
  infm && $0=="---" { infm=0; started=1; next }
  started { print }
' "$INSTRUCTIONS_FILE")

INSTRUCTIONS_BODY="${INSTRUCTIONS_BODY//\$\{CLAUDE_PLUGIN_ROOT\}/${PLUGIN_ROOT}}"

BEGIN_TAG="<!-- BEGIN ${LABEL}: v:${VERSION} hash:${HASH} -->"
END_TAG="<!-- END ${LABEL} -->"

BLOCK="${BEGIN_TAG}
${INSTRUCTIONS_BODY}
${END_TAG}"

# ---------------------------------------------------------------------------
# Resolve which files to update, handling symlink deduplication
# ---------------------------------------------------------------------------
resolve_targets() {
  local claude="CLAUDE.md"
  local agents="AGENTS.md"

  local claude_exists=false
  local agents_exists=false
  [[ -e "$claude" ]] && claude_exists=true
  [[ -e "$agents" ]] && agents_exists=true

  if ! $claude_exists && ! $agents_exists; then
    echo "[init-update-project] Neither CLAUDE.md nor AGENTS.md found — no-op" >&2
    exit 0
  fi

  # If both exist, check for symlink relationship
  if $claude_exists && $agents_exists; then
    local claude_real agents_real
    claude_real=$(realpath "$claude")
    agents_real=$(realpath "$agents")
    if [[ "$claude_real" == "$agents_real" ]]; then
      # Same inode — write only once to the real file
      echo "$claude_real"
      return
    fi
    echo "$claude_real"
    echo "$agents_real"
    return
  fi

  $claude_exists && echo "$(realpath "$claude")"
  $agents_exists && echo "$(realpath "$agents")"
}

mapfile -t TARGETS < <(resolve_targets)

# ---------------------------------------------------------------------------
# Update or insert the block in a single target file
# ---------------------------------------------------------------------------
update_file() {
  local target="$1"

  local begin_pattern="<!-- BEGIN ${LABEL}:"
  local end_pattern="<!-- END ${LABEL} -->"

  if grep -qF "$begin_pattern" "$target"; then
    local existing_tag
    existing_tag=$(grep -F "$begin_pattern" "$target" | head -n 1)

    if [[ "$existing_tag" == "$BEGIN_TAG" ]]; then
      echo "[init-update-project] ${target}: block is current (v:${VERSION} hash:${HASH}) — skipping"
      return
    fi

    echo "[init-update-project] ${target}: replacing outdated block"

    # Multi-line replace via Python for reliability across macOS/Linux,
    # avoiding sed/awk portability differences in multi-line patterns.
    python3 - "$target" "$begin_pattern" "$end_pattern" "$BLOCK" << 'PYEOF'
import sys, re

target      = sys.argv[1]
begin_pat   = re.escape(sys.argv[2])
end_pat     = re.escape(sys.argv[3])
replacement = sys.argv[4]

text = open(target).read()
pattern = rf'{begin_pat}.*?{end_pat}'
updated = re.sub(pattern, replacement, text, flags=re.DOTALL)
open(target, 'w').write(updated)
PYEOF

  else
    echo "[init-update-project] ${target}: inserting new block"
    printf '\n%s\n' "$BLOCK" >> "$target"
  fi
}

for target in "${TARGETS[@]}"; do
  update_file "$target"
done