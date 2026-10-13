# The repository span

Code: `orchestrator/flows/repo_scoping.py`, `repo_placement.py`. Checks:
`orchestrator/checks/check_elaboration_dispatch.py` (the items read from the matrix),
`check_repo_trd.py`.

The span is read from the matrix. No session is started. It is the first step of the outermost
step "Specs and Stories": script `atw-matrix prd --closure`.

## What the step reads

- The matrix (`atw-matrix`'s file): the Epic's PRD row, the features it needs, the elements that
  realize them, and everything those elements depend on.
- The repository inventory (`polyrepo inventory`).
- The naming rules of `<control>/.polyrepo/config.yaml`: the name pattern of each repository
  template.

## The items

An item is an element the PRD's features are realized by, or one such an element depends on,
whose code no pipeline has built: an element whose code is `built` or `deployed` is left out. Each
item carries its id, the element's name, the documents that describe it, its repository, and the
items it requires and is required by, from the `dependsOn` links between the elements.

The step fails when the matrix records no element to build for the Epic, when an element has no
repository, or when a repository may hold no product element (the control repository, the
architecture folder, a marketing repository).

## The span

The items are grouped by the repository the matrix places each in. A repository is a frontend
repository when its name matches the frontend template's pattern.

A repository the matrix names and the inventory lacks is created with `polyrepo create`, from the
template its name matches, with the purpose its matrix row states. Before the first creation the
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
