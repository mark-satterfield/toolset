# Diagnostics — how to see real state without breaking anything

Beads state lives in **two places that can disagree**: the local `.beads/` config in the repo,
and the actual database on the shared server. Every diagnosis starts by reading both. Nothing
here mutates anything.

## The one thing to understand first: the migration gate

On a **remote-backed** database with a **pending schema migration**, bd runs the migration
automatically the moment it *opens the store* — and if it can't (because the migration is
gated, or the working set is dirty), it refuses to open the store at all. That refusal hits
**every** command that touches the database: `bd config get/set`, `bd dolt set`, `bd sql`,
`bd migrate`, even the `bd dolt commit` the error message tells you to run. This is why a stuck
repo looks totally jammed.

Two consequences:

- **`bd dolt show` is your friend.** It reports the *connection configuration* (mode, host,
  port, database, server path, connection OK) **without opening the store**, so it works even
  when everything else is gated. It's the first thing to run.
- **To inspect a gated database, go server-side over SQL** (below). That is the only way in
  when `bd` won't open the store.

## Local-side reads

```bash
bd dolt show          # mode, host/port/database, server path, connection OK — never gated
bd dolt test          # connect to the configured server; ✓ or the error
bd dolt remote list   # is the git+https origin registered as a Dolt remote?
bd doctor             # bd's own health check (may open the store; can be gated)
cat .beads/metadata.json    # declared connection + project_id
grep -nE 'shared-server|dolt|issue-prefix' .beads/config.yaml
```

`bd dolt show` also prints the config-source priority order, a reminder that env vars override
`metadata.json` override `config.yaml`.

## Server-side reads (the escape hatch)

The shared server speaks the MySQL protocol on the shared port. There is usually **no** mysql
client installed, and you must **never** point the raw `dolt` CLI at the running server's data
directory (it corrupts the journal). Use a throwaway Python client via `uv` — this talks to the
server the same safe way `bd` does:

```bash
uv run --with pymysql --python 3.14 python - <<'PY'
import pymysql
c = pymysql.connect(host="127.0.0.1", port=3308, user="root", password="", autocommit=True)
cur = c.cursor()
cur.execute("SHOW DATABASES"); print([r[0] for r in cur.fetchall()])
c.close()
PY
```

`scripts/beads_server.py` wraps the common read queries. The queries that matter, per database:

| Question | SQL (after `USE \`<db>\``) |
|---|---|
| Is the working set dirty? | `SELECT * FROM dolt_status` — rows ⇒ dirty (the migration blocker) |
| What is the database's identity? | `SELECT value FROM metadata WHERE \`key\`='_project_id'` |
| What prefix will it mint? | `SELECT value FROM config WHERE \`key\`='issue_prefix'` |
| What schema version is it on? | `SELECT MAX(version) FROM schema_migrations` |
| Does it actually hold issues? | `SELECT COUNT(*) FROM issues` |
| Which databases exist? | `SHOW DATABASES` (compare to the repos on disk) |

To find which data directory the running server is actually serving (useful when
`embeddeddolt` vs `dolt` confusion strikes):

```bash
lsof -a -p "$(cat ~/.beads/shared-server/dolt-server.pid)" -d cwd   # cwd = the live data dir
```

## Reading identity: local vs database

A **PROJECT IDENTITY MISMATCH** is the difference between:

- `metadata.json` → `project_id` (what the local clone thinks it is), and
- the database's `metadata._project_id` (what the database says it is).

The database is authoritative. Read both; if they differ, the repair is to write the
database's value into `metadata.json` (see `troubleshooting.md`).

## A quick mental checklist per repo

1. `bd dolt show` → shared server? correct port/database? connection OK?
2. Server-side → working set clean? schema version == fleet? prefix == project prefix?
3. `metadata.json` `project_id` == database `_project_id`?
4. `bd dolt remote list` → origin present?
5. Any orphaned `.beads/dolt`, `embeddeddolt`, or `dolt-server.*` files?
6. (root config) is this repo in `repos.additional`?

`scripts/audit-fleet.sh` runs exactly this checklist across every repo and prints the
anomalies.
