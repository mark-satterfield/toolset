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
| 1 | Gather what the Tasks are decomposed from | script `task_decomposition.context` | `story`, `span`, `elements`; the bead tracker | `tasks-<slug>.context.json`, `tasks-<slug>.items.json` | value `repository`, file `task context`, file `what the story builds`; plans steps 2 and 3 |
| 2 | Decompose the Story into Tasks | agent `task-decomposer` | `spec`, `data model`, `criteria`, `story document`, `span`, `elements`, `ui sources` when there are any, `task context`, `what the story builds` | `tasks-<slug>.json`, checked by `task_decomposition.task_grouping_check` | file `tasks` |
| 3 | Plan the Task beads | script `beadwrite.plan_story_tasks` | `tasks`, `story document`, the spec documents, `span`, `elements` | `tasks-<slug>.gaps.json` when the plan has a gap | a plan with a gap: file `task gaps`, value `gaps before the correction`, and steps 4 and 5 planned; otherwise value `task plan` and steps 6 to 8 planned |
| 4 | Correct what the repository builds that no Task cites, and the unsized Tasks | agent `task-decomposer`, continuing the session of step 2 | the inputs of step 2, `tasks`, `task gaps` | `tasks-<slug>.correction.json` | file `task correction` |
| 5 | Plan the Task beads with the correction | script `beadwrite.plan_story_tasks` | as step 3, and `task correction` | the correction merged into `tasks-<slug>.json` | value `task plan`, and steps 6 to 8 planned; a plan that still has a gap fails the step |
| 6 | Write one Task bead | script `beadwrite.write_task`, one step per Task, in build order | `tasks`, `story document`, the spec documents, `span`, `elements` | the Task bead; the Task's journal | value `task`, value `task edge counts`, value `task warnings` |
| 7 | Retire the Task beads the plan no longer names | script `beadwrite.retire_superseded_tasks` | as step 6; the bead tracker | bead edges and deletions | value `tasks retired`, value `task warnings` |
| 8 | Record the Tasks written | script `task_decomposition.record` | `story`, `task plan`, every `task`, `task edge counts` and `task warnings` | `tasks-<slug>.written.json` | file `tasks written`, value `tasks result` |

`what the story builds` (`tasks-<slug>.items.json`) is the items of what the Story builds: the
elements the Epic's architecture adds or changes in this repository (`repo-scoping.md`).

The task context lists the Tasks that already exist under the Story and that are started, or that
elaboration did not write, so the decomposer reuses them; and the open Tasks of other Epics in the
same repository (`stackWork`), so a Task that needs one of them is blocked by it instead of
duplicating it. It also holds `sharedCapabilities`, and `dependsOn`
(`repo_scoping.build_context`): for each thing the Story builds, each relationship of
`BUILD_DEPENDENCY_KINDS` that starts at it and ends at something the Story does not build, as
`{from, kind, to, toKind, side, stack, repository, builtBy}`, where `side` is the relationship's
side, `stack` is the far end's architecture-side stack for an architecture-side entry and the
stack the repositories hold it in for a repository-side one, and `builtBy` is the `storyKey` of
another Story of this Epic that builds the far end, or null. These are what the Tasks depend on,
never work. A repository-side element is a hint read from code: it may tell a Task where
existing code sits, never what to build.

## The grouping check

The decomposer's Tasks file is checked by `task_decomposition.task_grouping_check`: strict JSON,
then `tasks.schema.json`, then `hierarchy.task_grouping_problems`, which raises `ValueError` with
every problem (a content failure, so the session gets its one correction): when the Story builds
two or more things, each Task that cites exactly one thing: "Task <key> covers one thing: group
the things this Story builds into coherent Tasks".

A Task is a coherent unit of build work, sized on the wsjf skill's scale: one Task covers several
of the things the Story builds, every thing the Story builds is cited by some Task, and it is
never one Task per thing.

A plan has a gap when it holds no Task, a thing the Story builds is cited by no Task, or a
Task has no size. One correction is asked for. A correction that is merged a second time adds
nothing, because its Tasks cite items the first merge covered.

## One step per Task bead

Each Task bead write is its own step. A run that stops after a Task is written starts again at the
next Task, and the journal says which Tasks are written.

A write finds the Task under the Story by its elaboration key, and failing that by the items it
cites and by its title. A Task that exists is updated where it differs, or left as it is once
building has started; a second Task is never created, so the step is safe to run again after an
invalidation. A Task's edges onto the Tasks of the same Story it depends on are written with it,
which is why the steps run in build order.

A Task's description ends with its build contract. For each event the Task cites, the contract
lists it the way the Story document does: `E<n>: <name>, published by <publishers>:
<trigger>`, from the event item's `trigger` and `publishedBy`.

The same step creates the Task's journal (pipeline `build`) with its first step done and holding
the files `spec`, `data model`, `criteria`, `ui sources` when present, `TRD`, `story document` and
`tasks`, and the value `task key`, the Task's key in the Tasks file.

## Retiring superseded Tasks

When the decomposer's step runs again and its plan no longer names a Task bead that elaboration
wrote earlier and nobody has started, step 7 deletes that bead. Before it does, each `blocks` edge
from a Task of another Story onto it is added onto every written Task that cites an item it cited.
An edge with no such Task is reported as a warning. On a first run the step finds nothing to do.

## The result of a repository

Value `tasks result`: `ok`, `repoPath`, the Story's id and elaboration key, the Tasks written (key,
elaboration key, id, action, title, the keys it depends on, its blockers outside the Story), the
edge counts, the coverage before and after a correction, the warnings and the counts by action.
The done rule and the dispatch result read it from the journal.
