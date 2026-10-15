#!/usr/bin/env bash
#
# audit-fleet.sh — READ-ONLY audit of every repo's beads against the canonical state.
# Changes nothing. Prints a per-repo truth table and an anomaly list; with --json, prints one
# JSON object ({"checked", "versions", "anomalies": [{"repo", "detail"}]}) instead, which is
# what `polyrepo doctor` reads. See references/canonical-repo-state.md.
#
# Usage: audit-fleet.sh [--json] [--space S]
#
# The repos are every non-deprecated, non-archived repo on disk, in every app space, as the polyrepo tool
# (`polyrepo.py list`) reports them; deprecated and archived repos are not audited. `--space S`
# narrows the audit to the repos of one app space for that run.
#
# Configuration — the plugin's ATW_* contract (AGENT-TEAMS-WORKFORCE.md, "Project configuration"):
#   control repository   required  the variable CONTROL_REPO_ENV names in the pipeline-contracts
#                                  skill (schemas/driver-surface.schema.json); the root repo:
#                                  the issue prefix is read from its beads config, and it is
#                                  excluded from the audit
#   ATW_BEADS_PORT       optional  the shared Dolt server port (default 3308)
#
# Repo→database name mapping: replace '-' with '_' (my-repo -> my_repo).

set -u -o pipefail

JSON=0
SPACE=""
fatal() {
  if [ "$JSON" = 1 ]; then
    printf '{"error": "%s"}\n' "$1"
  else
    echo "FATAL: $1"
  fi
  exit 2
}

while [ $# -gt 0 ]; do
  case "$1" in
    --json) JSON=1 ;;
    --space) SPACE="${2:-}"; [ -n "$SPACE" ] || fatal "--space needs an app space"; shift ;;
    *) fatal "unknown argument: $1" ;;
  esac
  shift
done

CONTRACTS_DIR="$(cd "$(dirname "$0")/../../pipeline-contracts/scripts" && pwd)" || fatal "the pipeline-contracts skill scripts directory is missing"
CONTROL_REPO_VAR="$(python3 -I -c 'import sys; sys.path.insert(0, sys.argv[1]); from driver_surface_types import CONTROL_REPO_ENV; print(CONTROL_REPO_ENV)' "$CONTRACTS_DIR")" || fatal "could not read CONTROL_REPO_ENV from the pipeline-contracts driver surface"
CONTROL_REPO="${!CONTROL_REPO_VAR:-}"
[ -n "$CONTROL_REPO" ] || fatal "$CONTROL_REPO_VAR is not set — the root repo that holds the tracker"
PORT="${ATW_BEADS_PORT:-3308}"
POLYREPO="$(cd "$(dirname "$0")/../../polyrepo-repo/scripts" && pwd)/polyrepo.py"
command -v uv >/dev/null 2>&1 || fatal "uv not on PATH (needed to reach the server)"
PREFIX="$(cd "$CONTROL_REPO" && bd config get issue_prefix)" || fatal "could not read issue_prefix from the beads config in $CONTROL_REPO"
[ -n "$PREFIX" ] || fatal "the beads config in $CONTROL_REPO sets no issue_prefix"
LIST_ARGS=(list --json)
[ -n "$SPACE" ] && LIST_ARGS+=(--space "$SPACE")
REPOS_JSON="$(uv run --quiet "$POLYREPO" "${LIST_ARGS[@]}")" || fatal "polyrepo list failed: $REPOS_JSON"

BEADS_REPOS="$REPOS_JSON" BEADS_CONTROL="$CONTROL_REPO" BEADS_SHARED_PORT="$PORT" \
BEADS_PREFIX="$PREFIX" BEADS_JSON="$JSON" \
uv run --quiet --with pymysql --python 3.14 python - <<'PY'
import os, re, json, collections, sys, io
import pymysql

as_json = os.environ["BEADS_JSON"] == "1"
port    = int(os.environ["BEADS_SHARED_PORT"])
prefix  = os.environ["BEADS_PREFIX"]
control = os.path.realpath(os.environ["BEADS_CONTROL"])
paths   = {r["name"]: r["path"] for r in json.loads(os.environ["BEADS_REPOS"])["repos"]
           if r.get("path") and os.path.realpath(r["path"]) != control
           and r.get("lifecycle") not in ("deprecated", "archived")}
if as_json:
    sys.stdout = io.StringIO()

try:
    c = pymysql.connect(host="127.0.0.1", port=port, user="root", password="",
                        autocommit=True, connect_timeout=10)
except Exception as e:
    if as_json:
        sys.__stdout__.write(json.dumps({"error": f"shared Dolt server unreachable on {port}: {e}"}) + "\n")
        raise SystemExit(2)
    raise SystemExit(f"FATAL: shared Dolt server unreachable on {port}: {e}")
cur = c.cursor()
cur.execute("SHOW DATABASES")
server = {r[0] for r in cur.fetchall()}

repos = sorted(paths, key=str.lower)
def db_of(r):
    # bd finds a database by its project_id and keeps the name it was created under, so a
    # renamed repo stays on its original database; metadata.json names it.
    try:
        named = json.load(open(os.path.join(paths[r], ".beads", "metadata.json"))).get("dolt_database")
    except (OSError, ValueError):
        named = None
    return named or r.replace("-", "_")

hdr = f'{"REPO":<42}{"srv":<4}{"dirty":<6}{"schema":<7}{"prefix":<7}{"iss":<4}{"mode":<8}{"shared":<7}{"id":<5}'
print(hdr); print("-" * len(hdr))
anomalies, versions, checked = [], collections.Counter(), 0

for repo in repos:
    checked += 1
    db = db_of(repo)
    problems = []
    if db not in server:
        print(f"{repo:<42}{'NO':<4}{'-':<6}{'-':<7}{'-':<7}{'-':<4}{'-':<8}{'-':<7}{'-':<5}")
        anomalies.append((repo, f"database {db} missing on server")); continue

    try:
        cur.execute(f"USE `{db}`")
        cur.execute("SELECT * FROM dolt_status"); dirty = bool(cur.fetchall())
        cur.execute("SELECT MAX(version) FROM schema_migrations"); ver = cur.fetchone()[0]; versions[ver] += 1
        cur.execute("SELECT value FROM config WHERE `key`='issue_prefix'"); r = cur.fetchone(); pfx = r[0] if r else None
        cur.execute("SELECT COUNT(*) FROM issues"); iss = cur.fetchone()[0]
        cur.execute("SELECT value FROM metadata WHERE `key`='_project_id'"); r = cur.fetchone(); dbid = r[0] if r else None
    except pymysql.MySQLError as e:
        # One unreadable database must not hide the rest of the fleet's findings.
        print(f"{repo:<42}{'yes':<4}{'?':<6}{'?':<7}{'?':<7}{'?':<4}{'-':<8}{'-':<7}{'-':<5}")
        anomalies.append((repo, f"database {db} unreadable: {e.args[-1] if e.args else e}")); continue

    meta_p = os.path.join(paths[repo], ".beads", "metadata.json")
    cfg_p  = os.path.join(paths[repo], ".beads", "config.yaml")
    md = {}
    if os.path.exists(meta_p):
        try: md = json.load(open(meta_p))
        except Exception: problems.append("metadata.json unreadable")
    shared = os.path.exists(cfg_p) and re.search(r'shared-server:\s*true', open(cfg_p).read())
    idmatch = bool(dbid) and md.get("project_id") == dbid

    if dirty: problems.append("working set DIRTY")
    if pfx != prefix: problems.append(f"prefix={pfx}")
    if md.get("dolt_mode") != "server": problems.append(f"local mode={md.get('dolt_mode')}")
    if md.get("dolt_server_port") != port: problems.append(f"local port={md.get('dolt_server_port')}")
    if md.get("dolt_database") != db: problems.append(f"local db={md.get('dolt_database')}")
    if not idmatch: problems.append("project_id mismatch")
    if not shared: problems.append("no shared-server flag")

    print(f'{repo:<42}{"yes":<4}{("DIRTY" if dirty else "ok"):<6}{str(ver):<7}'
          f'{str(pfx):<7}{str(iss):<4}{str(md.get("dolt_mode")):<8}'
          f'{("yes" if shared else "NO"):<7}{("ok" if idmatch else "BAD"):<5}')
    if problems: anomalies.append((repo, "; ".join(problems)))

c.close()
top_ver = versions.most_common(1)[0][0] if versions else None

print()
print(f"checked: {checked}   schema versions across fleet: {dict(versions)}"
      + (f"   (current = {top_ver})" if top_ver else ""))
if anomalies:
    print(f"\nANOMALIES ({len(anomalies)}):")
    for repo, why in anomalies:
        print(f"  {repo}: {why}")
else:
    print("\nNo anomalies — every audited repo matches the canonical state.")
if as_json:
    sys.__stdout__.write(json.dumps({
        "checked": checked,
        "versions": {str(k): v for k, v in versions.items()},
        "anomalies": [{"repo": r, "detail": w} for r, w in anomalies],
    }) + "\n")
PY
