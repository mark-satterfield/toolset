#!/usr/bin/env bash
#
# audit-fleet.sh — READ-ONLY audit of every repo's beads against the canonical state.
# Changes nothing. Prints a per-repo truth table and an anomaly list. Run before a release,
# after a mass change, or whenever you suspect drift. See references/canonical-repo-state.md.
#
# Configuration (env overrides; defaults are SkillSpoke's):
#   BEADS_FLEET_DIR   parent directory containing the repos      (default: $PWD)
#   BEADS_REPO_GLOB   glob for child repos                       (default: "SkillSpoke-*")
#   BEADS_SHARED_PORT shared Dolt server port                    (default: 3308)
#   BEADS_PREFIX      required issue prefix                      (default: "ssbd")
#   BEADS_SKIP        space-separated repos to skip (deprecated) (default: "")
#                     (in a polyrepo project, get these from the manifest's lifecycle field)
#
# Repo→database name mapping: replace '-' with '_' (SkillSpoke-web -> SkillSpoke_web).
# The root/C2 repo (a name with no hyphen suffix, e.g. "SkillSpoke") is excluded by the glob.

set -u -o pipefail

BASE_DIR="${BEADS_FLEET_DIR:-$PWD}"
GLOB="${BEADS_REPO_GLOB:-SkillSpoke-*}"
PORT="${BEADS_SHARED_PORT:-3308}"
PREFIX="${BEADS_PREFIX:-ssbd}"
SKIP="${BEADS_SKIP:-}"

command -v uv >/dev/null 2>&1 || { echo "FATAL: uv not on PATH (needed to reach the server)"; exit 1; }

BEADS_FLEET_DIR="$BASE_DIR" BEADS_REPO_GLOB="$GLOB" BEADS_SHARED_PORT="$PORT" \
BEADS_PREFIX="$PREFIX" BEADS_SKIP="$SKIP" \
uv run --quiet --with pymysql --python 3.14 python - <<'PY'
import os, re, json, glob, collections
import pymysql

base   = os.environ["BEADS_FLEET_DIR"]
gpat   = os.environ["BEADS_REPO_GLOB"]
port   = int(os.environ["BEADS_SHARED_PORT"])
prefix = os.environ["BEADS_PREFIX"]
skip   = set(os.environ.get("BEADS_SKIP", "").split())

try:
    c = pymysql.connect(host="127.0.0.1", port=port, user="root", password="",
                        autocommit=True, connect_timeout=10)
except Exception as e:
    raise SystemExit(f"FATAL: shared Dolt server unreachable on {port}: {e}")
cur = c.cursor()
cur.execute("SHOW DATABASES")
server = {r[0] for r in cur.fetchall()}

repos = sorted(os.path.basename(p) for p in glob.glob(os.path.join(base, gpat))
               if os.path.isdir(p))
db_of = lambda r: r.replace("-", "_")

hdr = f'{"REPO":<42}{"srv":<4}{"dirty":<6}{"schema":<7}{"prefix":<7}{"iss":<4}{"mode":<8}{"shared":<7}{"id":<5}'
print(hdr); print("-" * len(hdr))
anomalies, versions, checked = [], collections.Counter(), 0

for repo in repos:
    if repo in skip:
        print(f"{repo:<42}(skipped — in BEADS_SKIP)")
        continue
    checked += 1
    db = db_of(repo)
    problems = []
    if db not in server:
        print(f"{repo:<42}{'NO':<4}{'-':<6}{'-':<7}{'-':<7}{'-':<4}{'-':<8}{'-':<7}{'-':<5}")
        anomalies.append((repo, f"database {db} missing on server")); continue

    cur.execute(f"USE `{db}`")
    cur.execute("SELECT * FROM dolt_status"); dirty = bool(cur.fetchall())
    cur.execute("SELECT MAX(version) FROM schema_migrations"); ver = cur.fetchone()[0]; versions[ver] += 1
    cur.execute("SELECT value FROM config WHERE `key`='issue_prefix'"); r = cur.fetchone(); pfx = r[0] if r else None
    cur.execute("SELECT COUNT(*) FROM issues"); iss = cur.fetchone()[0]
    cur.execute("SELECT value FROM metadata WHERE `key`='_project_id'"); r = cur.fetchone(); dbid = r[0] if r else None

    meta_p = os.path.join(base, repo, ".beads", "metadata.json")
    cfg_p  = os.path.join(base, repo, ".beads", "config.yaml")
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
PY
