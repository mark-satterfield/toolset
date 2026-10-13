# The pipelines

## What the pipelines are

There are three pipelines. Each works one kind of bead and hands its result to the next.

| Pipeline | Runs once per | Takes in | Produces |
|---|---|---|---|
| Elaboration | Epic | A ready Epic and its PRD | The architecture the PRD needs, the TRD, a Spec and a Story for each repository, and the Tasks under each Story, scored and ordered |
| Build | Task | A Task with its build contract, on its Story's branch | The Task's code and tests committed to the Story's branch, with the repository's whole test suite passing |
| Deploy | Story | A Story whose Tasks are all built | The Story's repository published and deployed to the development environment and verified, the record of what was built, and one merged pull request |

Every unit of work the pipelines do is an Epic, a Story or a Task, and reaches a pipeline
as one of those.

## Bugs

A Bug bead is a report that something is wrong. It is not pipeline work, and the driver
does not dispatch it: both routers skip a Bug and say why.

A person triages a Bug into an Epic, a Task, or a closure. The Epic or Task it becomes is
then pipeline work like any other.

A build that finds a defect fixes it in that run.

## Composites

A composite is a named unit a pipeline dispatches. The contracts declare every composite:
its name, what runs it, its phases and the pipeline role it plays.

Every composite the contracts declare has a workflow script, or is run by the orchestrator
or the driver as the contracts state. A composite that nothing runs is not declared.
