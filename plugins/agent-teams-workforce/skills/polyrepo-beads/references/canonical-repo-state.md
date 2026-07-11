# Canonical Repo State

This is the contract. Every active child repo's beads must match it. An audit is a comparison
against this document; a repair is the act of bringing a repo back to it.

Values in **angle brackets** are project-specific. **Read them from the shell environment, do
not hardcode them.** These `SKILLSPOKE_*` variables are exported in the shell, so they are
available both inside Claude Code sessions and to automation/scripts run outside it. The scripts
resolve each value as `SKILLSPOKE_* → BEADS_* → default`.

| Project value | Env var (source of truth) | SkillSpoke value |
|---|---|---|
| Fleet directory (parent of the repos) | `SKILLSPOKE_APP_ROOT` | `/Users/msat1971/projects/SkillSpoke/app` |
| Root / C2 repo (holds real issues + hydration list) | `SKILLSPOKE_CC` | `…/app/SkillSpoke` (database `SkillSpoke`) |
| Shared server port | `SKILLSPOKE_BEADS_PORT` (→ `3308`) | `3308` |
| Issue prefix | `SKILLSPOKE_BEADS_PREFIX` | `ssbd` (IDs look like `ssbd-123`) |
| Logs directory | `SKILLSPOKE_LOGS` | `/Users/msat1971/projects/SkillSpoke/logs` |
| Shared server data dir | — (bd-managed) | `~/.beads/shared-server/dolt/` |
| Repo → database name | — (rule) | `SkillSpoke-<x>` → `SkillSpoke_<x>` (hyphens → underscores, camelCase kept) |
| Git remote sync | — (bd-managed) | `refs/dolt/data` on each repo's `origin` |

> The prefix is `ss` (SkillSpoke) + `bd` (the beads CLI) = **`ssbd`**. If
> `SKILLSPOKE_BEADS_PREFIX` ever reads something else, treat it as suspect and confirm before
> any `rename-prefix` — a wrong value here renames the whole fleet's issues.

## The architecture (why the contract is shaped this way)

Beads stores issues in a **Dolt** database. There are two deployment models:

- **Per-repo / embedded** (bd's default): each repo runs its own Dolt server, or uses a local
  embedded database under `.beads/dolt/` (or `.beads/embeddeddolt/`). Fine for one repo;
  wasteful and confusing for a fleet — dozens of servers, dozens of ports.
- **Shared server** (this project): **one** Dolt SQL server runs at `~/.beads/shared-server/`
  and hosts every repo's database on one port. Each repo's `.beads/` holds only *config* that
  points at that server; the data lives in the server's data directory, not in the repo.

The live data on this machine is `~/.beads/shared-server/dolt/` — one subdirectory per database
(`SkillSpoke`, `SkillSpoke_web`, …, plus `beads_global`). Anything named `embeddeddolt` is the
**old embedded store** and is not the shared server; do not confuse the two.

**Config precedence** (highest wins), which is why a repo can *behave* correctly even when one
file looks wrong:

1. Environment variables — `BEADS_DOLT_*` (e.g. `BEADS_DOLT_SHARED_SERVER=1`)
2. `.beads/metadata.json` — local, per-clone connection details
3. `.beads/config.yaml` — team defaults, committed

The global `~/.beads/config.yaml` (`dolt.port: 3308`) supplies the port fleet-wide, so a repo
whose `metadata.json` still lists an old per-repo port may *still* connect to `3308`. Audit the
declared state, not just the effective one — drift you can't see today breaks tomorrow.

## What must be true for each repo

### 1. Connection mode: shared server

`.beads/config.yaml` contains (bd writes it nested):

```yaml
dolt:
    shared-server: true
    port: <3308>
    database: <SkillSpoke_repo_name>
```

`bd dolt show` must report `Mode: shared server`, `Server: ~/.beads/shared-server`, and
`✓ Server connection OK`. Set the flag with `bd config set dolt.shared-server true` (this
requires the store to open — see the migration gate in `troubleshooting.md`).

### 2. Connection details: metadata.json

```json
{
  "database": "dolt",
  "backend": "dolt",
  "dolt_mode": "server",
  "dolt_server_port": <3308>,
  "dolt_database": "<SkillSpoke_repo_name>",
  "project_id": "<must equal the database's own _project_id>"
}
```

- Set database/port with `bd dolt set database <name> --update-config` and
  `bd dolt set port <3308> --update-config` (the flag also writes `config.yaml`).
- `project_id` is the one field that is easy to get wrong. It **must equal** the value stored
  *inside* the database (`metadata` table, key `_project_id`). If they differ, `bd` refuses to
  connect with a **PROJECT IDENTITY MISMATCH**. `metadata.json` is per-clone and gitignored by
  bd's design — treat it as machine-local.

### 3. Database name: deterministic from the repo

`SkillSpoke-<x>` → `SkillSpoke_<x>` with hyphens replaced by underscores and camelCase
preserved (`SkillSpoke-careerPath-mcp-server` → `SkillSpoke_careerPath_mcp_server`). The
database with that name must exist on the shared server.

### 4. Issue prefix

The prefix is `<ssbd>`, stored authoritatively in the database's `config` table
(`issue_prefix`), **not** in `config.yaml` (the `issue-prefix:` line there is only read by
`bd init`). It **cannot** be set with `bd config set` — bd will tell you to use `bd init`
(forbidden), `bd bootstrap`, or `bd rename-prefix`. To correct a wrong prefix on an existing
database: `bd rename-prefix <ssbd>- --repair`. Never let it fall back to the directory name.

### 5. Schema version

All repos must be on the schema version current for the installed `bd` (SkillSpoke: **v53**,
bd 1.1.0). Mixed versions across the fleet is drift. Apply a pending migration with
`BD_ALLOW_REMOTE_MIGRATE=1 bd migrate` (see the gate in `troubleshooting.md`), then push.

### 6. Clean working set

The database's Dolt working set must have no uncommitted changes. A dirty working set on a
repo that also has a pending migration is the classic deadlock (`troubleshooting.md` → *Dirty
working set*). Check with `scripts/beads_server.py status <db>` (`dolt_status`).

### 7. Synced to the git remote

`bd dolt push` sends the database to `refs/dolt/data` on the repo's `origin` (a `git+https://…`
Dolt remote registered as `origin`). `bd dolt remote list` must show it. In shared-server mode
the push comes *from the shared server's copy* of the database.

### 8. Registered for multi-repo hydration

The **root** repo's `.beads/config.yaml` lists every active child under `repos.additional`
(paths relative to the root), so the root can hydrate issues across the fleet:

```yaml
repos:
    primary: "."
    additional:
        - "../SkillSpoke-web/"
        - "../SkillSpoke-auth-service/"
        # ... one line per active child
```

A newly onboarded repo must be added here; a deprecated repo must be removed.

## What does NOT belong in a repo

In shared-server mode these are orphaned leftovers from the per-repo-server era. All are
gitignored, so removing them is safe and produces no git changes:

- `.beads/dolt/` — an orphaned local Dolt database
- `.beads/embeddeddolt/` — an orphaned local *embedded* database
- `.beads/dolt-server.lock`, `.pid`, `.port`, `.log`, `.activity`, `.beads/dolt-config.log` —
  runtime files from a per-repo server that no longer runs

Keep: `.beads/config.yaml`, `.beads/metadata.json`, `.beads/.gitignore`, `hooks/`,
`README.md`, and bd's small state files. `scripts/converge-repo.sh --clean` removes the
orphans; verify `bd dolt test` still connects afterward (it will — the data is on the server).

## The root / command-and-control repo is special

The root repo (`SkillSpoke`) holds the fleet's real issues and the hydration list. It is
already on the shared server. **Never** reset its working set or force-push it during a bulk
operation, and never add it to a sweep that treats databases as empty. Audit it; repair it
only with explicit, case-by-case intent.
