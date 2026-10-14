# The repository span

Code: `orchestrator/flows/repo_scoping.py`, `repo_placement.py`.

The span is what the Epic's Stories build, grouped by repository. A Story is one repository's
share of what the Epic's architecture adds or changes. No session is started. The span is the
first step of the outermost step "Specs and Stories"; its script key is still
`atw-matrix epic --closure` (renaming it needs a journal migration).

## What the step reads

- The architect's result: `architecture_files.read_result(run, read_context(run))`, the file
  `<work>/architecture/result.json` that `<work>/architecture/context.json` names as
  `resultPath`. The one field read is `addedOrChangedElements`: the matrix ids of every service,
  component, piece of infrastructure and event the design adds or changes for the Epic. The TRD
  is not read here; its requirements reach every Story because the spec authors and reviewers
  are handed the TRD file.
- The matrix (`atw-matrix`'s file), used only to find each item's stack on the architecture side
  (`matrixtraverse.authority_holder`) and that stack's repository, the documents that describe
  it (`describedBy`), the architecture-side publishers of an event, and the architecture-side
  dependency relationships between the items.
- The project's naming rules (`.resource-naming.yaml`, resource `repository` from
  `stackName`), for the repository of a stack that names none.
- The repository inventory (`polyrepo inventory`; `polyrepo inventory --name <name>` for the one
  repository a creation looks up).
- `github_owner` of `<control>/.polyrepo/config.yaml`, for the GitHub membership check before a
  repository is created.

## What the Story builds

`story_build_entries` is the result's ids, plus, for each event among them, the services and
components the architecture side says publish it: an event is a fact with a meaning (its name,
its publisher and when it is triggered) and is built as part of the service that publishes it,
never as a Story or Task of its own. Each entry becomes one item (`story_builds`): its id
(`E<n>`), its matrix id, its name, the documents that describe it, kind `implementation-gap`, the
repository of the stack the architecture side places it in (`authority_holder`: for an event, the
one stack its publishers are homed in), the evidence `[<matrix id>, "architecture result"]`, and
the items it requires and is required by. `requires` is the other items its dependency-family
relationships on the architecture side reach directly; a repository-side relationship never makes
a `requires`, and a dependency on something no Story builds is context, not an item.

Everything else the Epic reaches in the matrix is context: the Tasks are handed it as what they
depend on or use (`task-decomposition.md`), never as work.

## Failures

`story_build_problems` reports, one sentence each, a text that is not a matrix id, and an entry
of `story_build_entries` that the matrix lacks, that is not on the architecture side, whose kind
is not service, component, infrastructure or event, that is an event with `externalSource`
(SkillSpoke does not build it), that the architecture side places in no stack (for an event:
its publishers are homed in no stack, or in more than one), or whose stack's `app` is
`marketing`. The architect's step refuses such a result (`architecture.md`); the span raises the
same problems again as a backstop. The step also fails when the architecture adds or changes
nothing to build ("the architecture adds or changes nothing to build for <bead>"), and when a
repository may hold no product entry (the control repository, the architecture folder, a
marketing repository).

## The span and a missing repository

The order is fixed, and only the stacks of what the Stories build are reached:

1. The items are built (`story_builds`).
2. A stack that names no repository is given the name the naming rules give it
   (`repository_name`: `atw-naming name repository --stack-name <stack name>` in the stack's
   app, imported, not run through a shell; for `stack:skillSpoke-sms-service` it is
   `SkillSpoke-sms-service`, never the raw stack name), written on the stack as its `repository`
   on the architecture side in one matrix change, so the stack, the steward's manifest and the
   created repository carry one name.
3. The items are grouped by repository (`repository_stacks`), and `_ruling` looks each name up in
   the inventory. A repository is a frontend repository when the type of its stacks is `web`.
4. Each name the inventory lacks becomes a missing repository (`_missing`): its stacks must have
   one type and one app, and never `marketing`.
5. `create_repositories` checks once that the GitHub CLI is signed in as an active member of the
   organisation, then runs `polyrepo create <name> --space <app> --template <type>`. When the
   check fails, the step fails with the stage `requires-human-action` and states what the owner
   must do; the next dispatch starts at this step again.
6. When the created repository's name differs from the one recorded, the step records it on each
   stack (`put stack --repository`).
7. Only then are the spec steps planned.

A stack arc42 names that has no repository, and in which no Story builds, is never touched.

## What the step writes and records

| File | Artifact | Content |
|---|---|---|
| `<work>/span-elements.json` | `elements` | the items of what the Stories build |
| `<work>/repo-scoping.json` | `span` | one placement per repository: its path, name, item ids and whether it is a frontend repository |
| `<work>/repo-creation.json` | `repository creation` | only when a repository had to be created: what was created and what failed |
| | `repositories` (value) | the repository paths of the span, in order |

## What the step plans

After itself, one container per repository, named for the repository, each with its first step
`spec_authoring.context`. That step is handed the repository's path, its slug, its Story key
(`S1`, `S2`, ...) and whether it is a frontend repository, and the artifacts of the span step and
the TRD step. `spec-authoring.md` describes the steps it plans.
