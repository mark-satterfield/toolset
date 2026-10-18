---
name: polyrepo-repo
description: >-
  Create, update, deprecate, list, or search a repository, and the steward's record of it.
  This is the steward's core skill and the command reference for the `polyrepo` tool, which
  reads every repo fact live from git and GitHub and keeps the manifest true to them. The
  first token of the request may be a CUDLS verb (create | update | delete | deprecate |
  list | search); if absent, infer the operation from the request. Use whenever a
  repository is added, renamed, deprecated or rebased, or when someone needs the count or
  list of repos, a repo's state against GitHub, a repo found by an attribute, or which
  tech stacks and checker configurations the repos hold.
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
GitHub owner, exclusions, the pointer to the vault's repository naming document, where each repository
is placed (`placement`) and how long a deprecated repository waits to be archived (`deprecation`);
every repo's path is discovered on disk.

Every command takes `--json` (one JSON object on stdout), `--config`, and `--no-cache`
(ignore the 5-minute freshness window on `git fetch` and the GitHub listing). Local git
facts are always read live. Exit status: 0 clean, 1 findings remain, 2 usage or
environment error; `grep` follows `rg` (0 match, 1 no match, 2 error).

A command that changes the steward's files (manifest, knowledge store, beads fleet list) commits
and pushes them itself, on `main` of the repo that holds them, with a message that says what
changed, and reports it under `records`. A line in the environment variable `POLYREPO_COMMIT_TRAILER` ends the message of every
commit the tool makes.

| Command | What it does |
|---|---|
| `reconcile [--fix] [--dry-run] [--no-fetch]` | Compare disk, GitHub and the manifest. `--fix` repairs every mechanical finding (manifest, push, GitHub rename). Archiving is `archive-due`'s. |
| `status [repo\|path …] [--no-fetch]` | Live state per repo: branch, `uncommitted` and `uncommitted_files`, `last_commit`, `main.ahead/behind/up_to_date`, GitHub `pushed_at`, and `archived`. |
| `list [--group G] [--lifecycle L] [--space S] [--include-inactive]` | Active repos, filtered; deprecated and archived repos only with `--include-inactive` or a `--lifecycle` filter naming them. |
| `search attr=value [attr~regex …] [--fetch] [--include-inactive]` | Active repos by any record attribute (deprecated and archived ones only with `--include-inactive` or a `lifecycle` term), dotted keys (`github.archived=false`, `main.behind=0`, `space=shared`); a term on `stacks` (`stacks~regex`) matches the matrix's stacks of each repo. It is not how to find where functionality lives: that is `atw-matrix find --kinds stack`. |
| `inventory [--all] [--no-fetch] [--name N] [--include-inactive]` | Every active repo's full record (deprecated and archived ones only with `--include-inactive` or `--name`), with the matrix's stacks that name it as their repository under `stacks` (each stack with its purpose and what it holds); `--all` adds every repo the manifest records that is not on disk; `--name` keeps only the repo with that name. |
| `grep <pattern> [--space S] [--repo R …] [-i] [-l] [-F] [-w] [--glob G …]` | `rg` across every in-scope repo on disk, for the steward's own upkeep. |
| `tech-stacks [--repo R …] [--space S] [--summary]` | The tech stacks each active repo holds and the checker configurations it carries, read from the files git tracks or does not ignore (virtual environments, `node_modules`, build output and `.worktrees/` excluded), in parallel and with no network; every active clone under the root and the config's `tiers.external` repos unless `--space` or `--repo` narrows it. Stacks, each with its `evidence`: `python`, `cdk` (with the app's `languages` from `cdk.json` and the `aws-cdk-lib` dependency), `typescript`, `javascript`, `web` (with the frameworks: Next.js, React, Vue, Svelte, Angular, Astro, Vite …), and the `shell`, `yaml`, `json`, `markdown`, `toml` and `dockerfile` files. Configs, each with its `path` and a `fingerprint` (hash of its normalised content; identical copies share it): `ruff`, `mypy`, `pyright`, `flake8` (files, `pyproject.toml#tool.*`, `setup.cfg`), `eslint`, `biome`, `prettier`, `tsconfig`, `pre-commit` (its hook ids in `detail`), `shellcheck`, `yamllint`, `markdownlint`, `cdk-nag` (the source files that import it), `ci` (each `.github/workflows/` job that runs a checker, with the tools) and `tasks` (Taskfile, Makefile, justfile and `package.json` scripts that run a checker). `gaps` names each `<stack>:<check>` with no tool: a tool counts when the repo configures it or runs it from its own pre-commit hooks or task runner; a CI workflow alone does not, since a shared workflow can run a tool only when the repo configures it. `--summary` groups repos by stack (`stacks`), configs by fingerprint (`configs`, `variant_counts`), and lists `gaps`, `gaps_by_check` and `code_stack_gaps`; its text form is Markdown. Exit 1 when a repo could not be scanned. |
| `rebase <repo …\|--all>` | Fetch and rebase `main` on `origin/main`; stops and reports on a conflict or a dirty tree. |
| `create <name> --space S [--template T] [--tier product\|tooling] [--lifecycle L] [--dir D] [--dry-run]` | Validate the name, render the Copier template (without `--template`, the template that builds the type of the name: `templates.kinds[].types` in the config), create and push the GitHub repo, add the manifest entry (with its tier: `--tier`, else `tooling` for the control repo and `product` for any other), record the repo's stack in the matrix (see *The matrix*; a failure is `matrix_error`, exit 1), then do the repo's full beads setup (see `beads-setup`) and add the repo to the beads fleet list. Every repo also gets GitNexus: the files are written before the first commit, the GITNEXUS block comes with the AGENTS.md blocks, and `ops/indexing/gitnexus-reindex.sh` indexes it once after the push (a failure is `gitnexus_error`, exit 1). |
| `clone <repo>` | Clone an existing GitHub repo into the one folder its name gives it (app space, then the folder the config places its type in; see *Placement, membership and deprecation*). A repo already at that folder is reported, not re-cloned. It refuses, exiting 2, when the repo already exists at any other path or is on disk twice. Anything that needs a local checkout of a repo uses this command; no session or script picks a folder or runs `git clone` itself. |
| `rename <repo> [<new-name>] [--also R …] [--skip-repo R …] [--keep-src R …] [--dry-run] [--trailer TEXT] [--pr-footer TEXT]` | Rename with every name the repository carries. On GitHub and locally together, repoint `origin` (the manifest entry is keyed by GitHub's id, so it stays true), move the `repository` of the matrix's stacks to the new name, and replace the old path in the beads fleet list with the new one. Then bring the stack ids and stack file names and the Python names (distribution, import package and its `src/{project}/{domain}` folder, moved with `git mv`) to what the project's naming command gives (`name repository-names`), and rewrite every import, dependency line, handler string and written reference to an old name in every other repository (paths in the config's `rename.sweep_exclude` are records and are never edited). Each repository that changes gets one worktree on branch `rename/<slug>`, its own `lint`, `typecheck` and `test` tasks run (only `ruff check` for a repository that waits on a library's renamed package; a failure is written in the pull request and the report and the pull request still opens), one commit and one pull request opened with the command `$ATW_PR_COMMAND` names (`skillspoke-pr`); nothing is merged. Any `--skip-repo` repository, and the `src/` files of a `--keep-src` repository are reported, never edited. The tool never edits the vault: it reports every vault document that still carries an old name (searched in the folders the config's `rename.documents` points at) under `names.documents.carry_old_names`, for the `filing-clerk`, which changes and pushes them in the same job (see *Renames reach the vault*). The tool re-keys each renamed package in the matrix (`atw-matrix rename`) and commits the matrix; `sync-documents --paths` for the documents the filing-clerk changed is run afterwards, then `commit`. With no new name only the stack and Python names are brought into line; `--also` adds further repositories to the same run so each repository still gets one pull request. `--dry-run` prints the whole plan (`names` in the JSON) before anything changes. Refuses an invalid or taken name (the last token must be a stack type), or a `main` not known to be pushed. |
| `deprecate <repo> [--dry-run]` | Refuses, naming the stack ids, while the matrix has a stack that names the repo (move or remove each first, see *The matrix*). Then `rename` to the `deprecated-` name, which records `deprecated_on` and removes the repo from the beads fleet list, then close every open pull request in the repo with the comment "Closed: this repository is deprecated." (branches are kept), reporting each one, then delete the local clone and its linked worktrees, and report every vault document that still carries the old name under `documents.carry_old_names`, for the `filing-clerk` in the same job (see *Renames reach the vault*). The clone is deleted (`shutil.rmtree`, only on a path under the repository root whose name starts with `deprecated-`) only when it holds no work that exists only on this machine: no uncommitted changes or untracked files outside ignored paths in the clone or any linked worktree, no stash, and no local branch or worktree `HEAD` with commits on no remote branch. Otherwise the clone is left, the rest of the deprecation stands, the reasons and the exact path to delete by hand are reported, and the command exits 1. `--dry-run` lists the pull requests it would close and whether it would delete the clone. |
| `beads-setup [repo…] [--space S] [--all] [--check] [--dry-run] [--trailer TEXT]` | Give a repo its complete beads setup: its database on the shared server (created through `bd bootstrap`, never `bd init`: a fresh database is bootstrapped embedded, given the fleet prefix, pushed to `refs/dolt/data`, then cloned into the shared server), identity and prefix repaired with `bd doctor --fix` and `converge-repo.sh`, the `.beads` config files (`config.yaml`, `metadata.json`, `.gitignore`) and a `.gitignore` with the beads and standard ignores for the repo's template kind committed and pushed to `main`, and the repo added to the beads fleet list. `--all` sets up every non-deprecated, non-archived repo with a gap or no database (`planned` repos included; `--space S` narrows it to one app space); `--check` reports gaps (missing or uncommitted `.beads` config, missing fleet list entry, incomplete `.gitignore`) and changes nothing. `create` runs it. |
| `beads-fleet [--fix]` | Check the beads fleet list (`repos.additional` in the control repo's `.beads/config.yaml`, config `beads.fleet_config`): every listed path exists and is an active fleet repo, and every active repo with a `.beads` folder is listed. `--fix` corrects the list. |
| `deprecated-prs [--fix]` | Report every open pull request in a `deprecated-` repo of the owner on GitHub. `--fix` closes each with the deprecation comment, keeping its branch. |
| `archive-due [--dry-run]` | Archive on GitHub (`gh repo archive --yes`) every deprecated repo whose `deprecated_on` is at least `deprecation.archive_after_days` (config) days ago, set its manifest `lifecycle` to `archived` (the record is kept), remove it from the beads fleet list, and delete its local clone and linked worktrees when no work exists only there (the same test as `deprecate`); a clone with uncommitted or untracked files, a stash or unpushed commits on any branch is kept and reported (`archived-clone-kept`). A repo with an open pull request or a matrix stack in it is not archived and is reported (`archive-kept`); a repo with no valid `deprecated_on` is reported (`archive-undated`). An entry already archived only has its clone retried, so the command is idempotent. Commits the records. JSON: `repos` (one row per deprecated or archived entry: `status` `archived`, `planned`, `kept`, `failed`, `not-due`, `undated` or `missing`, `detail`, `deprecated_on`, `due_on`, `clone`), `findings`, `fixed`, `open`. Exit 1 while anything is kept, undated or failed. The launchd agent `com.skillspoke.polyrepo-archive-due` runs it from the installed plugin every day at 07:00 (the JSON report and errors under `$SKILLSPOKE_LOGS/polyrepo-archive-due/`), and `doctor --fix` runs it, so a missed day catches up. It never deletes a repository. |
| `agents-sync [--check\|--dry-run] [--repo R …] [--space S] [--trailer TEXT]` | Write the shared `AGENTS.md` blocks (the SkillSpoke shared block, the GitNexus block and the Agent Teams Workforce block, listed under `agents_sync.blocks` in the config; a block's `exclude_spaces` lists the app spaces that do not receive it, and none lists any; `--space S` and `--repo R` narrow a run) into every repo, whatever its recorded tier: `AGENTS.md` is tier 2 in every repository (see *Tiers*), so each repo is committed on `main` in its primary working tree and pushed, with no worktree, branch or pull request. Before writing, a repo's `main` is fetched and brought up to `origin/main` (fast-forward, or a rebase of local commits); a repo whose tree is dirty or whose rebase conflicts is reported (state `stale-main`) and left. A push the remote rejects (for example branch protection) leaves the commit local and is reported (status `committed`, with the rejection as `detail`). `{{repo}}` in a block source becomes the repo's name; the GitNexus block replaces the older `<!-- gitnexus:start -->` section; `--check` reports repos out of date. |
| `naming <name>` | Read-only check of one repository name against the vault's repository naming document. JSON: `valid`, `pattern`, `kind`, `section` and `rule` (the document's section and `**Pattern:**` line the name matched), `document`, `type`, `types`, `space` and `folder` (where the config's `placement` puts it, or `folder_note` when the config maps no folder to its type) and `problem` (why a refused name is refused). Exit 0 when the name matches a pattern, else 1. |
| `tier <path>` | Say which tier the repository containing a path is in. JSON: `path`, `repository`, `repository_path`, `tier` (`product` or `tooling`), `source` (`manifest` or `config`) and `linked_worktree` (true when the path is in a linked worktree of the clone). A path inside a clone, its `.worktrees/` included, belongs to that clone; a linked worktree elsewhere belongs to the clone git names as its common directory. Exit 0 when a repository that records a tier contains the path, else 1 (`repository` and `tier` are null; `repository_path` names the git clone that contains the path, when there is one). |
| `tiers` | List every recorded tier (the manifest's, for the repos on disk, and the config's `tiers.external`). Finding: `tier-external` (a configured path that is not the root of a git clone). |
| `set-tier <repo> product\|tooling` | Record the tier on the repo's manifest entry, log it and commit it; the export is rewritten with the commit. |
| `gitnexus-sync [--check\|--dry-run] [--repo R …] [--space S]` | Give every repo its GitNexus files: `.gitnexusrc`, the `.gitnexus` ignore rule and the six skills in `.claude/skills/gitnexus/`, copied from the control repo files the config's `gitnexus` section names; commits and pushes each; `--check` reports repos out of date. |
| `templates-check` | Which templates lag the repos built from them, and which repo kinds have no template. |
| `environment [repo…] [--space S] [--fix]` | Check every active Python repo (a `pyproject.toml` and an `install` task in its Taskfile): `.venv/bin/python` exists and runs, every declared dependency is installed and importable, and `aws_cdk` imports where the code uses it. `--fix` removes a `.venv` whose interpreter is missing, a dangling link or does not start, runs the repo's `task install --force` for each gap (so a Taskfile `status` check on the `.venv` folder cannot skip it) and checks again; for an infra repo it also runs `cdk synth --profile dev`. `create` runs the same setup and checks. |
| `python-names [repo…] [--space S]` | Check every active Python repo (a `pyproject.toml`; the control repo excluded) against the Python names the naming command gives it (`name repository-names`): its `pyproject.toml` name, import package and source folder, `src` present for a `lib` and a `service`, `tests` present, no `__init__.py` in a project or team folder. One finding per failure. |
| `hooks-sync [--check\|--dry-run] [--repo R …] [--space S] [--trailer TEXT]` | Merge the shared hook registrations into every repo's `.claude/settings.json`, whatever its recorded tier: `.claude/` is tier 2 in every repository, so each repo is committed on `main` in its primary working tree and pushed, with no worktree, branch or pull request. The block is the settings fragment the config's `hooks_sync.block_file` names (its `hooks` key); `hooks_sync.exclude` and `exclude_spaces` work as in `agents_sync`. A handler the block owns is identified by the script path after the environment variable in a block command (`"$VAR/ops/x.sh"` owns `ops/x.sh`): every handler in the repo that names that path, through any variable, is replaced, and every other key, event, matcher group and handler the repo has is kept; the block's handlers go into the repo's group with the same matcher, or a new group. A missing file is created; a file that is not valid JSON is reported (state `invalid`) and left. A repo whose `.claude/settings.json` has uncommitted changes, that is not on `main`, or whose `main` cannot be brought up to `origin/main` is skipped and reported. A rejected push leaves the commit local (status `committed`, the rejection as `detail`). `create` merges the block into the new repo before its first commit. A project whose config has no `hooks_sync` section gets no hooks from `create` and an error from `hooks-sync`. |
| `checks-sync [--check\|--dry-run] [--repo R …] [--space S] [--trailer TEXT]` | Give every repo the canonical code checks of the stacks it holds, whatever its recorded tier: everything written is configuration and hooks (tier 2), so each repo is committed on `main` in its primary working tree and pushed. The spec is the file the config's `checks_sync.spec_file` names (the tool pins, the common pre-commit fragment and per stack the canonical files, the pre-commit fragment and the configurations they replace); `checks_sync.exclude` and `exclude_spaces` work as in `agents_sync`. The stacks come from the `tech-stacks` scan, read live; a code stack the spec does not list is reported as `unchecked`. Per repo it writes `.code-checks/` (the runner `run.py` and `cdk_nag_synth.py` from the plugin's `code_checks/`, and `checks.json`: stacks, pins, the tracked `cdk.json` files) and removes anything else there; copies each stack's canonical files; assembles `.pre-commit-config.yaml` from the common fragment, the repository's own entries and hooks that the canonical hooks do not own or replace (the spec's `supersedes`; an `exclude` on a common hook is kept), and one local entry of the stacks' hooks (a hook under `hook_files` gets a `files` pattern built from each app's folder, and is dropped when the repo has no `cdk.json`); removes what the canonical files replace (`pyproject.toml` tables, `setup.cfg` sections and files, nested ones included); points the `Taskfile.yml` `lint` task at the runner; and lists the TypeScript base first in a plain-JSON root `tsconfig.json`'s `extends`. States: `current`, `missing` (never synced), `outdated`, `unconsumed` (files current, but a tsconfig or ESLint config does not use or weakens the base, `package.json` lacks a Node package the base needs, a nested copy of a canonical file overrides it, or the commit hook is not installed), `invalid`. After the commit the hook is installed: `pre-commit install` when `core.hooksPath` is unset; otherwise a marked section that runs `pre-commit run` is added to that folder's `pre-commit` hook, committed when the folder is in the tree. A repo with uncommitted changes in a planned path, not on `main`, or whose `main` cannot be brought up to `origin/main` is skipped and reported; a rejected push leaves the commit local (status `committed`). `create` writes the checks after `git init`, before the first commit, and installs the hook. The edit hook (registered by `hooks-sync`) and the commit hook both run `.code-checks/run.py`. |
| `doctor [--fix]` | Every health check as one findings list: `reconcile`, `agents-sync --check`, `hooks-sync --check`, `checks-sync --check`, `tiers`, the beads fleet audit, `beads-setup --check`, `beads-fleet`, `environment`, `python-names`, `deprecated-prs`, `archive-due --dry-run`, the governance entries, the knowledge-store pointers, that the vault's repository naming document is readable and states every rule the tool needs, and the matrix's stacks against the repositories (`matrix`). `--fix` first runs `reconcile --fix`, `agents-sync`, `hooks-sync`, `checks-sync`, `beads-setup --all`, `beads-fleet --fix`, `deprecated-prs --fix` and `archive-due`, then repairs the matrix's stacks and commits the matrix. The launchd agent `com.skillspoke.polyrepo-daily` runs `doctor --fix` every day, logging under `$SKILLSPOKE_LOGS/polyrepo/`. |
| `commit --message TEXT` | Commit and push the steward's files after a hand edit. |

A record carries `name`, `space`, `path`, `lifecycle`, `tier`, `present` (disk, github,
manifest), `branch`, `uncommitted`, `uncommitted_files`, `last_commit`, `main`,
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
include `untracked-repo`, `orphan-entry`, `duplicate-entry`, `entry-unkeyed` (an entry that records
a name where GitHub has the repository: the fix records GitHub's id), `local-path`, `lifecycle`,
`name-mismatch`, `origin-stale`, `no-origin`, `unpushed`, `local-only`, `group-member-unknown`,
`group-member-inactive`, `repo-dependency-stored`, `retired-section`, `tier-missing`, and `open-items`
once every item in the section is settled. The rest are left open for the steward's
judgment, and each has an obvious next step:

| Finding | Settle it by |
|---|---|
| `deprecated-undated` | Find the date the repo was deprecated (`git log` of the manifest and of the registries it replaced) and write it as `deprecated_on` in the manifest, then `commit`. Never record today's date as a stand-in: it restarts the clock to archiving. |
| `deprecation-not-renamed` | `deprecate <repo>` if it is deprecated; otherwise set its `lifecycle` to `active` in the manifest. |
| `tier-invalid` | The entry's `tier` is neither `product` nor `tooling`: decide it (see *Tiers*) and `set-tier <repo> <tier>`. |
| `open-items` with unsettled items | Put each to the user in the reply, record the answer where it belongs, then remove the section. |
| `diverged`, `fetch-failed`, `no-default-branch`, `foreign-origin`, `github-missing`, `not-cloned`, `duplicate-name` | Inspect with `git` and `gh`, repair, and run `reconcile --fix` again. `not-cloned` is raised only for an active repo; a deprecated or archived repo is expected to have no local clone. |

## Operations (CUDLS)

- **create** — `create`. The name must match a naming pattern for its space (below). Pick the template whose kind matches the repo (`templates-check` lists
  the kinds).
  Every new repository is created private and with `allow_auto_merge=true` (the tool sets
  both); the owner is the only human, so every fleet repo allows auto-merge.
  A new repository gets its tier when it is created (see *Tiers*): `product` unless `--tier tooling`
  says otherwise (the control repo is `tooling` by default). A repository that is not plainly
  product or tooling is a question for the user, answered before `create`.
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
- **update** — Mechanical fields (`id`, `lifecycle`, archived state) are kept true
  by `reconcile --fix`; do not edit them. Groups: edit the manifest (below). What a
  repo holds and its purpose are the matrix's: a stack's `repository`, `app` and `executionUse`
  are `put stack` (see *The matrix*); its purpose is not written here.
- **rename** — `rename <repo> <new-name>`, on GitHub and locally together. The repo's entry in the beads repository list is replaced with the new path; its beads database keeps its name. The matrix's stacks that name the repo name the new one (`move-repository`). A rename covers the repository, the stack names, the Python names, every reference to them in the other repositories, the matrix, and the vault's architecture documents, which the `filing-clerk` changes and pushes in the same job (see *Renames reach the vault*).

  The Python names follow the vault's resource naming standard, section "Python names" (`resource-naming-standard.md`), which the steward does not copy. Every name comes from the project's naming command (the `resource-naming` skill): `name repository-names <repo>` gives the stack, stack file, source package, import package and distribution; never compose one by hand and never second-guess what it gives. One worktree and one pull request per repository changed. Run `--dry-run` first: the plan lists all of it before anything changes. A repository that the approved architecture says is to be merged or retired is not renamed. The new name must end in a repository type the naming document lists; `SkillSpoke-auth-utils` is refused.
- **delete / deprecate** — `deprecate <repo>`. A repository is never deleted: "delete" means deprecate, and a deprecated repository is archived automatically (see *Placement, membership and deprecation*). The steward never deletes a repository from GitHub and never proposes deleting one; only if the owner deletes one of their own accord does `reconcile --fix` remove its record. A deprecated entry (`deprecated_on`) is kept, and after archiving it stays with lifecycle `archived`; `list`, `search` and `inventory` leave both out unless `--include-inactive` or a `--lifecycle` filter asks for them. Its entry is removed from the beads repository list. The matrix must hold no stack that names it: `deprecate` refuses until each is moved or removed (see *The matrix*).
  The new name is the deprecated name the naming document gives the repository (`naming <name>`
  shows the rule).
  The rename happens on GitHub and locally together. Every open pull request in the repo is
  then closed with the comment "Closed: this repository is deprecated."; a deprecated repo
  never has an open pull request, and `doctor` reports any that does. Last, the local clone
  is deleted, unless it holds work that exists only on this machine (see the command
  table); a deprecated repo normally has no local clone. `reconcile`, `list` and `doctor`
  treat a deprecated or archived repo with no local clone as normal, never as a finding;
  `clone <repo>` brings one back when it is needed.
  `deprecate` records `deprecated_on` (the rename's date). `archive-due`, run daily by
  `com.skillspoke.polyrepo-archive-due` and by `doctor --fix`, archives the repo on GitHub
  `deprecation.archive_after_days` (config) days after `deprecated_on` (see the command table).
  Deprecated and archived are separate lifecycle states.
- **beads fleet list** — `repos.additional` in the control repo's `.beads/config.yaml` is
  what `com.skillspoke.beads-fleet-watch` watches; a stale path silently stops that repo's
  beads syncing. `create`, `rename`, `deprecate` and `archive-due` keep it true
  deterministically (add, replace, remove), re-reading the file immediately before each
  write and touching only the one entry. `beads-setup` over several repos writes the list once at the end of the run, so the watcher restarts once. Never edit it by hand for a repository change;
  `beads-fleet --fix` repairs drift.
- **list** — `list` or `inventory`: "how many repos", "which repos are deprecated".
- **search** — `search` for record attributes; `grep` for text, for the steward's own upkeep.
  Where functionality lives, and which repos hold a resource type ("which repos contain a
  DynamoDB table"), is the matrix: `atw-matrix find --kinds stack --text "<words>"`,
  `atw-matrix stacks --resource-type <type>`, then `node stack:<id>` for the repository.
  For a fact the manifest and the matrix do not hold, hand off to **polyrepo-info**.

## Tiers

Tier is decided by content, not by repository. The definition of tier 1 and tier 2 is the control repository's root `AGENTS.md`, section "Code quality", and what each tier does with a change is `.claude/rules/git-conventions.md` there; the steward keeps no copy of either.

Every manifest entry records in `tier` which kind of repository it is, that is, whether it holds product code:

| `tier` | Which repositories | What it means |
|---|---|---|
| `product` | the SkillSpoke services, libraries, infrastructure, web and mobile repositories (the shared, employer and marketing repositories included) | the repository holds product code: its product files are tier 1 (worktrees, pull request); its `AGENTS.md`, `CLAUDE.md` and `.claude/` are tier 2 |
| `tooling` | the machinery that builds SkillSpoke: the control repo `SkillSpoke`, the toolset repo and the `skillspoke-docs` vault | the repository holds no product code: all of it is tier 2 (committed on `main` in the primary working tree and pushed) |

The manifest holds the tier of every repository it has an entry for. The toolset repo and the vault are
outside the repository root and have no entry: the config's `tiers.external` lists each with its `name`,
its `path` (built from environment variables, `${SKILLSPOKE_ATW_PLUGIN_SOURCE}/../..` and
`${SKILLSPOKE_ROOT}/skillspoke-docs`) and its `tier`. `tier <path>` answers from these records. The
main-worktree guard hook of the plugin reads no record: the folder layout decides it. It blocks an edit to a
product file in the primary working tree of any git repository under `$SKILLSPOKE_APPS` except the
command-and-control repository at `$SKILLSPOKE_CC` (an `AGENTS.md` or `CLAUDE.md` at any depth, and anything
under the repository's `.claude/`, are tier 2 and are allowed).

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
| `create` | Records the stack the new repository holds when the naming command reads its name as a repository that holds a stack (`name check-repository`) and no stack already names it as its repository: the stack takes the repository's name, its app is the repository's space, its execution use is `imported` for a `lib` and `executable` otherwise, and the purpose is not stated. A stack the matrix already holds under that id gets its `repository`. |
| `rename` | `move-repository --from <old> --to <new>`: every stack's `repository` changes, and no id does. |
| `deprecate`, and `archive-due` | Refuse (`archive-due` keeps the repo deprecated and reports it), naming the stack ids, while any stack names the repository. Move each stack (`put stack --id stack:<name> --repository <other repo>`) or remove it (`remove stack:<name> --held`), run `commit`, then try again. |
| `doctor` | Reports an active code repository that no stack names, a stack whose repository is deprecated or archived, or exists nowhere, and an invalid matrix (`check`). `--fix` records the missing stack, removes a hint stack that holds nothing or else unsets the repository, and commits. A stack whose repository exists nowhere may belong to a repository elaboration has yet to create, so it is reported and left. |

A repository's lifecycle is not in the matrix: the tool reads it live. The matrix schema has
no field for a repository's role, and the steward writes none. After any write of your own, run
`commit`, then `check`; it must report `"valid": true`.

The matrix's code mark `verified` is set by the build driver and by no agent; its meaning is in the matrix design (`blueprint/design/matrix.md`). A stack or entry that is not verified is used like any other, and a difference between existing code and arc42 is never a discrepancy and never a finding.

## Naming rules

The rules are the vault's repository naming document,
`docs/tech/architecture/arc42/08-crosscutting-concepts/repository-naming.md` (vault root
`$SKILLSPOKE_ROOT/skillspoke-docs`); resource names follow `resource-naming-standard.md` beside
it. The steward has no naming rules of its own and keeps no copy of them (the owner's storage
rule is in the steward's instructions, *What you store*). The config's `naming.document` names
the document under `naming.document_root`, and the tool reads the rules from the document's own text
each time it runs: the project prefixes (the table), the repository types (the sentence "`{type}`
is one of ..."), the name patterns (the `**Pattern:**` line of each repositories section) and the
deprecated prefix. A name is checked against them only when it is new: when a repository is
created or renamed. No other command checks or reports the name of an existing repository;
cloning and deprecating use the rules only to place a repository and to give its deprecated name. A new name must
match a pattern, and an application name must end in a repository type the document lists
(`SkillSpoke-auth-utils` is refused); the command-and-control repository `SkillSpoke` is exempt.
A project is an open token: the document's project table lists today's projects and is not a limit. A
name whose first token is no listed project, no deprecated prefix and no non-application type is
checked by its shape, `{project}[-team]-{domain}-{type}` with `{type}` one of the document's types
(`devsecops-resourceNaming-lib` passes), and its project's repositories sit directly in
`$SKILLSPOKE_APPS/<project>`. `naming <name>` checks one name read-only and shows the document, the section and the pattern line
of the rule it matched. If the document does not state a rule the tool needs, the tool says so and
stops; hand that gap, and any change to the rules, to the `filing-clerk`, never into the config.

## Placement, membership and deprecation

These are the steward's own procedure; the project's values for them are in
`.polyrepo/config.yaml`.

**Placement.** Every clone sits under the repository root (the folder `root_env` names). Its app
space is the folder named by the first token of the repository's name; a deprecated repository
keeps the space of the name it had (the first token after the deprecated prefix). The config's
`placement.spaces` maps a first token to a folder of another name, compared without case. A space
listed under `placement.by_type` holds its repositories one folder deeper, in the folder mapped to
the repository's type (the last token of its name); every other space holds them directly. A new
name whose type has no mapped folder in such a space is refused until the config maps one; a clone
of an existing repository of such a type sits directly in the space. A new project is a new
first token: `create` places its first repository in a new folder of that name.

**Which repositories belong to the project.** A repository belongs to the project when the
manifest records it or its clone is under the repository root. The tool knows the project's
GitHub repositories from its records, not from a list of name prefixes: a repository on the
owner's GitHub account that no entry records and no clone holds is not the project's, and the
tool ignores it. `create` records a new repository; `reconcile --fix` records a clone under the
root that has no entry (`untracked-repo`). Each entry records GitHub's id of the repository, so
a rename on GitHub keeps the record; the name is read live.

**Deprecation.** A repository is retired by deprecating it, then archiving it, never by deleting
it. `deprecate` renames it to its deprecated name on GitHub and locally together, closes its open
pull requests with the comment "Closed: this repository is deprecated.", deletes its local clone
when no work exists only there, and records the date as `deprecated_on`. `archive-due` archives it
on GitHub `deprecation.archive_after_days` (config) days after that date and keeps the record with
lifecycle `archived`. Deprecated and archived are separate states. The steward never deletes a
repository on GitHub; when the owner deletes one, `reconcile --fix` removes its record entirely
(`orphan-entry`).

## Renames reach the vault

`rename` and `deprecate` list every vault document that still carries an old name
(`names.documents.carry_old_names` for `rename`, `documents.carry_old_names` for `deprecate`, and
`vault document for the filing-clerk` step lines). In the same job, right after the command,
the steward hands those documents, with each old name and its new name, to the `filing-clerk`,
which changes the names, commits and pushes the vault. The job is not finished, and is not
reported done, until the filing-clerk has updated and pushed every listed document; then the
steward runs `atw-matrix sync-documents --paths` on them and `commit`.

## Editing the manifest by judgment

For the fields the tool does not write (groups; a tier is written with `set-tier`): the manifest keeps no `purpose`,
`owns`, `role`, `owner`, `language` or `notes` on an entry, and no `conventions`, `ownership` or `relationships` section; its next write by
the tool drops the entry fields, and `reconcile` reports a retired section (`retired-section`). A group that a repository's type or its imports would give
is not stored. There is no
dependency field. A dependency is between services, components and infrastructure, never
between repos.

1. Edit `$SKILLSPOKE_CC/.polyrepo/manifest.yaml` preserving its comments — with an editor
   tool for a small change, or `uv run --with ruamel.yaml python3 …` (round-trip mode) for a
   programmatic one. The schema is `references/manifest-schema.md`; it also says what may
   and may not be stored.
2. Run `reconcile --json` and confirm it reports no new finding.
3. Run `commit --message "<what changed>"`; the message is the record of the change
   (`references/learning-protocol.md`).

Never add `local_path`, deploy waves, or any fact whose canonical home is another document.
Deployment order lives in `$SKILLSPOKE_CC/deployment/waves*.yaml`, not the manifest.

## Boundaries

You own the repos and their records. Facts outside the manifest, the matrix and the knowledge store are
**polyrepo-info**; the registry of the project's own scripts and procedures is
**polyrepo-governance**; first-time bootstrap is **polyrepo-setup**.
