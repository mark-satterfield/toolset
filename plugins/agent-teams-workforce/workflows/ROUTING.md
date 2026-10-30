# Unattended-mode routing policy

How the ready queue is drained: each tick claims the next ready bead, asks
the router that owns its kind of work — [`route-build`](route-build.js) for a Task, [`route-elaboration`](route-elaboration.js) for an Epic, Story, or feature — which composite owns it, runs that composite, reports,
(a Bug belongs to neither: it is a report awaiting triage, and both routers skip it — see [A Bug is never routed](#a-bug-is-never-routed))
and moves on. This file is the human-readable policy; each router is its
executable form. Keep them in sync — edit both when the policy changes.

**The tick is driven from OUTSIDE this folder. Do not look here for a sweep or
driver script: there is none, and there cannot be one — see
[The driver is not a workflow script](#the-driver-is-not-a-workflow-script)
before writing one.**

## The composites

| Composite | Front-end | For |
|---|---|---|
| `prd-to-spec` | not a workflow script: the Python orchestrator (`orchestrator/run.py`), started by the pipeline's driver. One dispatch claims the Epic and runs the steps of the Epic's step journal from the first that is not done: Open the run → Architecture → TRD → Specs and Stories (one container of steps per repository) → Tasks (one per repository) → Task edges → Score the Tasks → Apply the done rule → Story edges → Mark the Epic elaborated | a feature with no implementation-ready contract yet. It elaborates an existing Epic; the claim refuses, with a named reason, one that is not open, whose elaboration is done, or that another run owns. The driver selects only an Epic that is scored, has a PRD that resolves, waits on no Epic whose elaboration is not done, and is ready, or in progress with no live owner. In the Architecture step `aws-solutions-architect` establishes the architecture the PRD needs in the arc42 documents and has the TRD written; reviewers selected by rule review the unapproved content; a script approves it in the matrix and makes the reviewed documents effective. Nothing in it holds the Epic for a person: the decider rules on every matter, and the architect's specialist recommendations travel in the handback's `toolingRecommendations`. The repository span is read from the matrix: the elements the PRD's features are realized by, and what those depend on, that no pipeline has built, grouped by repository. Per repository, the spec steps write the contracts, the data model and the acceptance criteria, one review settles its findings, and the Story bead is written; the Task steps decompose the Story into sized Tasks, one step per Task bead write (an open Task of another Epic in the same repository that plans the work gets a `blocks` edge instead of a duplicate). Each step writes what it authors into beads itself, keyed by the elaboration key. The Task edges between Stories are written, the Tasks are scored, the done rule requires a Story and Tasks for every repository, and the Epic is marked elaborated. `orchestrator/specs/epic/prd-to-spec.md` describes it. |
| `task-to-deploy` | a workflow script the pipeline's driver dispatches with the Task's step journal. It runs the journal's steps from the first that is not done (`skills/pipeline-contracts/schemas/pipeline-steps.json`, pipeline `build`): workspace (the Story's branch) → infra-intent (an infrastructure Task) → regression scope → baseline suite-run → test agents and a Red check → implementers and a Green check → refactor → documentation → final suite-run → regression evidence → commit | work whose spec/contract already exists and is implementation-ready — the Task's build contract names its repository, its spec documents and the architecture views it is designed against, and the run builds to it without ruling any architecture of its own. An infrastructure Task (a type or label in the infrastructure vocabulary, rule 2 below) runs `infra-intent` first and has `cdk-stack-author` as its Green implementer |
## Type / label → composite

Routing is **deterministic first**: each router decides from `bead.type` and
`bead.labels` alone, with no agent in the loop. The **first matching rule wins**, so
the table is ordered. Labels can override the base type — an explicitly-labelled
bead is never mis-typed.

| # | Condition (type, or any label) | Composite |
|---|---|---|
| 1 | type `bug`; or label `bug` / `defect` / `regression` / `hotfix` | **SKIP** — awaiting triage |
| 2 | a type or label in the infrastructure vocabulary, defined by the `artifact-handoff` skill (`schemas/infra-vocabulary.schema.json`; `scripts/infra_vocabulary.py` prints it, passed as `infraVocabulary`) | `task-to-deploy`, with its Infra Intent phase |
| 3 | label `spec` / `spec-ready` / `implementation` / `implement` / `task-to-deploy` | `task-to-deploy` |
| 4 | type `feature` / `epic` / `story`; or label `feature` / `prd` / `requirement` / `prd-to-spec` | `prd-to-spec` |
| 5 | type `chore` / `docs` / `task` / `research` / `spike` | **SKIP** |
| 6 | anything else (unknown / unlabelled) | ambiguity classification, else **SKIP** |

Notes on order:

- **Bug and infra are checked before feature.** A bead can carry both a base
  `feature` type and a bug label or an infrastructure-vocabulary label; the more specific kind wins. A bug
  identified this way is skipped, not dispatched.
- **Spec-ready (rule 3) is checked before feature (rule 4)** on purpose. A
  feature that *already* has an implementation-ready spec skips prd-to-spec
  and goes straight to the build-and-deploy tail. Without a
  `spec*`/`implementation` label, a feature falls through to rule 4 and is routed
  to prd-to-spec.

### Ambiguity (rule 6)

When type and labels match nothing, the router does **not** guess. By policy it
SKIPs. Only when `allowAmbiguityAgent` is on (the default) does it ask the
read-only `ambiguity-detector` to classify from the title and description. That
agent authors nothing and never runs the composite — it only returns a pick and a
confidence. The router applies the verdict defensively:

- a **confident pick of one of the composites** is dispatched;
- **`skip`, low confidence, or any unexpected value** is a reported SKIP.

Set `allowAmbiguityAgent: false` to force a deterministic-only pass — genuinely
ambiguous beads then SKIP without spawning an agent.

### A Bug is never routed

A bug is a **reporting mechanism**, not a unit of work. It is never worked
directly. Every bug is **TRIAGED** — a judgment call requiring reason and common
sense, made by a person — and becomes an Epic, a Task, or a closure as a
non-defect. Bugs never have parents.

Both routers therefore SKIP a bug, naming triage as the destination:

- `route-build` skips it because it is not development work;
- `route-elaboration` skips it because it is not elaboration work either.

**There is no composite for a bug, by design.** The pipelines are elaboration,
build and deploy, and a Bug bead is work for none of them. The routers stop the
wrong dispatch and report the bug by name every pass — no automation classifies a
bug's outcome, because that classification is the judgment triage exists to make.
A build that finds a defect fixes it in that run.

## What `/loop` skips — and that skips are reported, never force-fit

A SKIP is a `null` composite from either router, carrying a `reason`. `/loop`
**reports every skip** (bead id + reason) and moves to the next ready bead. It
does **not** force an unmatched bead into the nearest-looking composite — a
mis-route costs more than a skip. Beads are skipped when they are:

- a **bug** (rule 1) — a report awaiting triage, not work. See
  [A Bug is never routed](#a-bug-is-never-routed).
- an **out-of-pipeline kind** — `chore`, `docs`, `task`, `research`, `spike`
  (rule 5). These are real work, just not work this pipeline automates.
- **unclassifiable** — type/labels match nothing and the ambiguity agent could
  not confidently route them (rule 6).

A skipped bead is left in the ready queue (its status is untouched). The operator
sees the reported reason and decides: relabel it so it routes, handle it manually,
or leave it. Routing is **advisory triage**, not a state mutation — the routers
reads a bead and returns a decision; it never closes, claims, or relabels.

To make a skipped bead route, give it a type/label from the table above — e.g. a
`spec-ready` label to a feature whose contract already exists. Labelling
something a `bug` does the opposite: it takes the bead OUT of the routed lane and
into the triage queue, which is the correct place for a defect report and the
wrong place for work already decided.

## How `/loop` self-paces — "until `atw-bd ready` is empty"

`/loop` runs **self-paced** (no fixed interval): it works as fast as each
composite completes and stops on a queue condition, not a clock. Every step below is
performed by the SESSION — `bd` through Bash, the composite through the Workflow tool.
None of it is a script in this folder. One tick:

1. **Check the queue.** Run `atw-bd ready`. If it is empty, **stop** — the loop is done.
2. **Claim the next bead.** Take the top ready bead and mark it in-progress
   (`atw-bd update --status` / claim), so a second runner can't grab the same bead.
3. **Route it.** Call `route-build` with `{ bead }` for a Task or Infra bead; call `route-elaboration` with `{ bead, humanInitiated }` for an Epic, Story, or feature. A Bug can be handed to either — both skip it, naming triage. Neither reads `childCount`.
   - composite is `task-to-deploy` → the pipeline's driver dispatches it: the driver opens the Task's
     step journal, names the run, and applies the journal changes the workflow reports while it runs.
     A session dispatches nothing and reports where the Task's journal stands.
   - composite is `prd-to-spec` → dispatch nothing and report it: elaboration is not a workflow
     script, and the pipeline's driver runs it.
   - composite is null → **report the skip** (id + reason) and leave the bead's
     status as it was.
4. **Report the outcome** — composite result, or the skip reason.
5. **Loop.** Go back to step 1.

The terminating condition is **`atw-bd ready` empty**, not a tick count. Skipped beads
do not block the loop (they're reported and stepped over), and they do not falsely
empty the queue (their status is untouched, so they remain visible to the
operator). The loop ends only when no claimable, routable work remains.

## The driver is not a workflow script

The loop above is a description of what a DRIVER does. Nothing in this folder
implements it, and adding a `sweep.js` here would not work.

**The Workflow runtime permits one level of nesting.** A leaf mini calls `agent()`
and returns an artifact; a composite calls `workflow()` to stitch minis together.
That is the one level, and it is already spent: `task-to-deploy` calls `tdd-red`,
`tdd-green` and the other minis. A sweep script that read `atw-bd ready`
and called `workflow('task-to-deploy')` per bead would be sweep → composite → mini, which is
two levels, and the runtime throws. This is not a limitation to work around; it is why
composites stay flat and why a full run is sequenced from outside rather than by
nesting one composite inside another (see `AGENT-TEAMS-WORKFORCE.md`, "The doctrine is
realized as `Workflow` scripts of two kinds").

So the driver is a caller of the Workflow tool, never a workflow script. Two exist:

| Driver | What it is | When it drives |
|---|---|---|
| **The orchestrating session** (`/loop`, or `/agent-teams-workforce:work-bead` one bead at a time) | A Claude Code session that routes a bead and reports where its pipeline stands | Routing, and the workflows a session runs itself (the portfolio workflows, `prd-creation`, `prd-validation`) |
| **An external supervisor the host project provides** | A process that claims beads, opens each bead's step journal, dispatches headless sessions for the build composite and the workflow steps of a Story's deploy, applies the journal changes they report, and starts the Python orchestrator for `prd-to-spec` | Every build, every deploy and every elaboration |

The consequence is worth stating plainly: **"unattended" is only as unattended as
whatever is driving it.** A `/loop` sweep stops when its session stops. An external
supervisor survives a session ending, and it is not part of this plugin.

### A build or a deploy continues from its step journal

`task-to-deploy`, `story-deploy-fix` and `built-version` run the steps of a bead's step journal. A run
that stopped is continued by the next dispatch, which begins at the first step the journal does not
mark done; nothing else decides where a run begins. The workflow reads the journal once, at its start,
and reports each change on its log as a `STEP-JOURNAL` line. After each step is done it also saves
the lines reported since its last save to the run's change log beside the journal
(`bin/atw-step-journal record`), because the harness keeps log lines only in the workflow record it
writes when the workflow ends. The driver applies each line, from the change log and then from the
workflow record, to the journal file with `orchestrator/core/journal_lines.py`, each change once.

### Dispatch by path, not by name

Both modes dispatch with `scriptPath`. Dispatch by bare `name` resolves the
composite against the **registry snapshot taken at session start**, and that
snapshot goes stale the moment a workflow script changes on disk.

The failure is silent in both directions. A long-running session keeps executing
the revision that existed when it began, so a fix landed mid-session never takes
effect; and the tool call records only the name, so nothing afterwards can
establish which revision actually ran. A run that looks reproducible is not.

`scriptPath` pins the artifact under execution.
