#!/usr/bin/env bash
#
# converge-repo.sh — bring ONE repo to the canonical beads state, idempotently.
# Implements the repair order in references/troubleshooting.md. Safe by default:
# it preserves data unless you explicitly allow discarding it, never force-pushes a
# database that holds issues without --force-diverged, and refuses the root repo.
#
# Usage:
#   converge-repo.sh <repo-path-or-name> [flags]
#
# Flags:
#   --dry-run          report the plan, change nothing
#   --clean            also remove orphaned local artifacts (.beads/dolt, dolt-server.*)
#   --discard-dirty    reset a dirty working set (DESTRUCTIVE) instead of committing it
#   --force-diverged   force-push when histories diverge (DESTRUCTIVE to remote history)
#   --allow-root       permit converging the root/C2 repo (normally refused)
#
# Config. Each value resolves: project env var → generic env var → default.
#   fleet dir  SKILLSPOKE_APP_ROOT   → BEADS_FLEET_DIR   → $PWD
#   port       SKILLSPOKE_BEADS_PORT → BEADS_SHARED_PORT → 3308
#   prefix     SKILLSPOKE_BEADS_PREFIX → BEADS_PREFIX    → ssbd
#   root repo  SKILLSPOKE_CC (basename)                  → "SkillSpoke"
#
# Repo→database: replace '-' with '_'. Requires: bd, uv, and the shared server running.

set -u -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVER="$SCRIPT_DIR/beads_server.py"
BASE_DIR="${SKILLSPOKE_APP_ROOT:-${BEADS_FLEET_DIR:-$PWD}}"
PORT="${SKILLSPOKE_BEADS_PORT:-${BEADS_SHARED_PORT:-3308}}"
PREFIX="${SKILLSPOKE_BEADS_PREFIX:-${BEADS_PREFIX:-ssbd}}"
ROOT_REPO="$(basename "${SKILLSPOKE_CC:-SkillSpoke}")"
export BD_ALLOW_REMOTE_MIGRATE=1
export BEADS_SHARED_PORT="$PORT"   # so beads_server.py connects to the same server

DRY=0; CLEAN=0; DISCARD=0; FORCE_DIV=0; ALLOW_ROOT=0; TARGET=""
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    --clean) CLEAN=1 ;;
    --discard-dirty) DISCARD=1 ;;
    --force-diverged) FORCE_DIV=1 ;;
    --allow-root) ALLOW_ROOT=1 ;;
    --*) echo "unknown flag: $a" >&2; exit 1 ;;
    *) TARGET="$a" ;;
  esac
done
[ -n "$TARGET" ] || { echo "usage: converge-repo.sh <repo-path-or-name> [flags]" >&2; exit 1; }

# Resolve target to an absolute repo path.
if [ -d "$TARGET/.beads" ]; then REPO_PATH="$(cd "$TARGET" && pwd)"
elif [ -d "$BASE_DIR/$TARGET/.beads" ]; then REPO_PATH="$(cd "$BASE_DIR/$TARGET" && pwd)"
else echo "FATAL: no .beads/ found for '$TARGET'" >&2; exit 1; fi
REPO="$(basename "$REPO_PATH")"
DB="$(printf '%s' "$REPO" | tr '-' '_')"
META="$REPO_PATH/.beads/metadata.json"

say() { printf '  %s\n' "$*"; }
LABEL=""; [ "$DRY" = 1 ] && LABEL="  [DRY-RUN]"
echo "▶ converge ${REPO}  (db=${DB})${LABEL}"

# Guard: never sweep the root/C2 repo (identified by SKILLSPOKE_CC).
if [ "$REPO" = "$ROOT_REPO" ]; then
  if [ "$ALLOW_ROOT" = 1 ]; then say "root repo '${REPO}' — proceeding (--allow-root)"
  else say "✗ refusing to converge root/C2 repo '${REPO}' (holds real issues); pass --allow-root to override"; exit 1; fi
else :; fi

# Preflight + existence.
command -v bd >/dev/null 2>&1 || { say "FATAL: bd not on PATH"; exit 1; }
command -v uv >/dev/null 2>&1 || { say "FATAL: uv not on PATH"; exit 1; }
if [ "$(uv run --quiet "$SERVER" exists "$DB")" != "1" ]; then
  say "✗ database ${DB} is NOT on the shared server."
  say "  Fix (troubleshooting.md §5): point metadata at the shared server + db name, then"
  say "  'BD_ALLOW_REMOTE_MIGRATE=1 bd bootstrap' (needs refs/dolt/data on the git remote)."
  exit 1
fi

# Read current server-side state.
STATUS="$(uv run --quiet "$SERVER" status "$DB")"
DIRTY=$(printf '%s' "$STATUS" | sed -n 's/^working_set: *//p' | grep -qi dirty && echo 1 || echo 0)
ISSUES=$(printf '%s' "$STATUS" | sed -n 's/^issues: *//p')
PFX=$(printf '%s' "$STATUS" | sed -n 's/^prefix: *//p')
say "state: dirty=${DIRTY} issues=${ISSUES} prefix=${PFX}"

if { [ "$FORCE_DIV" = 1 ] || [ "${ISSUES:-1}" = 0 ]; }; then FORCE_OK="allowed"; else FORCE_OK="BLOCKED (has issues; use --force-diverged)"; fi
if [ "$DRY" = 1 ]; then
  say "PLAN:"
  if [ "$DIRTY" = 1 ]; then
    if [ "$DISCARD" = 1 ]; then say "  - working set dirty -> reset --hard (DISCARD)"; else say "  - working set dirty -> commit (preserve)"; fi
  else say "  - working set clean"; fi
  say "  - align project_id + normalize metadata.json (mode=server, port=${PORT}, db=${DB})"
  say "  - bd migrate; set shared-server; pin port/database"
  if [ "$PFX" != "$PREFIX" ]; then say "  - rename-prefix ${PREFIX}-"; else say "  - prefix already ${PREFIX}"; fi
  say "  - bd dolt push (force on divergence: ${FORCE_OK})"
  if [ "$CLEAN" = 1 ]; then say "  - remove orphaned local artifacts"; else say "  - (keep local artifacts; pass --clean to remove)"; fi
  exit 0
fi

# 1) Dirty working set — preserve by default, discard only on request.
if [ "$DIRTY" = 1 ]; then
  if [ "$DISCARD" = 1 ]; then
    say "working set dirty -> reset --hard (--discard-dirty)"; uv run --quiet "$SERVER" reset "$DB" >/dev/null
  elif [ "${ISSUES:-1}" = 0 ]; then
    say "working set dirty, 0 issues -> reset --hard (nothing to preserve)"; uv run --quiet "$SERVER" reset "$DB" >/dev/null
  else
    say "working set dirty with ${ISSUES} issues -> commit (preserve)"; uv run --quiet "$SERVER" commit "$DB" "chore: commit working set before schema migration" >/dev/null
  fi
else
  say "working set already clean"
fi

# 2) Align identity + normalize local metadata (project_id must equal the DB's).
DBID="$(uv run --quiet "$SERVER" projectid "$DB")"
uv run --quiet --python 3.14 python - "$META" "$PORT" "$DB" "$DBID" <<'PY'
import json, sys, os
meta, port, db, dbid = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
m = {}
if os.path.exists(meta):
    try: m = json.load(open(meta))
    except Exception: m = {}
before = dict(m)
m.setdefault("database", "dolt"); m.setdefault("backend", "dolt")
m["dolt_mode"] = "server"; m["dolt_server_port"] = port; m["dolt_database"] = db; m["project_id"] = dbid
if m != before:
    json.dump(m, open(meta, "w"), indent=2); print("changed")
else:
    print("unchanged")
PY
say "metadata.json aligned (project_id=${DBID}, mode=server, port=${PORT}, db=${DB})"

# 3) Migrate (idempotent; no-op if already current).
if MOUT="$(cd "$REPO_PATH" && bd migrate 2>&1)"; then
  printf '%s' "$MOUT" | grep -q 'Version updated' && say "schema migrated" || say "schema already current"
else
  say "✗ bd migrate failed: $(printf '%s' "$MOUT" | tail -1)"; exit 1
fi

# 4) Shared-server mode + pins.
(cd "$REPO_PATH" && bd config set dolt.shared-server true >/dev/null) && say "shared-server = true" || { say "✗ could not set shared-server"; exit 1; }
(cd "$REPO_PATH" && bd dolt set port "$PORT" --update-config >/dev/null) && say "pinned port ${PORT}" || say "port pin issue (continuing)"
(cd "$REPO_PATH" && bd dolt set database "$DB" --update-config >/dev/null) && say "pinned database ${DB}" || say "database pin issue (continuing)"

# 5) Prefix.
if [ "$PFX" = "$PREFIX" ]; then say "prefix already ${PREFIX}"
else
  (cd "$REPO_PATH" && bd rename-prefix "${PREFIX}-" --repair >/dev/null) && say "prefix renamed to ${PREFIX}" || { say "✗ rename-prefix failed"; exit 1; }
fi

# 6) Connectivity.
(cd "$REPO_PATH" && bd dolt test >/dev/null 2>&1) && say "connection OK" || { say "✗ bd dolt test failed"; exit 1; }

# 7) Push (force only when safe).
POUT="$(cd "$REPO_PATH" && bd dolt push 2>&1)"; PRC=$?
if [ $PRC -eq 0 ]; then
  say "pushed"
elif printf '%s' "$POUT" | grep -qiE 'no common ancestor|diverged'; then
  if [ "$FORCE_DIV" = 1 ] || [ "${ISSUES:-1}" = 0 ]; then
    (cd "$REPO_PATH" && bd dolt push --force >/dev/null 2>&1) && say "pushed (--force, diverged history overwritten)" || { say "✗ force-push failed"; exit 1; }
  else
    say "✗ histories diverged and the database has ${ISSUES} issues — NOT force-pushing."
    say "  Decide: 'bd dolt push --force' (local wins) or 'bd bootstrap' (remote wins). Re-run with --force-diverged to force."
    exit 1
  fi
else
  say "✗ push failed: $(printf '%s' "$POUT" | tail -1)"; exit 1
fi

# 8) Optional cleanup of orphaned local artifacts (all gitignored).
if [ "$CLEAN" = 1 ]; then
  rm -rf "$REPO_PATH/.beads/dolt" "$REPO_PATH/.beads/embeddeddolt"
  rm -f "$REPO_PATH/.beads/dolt-server.lock" "$REPO_PATH/.beads/dolt-server.pid" \
        "$REPO_PATH/.beads/dolt-server.port" "$REPO_PATH/.beads/dolt-server.log" \
        "$REPO_PATH/.beads/dolt-server.activity" "$REPO_PATH/.beads/dolt-config.log"
  say "removed orphaned local artifacts"
else
  say "(kept local artifacts; pass --clean to remove orphans)"
fi

# 9) Verify. Capture first — piping a slow `bd dolt show` into `grep -q` trips pipefail via SIGPIPE.
SHOW="$(cd "$REPO_PATH" && bd dolt show 2>&1)"
if printf '%s' "$SHOW" | grep -q 'Mode:.*shared server'; then say "✓ verified: shared server mode"; else say "✗ post-check: not in shared server mode"; exit 1; fi
echo "  ✓ ${REPO}: converged"
