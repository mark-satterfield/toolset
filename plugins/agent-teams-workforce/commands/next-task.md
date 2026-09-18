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

**Order by WSJF, descending.** WSJF is stored on the issue as Beads metadata under the
`wsjf` rubric at Task level — written when `prd-to-spec` elaborates the Task's Epic, and
rewritten by the `wsjf-scoring` workflow — read it, do not recompute it:

```bash
bd show <id> --json --readonly \
  | jq -r 'if type=="array" then .[0] else (.issue // .) end | (.metadata // {})
           | "\(.wsjf // "")"'
```

A candidate with no stored `wsjf` has not been scored. It cannot be ranked, so it
is left out of the ordering rather than given a fallback position — run
`/agent-teams-workforce:wsjf-scoring` to score it. The readiness gate does not
score and never has a number to backfill.

Order the scored candidates by `wsjf` descending, breaking ties on `created_at`
ascending so the oldest goes first.

Then run `/agent-teams-workforce:task-ready <id>` on the candidates in that order.
That gate judges whether the issue carries what someone needs in order to work it,
and persists `review_status`, `review_missing`, `reviewed_at`, and
`ready_content_hash`. It is expensive only the first time — on later runs the content
hash matches, it reuses the stored verdict and reruns nothing.

**Gate on `Ready`, not on membership in `bd ready`.** `task-ready` returns a hard
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
workable.

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

A skip is an outcome. Never relabel a bead to make it routable — a skip's reason
names what the bead needs, and a new label is never it. If the router names
`route-elaboration`, the bead is an Epic or a Story: that is not development work
and does not belong to this command.

## 4. The worktree — owned by the composite, not by this command

Do not provision a tree here. **The composite establishes its own worktree.** Its first
phase is `workspace` (`workflows/workspace.js`): it fetches, fast-forwards, reuses an
existing tree for this bead or cuts a new one at `$ATW_WORKTREE_ROOT/<bead>-<repo>`
on a feature branch, verifies the result really is a linked worktree, and returns the path
that becomes `contract.repoPath` for every writing phase. A run that cannot verify a
worktree refuses to write.

Pass the contract's repository as it stands. The `workspace` phase recognises an existing
linked worktree on a feature branch for this bead and reuses it, so a later run still finds
the earlier attempt's tests.

## 5. Dispatch the composite

Read the Task's build contract with the `beads-contract` CLI — it is the one authority on
what a Task carries:

```bash
python3 "$ROOT/skills/beads-contract/scripts/beads-contract.py" contract <id>
```

Its `bead` field is the composite's `bead` argument, complete: id, title, description, the
repository, the spec documents and sections, the acceptance criteria, the Definition of Done,
the requirement ids and the SAD decision ids. Pass it as-is; do not rebuild it by hand and do
not drop fields from it. If `missing` names `repoPath`, the Task's build contract is incomplete:
the repository is ruled during elaboration, so release the claim, report the id and that reason, and stop — never
work out a repository yourself.

The project's configuration reaches the composite as arguments, read from the `ATW_*`
environment (see "Project configuration" in `AGENT-TEAMS-WORKFORCE.md`); a workflow script
cannot read the environment itself. `ATW_PR_COMMAND` is required: if it is unset, release
the claim, report `ATW_PR_COMMAND is unset`, and stop. Omit any other argument whose
variable is unset, and name it in your report.

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
