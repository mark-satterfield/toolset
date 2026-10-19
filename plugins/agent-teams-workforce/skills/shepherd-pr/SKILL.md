---
name: shepherd-pr
version: 4.0.0
description: Shepherd a PR until it qualifies for merging — work through everything on it that keeps it from qualifying (failing lint, type, test and other required checks; merge conflicts and a branch behind its base; unresolved review threads; CodeRabbit changes-requested reviews; reviewer questions) with confidence gating and a defensible audit trail. Invoking the skill runs its own loop (scripts/shepherd-pr.sh); each pass is one headless session running the /agent-teams-workforce:fix-pr command. The shepherd ends when the PR qualifies for merging, or when it cannot fix what is left; merging and closing are not its job.
category: github
tags: [pr-review, coderabbit, bot-feedback, thread-resolution, ci-triage, merge-warden]
author: Claude Code Flow
requires:
  - github-cli
  - git
  - jq
capabilities:
  - Work through a PR until GitHub's merge requirement facts show it qualifies for merging
  - Start one headless fix pass whenever GitHub shows something keeping it from qualifying
  - Wait on running checks without spending a session
  - End, naming what is still unfixed, when passes in a row change nothing (the same open non-repeat threads and the same failing checks) or the wait limit runs out
---

# PR Shepherd Skill

> **Shepherd PR Reviews:** Work through the issues on a PR until it qualifies for merging. Whenever GitHub shows something that keeps it from qualifying, start one pass that triages every open thread, decides a disposition, executes it, fixes CI, and leaves behind a defensible audit trail. The shepherd's job ends when the PR qualifies for merging, or when it cannot fix what is left. Merging and closing are not its job: whether a PR is merged by auto-merge or by a person is the owner's choice, and the shepherd neither waits for nor watches it.

## Invocation Model

Invoking this skill means shepherding the PR **until it qualifies for merging, or until the shepherd cannot fix what is left**. The loop lives in this skill's own script, `scripts/shepherd-pr.sh`, beside this SKILL.md. Run it; do not make a pass yourself — each pass is the `/agent-teams-workforce:fix-pr` command, which the loop starts.

```bash
bash "<this skill's base directory>/scripts/shepherd-pr.sh" <pr-number> [owner/repo] [working-directory]
```

- `<this skill's base directory>` is the directory this SKILL.md was loaded from (Claude Code states it as the skill's base directory when the skill loads; for the plugin copy it is `${CLAUDE_PLUGIN_ROOT}/skills/shepherd-pr`). Use that absolute path; never a path into some other repository.
- `[working-directory]` must be a linked git worktree of the PR's repository holding the PR's head branch — passes rebase, commit and push there, and a primary working tree is never written. Get it from the plugin's one worktree mechanism, which reuses the tree registered for the branch or creates one inside the repository: `python3 "<plugin root>/scripts/portfolio/gitfacts.py" provision --repo <repo> --branch <head> --name <repo>-pr<number> --from-origin` (`<plugin root>` is two directories above this skill's base directory). Pass the `worktree` it prints; when it prints `error` or `ok: false`, report that and stop. Never run `git worktree add` yourself and never write a worktree path: `gitfacts.py provision` alone decides where a worktree lives. Removing worktrees is not the shepherd's job either: each `provision` run removes the repository's clean worktrees whose PR GitHub reports MERGED, with their branches.
- The script runs until it ends on its own — often hours. In an interactive session, start it with `run_in_background: true` and wait for its exit notification. In a headless `claude -p` session, which cannot outlive its last turn, run it in the foreground with the largest `timeout` the Bash tool allows (the caller raises the ceiling through `BASH_MAX_TIMEOUT_MS`). If the command is cut off by the tool's timeout before the script exits, run the same command again; the script re-reads GitHub and carries on.
- Report the script's exit status and its last line.

### Exit status

| Exit | Outcome (`ending` file) | Meaning |
|:--|:--|:--|
| `0` | `qualifies` | The PR qualifies for merging. The job is done. |
| `0` | `merged` or `closed` | The PR was already merged or closed. Nothing is left for the shepherd. |
| `1` | — | The shepherd could not start: bad arguments, a missing tool, or the script is not in the plugin. |
| `2` | `could-not-fix` | The shepherd could not fix the PR. The message names what is still unfixed, or what it was still waiting on. |

Every ending the loop reaches is also written as one tab-separated line, `<exit> <outcome> <message>`, to `ending` in `SHEPHERD_LOG_DIR`, so a caller that runs the skill inside a session and cannot see the exit status reads it there.

Why this scheme: both `0` endings mean the shepherd's job is done and a caller has nothing to do about the shepherd; `2` is the one ending a caller treats differently, and it is kept apart from `1` so a shepherd that never ran is not mistaken for one that ran and could not fix the PR.

### How a pass is started

Each pass is a fresh headless `claude --print` session, run in the working directory, whose prompt is the command. The session loads this plugin with `--plugin-dir <plugin root>` (the plugin the loop script belongs to), so the command exists whatever repository the working directory is in, including one where the plugin is not enabled:

```text
/agent-teams-workforce:fix-pr <pr-number> <owner/repo> "<working-directory>"
```

Each pass's full output is kept as stream-json in `pass-<time>-<n>.jsonl`, and the loop's own lines in `loop.log`, under `SHEPHERD_LOG_DIR` (default `${CLAUDE_CONFIG_DIR:-~/.claude}/shepherd-pr/<owner>-<repo>-<pr>`). After each pass the loop prints whether the fix-pr command was loaded, how many tools the pass called and its result, and a WARNING when the pass did no work.

The pass session runs with `SHEPHERD_PR_PASS=1` in its environment. A session that sees `SHEPHERD_PR_PASS=1` is inside a pass: it never runs `scripts/shepherd-pr.sh`, so a pass never starts a loop of its own.

### When the loop starts a pass, and when it ends

What the loop does, every iteration, deciding only from GitHub's own state:

| GitHub reports | The loop |
|:--|:--|
| `MERGED` or `CLOSED` | ends quietly, exit 0 |
| a failing or cancelled check, an unresolved review thread, a `CHANGES_REQUESTED` review newer than the last pass, a review decision of `CHANGES_REQUESTED` with a changes-requested review none of whose threads is still open (the pass dismisses it), a reviewer question or comment, a CodeRabbit reply or a review body (CodeRabbit's outside-diff findings live there) newer than the last pass, a merge conflict (`DIRTY`) or a branch behind its base (`BEHIND`) | starts ONE headless pass session (`/agent-teams-workforce:fix-pr`) |
| nothing to fix, and the PR qualifies for merging: no review decision of `CHANGES_REQUESTED`, no unresolved review thread, every required check passed (`gh pr checks --required`; a repository that requires none passes), and `mergeStateStatus` is `CLEAN`, `HAS_HOOKS` or `UNSTABLE` | prints `PR #N qualifies for merging` and ends, exit 0 — it does not wait for the merge |
| nothing to fix, but the PR does not qualify yet: required checks still running, `mergeStateStatus` `BLOCKED`, `UNKNOWN` or `DRAFT`, or a read GitHub could not answer | waits and polls again — no session is spent; after `SHEPHERD_MAX_WAIT_SECONDS` (default 7200) of waiting since the last pass it ends, exit 2, saying what it is still waiting on |
| `SHEPHERD_MAX_STALLED_PASSES` (default 3) passes in a row that changed nothing (below) | ends, exit 2, naming what is still unfixed |

`BEHIND` appears only when the repository requires the branch to be current, so the loop rebases a branch behind its base exactly when GitHub's requirements call for it.

### When a pass changed nothing

A pass has either made the changes it can, or decided that what is left cannot or should not change. When the next pass essentially repeats the same thing, nothing changed. Precisely, a pass changed nothing when, at the start of the next pass, both of these are the same as at its own start:

- **Threads:** the set of open review threads that are not repeats of an already-addressed thread. A thread is addressed when it is fixed in code, or answered with a reasoned decline (the suggestion would be wrong to implement, or should not change) and resolved; a decline needs no commit, and because resolving the thread takes it out of the set, that pass counts as progress. A thread that raises again a finding already fixed or declined (CodeRabbit repeating a finding the pass answered as wrong or not to be changed) is a repeat, not new.
- **Checks:** the names of the failing checks (unit tests, lint, static analysis and every other check, each by name, not one combined CI state). The checks that passed still pass and the checks that failed still fail. A fix that makes a different check fail is new.

The head commit, the review decision and the merge state are not part of the comparison. Whether a thread is a repeat is judgment, so each pass records the threads it judged repeats, each with the earlier thread it repeats, in `repeats-pass-<n>.tsv` in `SHEPHERD_LOG_DIR` (the loop hands the path to the pass as `SHEPHERD_REPEATS_FILE`; see `/agent-teams-workforce:fix-pr` 3.6). The loop then compares deterministically.

### Guards

The loop never merges and does not wait for a merge. Every pass session runs with a deny rule on `Bash(gh pr merge:*)`: a pass never merges. The script never decides what to do about a thread; every decision is the pass's.

---

## 📖 Related

- **`scripts/shepherd-pr.sh`** (in this skill's directory): the deterministic loop. Starts one `/agent-teams-workforce:fix-pr` pass session whenever GitHub shows something to fix (a resolved but undismissed change request included), polls while the PR does not qualify yet and nothing is left to fix, and ends when the PR qualifies for merging (or is already merged or closed), or when it cannot fix what is left.
- **`/agent-teams-workforce:fix-pr`**: one pass — the argument contract, the pass guards, Phases 1 to 6 and the safety checklist.
