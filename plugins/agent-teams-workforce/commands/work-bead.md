---
description: "Route one bead to the composite that owns it and dispatch it, by path"
argument-hint: "<bead-id>"
allowed-tools: [Bash, Read, Workflow]
---

# Work a bead

Dispatch `$ARGUMENTS` through the pipeline that owns it. Do not implement anything
yourself and do not hand-roll a phase.

## 1. Resolve the bead

```bash
bd show $ARGUMENTS --json 2>/dev/null || bd show $ARGUMENTS
```

Pull out `id`, `title`, `description`, `type`, `labels`, and the parent chain.
Work out `repoPath` — the repository the bead's work lives in. If you cannot
determine it, say so and stop; a composite with no repo path cannot build.

## 2. Resolve the installed plugin root

```bash
ls -d ~/.claude/plugins/cache/mark-satterfield/agent-teams-workforce/*/ | sort -V | tail -1
```

Call that `$ROOT`. Every dispatch below uses `scriptPath`, never a bare `name` —
name dispatch resolves against the session-start snapshot and is refused by the
workflow dispatch guard.

## 3. Route it

```
Workflow({scriptPath: "$ROOT/workflows/route-bead.js",
  args: {bead: {id, type, labels, title, description,
                parentType, ancestorTypes, childCount}}})
```

Supply `parentType`, `ancestorTypes`, and `childCount` from the parent chain. Without
them a Task cannot be judged workable and will skip.

The router returns `{action, composite, reason}`:

| action | What to do |
| --- | --- |
| `work` | Dispatch that composite (step 4) |
| `decompose` | Dispatch that composite — it builds the hierarchy beneath this bead |
| `skip` | **Stop.** Report the id and the reason. Do not dispatch anything. |

A skip is an outcome, not an obstacle. Never relabel a bead to make it routable —
a Task that skips for a missing Story needs a Story, not a new label.

## 3b. Establish the worktree FIRST

Every writing phase edits the tree it is given, and nothing in the workflows creates
one — while `deploy.js` requires the work to be on a feature branch in a worktree.
That chain only closes if the worktree exists before dispatch. Without it, Red and
Green write to whatever tree they were handed, which is usually `main` in the main
working tree: the one place the rules forbid, and a tree two parallel runs would
collide in.

```bash
REPO=<the repo from step 1>
BRANCH=fix/$ARGUMENTS                 # or feat/ for a task
WT="$(dirname "$REPO")/$(basename "$REPO")-$ARGUMENTS"

git -C "$REPO" worktree list          # reuse one that already exists for this bead
git -C "$REPO" worktree add -b "$BRANCH" "$WT" 2>/dev/null \
  || git -C "$REPO" worktree add "$WT" "$BRANCH"
```

If a worktree for this bead already exists, REUSE it — a resumed or re-dispatched
run must land in the same tree as the attempt before it, or the second run cannot
see the first one's tests and re-authors them.

Pass `$WT` as `repoPath` to the composite, not `$REPO`. Everything downstream
inherits it.

## 4. Dispatch

```
Workflow({scriptPath: "$ROOT/workflows/<composite>.js",
  args: {bead: {id, title, description, repoPath: "$WT"}}})
```

For `prd-to-spec`, pass `{prd, repoPath, repos}` instead — and `repos` as every
repo the PRD spans, so one Story is created per repo.

## 5. Report

Five lines, no more:

- which composite ran, and why the router chose it
- the phase it reached
- deploy result (it should reach **Deploy-to-dev** and smoke-check, not stop at readiness)
- any gate that blocked it, with its feedback **verbatim**
- what you did NOT do
- the worktree and branch the work landed on

If a gate blocks you, report it. Do not work around it, do not edit the workflow
mid-run, and do not fall back to a subagent beside the pipeline.
