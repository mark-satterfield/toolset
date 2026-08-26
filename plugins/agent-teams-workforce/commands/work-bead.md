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

## 3b. The worktree — owned by the composite, not by this command

Skip any thought of provisioning a tree here. **The composite establishes its own
worktree.** Its first phase is `workspace`, which fetches, fast-forwards, reuses an
existing tree for this bead or cuts a new one under `.worktrees/<bead>-<repo>` on a
feature branch, and verifies the result really is a linked worktree before any phase
writes a line. Its return value is the sole source of `contract.repoPath`, and every
writing phase inherits it.

This used to live here, as shell in a markdown file that a model executed — and the
two runs that stranded production work in a main working tree are the two that skipped
it. A step the pipeline depends on cannot be a step the pipeline cannot see. It is now
code, in `workflows/workspace.js`, dispatched before the first writing phase, and a run
that cannot verify a worktree refuses to write rather than falling back to the tree it
was pointed at.

**So pass the plain repository.** `repoPath` is `$REPO`, not a worktree you built. If
you hand it a worktree anyway — a resumed run, say — `workspace` recognises a linked
worktree on a feature branch and reuses it, which is the same reuse guarantee this
section used to describe.

For an `elaborate` there is no worktree at all: that path authors documents and returns
bead specifications, so there is no feature branch for it to land on.

## 4. Dispatch — `work` only

```
Workflow({scriptPath: "$ROOT/workflows/<composite>.js",
  args: {bead: {id, title, description, repoPath: "$REPO"}}})
```

`$REPO` is the repository from step 1. The composite's `workspace` phase turns it into
the worktree; do not pre-cut one.

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
- the PR URL, or the explicit reason there is none

If a gate blocks you, report it. Do not work around it, do not edit the workflow
mid-run, and do not fall back to a subagent beside the pipeline.
