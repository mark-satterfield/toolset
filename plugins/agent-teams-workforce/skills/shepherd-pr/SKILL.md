---
name: shepherd-pr
version: 3.0.0
description: Shepherd a PR until it merges or closes — fix everything that keeps it from merging (failing lint, type, test and other required checks; merge conflicts and a branch behind its base; unresolved review threads; CodeRabbit changes-requested reviews; reviewer questions) with confidence gating and a defensible audit trail. Invoking the skill runs its own loop (scripts/shepherd-pr.sh); each pass is one headless session running the /agent-teams-workforce:fix-pr command; the loop never merges and never arms auto-merge: skillspoke-pr switches GitHub auto-merge on when it opens the PR, and GitHub merges.
category: github
tags: [pr-review, coderabbit, bot-feedback, thread-resolution, ci-triage, merge-warden]
author: Claude Code Flow
requires:
  - github-cli
  - git
  - jq
capabilities:
  - Follow a PR until GitHub reports it merged or closed
  - Start one headless fix pass whenever GitHub shows something blocking the merge
  - Wait on pending checks and auto-merge without spending a session
  - Stop for human action when passes stall, waiting cannot help, or a clean PR has auto-merge off
---

# PR Shepherd Skill

> **Shepherd PR Reviews:** Follow a PR until it merges or closes. Whenever GitHub shows something that blocks the merge, start one pass that triages every open thread, decides a disposition, executes it, fixes CI, and leaves behind a defensible audit trail, so GitHub auto-merge, which `skillspoke-pr` switched on when it opened the PR, can fire.

## Invocation Model

Invoking this skill means shepherding the PR **until GitHub reports it MERGED or CLOSED**. The loop lives in this skill's own script, `scripts/shepherd-pr.sh`, beside this SKILL.md. Run it; do not make a pass yourself — each pass is the `/agent-teams-workforce:fix-pr` command, which the loop starts.

```bash
bash "<this skill's base directory>/scripts/shepherd-pr.sh" <pr-number> [owner/repo] [working-directory]
```

- `<this skill's base directory>` is the directory this SKILL.md was loaded from (Claude Code states it as the skill's base directory when the skill loads; for the plugin copy it is `${CLAUDE_PLUGIN_ROOT}/skills/shepherd-pr`). Use that absolute path; never a path into some other repository.
- `[working-directory]` must be a linked git worktree of the PR's repository holding the PR's head branch — passes rebase, commit and push there, and a primary working tree is never written. Get it from the plugin's one worktree mechanism, which reuses the tree registered for the branch or creates one inside the repository: `python3 "<plugin root>/scripts/portfolio/gitfacts.py" provision --repo <repo> --branch <head> --name <repo>-pr<number> --from-origin` (`<plugin root>` is two directories above this skill's base directory). Pass the `worktree` it prints; when it prints `error` or `ok: false`, report that and stop. Never run `git worktree add` yourself and never write a worktree path: `gitfacts.py provision` alone decides where a worktree lives.
- The script runs for as long as the PR is open — often hours. In an interactive session, start it with `run_in_background: true` and wait for its exit notification. In a headless `claude -p` session, which cannot outlive its last turn, run it in the foreground with the largest `timeout` the Bash tool allows (the caller raises the ceiling through `BASH_MAX_TIMEOUT_MS`). If the command is cut off by the tool's timeout while the PR is still open, run the same command again; the script re-reads GitHub and carries on.
- Report the script's exit status and its last state line. Exit statuses: `0` merged or closed; `1` stopped for human action (it prints why).

### How a pass is started

Each pass is a fresh headless `claude --print` session, run in the working directory, whose prompt is the command. The session loads this plugin with `--plugin-dir <plugin root>` (the plugin the loop script belongs to), so the command exists whatever repository the working directory is in, including one where the plugin is not enabled:

```text
/agent-teams-workforce:fix-pr <pr-number> <owner/repo> "<working-directory>"
```

Each pass's full output is kept as stream-json in `pass-<time>-<n>.jsonl`, and the loop's own lines in `loop.log`, under `SHEPHERD_LOG_DIR` (default `${CLAUDE_CONFIG_DIR:-~/.claude}/shepherd-pr/<owner>-<repo>-<pr>`). After each pass the loop prints whether the fix-pr command was loaded, how many tools the pass called and its result, and a WARNING when the pass did no work.

The pass session runs with `SHEPHERD_PR_PASS=1` in its environment. A session that sees `SHEPHERD_PR_PASS=1` is inside a pass: it never runs `scripts/shepherd-pr.sh`, so a pass never starts a loop of its own.

### When the loop starts a pass, and when it stops

What the loop does, every iteration, deciding only from GitHub's own state:

| GitHub reports | The loop |
|:--|:--|
| `MERGED` or `CLOSED` | exits 0 |
| a failing or cancelled check, an unresolved review thread, a `CHANGES_REQUESTED` review newer than the last pass, a review decision of `CHANGES_REQUESTED` with a changes-requested review none of whose threads is still open (the pass dismisses it), a reviewer question or comment, a CodeRabbit reply or a review body (CodeRabbit's outside-diff findings live there) newer than the last pass, a merge conflict (`DIRTY`) or a branch behind its base (`BEHIND`) | starts ONE headless pass session (`/agent-teams-workforce:fix-pr`) |
| checks still pending, or nothing to fix | waits and polls again — no session is spent; after `SHEPHERD_MAX_WAIT_SECONDS` (default 7200) of waiting since the last pass it exits 1 for human action |
| nothing to fix, every check passing, and auto-merge off (for example a PR opened before `skillspoke-pr` armed auto-merge) | exits 1 for human action: GitHub will not merge it, and the loop does not arm auto-merge, which is `skillspoke-pr`'s job |
| `SHEPHERD_MAX_STALLED_PASSES` (default 3) passes in a row that changed nothing on the PR | exits 1 for human action |

### Guards

The loop never arms auto-merge and never merges: `skillspoke-pr` switches GitHub auto-merge on when it opens the PR, and GitHub merges. Every pass session runs with a deny rule on `Bash(gh pr merge:*)`: a pass never merges. The script never decides what to do about a thread; every decision is the pass's.

---

## 📖 Related

- **`scripts/shepherd-pr.sh`** (in this skill's directory): the deterministic loop. Starts one `/agent-teams-workforce:fix-pr` pass session whenever GitHub shows something to fix (a resolved but undismissed change request included), polls while checks are pending or GitHub's merge is due, and exits when the PR is merged or closed, or stops for human action.
- **`/agent-teams-workforce:fix-pr`**: one pass — the argument contract, the pass guards, Phases 1 to 6 and the safety checklist.
