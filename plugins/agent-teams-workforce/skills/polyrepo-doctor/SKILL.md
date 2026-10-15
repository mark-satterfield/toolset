---
name: polyrepo-doctor
description: >-
  Health check for the project's repositories and the steward's records of them: reconcile
  disk, GitHub and the manifest; check that every repo carries the current shared
  `AGENTS.md` blocks; audit every repo's beads and the beads fleet list; check that no
  deprecated repo has an open pull request; check that every governance entry and
  knowledge-store pointer still resolves; check the repository-naming document against the
  naming patterns; check the matrix's stacks against the repositories; check that every
  repository records a tier and that the tier export is current. Reports findings, and with `--fix` repairs every finding it can. Use for
  a health check before a release, after significant changes, on a schedule, or on request.
---

# Polyrepo Doctor

The tool is `uv run "${CLAUDE_PLUGIN_ROOT}/skills/polyrepo-repo/scripts/polyrepo.py"` (see
the `polyrepo-repo` skill for its commands). Every check is deterministic and runs in the
tool: start from `doctor --json`, or `doctor --fix --json` to repair first.

## Checks

| Check | What it runs | Clean when |
|---|---|---|
| `reconcile` | `reconcile` | no open finding; a deprecated or archived repo with no local clone is normal (`deprecate` deletes the clone) and raises none |
| `agents-sync` | `agents-sync --check` | every repo on disk that is not deprecated, outside `apps/marketing/`, has the current shared `AGENTS.md` blocks |
| `tiers` | `tiers`: the tier export (`.polyrepo/repository-tiers.json`) against the manifest's tiers and the config's `tiers.external` | the export exists and holds exactly what the manifest and the config give, and every external path is the root of a git clone. Kinds: `tier-export-missing`, `tier-export-stale` (both repaired by `tiers --write`, which `doctor --fix` runs), `tier-external` (the config's path does not resolve: correct `tiers.external` in the config). A manifest entry with no tier is a `reconcile` finding (`tier-missing`), repaired by `reconcile --fix` |
| `gitnexus-sync` | `gitnexus-sync --check` | every non-marketing repo that is not deprecated has `.gitnexusrc`, the `.gitnexus` ignore rule and the current `.claude/skills/gitnexus/` |
| `beads` | `polyrepo-beads/scripts/audit-fleet.sh --json` over every non-deprecated, non-archived repo on disk, in every app space except marketing | no anomaly |
| `beads-setup` | `beads-setup --check`: every non-deprecated, non-archived repo (whatever its lifecycle, `planned` included; `apps/marketing/` excluded) has `.beads/config.yaml`, `metadata.json` and `.beads/.gitignore` committed, an entry in the beads fleet list, and a `.gitignore` with the beads and standard ignores | no gap |
| `beads-fleet` | `beads-fleet`: the beads fleet list (`repos.additional` in the control repo's `.beads/config.yaml`), which `com.skillspoke.beads-fleet-watch` watches | every listed path exists and is an active fleet repo, and every active repo with a `.beads` folder is listed |
| `environment` | `environment`: every non-deprecated, non-archived Python repo (a `pyproject.toml` and an `install` task in its Taskfile; `apps/marketing/` excluded) | `.venv/bin/python` exists and runs, every declared dependency is installed and importable, and `aws_cdk` imports wherever the code uses it. A gap is repaired with `environment <repo> --fix` (runs the repo's `task install`; it is not part of `doctor --fix`); a failure that needs a change to the repo's code or `pyproject.toml` is reported to the owner |
| `python-names` | `python-names`: every non-deprecated, non-archived repo with a `pyproject.toml` (the control repo and `apps/marketing/` excluded) | The three `atw-naming check` commands (`python-distribution`, `python-package`, `python-package-path`) against the repo's `pyproject.toml` name and its source folder; `src` present for a `lib` and a `service`; `tests` present; no `__init__.py` in an app or team folder. A failure is repaired by `rename <repo> [--also R …]`, which opens a pull request; a missing `tests` folder is the repo's own work and is reported |
| `deprecated-prs` | `deprecated-prs`: every open pull request on GitHub in a repo of the owner whose name starts with `deprecated-` | no deprecated repo has an open pull request |
| `governance` | each manifest `governance` entry: its `location` exists, and a script or tool's `invoke` (up to its first `<placeholder>`) runs with `--help` | every entry resolves and runs |
| `knowledge` | each `location` or `pointer` entry in the knowledge store: every path in its `resolves` exists | every pointer resolves |
| `naming-doc` | the config's `naming.document` (the vault's `repository-naming.md`) against `naming.patterns` | every pattern has a section, every example matches its section's pattern, deprecation examples and the archive delay agree with the tool |
| `matrix` | the matrix's stacks (`atw-matrix stacks`) and `atw-matrix check` against the repositories: every active code repository (a name ending in a stack type, outside `apps/marketing/`) is the `repository` of a stack, every stack's `repository` is an active repository, and the matrix is valid | no finding. Kinds: `stack-missing`, `stack-repository-renamed`, `stack-repository-inactive`, `stack-repository-missing`, `matrix-invalid`, and `error` when the matrix cannot be read |

The output is one findings list: each finding with its `check`, `subject` (repo or entry),
`kind` and `detail`, plus the count per check and, under `--fix`, what each repair did.
The launchd agent `com.skillspoke.polyrepo-daily` runs `doctor --fix` daily; its reports
are under `$SKILLSPOKE_LOGS/polyrepo/`.

## `--fix`

`doctor --fix` runs `reconcile --fix`, `tiers --write`, `agents-sync`, `gitnexus-sync`, `beads-setup --all`, `beads-fleet --fix` and then
`deprecated-prs --fix` before the checks; each commits and pushes what it changed. It then
repairs the matrix's stacks and commits the matrix: `stack-missing` records the stack
(repository side, purpose not stated), `stack-repository-renamed` names the new repository,
and `stack-repository-inactive` removes a hint stack that holds nothing or else unsets its
repository.
`beads-fleet --fix` removes every listed path that is missing or not an active fleet repo
and adds every unlisted active repo with a `.beads` folder. `deprecated-prs --fix` closes
every open pull request in a deprecated repo with the comment "Closed: this repository is
deprecated." and keeps its branch. `agents-sync` follows each repo's tier: a `tooling` repo is
committed on `main`; a `product` repo gets a pull request from a worktree, so its finding stays
(`pending`) until that pull request is merged. What stays open needs judgment:

- Reconcile judgment findings: settle them as the `polyrepo-repo` skill's finding table
  says, then run `reconcile` again.
- A `stack-repository-missing` finding: the stack names a repository that exists on neither disk
  nor GitHub. If elaboration has yet to create it, leave it; otherwise correct the stack's
  `repository` (`put stack --id stack:<name> --repository <repo>`) or unset it. A
  `matrix-invalid` finding names the problems `atw-matrix check` reports; fix the entry it
  names, or send it to the agent that owns it.
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
