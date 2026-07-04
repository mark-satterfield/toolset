---
name: version
description: >
  Bump plugin versions in this repo's .claude-plugin/marketplace.json after making changes. Detects which plugins changed, picks the semver bump (major/minor/patch) from commit history, updates the manifest, and commits — but does not push. Use when the user wants to bump versions, update versions, version-bump, or bump changed plugins after making changes — even just "version" or "bump".
---

# Plugin Version Bumper

Bump plugin versions in this repo's `.claude-plugin/marketplace.json` based on what changed and why.

This skill is scoped to the `mark-satterfield/toolset` repo. The manifest carries one `version` field per plugin under `plugins/` — there is no registry-level version. Bump a plugin's version based on commits to its source directory.

## Versioning Rules

| Bump | When | Example |
| --- | --- | --- |
| `patch` | Bug fixes, typo corrections, small adjustments | `1.0.0 → 1.0.1` |
| `minor` | New skills, new features, non-breaking enhancements | `1.0.1 → 1.1.0` |
| `major` | Breaking changes — renamed skills, removed features, restructured plugin | `1.1.0 → 2.0.0` |

When in doubt, lean toward `patch`. The user can always override.

## Workflow

### 0. Staging

Every time this skill runs, check for changes that are unstaged and not ignored by `.gitignore`. Always tell the user about any such files — without exception.

If there are any, ask the human what they want done with them:

A. Staged for commit
B. Added to `.gitignore`
C. Left alone for now

Then follow their direction.

### 1. Detect Changes

Read `.claude-plugin/marketplace.json` to get the plugin list and current versions. Then determine which plugins have changes not yet reflected in their version.

Find the last commit that touched the manifest's version fields:

```bash
git log --oneline -1 -- .claude-plugin/marketplace.json
```

For each plugin, check for commits to its source directory since that version commit:

```bash
git log --oneline <last-version-commit>..HEAD -- plugins/<name>
```

Also check for uncommitted changes with `git diff --stat` and `git diff --cached --stat`, mapping changed files to plugins by path.

If the user specifies which plugins to bump, skip detection and focus on those.

### 2. Analyze Commit Types

For each changed plugin, read the commit messages to determine the bump level:

- Commits starting with `fix`, `style`, `docs`, `chore`, `perf` → **patch**
- Commits starting with `feat` → **minor**
- Commits containing `BREAKING CHANGE` or `!:` → **major**

The highest-level change wins. A plugin with both `fix` and `feat` commits gets a `minor` bump.

If the user specifies a bump level (e.g., "minor bump the git plugin"), use that instead.

### 3. Present the Plan

Show the user what you intend to do before making any changes:

```text
Plugin version bumps:

  git:         1.0.1 → 1.0.2 (patch)
    - fix(git): correct skill directory and name field namespacing

  plugin-name:  1.0.0 → 1.1.0 (minor)
    - feat(plugin-name): add R2 upload retry logic
    - fix(plugin-name): handle missing Chrome binary
```

Include the relevant commits so the user can verify the bump level makes sense.

**Wait for the user to confirm before proceeding.** They may want to adjust bump levels or skip certain plugins.

### 4. Apply the Bumps

Update the version in **both** locations for each bumped plugin:

1. `.claude-plugin/marketplace.json` — the registry-level manifest
2. `plugins/<name>/.claude-plugin/plugin.json` — the plugin's own manifest

Both files use 2-space indentation. Read each file, update its `version` field, and write it back. These two files must always agree — that's the whole point of this step.

After writing, stage every file you just changed so the commit in §6 includes the bumps. That is the single `.claude-plugin/marketplace.json`, plus one `plugins/<name>/.claude-plugin/plugin.json` for **each** plugin you bumped:

```bash
git add .claude-plugin/marketplace.json
git add plugins/<name>/.claude-plugin/plugin.json   # repeat for every bumped plugin
```

### 5. Report

After updating, show what changed:

```text
Updated versions:

  git:         1.0.1 → 1.0.2
    ✓ .claude-plugin/marketplace.json
    ✓ plugins/git/.claude-plugin/plugin.json

  plugin-name:  1.0.0 → 1.1.0
    ✓ .claude-plugin/marketplace.json
    ✓ plugins/plugin-name/.claude-plugin/plugin.json
```

### 6. Commit

**If the user indicated they didn't want to commit yet, let them commit on their own time.**

Otherwise, the default next step is to commit.

Spawn a subagent to execute this prompt:

```text
You are operating non-interactively. Create exactly one git commit from the currently staged changes. Emit no commentary, no narration, no preamble, no summary, no explanation. The commit is the only intended side effect.

1. Commit on whatever branch is currently checked out. Do not switch, create, or rebase branches, and do not consult branch protection. Committing directly to main or master is authorized and expected.

2. Commit only already-staged content. Do not run `git add`, do not stage anything, do not use `git commit -a`, and do not alter the working tree or unstaged changes.

3. First run `git diff --cached --quiet`. If it reports no staged changes, exit immediately with no commit and no output. Never create an empty commit.

4. Read the staged content with `git diff --cached` and `git diff --cached --stat` to determine what changed.

5. Determine the repo's required commit message format using the first source that exists:
   a. The template file named by `git config --local --get commit.template` (resolve ~ and paths relative to the repo root).
   b. `.gitmessage` or `.gitmessage.txt` at the repo root or under `.github/`.
   c. Commit conventions stated in CONTRIBUTING.md or docs.
   d. The dominant pattern across `git log -30 --pretty=%B` (subject style, type/scope prefix, casing, body wrapping, trailers, issue refs).
   e. If none exist and history is empty, use Conventional Commits: `type(scope): subject`.

6. Compose the message to match that format exactly, including subject length/style, type/scope, wrapped body, and any trailers or issue references the format requires. Derive content from the staged diff. Add no trailer, co-author line, or tool attribution that the discovered format does not itself require.

7. Write the message to a temp file and commit with `git commit -F <tmpfile>`, then remove the temp file. Do not push, tag, amend, or sign unless the discovered format requires signing.
```

## Edge Cases

- **No changes detected**: Tell the user all plugin versions are up to date. If they disagree, ask which plugin to bump and by how much.
- **New plugin not in manifest**: Flag it — the user needs to add the plugin entry to marketplace.json first.
- **Multiple bump-worthy changes in one plugin**: Use the highest bump level across all changes.
- **User says "bump all"**: Bump every plugin that has any changes, even if it's just a chore commit.
