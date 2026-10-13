---
name: elaborate-prd-epic
description: >-
  How a PRD/Epic is elaborated into the TRD, the Spec(s), and the Story and Task
  beads beneath it, who runs that, and how to read what a run wrote. Use after
  resolving a PRD/Epic pair from either end — a PRD document via
  /agent-teams-workforce:start-prd, or an Epic bead via
  /agent-teams-workforce:work-bead — to report where the Epic's elaboration stands.
allowed-tools: [Read, Bash, Glob]
---

# Elaborate a PRD/Epic

The pipeline elaborates an Epic and reads the PRD linked to it; the two are created
together. Nothing decomposes the Epic. The **file** side decomposes — PRD to TRD to
Spec — and the beads are what that chain deposits: one Story per Spec, Tasks per
Spec. The Epic is the container they land under.

## Who runs elaboration

Elaboration, `prd-to-spec`, runs in the Python orchestrator
(`${CLAUDE_PLUGIN_ROOT}/orchestrator/run.py prd-to-spec`). The pipeline's driver starts it: the
driver's elaboration lane selects an Epic, builds the dispatch arguments (the Epic, its PRD, the
architecture root, the design system), starts the orchestrator as a child process, and reads
its handback file. `orchestrator/specs/epic/driver-contract.md` describes that boundary.

No command, skill or workflow dispatches elaboration, and a session does not start the
orchestrator or the driver. This skill dispatches nothing: it reports where an Epic's
elaboration stands and what a run wrote.

## What makes an Epic eligible

The driver selects an Epic that is open, has a PRD that resolves, carries a WSJF score, has no
unmet prerequisite, and whose elaboration state is ready, or in progress with no live run owning
it (`orchestrator/specs/epic/driver-contract.md` §2). The Epic's elaboration state, its values,
and the keys that record who set it, when and why are bead metadata defined in one place: the
`LANE_KEYS` group of the JSON Schema `schemas/bead-metadata.schema.json` in the
`agent-teams-workforce:beads-contract` skill. Read them there, and read an Epic's values with
that skill's `metadata get`; this skill restates none of them.

A dispatch claims the Epic before it runs a step. The claim is refused, with
`stage: epic-lifecycle` and a `refusal` naming the code, when:

| Code | Meaning | What unblocks it |
| --- | --- | --- |
| `not-an-open-epic` | the id names no open Epic | Pass the right Epic |
| `epic-done` | its elaboration is already finished | A person sets its elaboration state back to in progress to elaborate again |
| `epic-owned` | in progress under another run's owner token | The driver reclaims it once that run is known not to be live |

## What a dispatch does

One dispatch is one pass over the Epic's step journal,
`<control repository>/.claude/workflow-runs/step-journals/<epic id>.step-journal.json`. The
journal lists the steps; a dispatch starts at the first step that is not done, and nothing else
decides where it begins. The outermost steps are Open the run, Architecture, TRD, Specs and
Stories, Tasks, Task edges, Score the Tasks, Apply the done rule, Story edges and Mark the Epic
elaborated. `orchestrator/specs/epic/prd-to-spec.md` describes the dispatch, and the documents
beside it describe each part.

The repository span is not an input: the span step reads it from the matrix, from the elements
the PRD's features are realized by and what those depend on, and creates a repository the
matrix names and the inventory lacks.

An earlier start is made only when the owner asks for it; the named step and every step after it
are then set back to planned in the journal.

## Read what a run wrote — do NOT write it yourself

The run writes the hierarchy into beads itself, each part in the step that authors it: one step
writes each Story under the Epic, one step writes each Task with its judged size and its `blocks`
edges inside the Story, one step writes the `blocks` edges between Tasks of different Stories,
and one step writes the edges between Stories. Every write is keyed by the durable elaboration
key (a `LANE_KEYS` metadata key in the schema above), so a Story or Task that already exists is
updated, never duplicated. Writing any of it again yourself creates duplicates.

Where to read it:

- The journal. `atw-step-journal next --dir <step journals directory> --bead <epic id>` prints the
  step the next dispatch begins at; a failed step holds its structured cause. `artifacts --step
  <id>` prints what a step recorded.
- Beads. The Stories are the Epic's children and the Tasks are each Story's children.
- The run record `<work>/run.json` in the Epic's work directory
  (`<control repository>/.claude/workflow-runs/artifacts/<epic id>/`), which holds the last
  dispatch's result and its sessions.

What the dispatch result holds, each field read from the journal:

- `repoSpan` — the repositories of the span; `createdRepos` — repositories the span step created.
- `hierarchy: {epic, stories, tasks}` — each Story and Task with the `id` and `elabKey` it was
  written under.
- `closureEdges`, `crossStoryDependencies` — the Task edges that cross Stories; `storyEdges` — the
  edges between Stories.
- `beadsEmitted` — how many Stories and Tasks the journal records as written.
- `lifecycleDone` — whether the Epic is marked elaborated. When it is false the Epic's
  elaboration stays in progress and the next dispatch continues at the journal's next step.
- `requiredHumanActions` — what the owner must do, when a step failed at stage
  `requires-human-action`.

Every failure carries `failure: { stage, cause, classification, ... }`. The cause is set where
the failure happens from exit codes and structured fields, never by matching text. A transient
cause is retried by the driver after a pause or a backoff. An ordinary item failure is recorded
and the item is excluded for the driver's current invocation while other eligible work continues.
A setup or pipeline-code defect stops new dispatch. A failed run dispatches no repair or
diagnosis agent.

Report `beadsEmitted` and `lifecycleDone` exactly as recorded; never compose them from your own
account of what you think landed.

## Report

The report contains the following, carried by the caller's schema when one is given:

- Epic: its id, its elaboration state, and whether it is marked elaborated
- PRD: its path
- Where the journal stands: the next step, and a failed step with its cause
- Repo span: the repositories the journal records, and each repository the run created
- Stories: how many, and which repository each covers
- Tasks: how many, and how many dependency edges cross Stories
- That elaboration is run by the pipeline's driver, and that this session dispatched nothing
- When the Epic is elaborated, the next command: `/agent-teams-workforce:next-task`, which claims
  the highest-WSJF Task that is ready
