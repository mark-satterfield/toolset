#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pymysql"]
# ///
"""
beads_server.py — talk to the running shared Dolt server over its SQL protocol.

This is the ONLY safe way to inspect or unstick a beads database when `bd` itself is gated by a
pending schema migration (bd refuses to open the store; the SQL protocol does not). It is also
the ONLY safe way to poke the databases directly: never run the raw `dolt` CLI against the
running server's data directory — it corrupts the journal. Going through the server (as this
does) is safe.

Read-only subcommands change nothing. `reset` and `commit` mutate the working set and are the
documented escape from the dirty-table deadlock (see references/troubleshooting.md §2).

Usage:
  beads_server.py list                      # SHOW DATABASES
  beads_server.py exists <db>               # prints 1 / 0
  beads_server.py status <db>               # dirty? schema version, prefix, project_id, issues
  beads_server.py projectid <db>            # prints the database's metadata._project_id
  beads_server.py prefix <db>               # prints config.issue_prefix
  beads_server.py reset <db>                # MUTATES: CALL DOLT_RESET('--hard')  (discard working set)
  beads_server.py commit <db> "<message>"   # MUTATES: CALL DOLT_COMMIT('-Am', message)

Connection (env overrides): BEADS_SHARED_HOST=127.0.0.1  BEADS_SHARED_PORT=3308  BEADS_SHARED_USER=root
Run directly (uv installs pymysql), or: uv run --with pymysql python beads_server.py ...
"""
import os
import sys

import pymysql

HOST = os.environ.get("BEADS_SHARED_HOST", "127.0.0.1")
PORT = int(os.environ.get("BEADS_SHARED_PORT", "3308"))
USER = os.environ.get("BEADS_SHARED_USER", "root")
PASSWORD = os.environ.get("BEADS_SHARED_PASSWORD", "")


def connect():
    try:
        return pymysql.connect(
            host=HOST, port=PORT, user=USER, password=PASSWORD,
            autocommit=True, connect_timeout=10,
        )
    except Exception as e:  # boundary: the server may be down
        print(f"ERROR: cannot reach shared Dolt server at {HOST}:{PORT}: {e}", file=sys.stderr)
        sys.exit(3)


def _databases(cur):
    cur.execute("SHOW DATABASES")
    return [r[0] for r in cur.fetchall()]


def _require_db(cur, db):
    if db not in _databases(cur):
        print(f"ERROR: database '{db}' is not on the server", file=sys.stderr)
        sys.exit(2)
    cur.execute(f"USE `{db}`")


def _scalar(cur, sql):
    cur.execute(sql)
    row = cur.fetchone()
    return row[0] if row else None


def cmd_list(cur, _args):
    for d in _databases(cur):
        print(d)


def cmd_exists(cur, args):
    print("1" if args[0] in _databases(cur) else "0")


SQL_PREFIX = "SELECT value FROM config WHERE `key`='issue_prefix'"
SQL_PROJECT_ID = "SELECT value FROM metadata WHERE `key`='_project_id'"


def cmd_status(cur, args):
    db = args[0]
    _require_db(cur, db)
    cur.execute("SELECT table_name, status FROM dolt_status")
    dirty = cur.fetchall()
    working = "DIRTY (" + ", ".join(r[0] for r in dirty) + ")" if dirty else "clean"
    schema_max = _scalar(cur, "SELECT MAX(version) FROM schema_migrations")
    prefix = _scalar(cur, SQL_PREFIX)
    project_id = _scalar(cur, SQL_PROJECT_ID)
    issues = _scalar(cur, "SELECT COUNT(*) FROM issues")
    print(f"database:    {db}")
    print(f"working_set: {working}")
    print(f"schema_max:  {schema_max}")
    print(f"prefix:      {prefix}")
    print(f"project_id:  {project_id}")
    print(f"issues:      {issues}")


def cmd_projectid(cur, args):
    _require_db(cur, args[0])
    pid = _scalar(cur, "SELECT value FROM metadata WHERE `key`='_project_id'")
    if pid is None:
        print("ERROR: no _project_id in database metadata", file=sys.stderr)
        sys.exit(2)
    print(pid)


def cmd_prefix(cur, args):
    _require_db(cur, args[0])
    print(_scalar(cur, "SELECT value FROM config WHERE `key`='issue_prefix'") or "")


def cmd_reset(cur, args):
    db = args[0]
    _require_db(cur, db)
    cur.execute('CALL DOLT_RESET("--hard")')
    cur.execute("SELECT * FROM dolt_status")
    print("clean" if not cur.fetchall() else "STILL DIRTY")


def cmd_commit(cur, args):
    db, msg = args[0], (args[1] if len(args) > 1 else "wip: commit working set")
    _require_db(cur, db)
    cur.execute("CALL DOLT_COMMIT('-A', '-m', %s)", (msg,))
    print("committed")


COMMANDS = {
    "list": (cmd_list, 0), "exists": (cmd_exists, 1), "status": (cmd_status, 1),
    "projectid": (cmd_projectid, 1), "prefix": (cmd_prefix, 1),
    "reset": (cmd_reset, 1), "commit": (cmd_commit, 1),
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(0 if len(sys.argv) < 2 else 1)
    cmd, min_args = COMMANDS[sys.argv[1]]
    args = sys.argv[2:]
    if len(args) < min_args:
        print(f"ERROR: '{sys.argv[1]}' needs {min_args} argument(s)", file=sys.stderr)
        sys.exit(1)
    conn = connect()
    try:
        cmd(conn.cursor(), args)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
