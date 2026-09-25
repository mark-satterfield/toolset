---
name: polyrepo-doctor
description: >-
  Health check for the project's repositories and the steward's records of them: reconcile
  disk, GitHub and the manifest; check that every repo carries the current shared
  `AGENTS.md` block; check that the repo templates keep up with the repos built from them;
  check that every knowledge-store and governance pointer still resolves. Reports findings,
  and with `--fix` repairs every finding it can. Use for a health check before a release,
  after significant changes, on a schedule, or on request.
---

# Polyrepo Doctor

The tool is `uv run "${CLAUDE_PLUGIN_ROOT}/skills/polyrepo-repo/scripts/polyrepo.py"` (see
the `polyrepo-repo` skill for its commands). Run every check with `--json`.

## Checks

| Check | Command | Clean when |
|---|---|---|
| Disk, GitHub and manifest agree | `reconcile --json` (with `--fix` under `--fix`) | exit 0, `open` is 0 |
| Every repo has the current shared `AGENTS.md` blocks | `agents-sync --check --json` | exit 0 |
| Knowledge-store pointers resolve | read `.polyrepo/knowledge.yaml`; for each `kind: location` or `pointer` entry, confirm the file, folder, vault note or command it names exists (vault notes through `obsidian-cli vault="skillspoke-docs"`) | every pointer resolves |
| Governance entries resolve | for each manifest `governance` entry, confirm its `location` exists and its `invoke` runs (`--help` or equivalent) | every entry resolves |

The tool's `doctor` command runs the three tool checks in parallel and the governance location check, and returns them as one findings list; start from `doctor --json`, then run the knowledge-store check. The launchd agent `com.skillspoke.polyrepo-daily` runs `reconcile --fix` and `doctor` daily; its reports are under `$SKILLSPOKE_LOGS/polyrepo/`.

## Output

One findings list: each finding with its check, repo or entry, severity, and the evidence
(the tool's `detail`, or the path that did not resolve). End with the count per check.

## `--fix`

- `reconcile --fix` repairs every mechanical finding. Settle the judgment findings it leaves
  open as the `polyrepo-repo` skill's finding table says, then run `reconcile` again.
- `agents-sync` (without `--check`) writes the blocks into every out-of-date repo, committing
  and pushing each on `main`.
- A lagging template: bring the template up to what its repos now share, in
  `$SKILLSPOKE_CC/repositories/templates/`, and commit it. A repo kind with no template:
  report it with the repos of that kind; creating a new template is a judgment the steward
  makes when a request needs a repo of that kind.
- A knowledge-store or governance pointer that no longer resolves: find where the thing
  now lives and update the entry (**polyrepo-info** or **polyrepo-governance**), or retire
  the entry with the reason when the thing is gone.

Report exactly what changed and what is still open.

## Boundaries

Every write goes through the tool or the owning skill (**polyrepo-repo**,
**polyrepo-info**, **polyrepo-governance**) and its learning protocol.
