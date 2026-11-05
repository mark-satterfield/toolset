# Task decomposition: one repository's Tasks

Code: `orchestrator/flows/task_decomposition.py`, `scripts/portfolio/beadwrite.py`,
`scripts/portfolio/hierarchy.py`.

Under the outermost step "Tasks" each Story bead write plans one container for its repository,
named for the repository, with its first step. Every step below is one step of the Epic's journal.
A step takes each file it reads from the artifacts of the steps its `inputs` name: the repository's
container under "Specs and Stories" hands over the spec documents, the UI sources, the Story
document and the Story; the span step hands over the span and the elements.

## The steps of one repository

| # | Description | Performed by | Reads (artifact) | Writes | Records (artifact) |
|---|---|---|---|---|---|
| 1 | Gather what the Tasks are decomposed from | script `task_decomposition.context` | `story`, `span`, `elements`; the bead tracker | `tasks-<slug>.context.json` | value `repository`, file `task context`; plans steps 2 and 3 |
| 2 | Decompose the Story into Tasks | agent `task-decomposer` | `spec`, `data model`, `criteria`, `story document`, `span`, `elements`, `ui sources` when there are any, `repository context`, `task context` | `tasks-<slug>.json`, checked by `task_decomposition.task_grouping_check` | file `tasks` |
| 3 | Plan the Task beads | script `beadwrite.plan_story_tasks` | `tasks`, `story document`, the spec documents, `span`, `elements` | `tasks-<slug>.gaps.json` (`task-gaps.schema.json`) when the plan has a gap | a plan with a gap: file `task gaps`, value `gaps before the correction`, and steps 4 and 5 planned; otherwise value `task plan` and steps 6 to 9 planned |
| 4 | Correct what the repository builds that no Task cites, and the unsized Tasks | agent `task-decomposer`, continuing the session of step 2 | the inputs of step 2, `tasks`, `task gaps` | `tasks-<slug>.correction.json`, checked by `tasks-correction.schema.json` and for titles that repeat a saved Task's or each other | file `task correction` |
| 5 | Plan the Task beads with the correction | script `beadwrite.plan_story_tasks` | as step 3, and `task correction` | the correction merged into `tasks-<slug>.json` | value `task plan`, and steps 6 to 9 planned; a plan that still has a gap fails the step |
| 6 | Write one Task bead | script `beadwrite.write_task`, one step per Task, in build order | `tasks`, `story document`, the spec documents, `span`, `elements` | the Task bead with no edges; the Task's journal | value `task`, value `task warnings` |
| 7 | Retire the Task beads the plan no longer names | script `beadwrite.retire_superseded_tasks` | as step 6; the bead tracker | bead edges and deletions | value `tasks retired`, value `task warnings` |
| 8 | Set the edges between the Tasks of the Story, at once | script `beadwrite.write_story_task_edges` | as step 6; the bead tracker | one `bd dep add --file -` request, and `bd dep remove` for each edge dropped | value `task edge counts`, value `task warnings` |
| 9 | Record the Tasks written | script `task_decomposition.record` | `story`, `task plan`, every `task`, `task edge counts` and `task warnings` | `tasks-<slug>.written.json` | file `tasks written`, value `tasks result` |

What the Story builds is the `items` of the repository context (`spec-<slug>.context.json`,
`spec-context.schema.json`): the elements the Epic's architecture adds or changes in this
repository (`repo-scoping.md`).

The task context (`task-context.schema.json`, which says what each member holds) names the Tasks
that already exist under the Story and that are started, or that elaboration did not write, so
the decomposer reuses them. It names the stacks the Story builds in with the entries it builds
there; the decomposer itself asks the matrix for the open Tasks of other Epics in those stacks
(`atw-matrix work`), so a Task that needs one of them is blocked by it instead of duplicating it.
A Task cites what it builds by item id; `hierarchy.stated_ids` derives its matrix ids (its stack,
the entries and the shared capabilities that work must use) from those items, and the decomposer
states none. Its `dependsOn`
(`repo_scoping.build_context`) is what the Tasks depend on, never work. A repository-side element
is a hint read from code: it may tell a Task where existing code sits, never what to build.

## The grouping check

The decomposer's Tasks file is checked by `task_decomposition.task_grouping_check`: strict JSON,
then `tasks.schema.json`, then `task_decomposition.duplicate_title_problems` ("Task <key> repeats
the title of Task <key>": no two Tasks of a Story share a title), then
`hierarchy.task_grouping_problems`, which raises `ValueError` with
every problem (a content failure, so the session gets its one correction): when the Story builds
two or more things, each Task that cites exactly one thing: "Task <key> covers one thing: group
the things this Story builds into coherent Tasks".

A Task is a coherent unit of build work, sized on the wsjf skill's scale: one Task covers several
of the things the Story builds, every thing the Story builds is cited by some Task, and it is
never one Task per thing.

A thing the Story builds whose entry carries the verified flag (the span marks its item `state`
`built`) is not work (`hierarchy.work_items`): no Task has to cite it.

A plan has a gap when it holds no Task, a thing the Story builds is cited by no Task, or a
Task has no size. One correction is asked for. A correction that is merged a second time adds
nothing, because its Tasks cite items the first merge covered.

## A stored Tasks file

Steps 3, 5, 6 and 7 read the Tasks file and the corrections the decomposer wrote earlier. Each of
them first checks those files against their current contracts (`task_decomposition.refuse_stale_tasks`):
the Tasks file as the decomposer wrote it by `task_grouping_check`, a Tasks file a correction was
merged into by `tasks.schema.json` and its unique titles, and each correction by
`tasks-correction.schema.json` and its unique titles. A file
passed its check when its writer's step was accepted, so a file the check refuses now was written
to an earlier contract (`StaleInputError`): the step that wrote it (step 2, or the correction) and
every step after it inside its repository's container are set back to planned, and no Task bead
is written from it. Every other repository's container keeps its state, since none reads the file. The writer's next
session is handed what the check found in its earlier output (`tasks-<slug>.json.stale.json`).

## One step per Task bead

Each Task bead write is its own step. A run that stops after a Task is written starts again at the
next Task, and the journal says which Tasks are written.

A write finds the Task under the Story by its elaboration key, and failing that by the items it
cites and by its title. A Task that exists is updated where it differs, or left as it is once
building has started; a second Task is never created, so the step is safe to run again after an
invalidation. It writes no edge.

Once every Task bead of the Story is written, one step sets the Story's edges at once: the Task's
edges onto the Tasks of the same Story it depends on, and a blocker outside the Story
(`blockedByExternal`), written only when the tracker holds that bead; one it does not hold is left
out with a warning. An edge between Tasks of the Story that the saved Tasks no longer name is
removed, and a Task whose build has started is left as it is. It compares with what beads holds, so
it is safe to run again. One read of the edges, one cycle check and one request happen under one
hold of the edge lock.

A journal planned before this step existed has no such step, so `beadwrite.write_all_task_edges`
also writes any edge within a Story that beads lacks; for every other journal it finds nothing.
A Task whose `type` is in the infrastructure vocabulary (`infra-vocabulary.schema.json`), or that
builds a piece of infrastructure, carries the label `infrastructure`, so its build adds the Infra
Intent phase.

A Task's description ends with its build contract. For each event the Task cites, the contract
lists it the way the Story document does: `E<n>: <name>, published by <publishers>:
<trigger>`, from the event item's `trigger` and `publishedBy`.

The same step creates the Task's journal (pipeline `build`) with its first step done and holding
the files `spec`, `data model`, `criteria`, `ui sources` when present, `TRD`, `story document` and
`tasks`, and the value `task key`, the Task's key in the Tasks file.

## Retiring superseded Tasks

When the decomposer's step runs again and its plan no longer names a Task bead that elaboration
wrote earlier (its elaboration key is a `task:` key of the Story) and nobody has started, step 7
deletes that bead. A Task bead under the Story that elaboration did not write is never deleted. Before it does, each `blocks` edge
from a Task of another Story onto it is added onto every written Task that cites an item it cited.
An edge with no such Task is reported as a warning. On a first run the step finds nothing to do.

## The result of a repository

Value `tasks result`: `ok`, `repoPath`, the Story's id and elaboration key, the Tasks written (key,
elaboration key, id, action, title, the keys it depends on, its blockers outside the Story), the
edge counts, the coverage before and after a correction, the warnings and the counts by action.
The done rule and the dispatch result read it from the journal.
