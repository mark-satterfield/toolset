# Unattended-mode routing policy

How the ready queue is drained: each tick claims the next ready bead, asks
the router that owns its kind of work — [`route-build`](route-build.js) for a Task or Bug, [`route-elaboration`](route-elaboration.js) for an Epic, Story, or feature — which composite owns it, runs that composite, reports,
and moves on. This file is the human-readable policy; each router is its
executable form. Keep them in sync — edit both when the policy changes.

**The tick is driven from OUTSIDE this folder. Do not look here for a sweep or
driver script: there is none, and there cannot be one — see
[The driver is not a workflow script](#the-driver-is-not-a-workflow-script)
before writing one.**

## The four composites

| Composite | Front-end | For |
|---|---|---|
| `prd-to-spec` | prd-reconciliation → prd-validation → architecture → repo-scoping → trd-authoring → spec-authoring → task-decomposition → emit-beads | a feature with no implementation-ready contract yet. Reconciliation runs FIRST and before any gate: a PRD whose requirements already ship is closed, a delta that is really a defect or an infrastructure switch is rerouted to `bug-fix` / `infra-change`, and everything that continues is specified against the DELTA PRD. The repo span is RULED by `repo-scoping` after the architecture decision — it is an output of the run, recomputed every time and never pre-staged; a repository the work needs and the project does not have comes back as a human action, never created here. The final phase WRITES the Epic → Story → Task hierarchy into beads itself, parent before child, and reports what landed on `emissionOk` / `beadsEmitted` / `emission` — the caller does not run `bd` for it. It also RETIRES the stand-in roll-up Stories the Epic was carrying: a Task that reached the build lane parentless had one minted for it on the side, and once this run authors the Spec-backed Story that work belongs under, the stand-in's Tasks are re-parented onto a real Story and it is closed. That repair is reported on `emission.heal` and never moves the emission verdict |
| `task-to-deploy` | spec-freshness → red → green → refactor → integration → adversarial → deploy | work whose spec/contract already exists and is implementation-ready |
| `bug-fix` | bug-triage → shared tail | a defect/regression in existing behavior |
| `infra-change` | infra-intent → shared tail (subset) | an infrastructure/provisioning change (CDK/IaC, AWS resources, deploy plumbing) |

## Type / label → composite

Routing is **deterministic first**: each router decides from `bead.type` and
`bead.labels` alone, with no agent in the loop. The **first matching rule wins**, so
the table is ordered. Labels can override the base type — an explicitly-labelled
bead is never mis-typed.

| # | Condition (type, or any label) | Composite |
|---|---|---|
| 1 | type `bug`; or label `bug` / `defect` / `regression` / `hotfix` | `bug-fix` |
| 2 | type `infra` / `infrastructure`; or label `infra` / `infrastructure` / `cdk` / `iac` / `provisioning` | `infra-change` |
| 3 | label `spec` / `spec-ready` / `implementation` / `implement` / `task-to-deploy` | `task-to-deploy` |
| 4 | type `feature` / `epic` / `story`; or label `feature` / `prd` / `requirement` / `prd-to-spec` | `prd-to-spec` |
| 5 | type `chore` / `docs` / `task` / `research` / `spike` | **SKIP** |
| 6 | anything else (unknown / unlabelled) | ambiguity classification, else **SKIP** |

Notes on order:

- **Bug and infra are checked before feature.** A bead can carry both a base
  `feature` type and a `bug`/`infra` label; the more specific kind wins.
- **Spec-ready (rule 3) is checked before feature (rule 4)** on purpose. A
  feature that *already* has an implementation-ready spec skips prd-to-spec
  re-derivation and goes straight to the build-and-deploy tail. Without a
  `spec*`/`implementation` label, a feature falls through to rule 4 and runs
  prd-to-spec first.

### Ambiguity (rule 6)

When type and labels match nothing, the router does **not** guess. By policy it
SKIPs. Only when `allowAmbiguityAgent` is on (the default) does it ask the
read-only `ambiguity-detector` to classify from the title and description. That
agent authors nothing and never runs the composite — it only returns a pick and a
confidence. The router applies the verdict defensively:

- a **confident pick of one of the four composites** is dispatched;
- **`skip`, low confidence, or any unexpected value** is a reported SKIP.

Set `allowAmbiguityAgent: false` to force a deterministic-only pass — genuinely
ambiguous beads then SKIP without spawning an agent.

## What `/loop` skips — and that skips are reported, never force-fit

A SKIP is a `null` composite from either router, carrying a `reason`. `/loop`
**reports every skip** (bead id + reason) and moves to the next ready bead. It
does **not** force an unmatched bead into the nearest-looking composite — a
mis-route costs more than a skip. Beads are skipped when they are:

- an **out-of-pipeline kind** — `chore`, `docs`, `task`, `research`, `spike`
  (rule 5). These are real work, just not work this pipeline automates.
- **unclassifiable** — type/labels match nothing and the ambiguity agent could
  not confidently route them (rule 6).

A skipped bead is left in the ready queue (its status is untouched). The operator
sees the reported reason and decides: relabel it so it routes, handle it manually,
or leave it. Routing is **advisory triage**, not a state mutation — the routers
reads a bead and returns a decision; it never closes, claims, or relabels.

To make a skipped bead route, give it a type/label from the table above — e.g.
add a `bug` label to a defect filed as a plain `task`, or a `spec-ready` label to
a feature whose contract already exists.

## How `/loop` self-paces — "until `bd ready` is empty"

`/loop` runs **self-paced** (no fixed interval): it works as fast as each
composite completes and stops on a queue condition, not a clock. Every step below is
performed by the SESSION — `bd` through Bash, the composite through the Workflow tool.
None of it is a script in this folder. One tick:

1. **Check the queue.** Run `bd ready`. If it is empty, **stop** — the loop is done.
2. **Claim the next bead.** Take the top ready bead and mark it in-progress
   (`bd update --status` / claim), so a second runner can't grab the same bead.
3. **Route it.** Call `route-build` with `{ bead }` for a Task, Bug, or Infra bead; call `route-elaboration` with `{ bead, humanInitiated }` for an Epic, Story, or feature. Neither reads `childCount`.
   - composite is non-null → run that composite on-demand, dispatched by path
     (`Workflow({ scriptPath: 'plugins/agent-teams-workforce/workflows/<composite>.js', args: { bead } })`).
   - composite is null → **report the skip** (id + reason) and leave the bead's
     status as it was.
4. **Report the outcome** — composite result, or the skip reason.
5. **Loop.** Go back to step 1.

The terminating condition is **`bd ready` empty**, not a tick count. Skipped beads
do not block the loop (they're reported and stepped over), and they do not falsely
empty the queue (their status is untouched, so they remain visible to the
operator). The loop ends only when no claimable, routable work remains.

## The driver is not a workflow script

The loop above is a description of what a DRIVER does. Nothing in this folder
implements it, and adding a `sweep.js` here would not work.

**The Workflow runtime permits one level of nesting.** A leaf mini calls `agent()`
and returns an artifact; a composite calls `workflow()` to stitch minis together.
That is the one level, and it is already spent: `bug-fix` calls `tdd-red`,
`prd-to-spec` calls `spec-authoring`, and so on. A sweep script that read `bd ready`
and called `workflow('bug-fix')` per bead would be sweep → composite → mini, which is
two levels, and the runtime throws. This is not a limitation to work around; it is why
composites stay flat and why a full run is sequenced from outside rather than by
nesting one composite inside another (see `AGENT-TEAMS-WORKFORCE.md`, "The doctrine is
realized as `Workflow` scripts of two kinds").

So the driver is a caller of the Workflow tool, never a workflow script. Two exist:

| Driver | What it is | When it drives |
|---|---|---|
| **The orchestrating session** (`/loop`, or `/agent-teams-workforce:next-task` / `:work-bead` one bead at a time) | A Claude Code session running the loop below with the Workflow tool | Interactive and semi-attended work |
| **`ops/sdlc-automation` in the SkillSpoke repo** | A Python supervisor that claims beads, dispatches headless sessions, and journals every run | Long unattended campaigns |

The consequence is worth stating plainly: **"unattended" is only as unattended as
whatever is driving it.** A `/loop` sweep stops when its session stops. The Python
supervisor is the one that survives a session ending, and it is not part of this plugin.

### Both run modes use the same composites

- **On-demand:** `Workflow({ scriptPath: '.../workflows/bug-fix.js', args: { bead } })`
  (etc.) for a chosen bead — the operator picks the composite.
- **Unattended:** `/loop` self-paces over `bd ready`, using `route-build` to pick
  the composite per bead. Same composites, same minis — only the selection differs.

### Dispatch by path, not by name

Both modes dispatch with `scriptPath`. Dispatch by bare `name` resolves the
composite against the **registry snapshot taken at session start**, and that
snapshot goes stale the moment a workflow script changes on disk.

The failure is silent in both directions. A long-running session keeps executing
the revision that existed when it began, so a fix landed mid-session never takes
effect; and the tool call records only the name, so nothing afterwards can
establish which revision actually ran. A run that looks reproducible is not.

`scriptPath` pins the artifact under execution, and `resumeFromRunId` continues
a run whose revision is already pinned. Name dispatch is refused by
`pre-tool-workflow-dispatch-guard.cjs`, which detects the stale-snapshot form
and names the path-pinned replacement.
