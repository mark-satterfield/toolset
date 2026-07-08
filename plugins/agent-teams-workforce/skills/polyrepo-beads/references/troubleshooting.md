# Troubleshooting Runbook

Each failure mode below is real and has been observed on this fleet. For each: the **signature**
(what you see), **why** it happens, and the **fix** (exact commands). Read `diagnostics.md`
first — you diagnose from the database's actual state, not from guesses.

**The canonical repair order** for a stuck repo (each step is conditional on the previous
state; skip what is already true):

1. Clean the working set if dirty →
2. Align project identity →
3. Migrate the schema →
4. Set shared-server mode + pin port/database →
5. Fix the prefix if wrong →
6. Push (force only on genuine divergence) →
7. Remove orphaned local artifacts.

`scripts/converge-repo.sh` performs exactly this, idempotently. Do it by hand only when you
need to understand or when the script's guardrails stop on something unusual.

Throughout: `export BD_ALLOW_REMOTE_MIGRATE=1` (you are the sole designated migrator).

---

## 1. Schema-migration gate on a remote-backed database

**Signature**
```
refusing to auto-apply 1 pending schema migration to a remote-backed database (v52 -> v53):
migrating clones independently forks the schema (#4259)
```
Every store-opening `bd` command prints this and fails.

**Why** — bd will not silently migrate a database that syncs with a remote, because migrating
two clones independently forks the schema and `bd dolt pull` can no longer merge. It wants one
designated migrator.

**Fix** — you are that migrator:
```bash
BD_ALLOW_REMOTE_MIGRATE=1 bd migrate    # applies the pending migration(s)
bd dolt push                            # publish the migrated schema to the remote
```
If **another** machine already migrated, don't migrate here — re-clone: `bd bootstrap` (this
replaces the local database; push or export first if it holds unpushed issues).

---

## 2. Dirty working set blocks the migration (the deadlock)

**Signature**
```
schema migration: pending schema migrations alter pre-existing dirty tables:
comments, dependencies, events, issues; run 'bd dolt commit' to commit the working set
at the current schema, then re-run the migration (#4566)
```
…and running `bd dolt commit` (or `bd sql`, or anything) prints the **same** error. A true
deadlock: the migration needs a clean working set, but you can't open the store to clean it,
because opening triggers the migration.

**Why** — an earlier `bd` write left uncommitted changes in the Dolt working set; the migration
can't alter dirty tables; and bd's migrate-on-open means no `bd` command can get in to commit
them.

**Fix — break it server-side** (the one path bd's gate can't block). Confirm first whether the
database holds anything worth keeping:
```bash
# inspect (read-only)
scripts/beads_server.py status <db>          # shows dolt_status + issue count

# CASE A — no issues worth keeping (common on freshly (re)created fleet DBs): discard
scripts/beads_server.py reset <db>           # CALL DOLT_RESET('--hard')

# CASE B — issues to preserve: commit the working set at the current schema instead
scripts/beads_server.py commit <db> "wip: commit before schema migration"
```
Then the migration proceeds normally:
```bash
BD_ALLOW_REMOTE_MIGRATE=1 bd migrate
```
> Do **not** reach for the raw `dolt` CLI here — talk to the running server over SQL (that is
> what `beads_server.py` does). Raw `dolt` against the live data dir corrupts the journal.

---

## 3. Project identity mismatch

**Signature**
```
PROJECT IDENTITY MISMATCH — refusing to connect
  Local project ID (metadata.json):  9e1a4e68-...
  Database project ID:               7fd3c35d-...
```

**Why** — the repo's `.beads/metadata.json` carries a different `project_id` than the database
itself stores in its `metadata._project_id`. This commonly surfaces right after a
`DOLT_RESET --hard`, because the reset reverts the database to a committed HEAD whose identity
differs from whatever the local clone last recorded.

**Fix** — the database is authoritative; write its identity into the local file (never
`bd init`):
```bash
DBID=$(scripts/beads_server.py projectid <db>)   # reads metadata._project_id from the server
# set metadata.json "project_id" = "$DBID"  (a JSON edit; converge-repo.sh does this for you)
```
Read the database's id **after** any reset, then align. Re-run `bd migrate`.

---

## 4. Divergent histories on push ("no common ancestor")

**Signature**
```
Error: dolt push failed: ... Error 1105 (HY000): unknown push error; no common ancestor
Local and remote Dolt histories have diverged.
```

**Why** — the local database and the remote have independent commit histories with no shared
base — usually because a database was re-created (or `bd init`-ed) at some point, forking from
what's on `refs/dolt/data`.

**Fix** — decide which side is authoritative:
```bash
# local is authoritative (you just migrated/repaired it): overwrite the remote
bd dolt push --force

# remote is authoritative (someone else's copy is the good one): adopt it
bd bootstrap
```
On this fleet, after a repair the **local** (freshly migrated) copy is authoritative, so
`--force` is correct — but only because the child databases hold no issues worth keeping.
Never force-push the root repo casually.

---

## 5. Database missing on the shared server

**Signature** — `bd` operations fail to find the database, or a fleet audit shows the repo's
`SkillSpoke_<name>` database absent from `SHOW DATABASES`.

**Why** — the repo was never given a database on the shared server (e.g. it stayed in embedded
mode), or its database was dropped.

**Fix** — recreate it from the git remote (which holds `refs/dolt/data`), never `bd init`:
```bash
# point the repo at the shared server + intended database name first (metadata.json /
# bd dolt set), then:
BD_ALLOW_REMOTE_MIGRATE=1 bd bootstrap        # clones refs/dolt/data into the shared server
BD_ALLOW_REMOTE_MIGRATE=1 bd migrate          # bootstrap clones the remote's (older) schema; upgrade it
bd dolt push
```
Check the remote actually has data first: `git ls-remote <origin> 'refs/dolt/*'` should show
`refs/dolt/data`. If it doesn't, the repo has no recoverable database — escalate to the human;
do not fabricate one.

---

## 6. Ghost database (local points at a database that isn't there)

**Signature**
```
database <name> not found on Dolt server
```
The `.beads/` config points at a shared-server database that does not exist (a pointer to
nothing).

**Why** — the local config survived but the database on the server was removed or never
created.

**Fix** — clear the stale local database pointer and re-establish from the remote:
```bash
rm -rf .beads/dolt            # remove any residual local shadow (gitignored)
BD_ALLOW_REMOTE_MIGRATE=1 bd bootstrap
```
Then continue with the canonical repair order (migrate → configure → push).

---

## 7. Stray per-repo server / stale lock files / mode drift

**Signature** — `bd dolt show` reports `Mode: per-project` instead of `shared server`;
`metadata.json` lists a unique per-repo `dolt_server_port` (e.g. 3417) instead of the shared
port; or leftover `.beads/dolt-server.{lock,pid,port}` files, or a `.beads/dolt/` directory.

**Why** — the repo was set up (or left) in per-repo-server or embedded mode instead of shared
mode.

**Fix**
```bash
bd dolt stop 2>&1 || true                     # stop any per-repo server (harmless if none)
bd config set dolt.shared-server true
bd dolt set port 3308 --update-config
bd dolt set database <SkillSpoke_repo_name> --update-config
# remove orphaned local artifacts (all gitignored):
rm -rf .beads/dolt .beads/embeddeddolt
rm -f  .beads/dolt-server.lock .beads/dolt-server.pid .beads/dolt-server.port \
       .beads/dolt-server.log  .beads/dolt-server.activity .beads/dolt-config.log
bd dolt test                                  # confirm still connected to the shared server
```
Note: `bd config set dolt.shared-server true` opens the store, so a stuck database must be
un-stuck (sections 1–3) first.

---

## 8. Wrong or directory-derived prefix

**Signature** — an audit shows the database's `config.issue_prefix` is not the project prefix,
or new issues would be minted as `<dirname>-N` instead of `<ssbd>-N`.

**Why** — the prefix was never set, so bd defaulted it to the directory name; or it was set
wrong. It cannot be corrected with `bd config set` (bd rejects `issue_prefix`).

**Fix**
```bash
bd rename-prefix <ssbd>- --repair    # renames all issues + references to the correct prefix
```
(`--repair` also consolidates a database that ended up with *multiple* prefixes.) Prefix must
end with a hyphen and be ≤ 8 chars.

---

## 9. Forward schema skew (database ahead of the bd binary)

**Signature** — messages about *forward* schema drift; the database is on a newer schema than
the installed `bd`.

**Why** — the `bd` binary on this machine is older than the one that migrated the database.

**Fix** — upgrade `bd` to match the fleet (`brew upgrade beads` or the project's install path).
As a temporary read-only measure, `--ignore-schema-skew` lets commands proceed "despite forward
schema drift (some queries may fail)" — do not rely on it for writes.

---

## Safety — before any destructive step

| Action | Destroys | Only when |
|---|---|---|
| `DOLT_RESET('--hard')` | the uncommitted working set | you've confirmed the database has no issues worth keeping (`SELECT COUNT(*) FROM issues` == 0, or the human says so) |
| `bd dolt push --force` | the remote's diverged history | the local copy is authoritative — **never** for the root repo in a sweep |
| `bd bootstrap` | the local database (replaces it) | the remote is authoritative, or the local is empty/stuck and the remote has `refs/dolt/data` |
| `rm -rf .beads/dolt` | an orphaned local shadow db | you're in shared-server mode (data is on the server), or you're about to re-bootstrap |

When in doubt, **inspect first** (`beads_server.py status <db>` shows the issue count and dirty
state) and prefer the non-destructive branch (CASE B commit over CASE A reset; adopt-remote
over force-push) unless you have positively confirmed there is nothing to lose.

## The forbidden moves (repeat)

- **`bd init`** — mints a new identity, forks history. Use `bd bootstrap`.
- **Raw `dolt` CLI on the running server's data dir** — journal corruption. Use `bd` or the
  SQL protocol.
- **Migrating the same remote-backed database from two machines** — silent schema fork. One
  designated migrator, then push.
