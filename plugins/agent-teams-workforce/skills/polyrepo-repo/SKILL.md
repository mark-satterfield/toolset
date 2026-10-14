---
name: polyrepo-repo
description: >-
  Create, update, deprecate, list, or search a repository, and the steward's record of it.
  This is the steward's core skill and the command reference for the `polyrepo` tool, which
  reads every repo fact live from git and GitHub and keeps the manifest true to them. The
  first token of the request may be a CUDLS verb (create | update | delete | deprecate |
  list | search); if absent, infer the operation from the request. Use whenever a
  repository is added, renamed, deprecated or rebased, or when someone needs the count or
  list of repos, a repo's state against GitHub, or a repo found by an attribute.
---

# Polyrepo Repo

## The tool

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/skills/polyrepo-repo/scripts/polyrepo.py" <command> [--json]
```

Invoke it by that path (a bare `polyrepo` on `PATH` may be an unrelated program). It finds
its settings at `.polyrepo/config.yaml` in this order: `--config`, `$POLYREPO_CONFIG`, the
nearest `.polyrepo/config.yaml` above the working directory, `$SKILLSPOKE_CC/.polyrepo/`.
The config names the environment variable holding the repository root (`root_env`), the
GitHub owner, exclusions, and the naming patterns; every repo's path is discovered on disk.

Every command takes `--json` (one JSON object on stdout), `--config`, and `--no-cache`
(ignore the 5-minute freshness window on `git fetch` and the GitHub listing). Local git
facts are always read live. Exit status: 0 clean, 1 findings remain, 2 usage or
environment error; `grep` follows `rg` (0 match, 1 no match, 2 error).

A command that changes the steward's files (manifest, changelog, knowledge store, beads fleet list) commits
and pushes them itself, on `main` of the repo that holds them, and reports it under
`records`.

| Command | What it does |
|---|---|
| `reconcile [--fix] [--dry-run] [--no-fetch]` | Compare disk, GitHub and the manifest. `--fix` repairs every mechanical finding (manifest, push, GitHub rename, archive) and appends the changelog. |
| `status [repo\|path …] [--no-fetch]` | Live state per repo: branch, `uncommitted` and `uncommitted_files`, `last_commit`, `main.ahead/behind/up_to_date`, GitHub `pushed_at`, and `archived`. |
| `list [--group G] [--lifecycle L] [--space S]` | Repos, filtered. |
| `search attr=value [attr~regex …] [--fetch]` | Repos by any record attribute, dotted keys (`github.archived=false`, `main.behind=0`, `space=shared`); a term on `stacks` (`stacks~regex`) matches the matrix's stacks of each repo. It is not how to find where functionality lives: that is `atw-matrix find --kinds stack`. |
| `inventory [--all] [--no-fetch] [--name N]` | Every repo's full record, with the matrix's stacks that name it as their repository under `stacks` (each stack with its purpose and what it holds); `--all` adds every repo the manifest or GitHub has that is not on disk; `--name` keeps only the repo with that name. |
| `grep <pattern> [--space S] [--repo R …] [-i] [-l] [-F] [-w] [--glob G …]` | `rg` across every in-scope repo on disk, for the steward's own upkeep. |
| `rebase <repo …\|--all>` | Fetch and rebase `main` on `origin/main`; stops and reports on a conflict or a dirty tree. |
| `create <name> --space S --template T [--lifecycle L] [--dir D] [--dry-run]` | Validate the name, render the Copier template, create and push the GitHub repo, add the manifest entry, record the repo's stack in the matrix (see *The matrix*; a failure is `matrix_error`, exit 1), then do the repo's full beads setup (see `beads-setup`) and add the repo to the beads fleet list. Every repo outside `apps/marketing/` also gets GitNexus: the files are written before the first commit, the GITNEXUS block comes with the AGENTS.md blocks, and `ops/indexing/gitnexus-reindex.sh` indexes it once after the push (a failure is `gitnexus_error`, exit 1). |
| `clone <repo>` | Clone an existing GitHub repo into the one folder its name gives it (app space, then the template placement folder for its kind). A repo already at that folder is reported, not re-cloned. It refuses, exiting 2, when the repo already exists at any other path or is on disk twice. Anything that needs a local checkout of a repo uses this command; no session or script picks a folder or runs `git clone` itself. |
| `rename <repo> [<new-name>] [--also R …] [--skip-repo R …] [--keep-src R …] [--dry-run] [--trailer TEXT] [--pr-footer TEXT]` | Rename with every name the repository carries. On GitHub and locally together, repoint `origin`, rename the manifest entry, move the `repository` of the matrix's stacks to the new name, and replace the old path in the beads fleet list with the new one. Then bring the stack ids and stack file names and the Python names (distribution, import package and its `src/{app}/{domain}` folder, moved with `git mv`) to what `atw-naming` gives, and rewrite every import, dependency line, handler string and written reference to an old name in every other repository (paths in the config's `rename.sweep_exclude` are records and are never edited). Each repository that changes gets one worktree on branch `rename/<slug>`, its own `lint`, `typecheck` and `test` tasks run (only `ruff check` for a repository that waits on a library's renamed package; a failure is written in the pull request and the report and the pull request still opens), one commit and one pull request opened with `rename.pr_command` (`skillspoke-pr`); nothing is merged. A repository under `apps/marketing/`, any `--skip-repo` repository, and the `src/` files of a `--keep-src` repository are reported, never edited. The arc42 documents of the vault (`rename.documents`) are swept for the old names (names only) and committed and pushed, and the matrix follows (`atw-matrix rename`, `sync-documents --paths`, `commit`). With no new name only the stack and Python names are brought into line; `--also` adds further repositories to the same run so each repository still gets one pull request. `--dry-run` prints the whole plan (`names` in the JSON) before anything changes. Refuses an invalid or taken name (the last token must be a stack type), or a `main` not known to be pushed. |
| `deprecate <repo> [--dry-run]` | Refuses, naming the stack ids, while the matrix has a stack that names the repo (move or remove each first, see *The matrix*). Then `rename` to the `deprecated-` name, which records `deprecated_on` and removes the repo from the beads fleet list, then close every open pull request in the repo with the comment "Closed: this repository is deprecated." (branches are kept), reporting each one, then delete the local clone and its linked worktrees. The clone is deleted (`shutil.rmtree`, only on a path under the repository root whose name starts with `deprecated-`) only when it holds no work that exists only on this machine: no uncommitted changes or untracked files outside ignored paths in the clone or any linked worktree, no stash, and no local branch or worktree `HEAD` with commits on no remote branch. Otherwise the clone is left, the rest of the deprecation stands, the reasons and the exact path to delete by hand are reported, and the command exits 1. `--dry-run` lists the pull requests it would close and whether it would delete the clone. |
| `beads-setup [repo…] [--all] [--check] [--dry-run] [--trailer TEXT]` | Give a repo its complete beads setup: its database on the shared server (created through `bd bootstrap`, never `bd init`: a fresh database is bootstrapped embedded, given the fleet prefix, pushed to `refs/dolt/data`, then cloned into the shared server), identity and prefix repaired with `bd doctor --fix` and `converge-repo.sh`, the `.beads` config files (`config.yaml`, `metadata.json`, `.gitignore`) and a `.gitignore` with the beads and standard ignores for the repo's template kind committed and pushed to `main`, and the repo added to the beads fleet list. `--all` sets up every non-deprecated, non-archived repo with a gap or no database (`planned` repos included; `apps/marketing/` is never touched); `--check` reports gaps (missing or uncommitted `.beads` config, missing fleet list entry, incomplete `.gitignore`) and changes nothing. `create` runs it. |
| `beads-fleet [--fix]` | Check the beads fleet list (`repos.additional` in the control repo's `.beads/config.yaml`, config `beads.fleet_config`): every listed path exists and is an active fleet repo, and every active repo with a `.beads` folder is listed. `--fix` corrects the list. |
| `deprecated-prs [--fix]` | Report every open pull request in a `deprecated-` repo of the owner on GitHub. `--fix` closes each with the deprecation comment, keeping its branch. |
| `agents-sync [--check\|--dry-run] [--repo R …]` | Write the shared `AGENTS.md` blocks (the SkillSpoke shared block, the GitNexus block and the Agent Teams Workforce block, listed under `agents_sync.blocks` in the config) into every repo, committing and pushing each; `{{repo}}` in a block source becomes the repo's name; the GitNexus block replaces the older `<!-- gitnexus:start -->` section; `--check` reports repos out of date. |
| `gitnexus-sync [--check\|--dry-run] [--repo R …]` | Give every non-marketing repo its GitNexus files: `.gitnexusrc`, the `.gitnexus` ignore rule and the six skills in `.claude/skills/gitnexus/`, copied from the control repo files the config's `gitnexus` section names; commits and pushes each; `--check` reports repos out of date. |
| `templates-check` | Which templates lag the repos built from them, and which repo kinds have no template. |
| `environment [repo…] [--fix]` | Check every active Python repo (a `pyproject.toml` and an `install` task in its Taskfile; `apps/marketing/` excluded): `.venv/bin/python` exists and runs, every declared dependency is installed and importable, and `aws_cdk` imports where the code uses it. `--fix` runs the repo's `task install` for each gap and checks again; for an infra repo it also runs `cdk synth --profile dev`. `create` runs the same setup and checks. |
| `python-names [repo…]` | Check every active Python repo (a `pyproject.toml`; the control repo and `apps/marketing/` excluded) against the Python names of the naming standard: `atw-naming check python-distribution`, `python-package` and `python-package-path` against its `pyproject.toml` name and its source folder, `src` present for a `lib` and a `service`, `tests` present, no `__init__.py` in an app or team folder. One finding per failure. |
| `doctor [--fix]` | Every health check as one findings list: `reconcile`, `agents-sync --check`, the beads fleet audit, `beads-setup --check`, `beads-fleet`, `environment`, `python-names`, `deprecated-prs`, the governance entries, the knowledge-store pointers, the repository-naming document against the naming patterns, and the matrix's stacks against the repositories (`matrix`). `--fix` first runs `reconcile --fix`, `agents-sync`, `beads-setup --all`, `beads-fleet --fix` and `deprecated-prs --fix`, then repairs the matrix's stacks and commits the matrix. The launchd agent `com.skillspoke.polyrepo-daily` runs `doctor --fix` every day, logging under `$SKILLSPOKE_LOGS/polyrepo/`. |
| `commit --message TEXT` | Commit and push the steward's files after a hand edit. |

A record carries `name`, `space`, `path`, `lifecycle`, `present` (disk, github,
manifest), `naming`, `branch`, `uncommitted`, `uncommitted_files`, `last_commit`, `main`,
`origin_url`, `github`, `groups` (only for a repo that exists and is active) and, in
`inventory` and in `search` on `stacks`, `stacks`: the matrix's stacks that name the repo, each
with its `id`, `name`, `type`, `side`, `purpose`, `executionUse` and what it holds. A record
has no `purpose`, `owns` or `role`: those are the matrix's. A record has no dependencies:
a dependency is between services, components and infrastructure, never between repos.
Answer "what depends on what" with `atw-matrix deps --of <id>` and `deps --on <id>`; each
result names the stack that holds the target, and `node stack:<id>` its repository. When the
question needs what code does today, use GitNexus or the GraphRAG MCP server. Never record a
repo to repo edge.

### Reconcile findings

Each finding carries `mechanical` (true when `--fix` repairs it, with the repair in
`fix`), `status` (`open`, `fixed`, `failed`, `planned`) and `error`. Mechanical kinds
include `untracked-repo`, `untracked-github`, `orphan-entry`, `renamed`, `remote-url`,
`local-path`, `lifecycle`, `name-mismatch`, `origin-stale`, `no-origin`, `unpushed`,
`local-only`, `deprecated-undated`, `archive-due`, `group-member-unknown`,
`group-member-inactive`, `group-member-renamed`, `repo-dependency-stored`, and `open-items`
once every item in the section is settled. The rest are left open for the steward's
judgment, and each has an obvious next step:

| Finding | Settle it by |
|---|---|
| `deprecation-not-renamed` | `deprecate <repo>` if it is deprecated; otherwise set its `lifecycle` to `active` in the manifest. |
| `naming-violation`, `space-mismatch` | Choose the correct name or space from the naming patterns, then `rename <repo> <new-name>`. |
| `open-items` with unsettled items | Put each to the user in the reply, record the answer where it belongs, then remove the section. |
| `diverged`, `fetch-failed`, `no-default-branch`, `foreign-origin`, `github-missing`, `github-only`, `not-cloned`, `duplicate-name` | Inspect with `git` and `gh`, repair, and run `reconcile --fix` again. `not-cloned` is raised only for an active repo; a deprecated or archived repo is expected to have no local clone. |

## Operations (CUDLS)

- **create** — `create`. The name must match a naming pattern for its space (below). Pick the template whose kind matches the repo (`templates-check` lists
  the kinds).
  Every new repository is created private and with `allow_auto_merge=true` (the tool sets
  both); the owner is the only human, so every fleet repo allows auto-merge.
  Creating a repo includes its beads setup, its entry in the control repo's beads repository
  list, and a correct `.gitignore`; `create` does all three, and fails (exit 1) when beads setup
  fails, after the repo and manifest entry exist. `beads-setup` repairs it.
  Creating a repo also ends with a working development environment: `create` runs the
  template's setup task (`task install`) before the first commit (so the lockfile is committed),
  then verifies `.venv/bin/python`, every declared dependency, and for an infra template
  `cdk synth --profile dev`. It exits 1 with `environment_error` when any of them does not
  hold; `environment <repo> --fix` repairs it.
  It also records the repo's stack in the matrix (see *The matrix*); the stack's purpose is
  the architect's, so `create` takes none.
- **update** — Mechanical fields (`remote_url`, `lifecycle`, archived state) are kept true
  by `reconcile --fix`; do not edit them. Groups and `owner`: edit the manifest (below). What a
  repo holds and its purpose are the matrix's: a stack's `repository`, `app` and `executionUse`
  are `put stack` (see *The matrix*); its purpose is not written here.
- **rename** — `rename <repo> <new-name>`, on GitHub and locally together. The repo's entry in the beads repository list is replaced with the new path; its beads database keeps its name. The matrix's stacks that name the repo name the new one (`move-repository`). A rename covers the repository, the stack names, the Python names, every reference to them in the other repositories, the architecture documents and the matrix.

  The Python names follow the resource naming standard's "Python names" section. `src` is the source root and `tests` the unit test root. The source package is `src/{app}/{domain}` (`src/{app}/{team}/{domain}` for a team repository), in snake_case without the stack type, imported as `{app}.{domain}`: `shared-apiClient-lib` gives `src/shared/api_client`, imported as `shared.api_client`. The published package (`name` in `pyproject.toml`, the name in CodeArtifact) is hyphenated lower case with the type (`shared-api-client-lib`). The brand is `skillspoke` in Python. The app folder (`src/shared/`, `src/skillspoke/`) is a namespace package with no `__init__.py`, and each repository's `__init__.py` starts at the domain folder. Every name comes from `atw-naming` with `--repository` (`name python-package`, `name python-package-path`, `name python-distribution`, `name stack`, `name cdk-stack-file`; `check <type> <name> --repository <repo>` verifies one); never compose one by hand and never second-guess what it gives, a team repository included (`skillspoke.team.support`). One worktree and one pull request per repository changed. Run `--dry-run` first: the plan lists all of it, the arc42 documents and lines included, before anything changes. A repository that the approved architecture says is to be merged or retired is not renamed. The new name must end in a stack type; `SkillSpoke-auth-utils` is refused.
- **delete / deprecate** — `deprecate <repo>`. A repository is never deleted from GitHub. Its entry is removed from the beads repository list. The matrix must hold no stack that names it: `deprecate` refuses until each is moved or removed (see *The matrix*).
  The new name is `deprecated-` plus the old name, all lowercase
  (`SkillSpoke-eventsPublisher-service` → `deprecated-skillspoke-eventspublisher-service`).
  The rename happens on GitHub and locally together. Every open pull request in the repo is
  then closed with the comment "Closed: this repository is deprecated."; a deprecated repo
  never has an open pull request, and `doctor` reports any that does. Last, the local clone
  is deleted, unless it holds work that exists only on this machine (see the command
  table); a deprecated repo normally has no local clone. `reconcile`, `list` and `doctor`
  treat a deprecated or archived repo with no local clone as normal, never as a finding;
  `clone <repo>` brings one back when it is needed.
  `reconcile --fix` archives the repo on GitHub `deprecation.archive_after_days` (60) after
  `deprecated_on`. Deprecated and archived are separate lifecycle states.
- **beads fleet list** — `repos.additional` in the control repo's `.beads/config.yaml` is
  what `com.skillspoke.beads-fleet-watch` watches; a stale path silently stops that repo's
  beads syncing. `create`, `rename`, `deprecate` and the `archive-due` repair keep it true
  deterministically (add, replace, remove), re-reading the file immediately before each
  write and touching only the one entry. `beads-setup` over several repos writes the list once at the end of the run, so the watcher restarts once. Never edit it by hand for a repository change;
  `beads-fleet --fix` repairs drift.
- **list** — `list` or `inventory`: "how many repos", "which repos are deprecated".
- **search** — `search` for record attributes; `grep` for text, for the steward's own upkeep.
  Where functionality lives, and which repos hold a resource type ("which repos contain a
  DynamoDB table"), is the matrix: `atw-matrix find --kinds stack --text "<words>"`,
  `atw-matrix stacks --resource-type <type>`, then `node stack:<id>` for the repository.
  For a fact the manifest and the matrix do not hold, hand off to **polyrepo-info**.

## The matrix

The matrix holds stacks, and a repository is an attribute of a stack: a stack's `repository` is
the one repository that holds it, and a repository can hold several stacks. There is no row for
a repository and none for an app. The steward owns the facts the repositories show: a stack's
`name`, `app`, `executionUse`, `repository` and the `commands` the repository declares. A
stack's `purpose` is the solutions architect's (decided from the effective arc42 documents; a
stack no document gives a purpose for says the purpose is not stated), and the steward writes
none. Read and write the matrix only through `${CLAUDE_PLUGIN_ROOT}/bin/atw-matrix`, put the
environment assignment `ATW_MATRIX_ROLE=repository-steward` on every write command line, and
state `--side repository` on every write:

```bash
"${CLAUDE_PLUGIN_ROOT}/bin/atw-matrix" stacks --repository <repo>
"${CLAUDE_PLUGIN_ROOT}/bin/atw-matrix" node stack:<name>
ATW_MATRIX_ROLE=repository-steward "${CLAUDE_PLUGIN_ROOT}/bin/atw-matrix" put stack --side repository --name <stack> --app <app> --execution-use <executable|imported> --repository <repo> --purpose "The purpose is not stated."
ATW_MATRIX_ROLE=repository-steward "${CLAUDE_PLUGIN_ROOT}/bin/atw-matrix" put stack --side repository --id stack:<name> --repository <repo>
ATW_MATRIX_ROLE=repository-steward "${CLAUDE_PLUGIN_ROOT}/bin/atw-matrix" move-repository --from <old repo> --to <new repo>
ATW_MATRIX_ROLE=repository-steward "${CLAUDE_PLUGIN_ROOT}/bin/atw-matrix" remove stack:<name> --held
ATW_MATRIX_ROLE=repository-steward "${CLAUDE_PLUGIN_ROOT}/bin/atw-matrix" commit
"${CLAUDE_PLUGIN_ROOT}/bin/atw-matrix" check
```

The tool keeps the matrix true to the repositories, and commits the matrix file after it
changes it:

| Work | What the tool does in the matrix |
|---|---|
| `create` | Records the stack the new repository holds when its name ends in a stack type the naming rules list (`.resource-naming.yaml`, `segments.type.enum`) and no stack already names it as its repository: the stack takes the repository's name, its app is the repository's space, its execution use is `imported` for a `lib` and `executable` otherwise, and the purpose is not stated. A stack the matrix already holds under that id gets its `repository`. |
| `rename` | `move-repository --from <old> --to <new>`: every stack's `repository` changes, and no id does. |
| `deprecate`, and the archive repair | Refuse, naming the stack ids, while any stack names the repository. Move each stack (`put stack --id stack:<name> --repository <other repo>`) or remove it (`remove stack:<name> --held`), run `commit`, then try again. |
| `doctor` | Reports an active code repository that no stack names, a stack whose repository was renamed, is deprecated or archived, or exists nowhere, and an invalid matrix (`check`). `--fix` records the missing stack, names the renamed repository, removes a hint stack that holds nothing or else unsets the repository, and commits. A stack whose repository exists nowhere may belong to a repository elaboration has yet to create, so it is reported and left. |

A repository's lifecycle is not in the matrix: the tool reads it live. The matrix schema has
no field for a repository's role, and the steward writes none. After any write of your own, run
`commit`, then `check`; it must report `"valid": true`. `apps/marketing/` repositories keep
their rows as they are.

The matrix has one code mark, `verified`, recorded with the commit on a stack, on the entries
in it and on the relationships the code makes real. The build driver sets it when a Story's
code has been built and tested and has passed, including its CI/CD and its CDK. No agent sets
it. No deployed mark and no merged mark exists, and absent means not verified. Verified means
real: the entry or relationship exists, and its code is trusted and is expected to match the
architecture. Not verified means it still has to be made real: use it like any other, and
assume it may still have to be built. Existing code for it is a hint of how something was once
solved and may be stale, and a difference between that code and arc42 is never a discrepancy
and never a finding.

## Naming patterns

The config's `naming.patterns` are the rule; in summary: `SkillSpoke` and
`SkillSpoke-{name}` are the personal-agent app; `shared-{name}` is shared or sharable across
the whole company; `marketing-{name}` is marketing; `employer-{name}` is the employer app;
`{internal|tool}-skillspoke-{name}` is non-application (GitHub only); `deprecated-{name}` as
above. An application name must also end in a stack type (`service`, `infra`, `lib`, `web`,
`mobile`, `extension`, `assets`: `segments.type.enum` of `.resource-naming.yaml`), which the
tool checks after the regex matches; a name with no hyphen (`SkillSpoke`, the control
repository) is exempt. Each app space is a subfolder of the repository root. The canonical statement is the
vault's `repository-naming.md` (the config's `naming.document`); `doctor` checks that its
sections, examples, deprecation examples and archive delay agree with the patterns.

## Editing the manifest by judgment

For the fields the tool does not write (groups, `owner`): the manifest keeps no `purpose`,
`owns` or `role`, and its next write by the tool drops them. There is no
dependency field. A dependency is between services, components and infrastructure, never
between repos.

1. Edit `$SKILLSPOKE_CC/.polyrepo/manifest.yaml` preserving its comments — with an editor
   tool for a small change, or `uv run --with ruamel.yaml python3 …` (round-trip mode) for a
   programmatic one. The schema is `references/manifest-schema.md`; it also says what may
   and may not be stored.
2. Append a changelog entry (`references/learning-protocol.md`).
3. Run `reconcile --json` and confirm it reports no new finding.
4. Run `commit --message "<what changed>"`.

Never add `local_path`, deploy waves, or any fact whose canonical home is another document.
Deployment order lives in `$SKILLSPOKE_CC/deployment/waves*.yaml`, not the manifest.

## Boundaries

You own the repos and their records. Facts outside the manifest, the matrix and the knowledge store are
**polyrepo-info**; the registry of the project's own scripts and procedures is
**polyrepo-governance**; first-time bootstrap is **polyrepo-setup**.
