# Pipeline blueprint

The blueprint is the requirements and the design of the pipelines and their tooling: what
they must do and why (requirements), and how they do it (design).

It covers two things that work as one system:

- the `agent-teams-workforce` plugin (this directory's parent): agents, skills, workflows,
  scripts and schemas;
- the driver in `ops/sdlc-automation` of the control repository, which runs the pipelines.

## How it is used

A session reads the blueprint document for an area before it changes that area. A change
that alters what an area must do, or how it does it, updates the document in the same
change. A user-level PreToolUse hook (`~/.claude/hooks/pre-tool-use/blueprint-pointer.sh`)
names the documents for the area to every session that edits a file under the plugin;
`blueprint/areas.json` says which documents cover which area, and changes when an area or a
document is added, renamed or removed. The blueprint states what is required now. Git holds how it got there.

Where a blueprint document and the code or data differ, the document states the requirement
and the code or data is what changes.

## Layout

| Path | Holds |
|---|---|
| `blueprint/requirements/<topic>.md` | What one topic must do and why. No field names, file formats, command names or code structure. |
| `blueprint/design/<topic>.md` | How one topic meets its requirements: structures, formats, commands, the steps that read and write. |
| `blueprint/areas.json` | Which documents state the requirements and design of each area of the plugin, by path pattern. |

One topic per document. A topic has the same file name in both folders.

## Documents

| Topic | Requirements | Design |
|---|---|---|
| The matrix | [requirements/matrix.md](requirements/matrix.md) | [design/matrix.md](design/matrix.md) |
| The pipelines | [requirements/pipelines.md](requirements/pipelines.md) | [design/pipelines.md](design/pipelines.md) (overview and diagrams) |
| The pipelines: elaboration and task decomposition | [requirements/pipelines.md](requirements/pipelines.md), [requirements/matrix.md](requirements/matrix.md) | [design/pipelines-elaboration.md](design/pipelines-elaboration.md) |
| The pipelines: architecture and matrix states | [requirements/matrix.md](requirements/matrix.md) | [design/pipelines-architecture-states.md](design/pipelines-architecture-states.md) |
| The pipelines: build | [requirements/pipelines.md](requirements/pipelines.md) | [design/pipelines-build.md](design/pipelines-build.md) |
| The pipelines: deploy, deploy fix and verification | [requirements/pipelines.md](requirements/pipelines.md) | [design/pipelines-deploy.md](design/pipelines-deploy.md) |
| The pipelines: driver and routing | [requirements/pipelines.md](requirements/pipelines.md) | [design/pipelines-driver.md](design/pipelines-driver.md) |

The pipeline topic's design is split into one diagram document per pipeline, all named
`pipelines-<part>.md` and linked from the parent `design/pipelines.md`, because one document
holding every pipeline's diagrams would be unreadable. Their requirements stay in the one
`requirements/pipelines.md` (with `requirements/matrix.md`).
