# `prd-to-spec`: elaborate one Epic

Code: `orchestrator/flows/prd_to_spec.py` (the dispatch and the open-run step),
`orchestrator/core/journal_run.py` (the loop), and the flow modules that register the code of each
step.

## What one dispatch does

One dispatch is one operating-system process for one Epic. It:

1. Checks its arguments: the Epic id, `beadsRepoPath` and a PRD file that can be read.
2. Claims the Epic (`elaboration.start`). A refused claim ends the dispatch with the refusal.
3. Opens the Epic's step journal,
   `<control>/.claude/workflow-runs/step-journals/<epic>.step-journal.json`. When the file does not
   exist it is created with every outermost step planned. An existing journal is left as it is.
4. Runs the loop: ask the journal for the next step that is not done, run it, repeat, until no step
   is left or a step fails.
5. Assembles the dispatch result from the journal (`flows/elaboration_result.py`).
6. Releases the claim, unless the journal's last step marked the Epic elaborated.
7. Writes the run record `<work>/run.json` and the handback.

The claim, its release, the run record and the handback belong to the dispatch and are not journal
steps.

## Where a run begins

The journal alone decides. A restart is the same loop on the same file, so it begins at the first
step that has no child steps and is not done. No file content, hash or timestamp is compared, and
no step checks whether an earlier output still exists: a step that reads a missing file fails as
any step fails.

An earlier start happens when the owner asks for it: `atw-step-journal invalidate` sets the
named step and every step after it back to planned, and removes the steps those steps planned. The
driver's `elabmark.py --bead <id> --start-at <step>` does the same through its `journalstart.py`.
The next dispatch runs from that step.

The runner makes an earlier start of its own in one case: a step reads a file an earlier step
wrote, and the file does not satisfy the contract the step reads it by, because the contract
changed after the file was written (`StaleInputError`). The step is not failed; the step that
wrote the file and every step after it are set back to planned, and the run goes on from there.
A helper's request file is written by the step directly above the helper. The same writer named
twice in one dispatch fails the step; when that writer is a script step, the failure is a pipeline
code defect, since its code wrote the file to a contract other than its readers'. The architecture context file, which the open-run step
writes, is not handled this way: a step that finds it written to an earlier contract writes it
again in place to the current one, from the PRD and architecture root the dispatch names and the
vault commit the file recorded, and sets no step back to planned.

A helper's request file is stale only when the session of the step above the helper was made under
another agent definition or contracts, or that step holds no session. When that session is one of
the current agent definition and contracts, the request is its mistake (`MalformedRequestError`):
the runner writes the errors beside the request, continues that session to correct the request
file in place (checked against the request's contract, with one corrective resume), and runs the
helper again. Nothing is set back to planned. The same request malformed twice in one dispatch
fails the helper's step.

A step continues an agent session only when the session's agent definition and contract schemas
are unchanged since it started (their fingerprint, recorded when the session started); otherwise
it starts a new session. A session ended by a timeout is continued by the next dispatch.

## The outermost steps

| # | Description | Performed by | Plans |
|---|---|---|---|
| 1 | Open the run | script `prd_to_spec.open_run` | the pack, the TRD seed, the architect's step, the index and the check under Architecture |
| 2 | Architecture | container | its steps are planned by step 1 and by the steps under it (`architecture.md`) |
| 3 | TRD | script `trd.confirm` | nothing (`trd-authoring.md`) |
| 4 | Specs and Stories | container, created with the span step `atw-matrix epic --closure` | the span step reads what the Epic's architecture adds or changes (the architect's `addedOrChangedElements`) and where the architect says the Epic's work that leaves elements unchanged lands (`unchangedWorkElements`), and plans one container per repository a Story builds in (`repo-scoping.md`, `spec-authoring.md`) |
| 5 | Tasks | container | each Story bead write plans one container for its repository (`task-decomposition.md`) |
| 6 | Task edges | container, created with step `beadwrite.closure_task_edges` | that step plans the listing, the mapper's step and the edge write |
| 7 | Score the Tasks | script `elaboration.score` | nothing |
| 8 | Apply the done rule | script `elaboration.done_rule` | nothing |
| 9 | Story edges | script `storyedges.story_edges` | nothing |
| 10 | Mark the Epic elaborated | script `elaboration.finish` | nothing |

## How a step runs

A step with a `script` is run by the handler registered for that key; a step with an `agent` by the
launch builder registered for that agent (`core/journal_registry.py`). Both are given the step, the
run context, the tools and the artifacts of the steps the step's `inputs` name. An input that has
child steps hands over the artifacts of every step below it. A step reads no earlier output any
other way.

The runner marks the step running before its code or its session starts. When the output is
written and accepted, one journal change records the step's artifacts, adds every step the result
plans, records the parameters of each planned step as the value artifact `for <step id>`, and marks
the step done. A step that raises is marked failed with a structured cause, and the dispatch ends
with that failure.

Steps run in the order the journal lists them. Consecutive sibling steps that each have an agent,
have no child steps and whose inputs are all done run as concurrent sessions, at most
`ATW_ORCH_SESSIONS` at a time. This is how the contracts and data-model authors of one repository
run together. The repositories' containers under Specs and Stories, and under Tasks, run at the
same time, at most `ATW_ORCH_SESSIONS` of them, each running its own steps in order.

## Task edges

| Step | Performed by | Reads | Records |
|---|---|---|---|
| Derive the Task edges the elements' requirements make | script `beadwrite.closure_task_edges` | every repository's Story document, spec documents and Tasks file, the span and the elements | file `closure edges`; fails when a required element has no Task that builds it |
| List the Tasks of every Story for the dependency mapper | script `task_edges.listing` | the Tasks files, `closure edges` | file `task dependency listing` (`task-dependency-listing.schema.json`), which points to each Story's Tasks file and the closure edges |
| Map the dependencies between Tasks of different Stories | agent `task-dependency-mapper`, only when the span has two or more repositories | the Tasks files, `closure edges`, the listing | file `task dependencies` |
| Write the edges between Tasks of different Stories | script `beadwrite.write_all_task_edges` | `task dependencies` when the mapper ran, `closure edges`, the files of every Story | file `task edges written`, value `edges result`; an edge that would close a cycle over the Tasks, or make two Stories depend on each other, is dropped with a warning, and an edge that names no Task of the run, joins one Story or repeats another is rejected with a warning (`beadwrite.plan_task_edges`); each warning is also emitted as a `warning` note |

## Finish

| Step | What it does | Records |
|---|---|---|
| `elaboration.score` | scores the Epic's Tasks without marking the Epic | value `unscored tasks` |
| `elaboration.done_rule` | fails unless every repository of the span (the span step's value `repositories`) has its Story, its Tasks with every thing the Story builds cited, and no Task is unscored | value `done rule` |
| `storyedges.story_edges` | writes the dependency edges between the Epic's Stories | value `story edges` |
| `elaboration.finish` | marks the Epic elaborated | value `lifecycle done` |

## The dispatch result

Every field comes from the journal, so the result is the same whichever dispatch ran a step.

| Field | Source in the journal |
|---|---|
| `ok` | no step is left that is not done |
| `stage` | the script key, agent or description of the next step that is not done; `finish` when none is left |
| `repoSpan` | value `repositories` of the span step |
| `createdRepos` | the `created` list of the file `repository creation` of the span step |
| `hierarchy.stories` | every value `story` (the Story bead write steps) |
| `hierarchy.tasks` | every value `task` (the Task bead write steps) |
| `hierarchy.epic` | the dispatch argument `epic` |
| `beadsEmitted` | the number of those Stories and Tasks |
| `artifacts.dir`, `artifacts.epicId` | the Epic's work directory and id |
| `artifacts.phases` | `trd: passed` when step `trd.confirm` is done and holds the file `TRD`; `spec:<slug>: passed` for each value `story` |
| `artifacts.filing` | `trd.md`: the dispatch argument `trdPath`, once the TRD phase passed |
| `closureEdges`, `crossStoryDependencies` | value `edges result` of step `beadwrite.write_all_task_edges` |
| `storyEdges` | value `story edges` |
| `lifecycleDone` | value `lifecycle done` |
| `requiredHumanActions` | the evidence of a next step that failed with the stage `requires-human-action` |
| `failure` | the cause recorded on the failed step, when this dispatch ran it |

## Story and Task journals

The step that writes a Story bead creates the Story's journal in the same directory, for the
`deploy` pipeline; the step that writes a Task bead creates the Task's journal, for the `build`
pipeline. The first step of each is the creating step itself, done, holding the files the bead's
later steps are handed: the spec documents, the UI sources when the repository has them, the TRD
and the Story document; for a Task also the Tasks file and the value `task key`. A creating step
that runs again replaces the journal it created, unless a later step of that journal has started.
