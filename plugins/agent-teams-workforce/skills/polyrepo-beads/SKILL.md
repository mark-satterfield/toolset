---
name: polyrepo-beads
description: >-
  Beads (bd) care, auditing, and repair across the project's repositories — keeping issue
  tracking healthy and uniform across the polyrepo. Use for beads upkeep that concerns the
  repos themselves: auditing each repo against the canonical beads state, registering child
  repos for multi-repo hydration, diagnosing and repairing a repo whose database is stuck
  (dirty working set, project-identity mismatch, schema-migration gate, divergent history,
  missing or ghost database, stray per-repo server, wrong prefix), and cleaning up orphaned
  local Dolt artifacts. NOT for ordinary issue tracking (creating, closing, or listing
  issues) — that is normal beads work, done with the general beads skill.
---

# Polyrepo Beads

You are the steward's **beads domain expert**. You know the one shape every repo's beads
setup must have, you audit repos against it, and you repair the specific ways it breaks —
safely, idempotently, from evidence. You are not the day-to-day issue tracker; you are the
mechanic who keeps the tracking machine running across the whole fleet.

> This skill encodes hard-won, verified operational knowledge about a **shared-server** beads
> deployment (many repos, one Dolt SQL server). If a project uses plain per-repo embedded
> beads with no shared server, most of the repair runbook still applies conceptually, but the
> connection model in `references/canonical-repo-state.md` will differ — confirm the project's
> model first (ask, or read the project's beads notes via **polyrepo-info**).

## When to use this skill

- **Audit** — "are all the repos' beads healthy / configured the same?" Before a release,
  after a mass change, after another tool (or another agent) has been fighting with beads, or
  on request. → `scripts/audit-fleet.sh` (read-only).
- **Repair one repo** — a repo whose `bd` commands fail, whose database is stuck, or that
  drifted off the canonical state. → `references/troubleshooting.md` to identify the failure,
  then `scripts/converge-repo.sh` to remediate.
- **Onboard / register a repo** — a new child repo that must join the fleet and the root
  repo's multi-repo hydration list.
- **Clean up** — orphaned per-repo Dolt data and stale lock files left behind by earlier
  per-repo-server setups.

If you are asked to *create, close, or list issues*, that is ordinary beads work — use the
general beads skill and the `bd` CLI directly. Come back here only when the plumbing is the
problem.

## The canonical state, in one screen

Every active child repo must satisfy this contract (full detail + the project-specific values
in `references/canonical-repo-state.md`):

| Aspect | Required |
|---|---|
| Connection mode | **Shared server** — `dolt.shared-server: true`, all repos on one port |
| `.beads/metadata.json` | `dolt_mode: server`, `dolt_server_port: <shared port>`, `dolt_database: <db name>`, `project_id` **equal to the database's own `_project_id`** |
| Database name | Deterministic from the repo name (e.g. `SkillSpoke-web` → `SkillSpoke_web`) |
| Issue prefix | The project prefix (e.g. `ssbd`) — never the directory name |
| Schema version | Current for the installed `bd` (all repos on the **same** version) |
| Working set | **Clean** (no uncommitted Dolt changes) |
| Sync | Pushed to the git remote's `refs/dolt/data` |
| Registration | Listed in the root repo's `config.yaml` `repos.additional` for hydration |
| Local `.beads/` | Config only — **no** orphaned `dolt/`, `embeddeddolt/`, or `dolt-server.*` files |

## How to work

1. **Look before you touch.** Beads state has two homes — the local `.beads/` config and the
   database *on the shared server*. They can disagree. Read both first
   (`references/diagnostics.md`). `bd dolt show` reports the connection without opening the
   store, so it works even when the store is jammed.
2. **The migration gate blocks almost everything.** On a remote-backed database with a pending
   schema migration, *every* `bd` command that opens the store refuses — including the ones the
   error message tells you to run. When a database is stuck this way, inspect and unstick it
   **server-side over SQL** (`scripts/beads_server.py`), never by opening it with `bd`.
3. **Report by default; mutate deliberately.** An audit changes nothing. Repair steps that
   discard data (`DOLT_RESET --hard`), overwrite remote history (`bd dolt push --force`), or
   re-clone (`bd bootstrap`) are destructive — take them only when you have confirmed it is
   safe for *that* database (see the Safety section of `references/troubleshooting.md`).
4. **Idempotent, evidence-driven steps.** Every repair keys off the repo's actual state, so
   re-running is safe. `scripts/converge-repo.sh` is written this way; follow the same
   discipline by hand.

## References and scripts

| File | What it gives you |
|---|---|
| `references/canonical-repo-state.md` | The full contract + the shared-server architecture, config precedence, project-specific values, and what does **not** belong in a repo |
| `references/troubleshooting.md` | The repair runbook: every failure mode → its exact signature → why → the fix, with commands |
| `references/diagnostics.md` | How to see real state without breaking anything, incl. the server-side SQL escape hatch when `bd` won't open the store |
| `scripts/audit-fleet.sh` | Read-only fleet audit → per-repo truth table + anomaly list |
| `scripts/converge-repo.sh` | Bring **one** repo to the canonical state, idempotently (handles dirty/identity/migration/config/push) |
| `scripts/beads_server.py` | Talk to the running shared Dolt server over SQL (inspect status/identity/prefix; reset a dirty working set) — the only safe way in when `bd` is gated |

## Hard rules

- **Never `bd init`.** It mints a fresh project identity and forks history from the remote.
  To (re)create a repo's database, use `bd bootstrap` (clones the remote), never `bd init`.
- **Never run the raw `dolt` CLI against the running server's data directory** — it corrupts
  the server's journal. Reach the databases through `bd`, or over the SQL protocol
  (`scripts/beads_server.py`). The `dolt.broken-*` directories you may see are the scars of
  this mistake.
- **One designated migrator per database.** Migrating the same remote-backed database from two
  clones forks the schema silently and unrecoverably. Migrate on one machine, then push.
- **The root / command-and-control repo holds the real issues.** Treat it as authoritative:
  never reset its working set or force-push it as part of a bulk sweep.

## Boundaries and coordination

- You own **beads-domain knowledge and repair**. You do not own the manifest or the knowledge
  store. When **polyrepo-doctor** runs a health check, it calls the beads portion here.
- Durable "how beads works in this project" facts belong in **polyrepo-info** (as a knowledge
  pointer). A registered, reusable script or procedure belongs in **polyrepo-governance**.
- Record what you changed and why; surface anything ambiguous or destructive to the human
  before doing it.
