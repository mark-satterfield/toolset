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
| `status [repo\|path …] [--no-fetch]` | Live state per repo: branch, `uncommitted` and `uncommitted_files`, `last_commit`, `main.ahead/behind/up_to_date`, GitHub `pushed_at`, `archived`, and dependencies (as recorded, never checked against code). |
| `list [--group G] [--lifecycle L] [--space S]` | Repos, filtered. |
| `search attr=value [attr~regex …] [--fetch]` | Repos by any record attribute, dotted keys (`github.archived=false`, `main.behind=0`, `space=shared`). |
| `inventory [--all] [--no-fetch]` | Every repo's full record; `--all` adds every repo the manifest or GitHub has that is not on disk. |
| `purpose <repo> [--text T]` | Record (`--text`) or confirm the repo's purpose at its current `main`; clears `purpose-recheck`. |
| `grep <pattern> [--space S] [--repo R …] [-i] [-l] [-F] [-w] [--glob G …]` | `rg` across every in-scope repo on disk. |
| `rebase <repo …\|--all>` | Fetch and rebase `main` on `origin/main`; stops and reports on a conflict or a dirty tree. |
| `create <name> --space S --template T --purpose TEXT [--lifecycle L] [--dir D] [--dry-run]` | Validate the name, render the Copier template, create and push the GitHub repo, add the manifest entry, and add the repo to the beads fleet list when it has a `.beads` folder. |
| `clone <repo>` | Clone an existing GitHub repo into the one folder its name gives it (app space, then the template placement folder for its kind). A repo already at that folder is reported, not re-cloned. It refuses, exiting 2, when the repo already exists at any other path or is on disk twice. Anything that needs a local checkout of a repo uses this command; no session or script picks a folder or runs `git clone` itself. |
| `rename <repo> <new-name> [--dry-run]` | Rename on GitHub and locally together, repoint `origin`, rename the manifest entry, and replace the old path in the beads fleet list with the new one. Refuses an invalid or taken name, or a `main` not known to be pushed. |
| `deprecate <repo> [--dry-run]` | `rename` to the `deprecated-` name, which records `deprecated_on` and removes the repo from the beads fleet list, then close every open pull request in the repo with the comment "Closed: this repository is deprecated." (branches are kept), reporting each one, then delete the local clone and its linked worktrees. The clone is deleted (`shutil.rmtree`, only on a path under the repository root whose name starts with `deprecated-`) only when it holds no work that exists only on this machine: no uncommitted changes or untracked files outside ignored paths in the clone or any linked worktree, no stash, and no local branch or worktree `HEAD` with commits on no remote branch. Otherwise the clone is left, the rest of the deprecation stands, the reasons and the exact path to delete by hand are reported, and the command exits 1. `--dry-run` lists the pull requests it would close and whether it would delete the clone. |
| `beads-fleet [--fix]` | Check the beads fleet list (`repos.additional` in the control repo's `.beads/config.yaml`, config `beads.fleet_config`): every listed path exists and is an active fleet repo, and every active repo with a `.beads` folder is listed. `--fix` corrects the list. |
| `deprecated-prs [--fix]` | Report every open pull request in a `deprecated-` repo of the owner on GitHub. `--fix` closes each with the deprecation comment, keeping its branch. |
| `agents-sync [--check\|--dry-run] [--repo R …]` | Write the shared `AGENTS.md` blocks (the SkillSpoke shared block and the Agent Teams Workforce block, listed under `agents_sync.blocks` in the config) into every repo, committing and pushing each; `--check` reports repos out of date. |
| `templates-check` | Which templates lag the repos built from them, and which repo kinds have no template. |
| `doctor [--fix]` | Every health check as one findings list: `reconcile`, `agents-sync --check`, the beads fleet audit, `beads-fleet`, `deprecated-prs`, the governance entries, the knowledge-store pointers, and the repository-naming document against the naming patterns. `--fix` first runs `reconcile --fix`, `agents-sync`, `beads-fleet --fix` and `deprecated-prs --fix`. The launchd agent `com.skillspoke.polyrepo-daily` runs `doctor --fix` every day, logging under `$SKILLSPOKE_LOGS/polyrepo/`. |
| `commit --message TEXT` | Commit and push the steward's files after a hand edit. |

A record carries `name`, `space`, `path`, `lifecycle`, `role`, `present` (disk, github,
manifest), `naming`, `branch`, `uncommitted`, `uncommitted_files`, `last_commit`, `main`,
`origin_url`, `github`, `purpose`, `purpose_head`, `purpose_stale`, `owns` (`item`,
`confirmed`), `groups` (only for a repo that exists and is active), `dependencies`
(`depends_on`, `depended_on_by`, each `repo`, `kind`). `owns[].confirmed` is read live from
the owning repo's tracked files; it is null when that repo is not on disk. Dependencies are
never derived from repository code and carry no `confirmed`: they come from the effective
arc42 architecture in the `skillspoke-docs` vault (`docs/tech/architecture/arc42/`), or are
recorded as none.

### Reconcile findings

Each finding carries `mechanical` (true when `--fix` repairs it, with the repair in
`fix`), `status` (`open`, `fixed`, `failed`, `planned`) and `error`. Mechanical kinds
include `untracked-repo`, `untracked-github`, `orphan-entry`, `renamed`, `remote-url`,
`local-path`, `lifecycle`, `name-mismatch`, `origin-stale`, `no-origin`, `unpushed`,
`local-only`, `deprecated-undated`, `archive-due`, `group-member-unknown`,
`group-member-inactive`, `group-member-renamed`, `dependency-endpoint`, and `open-items`
once every item in the section is settled. The rest are left open for the steward's
judgment, and each has an obvious next step:

| Finding | Settle it by |
|---|---|
| `purpose-missing`, `purpose-recheck` | Read the repo, then `purpose <repo> --text "<one line>"` (or `purpose <repo>` to confirm the current one). |
| `deprecation-not-renamed` | `deprecate <repo>` if it is deprecated; otherwise set its `lifecycle` to `active` in the manifest. |
| `naming-violation`, `space-mismatch` | Choose the correct name or space from the naming patterns, then `rename <repo> <new-name>`. |
| `owns-unconfirmed` | Read the owning repo's code; correct the `owns` item or remove it. |
| `open-items` with unsettled items | Put each to the user in the reply, record the answer where it belongs, then remove the section. |
| `diverged`, `fetch-failed`, `no-default-branch`, `foreign-origin`, `github-missing`, `github-only`, `not-cloned`, `duplicate-name` | Inspect with `git` and `gh`, repair, and run `reconcile --fix` again. `not-cloned` is raised only for an active repo; a deprecated or archived repo is expected to have no local clone. |

## Operations (CUDLS)

- **create** — `create`. The name must match a naming pattern for its space (below). The
  caller supplies the purpose; if none is given, write one line from what the caller said
  the repo is for. Pick the template whose kind matches the repo (`templates-check` lists
  the kinds).
  Every new repository is created private and with `allow_auto_merge=true` (the tool sets
  both); the owner is the only human, so every fleet repo allows auto-merge.
- **update** — Mechanical fields (`remote_url`, `lifecycle`, archived state) are kept true
  by `reconcile --fix`; do not edit them. Purpose: `purpose <repo> --text`. Groups, `owns`,
  dependencies, `role`, `owner`: edit the manifest (below).
- **rename** — `rename <repo> <new-name>`, on GitHub and locally together.
- **delete / deprecate** — `deprecate <repo>`. A repository is never deleted from GitHub.
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
  write and touching only the one entry. Never edit it by hand for a repository change;
  `beads-fleet --fix` repairs drift.
- **list** — `list` or `inventory`: "how many repos", "which repos are deprecated".
- **search** — `search` for record attributes; `grep` for content. For facts neither holds
  (which repos contain a DynamoDB table), hand off to **polyrepo-info**.

## Naming patterns

The config's `naming.patterns` are the rule; in summary: `SkillSpoke` and
`SkillSpoke-{name}` are the personal-agent app; `shared-{name}` is shared or sharable across
the whole company; `marketing-{name}` is marketing; `employer-{name}` is the employer app;
`{internal|tool}-skillspoke-{name}` is non-application (GitHub only); `deprecated-{name}` as
above. Each app space is a subfolder of the repository root. The canonical statement is the
vault's `repository-naming.md` (the config's `naming.document`); `doctor` checks that its
sections, examples, deprecation examples and archive delay agree with the patterns.

## Editing the manifest by judgment

For the fields the tool does not write (groups, `owns`, dependencies, `role`, `owner`):
a dependency edge is recorded only from the effective arc42 architecture in the
`skillspoke-docs` vault, never from repository code; with no architecture source, record
none.

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

You own the repos and their records. Facts outside the manifest and the knowledge store are
**polyrepo-info**; the registry of the project's own scripts and procedures is
**polyrepo-governance**; first-time bootstrap is **polyrepo-setup**.
