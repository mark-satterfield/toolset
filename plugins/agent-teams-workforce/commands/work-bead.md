---
description: "Route one bead to the composite that owns it and dispatch it, by path"
argument-hint: "<bead-id>"
allowed-tools: [Bash, Read, Skill, Workflow]
---

# Work a bead

Dispatch `$ARGUMENTS` through the pipeline that owns it. Do not implement anything
yourself and do not hand-roll a phase.

## 1. Resolve the bead

```bash
bd show $ARGUMENTS --json || bd show $ARGUMENTS
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

There are two routers, split by the kind of work. Pick by the bead's type — do not
guess, and do not send a bead to both.

**Task, Bug, or Infra — DEVELOPMENT work:**

```
Workflow({scriptPath: "$ROOT/workflows/route-build.js",
  args: {bead: {id, type, labels, title, description,
                parentType, ancestorTypes}}})
```

Supply `parentType` and `ancestorTypes` from the parent chain. Without them a Task
cannot be judged workable and will skip. There is no `humanInitiated` flag here and
that is deliberate: a Task under a Story under an Epic was already authorised when
someone chose to elaborate that Epic. This is what lets an unattended build loop run.

**Epic, Story, or Feature — ELABORATION work:**

```
Workflow({scriptPath: "$ROOT/workflows/route-elaboration.js",
  args: {bead: {id, type, labels, title, description,
                parentType, ancestorTypes},
         humanInitiated: true}})
```

`humanInitiated: true` is correct here and **only** here: a person typed this command.
Existence is not readiness — an Epic sitting there is not a request to elaborate it.
An unattended sweep must leave the flag unset and take the skip.

Do **not** pass `childCount`. Neither router reads it. An Epic that already has
Stories can still need working, because its PRD may have moved on and the beads
beneath it drifted — treating "has children" as "done" is how that drift goes unseen.

The router returns `{action, composite, reason}`:

| action | What to do |
| --- | --- |
| `work` | Dispatch that composite (step 3b, then 4) |
| `elaborate` | **Go to step 5.** No worktree, no composite dispatch from here. |
| `skip` | **Stop.** Report the id and the reason. Do not dispatch anything. |

A skip is an outcome, not an obstacle. Never relabel a bead to make it routable —
a Task that skips for a missing Story needs a Story, not a new label.

## 3b. Establish the worktree FIRST — `work` only

Skip this entire step for an `elaborate`. That path authors documents and returns
bead specifications; it writes no code, so there is no feature branch for it to land
on and no tree for two runs to collide in.


Every writing phase edits the tree it is given, and nothing in the workflows creates
one — while `deploy.js` requires the work to be on a feature branch in a worktree.
That chain only closes if the worktree exists before dispatch. Without it, Red and
Green write to whatever tree they were handed, which is usually `main` in the main
working tree: the one place the rules forbid, and a tree two parallel runs would
collide in.

```bash
REPO=<the repo from step 1>
git -C "$REPO" worktree list          # ALWAYS look first — see below
```

**Follow the convention already in use.** This fleet keeps worktrees under a
`.worktrees/` directory beside the repo, named `<bead>-<repo-or-domain>`, e.g.
`apps/personal-agent/.worktrees/ssbd-0wmo-document`. Read the existing list and
match it. Inventing a third layout scatters the fleet's worktrees across
directories where the next run will not find them.

```bash
WTDIR="$(dirname "$REPO")/.worktrees"
WT="$WTDIR/$ARGUMENTS-$(basename "$REPO" | sed 's/^SkillSpoke-//')"
BRANCH=fix/$ARGUMENTS                 # feat/ for a task

# Branch from the CURRENT tip, not a stale ref. Fetch first, then use whichever of
# local main / origin/main is ahead. A worktree cut from an older commit silently
# omits work that has already landed — and the Red survey, looking for tests that
# ARE committed but not in this tree, finds nothing and re-authors them.
git -C "$REPO" fetch origin main
BASE=$(git -C "$REPO" rev-parse main)
git -C "$REPO" merge-base --is-ancestor "$BASE" origin/main && BASE=$(git -C "$REPO" rev-parse origin/main)

if ! git -C "$REPO" worktree list --porcelain | grep -q "$ARGUMENTS"; then
  git -C "$REPO" worktree add -b "$BRANCH" "$WT" "$BASE"
fi
```

**Then confirm the worktree actually has what you expect.** A worktree at the wrong
commit is invisible until a phase behaves oddly:

```bash
git -C "$WT" log --oneline -1
git -C "$REPO" log --oneline -1 main
```

If they differ, say so before dispatching — the run will not see work that is
committed on `main` but absent from the tree it was given.

If a worktree for this bead already exists, REUSE it — a resumed or re-dispatched
run must land in the same tree as the attempt before it, or the second run cannot
see the first one's tests and re-authors them.

Pass `$WT` as `repoPath` to the composite, not `$REPO`. Everything downstream
inherits it.

## 4. Dispatch — `work` only

```
Workflow({scriptPath: "$ROOT/workflows/<composite>.js",
  args: {bead: {id, title, description, repoPath: "$WT"}}})
```

Then go to step 6.

## 5. Elaborate — `elaborate` only

The bead is an Epic or a Story: the tracker face of a document. Nothing decomposes
it. Its **document** is what decomposes, and the beads beneath it are what that
chain deposits.

Resolve the other face — the PRD (for an Epic) or the Spec (for a Story):

```bash
ls ~/projects/SkillSpoke/skillspoke-docs/docs/product/
```

- Found → read it and extract `title` and `body`.
- Not found → **mint it** from the bead's title and description, authored to the
  PRD template. Minting completes the pair; it is not what authorizes the build —
  your invoking this command is.

Then invoke the `elaborate-prd-epic` skill with the resolved pair. It owns the repo
span, the `prd-to-spec` dispatch, writing the returned hierarchy into beads with
`bd`, and the report. `/agent-teams-workforce:start-prd` hands off to the same
skill from the other door — do not re-implement any of it here.

## 6. Report

Five lines, no more:

- which composite ran, and why the router chose it
- the phase it reached
- deploy result (it should reach **Deploy-to-dev** and smoke-check, not stop at readiness)
- any gate that blocked it, with its feedback **verbatim**
- what you did NOT do
- the worktree and branch the work landed on

If a gate blocks you, report it. Do not work around it, do not edit the workflow
mid-run, and do not fall back to a subagent beside the pipeline.
