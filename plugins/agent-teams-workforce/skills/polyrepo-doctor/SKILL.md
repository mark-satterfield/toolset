---
name: polyrepo-doctor
description: >-
  Health check for the project's repositories and the steward's records of them: reconcile
  disk, GitHub and the manifest; check that every repo carries the current shared
  `AGENTS.md` blocks; audit every repo's beads and the beads fleet list; check that no
  deprecated repo has an open pull request and none is overdue for archiving; check that every governance entry and
  knowledge-store pointer still resolves; check the template types with the naming command;
  check the matrix's stacks against the repositories; check that every
  repository records a tier. Reports findings, and with `--fix` repairs every finding it can. Use for
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
| `agents-sync` | `agents-sync --check` | every repo on disk that is not deprecated has the current shared `AGENTS.md` blocks |
| `hooks-sync` | `hooks-sync --check` | every repo on disk that is not deprecated registers the current shared hooks in its `.claude/settings.json` |
| `checks-sync` | `checks-sync --check` | every repo on disk that is not deprecated has the current canonical code checks of its technologies (`.code-checks/`, the canonical configuration files, the assembled `.pre-commit-config.yaml`, the `lint` task), nothing that contradicts them, every repository file consuming them, and the commit hook installed. A note on a repository's own file (a tsconfig or ESLint config that weakens the base, missing Node devDependencies) is tier 1 work in that repository |
| `tiers` | `tiers`: the config's `tiers.external` | every external path is the root of a git clone. Kind: `tier-external` (the config's path does not resolve: correct `tiers.external` in the config). A manifest entry with no tier is a `reconcile` finding (`tier-missing`), repaired by `reconcile --fix` |
| `gitnexus-sync` | `gitnexus-sync --check` | every repo that is not deprecated has `.gitnexusrc`, the `.gitnexus` ignore rule and the current `.claude/skills/gitnexus/` |
| `beads` | `polyrepo-beads/scripts/audit-fleet.sh --json` over every non-deprecated, non-archived repo on disk, in every app space | no anomaly |
| `beads-setup` | `beads-setup --check`: every non-deprecated, non-archived repo (whatever its lifecycle, `planned` included) has `.beads/config.yaml`, `metadata.json` and `.beads/.gitignore` committed, a beads sync remote and Dolt remote `origin` that name its GitHub repository (`beads-remote-stale` otherwise; `beads-setup` repairs it), an entry in the beads fleet list, and a `.gitignore` with the beads and standard ignores | no gap |
| `beads-fleet` | `beads-fleet`: the beads fleet list (`repos.additional` in the control repo's `.beads/config.yaml`), which the project's fleet-watch launchd agent watches | every listed path exists and is an active fleet repo, and every active repo with a `.beads` folder is listed |
| `environment` | `environment`: every non-deprecated, non-archived Python repo (a `pyproject.toml` and an `install` task in its Taskfile) | `.venv/bin/python` exists and runs, every declared dependency is installed and importable, and `aws_cdk` imports wherever the code uses it. A gap is repaired with `environment <repo> --fix` (removes a `.venv` whose interpreter is missing, a dangling link or does not start, then runs the repo's `task install --force`; it is not part of `doctor --fix`); a failure that needs a change to the repo's code or `pyproject.toml` is reported to the owner |
| `python-names` | `python-names`: every non-deprecated, non-archived repo with a `pyproject.toml` (the control repo excluded) | The repo's `pyproject.toml` name, import package and source folder compared with what the naming command gives the repository name (`name repository-names`); `src` present when the template that builds the repository's type renders a `pyproject.toml` and a `src` folder; `tests` present; no `__init__.py` in a project or team folder. A failure is repaired by `rename <repo> [--also R …]`, which opens a pull request; a missing `tests` folder is the repo's own work and is reported |
| `deprecated-prs` | `deprecated-prs`: every open pull request on GitHub in a repo of the owner whose name starts with `deprecated-` | no deprecated repo has an open pull request |
| `archive-due` | `archive-due --dry-run`: every deprecated repo whose `deprecated_on` is at least `deprecation.archive_after_days` (config) days ago, and every archived repo with a local clone | nothing is due and nothing is kept. Kinds: `archive-planned` (due; `doctor --fix` archives it), `archive-kept` (an open pull request or a matrix stack in it), `archive-undated` (no valid `deprecated_on`), `archive-failed`, `archived-clone-kept` (the clone holds work that exists only on this machine) |
| `governance` | each manifest `governance` entry: its `location` exists, and a script or tool's `invoke` (up to its first `<placeholder>`) runs with `--help` | every entry resolves and runs |
| `knowledge` | each `location` or `pointer` entry in the knowledge store: every path in its `resolves` exists | every pointer resolves |
| `templates` | the config's `templates.kinds[].types`, the steward's map from repository types to the template that builds them, each checked with the naming command (`token check <type> --role type --in repository`) | the naming command accepts every listed type. Kind: `type-unknown`, with the command's violations |
| `organization` | the environment variable values the steward's record `organization-structure.md` states, against the environment variables | each stated value equals the variable's value. Kinds: `unset`, `differs`, `missing` |
| `matrix` | the matrix's stacks (`atw-matrix stacks`) and `atw-matrix check` against the repositories: every active code repository (a name the naming command reads as a repository of kind `repository`, with a type) is the `repository` of a stack, every stack's `repository` is an active repository, each command a stack records (`commands`, a copy of what the repository declares) is still a task of the repository's Taskfile or a script of its package.json, and the matrix is valid | no finding. Kinds: `stack-missing`, `stack-repository-inactive`, `stack-repository-missing`, `stack-command-stale` (refresh it with `put stack --commands-<test|publish|deploy>` from what the repository declares now), `matrix-invalid`, and `error` when the matrix cannot be read |

The output is one findings list: each finding with its `check`, `subject` (repo or entry),
`kind` and `detail`, plus the count per check and, under `--fix`, what each repair did.
The project's daily launchd agent runs `doctor --fix`; where it writes its reports is in the
steward's organization record.

## `--fix`

`doctor --fix` runs `reconcile --fix`, `agents-sync`, `hooks-sync`, `checks-sync`, `gitnexus-sync`, `beads-setup --all`, `beads-fleet --fix`,
`deprecated-prs --fix` and then `archive-due` before the checks; each commits and pushes what it changed.
`archive-due` archives every deprecated repo that is due (the project's scheduled
`archive-due` job runs it daily too, so `doctor --fix` catches up a missed day).
It then
repairs the matrix's stacks and commits the matrix: `stack-missing` records the stack
(repository side, purpose not stated), and `stack-repository-inactive` removes a hint stack that holds nothing or else unsets its
repository.
`beads-fleet --fix` removes every listed path that is missing or not an active fleet repo
and adds every unlisted active repo with a `.beads` folder. `deprecated-prs --fix` closes
every open pull request in a deprecated repo with the comment "Closed: this repository is
deprecated." and keeps its branch. `agents-sync`, `hooks-sync` and `checks-sync` commit every repo on `main` in its primary working tree and push it, whatever its tier (`AGENTS.md`
and `.claude/` are tier 2 in every repository); a repo whose `main` cannot be brought up to `origin/main`
(`stale-main`) or whose push the remote rejects (`committed`) keeps its finding until that is settled. What stays open needs judgment:

- Reconcile judgment findings: settle them as the `polyrepo-repo` skill's finding table
  says, then run `reconcile` again.
- `archive-kept`: an open pull request (close it with `deprecated-prs --fix`, or report it when
  it must be kept) or a matrix stack (move or remove it) holds the repo deprecated; the next run
  archives it. `archived-clone-kept`: report the clone and the work that exists only there to
  the owner; never delete it. A repository is never deleted, and you never propose deleting one.
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
- A `templates` finding (`type-unknown`): the config's template map lists a type the naming
  command refuses. Correct the map in `.polyrepo/config.yaml` to the types the command accepts.

Report exactly what changed and what is still open.

## Boundaries

Every write goes through the tool or the owning skill (**polyrepo-repo**,
**polyrepo-info**, **polyrepo-governance**, **polyrepo-beads**) and its learning protocol.
Every change to a vault document goes to the `filing-clerk`.
