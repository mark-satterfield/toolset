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

| Command | What it does |
|---|---|
| `reconcile [--fix] [--dry-run] [--no-fetch]` | Compare disk, GitHub and the manifest. `--fix` repairs every mechanical finding (manifest, push, GitHub rename, archive) and appends the changelog. |
| `status [repo\|path …] [--no-fetch]` | Live state per repo: branch, `uncommitted`, `last_commit`, `main.ahead/behind/up_to_date`, GitHub `pushed_at`, `archived`. |
| `list [--group G] [--lifecycle L] [--space S]` | Repos, filtered. |
| `search attr=value [attr~regex …] [--fetch]` | Repos by any record attribute, dotted keys (`github.archived=false`, `main.behind=0`, `space=shared`). |
| `inventory [--all] [--no-fetch]` | Every repo's full record; `--all` adds GitHub-only repos. |
| `purpose <repo> [--text T]` | Record (`--text`) or confirm the repo's purpose at its current `main`; clears `purpose-recheck`. |
| `grep <pattern> [--space S] [--repo R …] [-i] [-l] [-F] [-w] [--glob G …]` | `rg` across every in-scope repo on disk. |
| `rebase <repo …\|--all>` | Fetch and rebase `main` on `origin/main`; stops and reports on a conflict or a dirty tree. |
| `create <name> --space S --template T --purpose TEXT [--lifecycle L] [--dir D] [--dry-run]` | Validate the name, render the Copier template, create and push the GitHub repo, add the manifest entry. |
| `deprecate <repo> [--dry-run]` | Rename to the `deprecated-` name on GitHub and locally, repoint `origin`, record `deprecated_on`. |
| `agents-sync [--check\|--dry-run] [--repo R …]` | Write the shared `AGENTS.md` block into every repo, committing and pushing each; `--check` reports repos out of date. |
| `templates-check` | Which templates lag the repos built from them, and which repo kinds have no template. |
| `doctor` | Runs `reconcile`, `agents-sync --check` and `templates-check` in parallel and checks every `governance` location; one findings list. The launchd agent `com.skillspoke.polyrepo-daily` runs `reconcile --fix` then `doctor` every day, logging under `$SKILLSPOKE_LOGS/polyrepo/`. |

A record carries `name`, `space`, `path`, `lifecycle`, `role`, `present` (disk, github,
manifest), `naming`, `branch`, `uncommitted`, `last_commit`, `main`, `origin_url`, `github`,
`purpose`, `purpose_head`, `purpose_stale`, `owns`, `groups`, `dependencies`
(`depends_on`, `depended_on_by`).

### Reconcile findings

Each finding carries `mechanical` (true when `--fix` repairs it, with the repair in
`fix`), `status` (`open`, `fixed`, `failed`, `planned`) and `error`. Mechanical kinds
include `untracked-repo`, `untracked-github`, `orphan-entry`, `renamed`, `remote-url`,
`local-path`, `lifecycle`, `name-mismatch`, `origin-stale`, `no-origin`, `unpushed`,
`local-only`, `deprecated-undated` and `archive-due`. The rest are left open for the
steward's judgment, and each has an obvious next step:

| Finding | Settle it by |
|---|---|
| `purpose-missing`, `purpose-recheck` | Read the repo, then `purpose <repo> --text "<one line>"` (or `purpose <repo>` to confirm the current one). |
| `deprecation-not-renamed` | `deprecate <repo>` if it is deprecated; otherwise set its `lifecycle` to `active` in the manifest. |
| `naming-violation`, `space-mismatch` | Choose the correct name or space from the naming patterns; rename on GitHub and locally together (`gh repo rename`, move the folder, repoint `origin`), then `reconcile --fix`. |
| `diverged`, `fetch-failed`, `no-default-branch`, `foreign-origin`, `github-missing`, `github-only`, `not-cloned`, `duplicate-name` | Inspect with `git` and `gh`, repair, and run `reconcile --fix` again. |

## Operations (CUDLS)

- **create** — `create`. The name must match a naming pattern for its space (below). The
  caller supplies the purpose; if none is given, write one line from what the caller said
  the repo is for. Pick the template whose kind matches the repo (`templates-check` lists
  the kinds).
- **update** — Mechanical fields (`remote_url`, `lifecycle`, archived state) are kept true
  by `reconcile --fix`; do not edit them. Purpose: `purpose <repo> --text`. Groups, `owns`,
  dependencies, `role`, `owner`: edit the manifest (below).
- **delete / deprecate** — `deprecate <repo>`. A repository is never deleted. The new name
  is `deprecated-` plus the old name, with a leading `SkillSpoke-` lowercased to
  `skillspoke-` (`SkillSpoke-example` → `deprecated-skillspoke-example`). The rename
  happens on GitHub and locally together, and the folder stays in its app space.
  `reconcile --fix` archives the repo on GitHub `deprecation.archive_after_days` (60) after
  `deprecated_on`. Deprecated and archived are separate lifecycle states.
- **list** — `list` or `inventory`: "how many repos", "which repos are deprecated".
- **search** — `search` for record attributes; `grep` for content. For facts neither holds
  (which repos contain a DynamoDB table), hand off to **polyrepo-info**.

## Naming patterns

The config's `naming.patterns` are the rule; in summary: `SkillSpoke` and
`SkillSpoke-{name}` are the personal-agent app; `shared-{name}` is shared or sharable across
the whole company; `marketing-{name}` is marketing; `employer-{name}` is the employer app;
`{internal|tool}-skillspoke-{name}` is non-application (GitHub only); `deprecated-{name}` as
above. Each app space is a subfolder of the repository root.

## Editing the manifest by judgment

For the fields the tool does not write (groups, `owns`, dependencies, `role`, `owner`):

1. Edit `$SKILLSPOKE_CC/.polyrepo/manifest.yaml` preserving its comments — with an editor
   tool for a small change, or `uv run --with ruamel.yaml python3 …` (round-trip mode) for a
   programmatic one. The schema is `references/manifest-schema.md`; it also says what may
   and may not be stored.
2. Append a changelog entry (`references/learning-protocol.md`).
3. Run `reconcile --json` and confirm it reports no new finding.
4. Commit only `.polyrepo/manifest.yaml` and `.polyrepo/changelog.md` on `main` in
   `$SKILLSPOKE_CC` after `git pull --rebase --autostash`, and push.

Never add `local_path`, deploy waves, or any fact whose canonical home is another document.
Deployment order lives in `$SKILLSPOKE_CC/deployment/waves*.yaml`, not the manifest.

## Boundaries

You own the repos and their records. Facts outside the manifest and the knowledge store are
**polyrepo-info**; the registry of the project's own scripts and procedures is
**polyrepo-governance**; first-time bootstrap is **polyrepo-setup**.
