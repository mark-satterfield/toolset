# The repository span

Code: `orchestrator/flows/repo_scoping.py`, `repo_placement.py`.

The span is read from the matrix. No session is started. It is the first step of the outermost
step "Specs and Stories": script `atw-matrix epic --closure`.

## What the step reads

- The matrix (`atw-matrix`'s file): what `atw-matrix epic <id> --closure` returns for the Epic:
  its features, the entries that realize them, everything those entries depend on, and the stack
  that is the home of each, with the stack's repository, app and type.
- The repository inventory (`polyrepo inventory`; `polyrepo inventory --name <name>` for the one
  repository a creation looks up).
- `github_owner` of `<control>/.polyrepo/config.yaml`, for the GitHub membership check before a
  repository is created.

## The items

An item is a stack the Epic's closure reaches, or an architecture-side entry with a home in a
stack that is not verified: a stack that holds an entry, or starts a relationship, that is not
verified may still have to be built. Each item carries its id, its matrix id, its name, the
documents that describe it, its repository, and the items it requires and is required by, from
the dependency relationships between the entries.

The step fails when the matrix records nothing to build for the Epic, when an entry has no stack
or its stack names no repository (`noStack`, `noRepository`; the architect's steward step places
it), or when a repository may hold no product entry (the control repository, the architecture
folder, a marketing repository).

## The span

The items are grouped by the repository the matrix places each in. A repository is a frontend
repository when the type of its stacks is `web`.

A repository the matrix names and the inventory lacks is created with `polyrepo create --space
<the stacks' app> --template <the stacks' type>`; its stacks must have one type and one app. The
tool records the stack the new repository holds, and when the created repository's name differs
from the one recorded the step records it on each stack (`put stack --repository`). Before the
first creation the
step checks that the GitHub CLI is signed in as an active member of the organisation. When it is
not, the step fails with the stage `requires-human-action` and states what the owner must do; the
next dispatch starts at this step again.

## What the step writes and records

| File | Artifact | Content |
|---|---|---|
| `<work>/span-elements.json` | `elements` | the items |
| `<work>/repo-scoping.json` | `span` | one placement per repository: its path, name, item ids and whether it is a frontend repository |
| `<work>/repo-creation.json` | `repository creation` | only when a repository had to be created: what was created and what failed |
| | `repositories` (value) | the repository paths of the span, in order |

## What the step plans

After itself, one container per repository, named for the repository, each with its first step
`spec_authoring.context`. That step is handed the repository's path, its slug, its Story key
(`S1`, `S2`, ...) and whether it is a frontend repository, and the artifacts of the span step and
the TRD step. `spec-authoring.md` describes the steps it plans.
