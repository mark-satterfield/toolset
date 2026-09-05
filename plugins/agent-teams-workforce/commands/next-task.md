---
description: "Claim the next ready Task and run it through to deploy-in-dev"
argument-hint: "[--dry-run]"
allowed-tools: [Bash, Read, Workflow]
---

# Next task

Claim one ready development bead, route it, run it, report. One bead per
invocation — this is the body of the loop, not the loop itself.

To run continuously: `/loop /agent-teams-workforce:next-task`. Each tick claims
the next bead. Stop by cancelling the loop.

## Why this is a command and not a workflow script

The obvious implementation — a `sweep.js` that fetches `bd ready` and calls
`workflow('task-to-deploy')` per bead — **cannot work**. The Workflow runtime
permits one level of nesting, and the composites already spend it on their own
minis (`task-to-deploy` → `tdd-red`, `tdd-green`, …). A sweep calling a composite
calling a mini is two levels and throws.

So the session is the driver. That also bounds what "unattended" means here: it is
only as unattended as the session running it.

## 1. Pick the bead

Candidates come from the tracker's own ready semantics — open, unblocked, not
deferred or hooked:

```bash
bd ready --type task --json -n 0 --readonly > /tmp/ready-tasks.json
```

**Bugs are not candidates.** A bug is a reporting mechanism, triaged by a person
into an Epic, a Task, or a closure — `route-build` skips it and there is no
triage composite to dispatch. Do not query for them here.

**Order by WSJF, descending.** WSJF is stored on the issue as Beads metadata by the
`issue-ready` skill — read it, do not recompute it:

```bash
bd show <id> --json --readonly \
  | jq -r 'if type=="array" then .[0] else (.issue // .) end | (.metadata // {})
           | "\(.wsjf // "")"'
```

A candidate with no stored `wsjf` has not been through the readiness gate. Run
`/agent-teams-workforce:issue-ready <id>` on it. That gate reviews the issue, scores
it, and persists `wsjf`, `wsjf_calculated_at`, `review_status`, and
`ready_content_hash`. It is expensive only the first time — on later runs the content
hash matches, it reuses the stored verdict and reruns nothing.

Order the scored candidates by `wsjf` descending, breaking ties on `created_at`
ascending so the oldest goes first.

**Gate on `Ready`, not on membership in `bd ready`.** `issue-ready` returns a hard
boolean, and `Ready: TRUE` requires both a `READY` pipeline result and tracker-ready
state. Take the highest-WSJF candidate whose gate says `Ready: TRUE`. Skip any that
comes back `FALSE` and record its `Pipeline result` — an `INCOMPLETE` issue needs
work on the issue, not a dispatch.

If nothing is `Ready: TRUE`, report "no ready development work" with the reasons and
stop. That is a clean finish, not a failure.

Then claim the winner, so a second runner cannot take the same bead:

```bash
bd update <id> --claim
```

With `--dry-run`, print the ordered candidates with their scores and gate verdicts,
name the bead you would claim, then stop without claiming or dispatching.

## 2. Resolve the bead and its repo

```bash
bd show <id> --json || bd show <id>
```

Pull out `id`, `title`, `description`, `issue_type`, `labels`, and the parent
chain — you need `parentType` and `ancestorTypes` or a Task cannot be judged
workable. Work out `repoPath`, the repository the work lives in. If you cannot
determine it, release the claim and stop; a composite with no repo path cannot
build.

## 3. Route it

```bash
ls -d ~/.claude/plugins/cache/mark-satterfield/agent-teams-workforce/*/ | sort -V | tail -1
```

Call that `$ROOT`. Always dispatch by `scriptPath`, never a bare name.

```
Workflow({scriptPath: "$ROOT/workflows/route-build.js",
  args: {bead: {id, type, labels, title, description,
                parentType, ancestorTypes}}})
```

No `humanInitiated` flag: development work on a Task under a Story under an Epic
was authorised upstream when someone chose to elaborate that Epic. That is exactly
what lets this run unattended.

| action | What to do |
| --- | --- |
| `work` | Continue to step 4 |
| `skip` | Release the claim, report the id and the reason **verbatim**, and stop |

A skip is an outcome. Never relabel a bead to make it routable — a Task that skips
for a missing Story needs a Story, not a new label. If the router names
`route-elaboration`, the bead is an Epic or a Story: that is not development work
and does not belong to this command.

## 4. The worktree — owned by the composite, not by this command

Do not provision a tree here. **The composite establishes its own worktree.** Its first
phase is `workspace` (`workflows/workspace.js`): it fetches, fast-forwards, reuses an
existing tree for this bead or cuts a new one under `.worktrees/<bead>-<repo>` on a
feature branch, verifies the result really is a linked worktree, and returns the path
that becomes `contract.repoPath` for every writing phase.

This used to be shell in this file, executed by a model — and the runs that stranded
production work in a main working tree are the runs that skipped it. An unattended
command cannot depend on a step nothing enforces, so the step moved into the pipeline.
A run that cannot verify a worktree now refuses to write rather than falling back to
whatever tree it was pointed at.

Pass the plain repository. A resumed run that already has a worktree may pass it: the
`workspace` phase recognises a linked worktree on a feature branch and reuses it, so a
later run still finds the earlier attempt's tests.

## 5. Dispatch the composite

```
Workflow({scriptPath: "$ROOT/workflows/<composite>.js",
  args: {bead: {id, title, description, repoPath: "$REPO"}}})
```

`$REPO` is the repository from step 2. The composite's `workspace` phase turns it into
the worktree; do not pre-cut one.

`<composite>` is whatever the router named — `task-to-deploy` or `infra-change`.
Do not substitute your own. (`bug-fix` is reachable only on demand, after a
person has triaged a bug and decided it is a fix; the router never names it.)

## 6. Report, in five lines

- the bead claimed, its WSJF score, and how many candidates were considered
- which composite ran, and the router's reason
- the phase it reached — it should reach **Deploy-to-dev** and smoke-check, not
  stop at readiness
- any gate that blocked it, with its feedback **verbatim**
- the worktree and branch the work landed on
- the PR URL, or the explicit reason there is none

If a gate blocks, report it and stop. Do not work around it, do not edit a
workflow mid-run, and do not fall back to a subagent beside the pipeline. Leave
the bead claimed so the next run resumes it in the same worktree. The composite's
settle step has already pushed and PR'd whatever was written — report that PR URL.
