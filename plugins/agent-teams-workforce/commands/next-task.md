---
description: "Claim the next ready Task or Bug and run it through to deploy-in-dev"
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
bd ready --type bug  --json -n 0 --readonly > /tmp/ready-bugs.json
```

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

## 4. Establish the worktree FIRST

Every writing phase edits the tree it is handed, and nothing in the workflows
creates one — while `deploy.js` requires the work to be on a feature branch in a
worktree. Without this step, Red and Green write to whatever tree they were given,
usually `main`: the one place the rules forbid, and the tree two parallel runs
would collide in.

```bash
REPO=<the repo from step 2>
git -C "$REPO" worktree list          # ALWAYS look first — reuse beats create
```

Follow the layout already in use: worktrees under a `.worktrees/` directory beside
the repo, named `<bead>-<repo-or-domain>`. Read the list and match it.

```bash
WTDIR="$(dirname "$REPO")/.worktrees"
WT="$WTDIR/<id>-$(basename "$REPO" | sed 's/^SkillSpoke-//')"
BRANCH=feat/<id>                      # fix/<id> for a bug

# Branch from the CURRENT tip. A worktree cut from a stale ref silently omits work
# that already landed, and the Red survey then re-authors tests it cannot see.
git -C "$REPO" fetch origin main
# Land what already merged upstream before cutting a tree from it. Preferring
# origin/main as BASE hides the drift; fast-forwarding removes it.
if [ -z "$(git -C "$REPO" status --porcelain)" ] \
   && [ "$(git -C "$REPO" rev-parse --abbrev-ref HEAD)" = "main" ] \
   && git -C "$REPO" merge-base --is-ancestor main origin/main; then
  git -C "$REPO" merge --ff-only origin/main
else
  echo "NOT fast-forwarded: $(git -C "$REPO" rev-list --left-right --count main...origin/main) (left=local ahead, right=behind); report this before dispatching"
fi
BASE=$(git -C "$REPO" rev-parse main)

if ! git -C "$REPO" worktree list --porcelain | grep -q "<id>"; then
  git -C "$REPO" worktree add -b "$BRANCH" "$WT" "$BASE"
fi
```

If a worktree for this bead already exists, **reuse it** — a resumed run must land
in the same tree as the attempt before it, or it cannot see that attempt's tests
and re-authors them. A Task outlives any single agent: if one run does not finish,
a later one picks the same bead up, and it must find the earlier work.

## 5. Dispatch the composite

```
Workflow({scriptPath: "$ROOT/workflows/<composite>.js",
  args: {bead: {id, title, description, repoPath: "$WT"}}})
```

`<composite>` is whatever the router named — `task-to-deploy`, `bug-fix`, or
`infra-change`. Do not substitute your own.

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
