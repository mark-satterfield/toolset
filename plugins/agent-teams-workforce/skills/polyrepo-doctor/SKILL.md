---
name: polyrepo-doctor
description: >-
  Health check for the project's repositories and the steward's records of them: reconcile
  disk, GitHub and the manifest; check that every repo carries the current shared
  `AGENTS.md` blocks; audit every repo's beads; check that every governance entry and
  knowledge-store pointer still resolves; check the repository-naming document against the
  naming patterns. Reports findings, and with `--fix` repairs every finding it can. Use for
  a health check before a release, after significant changes, on a schedule, or on request.
---

# Polyrepo Doctor

The tool is `uv run "${CLAUDE_PLUGIN_ROOT}/skills/polyrepo-repo/scripts/polyrepo.py"` (see
the `polyrepo-repo` skill for its commands). Every check is deterministic and runs in the
tool: start from `doctor --json`, or `doctor --fix --json` to repair first.

## Checks

| Check | What it runs | Clean when |
|---|---|---|
| `reconcile` | `reconcile` | no open finding |
| `agents-sync` | `agents-sync --check` | every repo has the current shared `AGENTS.md` blocks |
| `beads` | `polyrepo-beads/scripts/audit-fleet.sh --json` over every active repo on disk, in every app space | no anomaly |
| `governance` | each manifest `governance` entry: its `location` exists, and a script or tool's `invoke` (up to its first `<placeholder>`) runs with `--help` | every entry resolves and runs |
| `knowledge` | each `location` or `pointer` entry in the knowledge store: every path in its `resolves` exists | every pointer resolves |
| `naming-doc` | the config's `naming.document` (the vault's `repository-naming.md`) against `naming.patterns` | every pattern has a section, every example matches its section's pattern, deprecation examples and the archive delay agree with the tool |

The output is one findings list: each finding with its `check`, `subject` (repo or entry),
`kind` and `detail`, plus the count per check and, under `--fix`, what each repair did.
The launchd agent `com.skillspoke.polyrepo-daily` runs `doctor --fix` daily; its reports
are under `$SKILLSPOKE_LOGS/polyrepo/`.

## `--fix`

`doctor --fix` runs `reconcile --fix` and then `agents-sync` before the checks; each commits
and pushes what it changed. What stays open needs judgment:

- Reconcile judgment findings: settle them as the `polyrepo-repo` skill's finding table
  says, then run `reconcile` again.
- A beads anomaly: repair the repo with the **polyrepo-beads** skill (`converge-repo.sh`,
  its troubleshooting runbook).
- A governance entry or knowledge pointer that no longer resolves: find where the thing now
  lives and update the entry (**polyrepo-governance** or **polyrepo-info**), or retire it
  with the reason when the thing is gone.
- A naming-document finding: the document and the config's patterns disagree. Correct the
  one that is wrong; when that is a naming rule itself, ask the user.

Report exactly what changed and what is still open.

## Boundaries

Every write goes through the tool or the owning skill (**polyrepo-repo**,
**polyrepo-info**, **polyrepo-governance**, **polyrepo-beads**) and its learning protocol.
