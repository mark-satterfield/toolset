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

**Task or Infra — DEVELOPMENT work:**

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

**Bug — neither.** A bug is a reporting mechanism, not work. It is TRIAGED by a
person into an Epic, a Task, or a closure. Both routers skip it, naming triage;
there is no triage composite to dispatch. Hand a bug to `route-build.js` and
report the skip — do not force it into `bug-fix`.

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
existing tree for this bead or cuts a new one at `$ATW_WORKTREE_ROOT/<bead>-<repo>`
on a feature branch, and verifies the result really is a linked worktree before any phase
writes a line. Its return value is the sole source of `contract.repoPath`, and every
writing phase inherits it. A run that cannot verify a worktree refuses to write.

**So pass the contract's repository as it stands.** `repoPath` is the repository the
Task's contract names, not a worktree you built. A resumed run finds its earlier tree
anyway: `workspace` recognises a linked worktree on a feature branch for this bead and
reuses it.

For an `elaborate` there is no worktree at all: that path authors documents and returns
bead specifications, so there is no feature branch for it to land on.

## 4. Dispatch — `work` only

Read the Task's build contract with the `beads-contract` CLI — it is the one authority on
what a Task carries:

```bash
python3 "$ROOT/skills/beads-contract/scripts/beads-contract.py" contract <id>
```

Its `bead` field is the composite's `bead` argument, complete: id, title, description, the
repository, the spec documents and sections, the acceptance criteria, the Definition of Done,
the requirement ids and the SAD decision ids. Pass it as-is; do not rebuild it by hand and do
not drop fields from it. If `missing` names `repoPath`, the Task's build contract is incomplete:
the repository is ruled during elaboration, so report the id and that reason and stop — never
work out a repository yourself.

The project's configuration reaches the composite as arguments, read from the `ATW_*`
environment (see "Project configuration" in `AGENT-TEAMS-WORKFORCE.md`); a workflow script
cannot read the environment itself. `ATW_PR_COMMAND` is required: if it is unset, report
`ATW_PR_COMMAND is unset` and stop. Omit any other argument whose variable is unset, and
name it in your report.

```
Workflow({scriptPath: "$ROOT/workflows/<composite>.js",
  args: {bead: <the contract's bead>,
         prCommand: "$ATW_PR_COMMAND",
         worktreeRoot: "$ATW_WORKTREE_ROOT",
         projectRoot: "$ATW_PROJECT_ROOT",
         artifactScript: "$ATW_ARTIFACT_SCRIPT"}})
```

Every value is the expanded value of its variable, not the literal variable name. The
composite's `workspace` phase turns the contract's repository into the worktree; do not
pre-cut one.

Then go to step 6.

## 5. Elaborate — `elaborate` only

The bead is an Epic or a Story: the tracker face of a document. Nothing decomposes
it. Its **document** is what decomposes, and the beads beneath it are what that
chain deposits.

Resolve the other face — the PRD (for an Epic) or the Spec (for a Story). PRDs live under
`$ATW_PRD_DIR`; if it is unset, report `ATW_PRD_DIR is unset` and stop:

```bash
ls -R "$ATW_PRD_DIR"
```

- Found → read it and extract `title` and `body`.
- Not found → **mint it** from the bead's title and description, authored to the
  PRD template. Minting completes the pair; it is not what authorizes the build —
  your invoking this command is.

Then invoke the `elaborate-prd-epic` skill with the resolved pair. It owns the
`prd-to-spec` dispatch and the report. The run writes the returned hierarchy into
beads itself; the skill verifies what landed rather than writing it by hand. `/agent-teams-workforce:start-prd` hands off to the same skill from
the other door — do not re-implement any of it here.

Do not work out a repo span. `prd-to-spec` RULES the span during the run, after
the architecture decision, and it is recomputed every run rather than stored — so
a span derived here would pin the answer to what was visible before the design
existed, and a re-run after an adjustment would inherit it.

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
