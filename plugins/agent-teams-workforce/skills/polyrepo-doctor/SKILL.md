---
name: polyrepo-doctor
description: >-
  Health check for the project's repositories and the steward's records of them: reconcile
  disk, GitHub and the manifest; check that every repo carries the current shared
  `AGENTS.md` blocks; audit every repo's beads and the beads fleet list; check that no
  deprecated repo has an open pull request and none is overdue for archiving; check that every governance entry and
  knowledge-store pointer still resolves; check that the vault's repository naming note is readable and states every rule the tool needs;
  check the matrix's stacks against the repositories; check that every
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
| `agents-sync` | `agents-sync --check` | every repo on disk that is not deprecated has the current shared `AGENTS.md` blocks |
| `tiers` | `tiers`: the tier export (`.polyrepo/repository-tiers.json`) against the manifest's tiers and the config's `tiers.external` | the export exists and holds exactly what the manifest and the config give, and every external path is the root of a git clone. Kinds: `tier-export-missing`, `tier-export-stale` (both repaired by `tiers --write`, which `doctor --fix` runs), `tier-external` (the config's path does not resolve: correct `tiers.external` in the config). A manifest entry with no tier is a `reconcile` finding (`tier-missing`), repaired by `reconcile --fix` |
| `gitnexus-sync` | `gitnexus-sync --check` | every repo that is not deprecated has `.gitnexusrc`, the `.gitnexus` ignore rule and the current `.claude/skills/gitnexus/` |
| `beads` | `polyrepo-beads/scripts/audit-fleet.sh --json` over every non-deprecated, non-archived repo on disk, in every app space | no anomaly |
| `beads-setup` | `beads-setup --check`: every non-deprecated, non-archived repo (whatever its lifecycle, `planned` included) has `.beads/config.yaml`, `metadata.json` and `.beads/.gitignore` committed, an entry in the beads fleet list, and a `.gitignore` with the beads and standard ignores | no gap |
| `beads-fleet` | `beads-fleet`: the beads fleet list (`repos.additional` in the control repo's `.beads/config.yaml`), which `com.skillspoke.beads-fleet-watch` watches | every listed path exists and is an active fleet repo, and every active repo with a `.beads` folder is listed |
| `environment` | `environment`: every non-deprecated, non-archived Python repo (a `pyproject.toml` and an `install` task in its Taskfile) | `.venv/bin/python` exists and runs, every declared dependency is installed and importable, and `aws_cdk` imports wherever the code uses it. A gap is repaired with `environment <repo> --fix` (runs the repo's `task install`; it is not part of `doctor --fix`); a failure that needs a change to the repo's code or `pyproject.toml` is reported to the owner |
| `python-names` | `python-names`: every non-deprecated, non-archived repo with a `pyproject.toml` (the control repo excluded) | The three `atw-naming check` commands (`python-distribution`, `python-package`, `python-package-path`) against the repo's `pyproject.toml` name and its source folder; `src` present for a `lib` and a `service`; `tests` present; no `__init__.py` in an app or team folder. A failure is repaired by `rename <repo> [--also R …]`, which opens a pull request; a missing `tests` folder is the repo's own work and is reported |
| `deprecated-prs` | `deprecated-prs`: every open pull request on GitHub in a repo of the owner whose name starts with `deprecated-` | no deprecated repo has an open pull request |
| `archive-due` | `archive-due --dry-run`: every deprecated repo whose `deprecated_on` is at least as many days ago as the vault's repository naming note states, and every archived repo with a local clone | nothing is due and nothing is kept. Kinds: `archive-planned` (due; `doctor --fix` archives it), `archive-kept` (an open pull request or a matrix stack in it), `archive-undated` (no valid `deprecated_on`), `archive-failed`, `archived-clone-kept` (the clone holds work that exists only on this machine) |
| `governance` | each manifest `governance` entry: its `location` exists, and a script or tool's `invoke` (up to its first `<placeholder>`) runs with `--help` | every entry resolves and runs |
| `knowledge` | each `location` or `pointer` entry in the knowledge store: every path in its `resolves` exists | every pointer resolves |
| `naming-doc` | the config's `naming.document` under `naming.document_root`: the vault's canonical repository naming note, `docs/tech/architecture/arc42/08-crosscutting-concepts/repository-naming.md`, read the way every command reads it | the note is found, and states every rule the tool needs: each project's prefix (the table with a `Project…` column and a `Prefix` column), the repository types, a pattern for each project and for the non-application and deprecated repositories, the names that belong to the project, and where repositories are placed. Kind `unreadable` carries the sentence naming the rule the note does not state. The report also carries `naming_note`: what was read from the note. There is no copy of the rules to compare |
| `templates` | the config's `templates.kinds[].types`, the steward's map from repository types to the template that builds them, against the types the naming note lists | no kind lists a type the note does not have. Kind: `type-unknown` |
| `organization` | the `SKILLSPOKE_*` values the steward's record `organization-structure.md` states, against the environment variables | each stated value equals the variable's value. Kinds: `unset`, `differs`, `missing` |
| `matrix` | the matrix's stacks (`atw-matrix stacks`) and `atw-matrix check` against the repositories: every active code repository (a name ending in a stack type) is the `repository` of a stack, every stack's `repository` is an active repository, each command a stack records (`commands`, a copy of what the repository declares) is still a task of the repository's Taskfile or a script of its package.json, and the matrix is valid | no finding. Kinds: `stack-missing`, `stack-repository-renamed`, `stack-repository-inactive`, `stack-repository-missing`, `stack-command-stale` (refresh it with `put stack --commands-<test|publish|deploy>` from what the repository declares now), `matrix-invalid`, and `error` when the matrix cannot be read |

The output is one findings list: each finding with its `check`, `subject` (repo or entry),
`kind` and `detail`, plus the count per check and, under `--fix`, what each repair did.
The launchd agent `com.skillspoke.polyrepo-daily` runs `doctor --fix` daily; its reports
are under `$SKILLSPOKE_LOGS/polyrepo/`.

## `--fix`

`doctor --fix` runs `reconcile --fix`, `tiers --write`, `agents-sync`, `gitnexus-sync`, `beads-setup --all`, `beads-fleet --fix`,
`deprecated-prs --fix` and then `archive-due` before the checks; each commits and pushes what it changed.
`archive-due` archives every deprecated repo that is due (the launchd agent
`com.skillspoke.polyrepo-archive-due` runs it daily too, so `doctor --fix` catches up a missed day).
It then
repairs the matrix's stacks and commits the matrix: `stack-missing` records the stack
(repository side, purpose not stated), `stack-repository-renamed` names the new repository,
and `stack-repository-inactive` removes a hint stack that holds nothing or else unsets its
repository.
`beads-fleet --fix` removes every listed path that is missing or not an active fleet repo
and adds every unlisted active repo with a `.beads` folder. `deprecated-prs --fix` closes
every open pull request in a deprecated repo with the comment "Closed: this repository is
deprecated." and keeps its branch. `agents-sync` commits every repo on `main` in its primary working tree and pushes it, whatever its tier (the blocks
are AI tooling, which is tier 2); a repo whose `main` cannot be brought up to `origin/main`
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
- A naming-document finding (`unreadable`): the note is missing, or does not state a rule the
  tool needs. The note is canonical and you hold no copy of its rules. You never edit the
  note: hand the missing or wrong rule to the `filing-clerk`, which files the change or brings
  the conflict to the owner. When the note is not found, `naming.document` and
  `naming.document_root` do not name it; set them to the note's path, never to a copy of
  your own.

Report exactly what changed and what is still open.

## Boundaries

Every write goes through the tool or the owning skill (**polyrepo-repo**,
**polyrepo-info**, **polyrepo-governance**, **polyrepo-beads**) and its learning protocol.
Every change to a vault document goes to the `filing-clerk`.
