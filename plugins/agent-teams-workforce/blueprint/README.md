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
change. The blueprint states what is required now. Git holds how it got there.

Where a blueprint document and the code or data differ, the document states the requirement
and the code or data is what changes.

## Layout

| Path | Holds |
|---|---|
| `blueprint/requirements/<topic>.md` | What one topic must do and why. No field names, file formats, command names or code structure. |
| `blueprint/design/<topic>.md` | How one topic meets its requirements: structures, formats, commands, the steps that read and write. |

One topic per document. A topic has the same file name in both folders.

## Documents

| Topic | Requirements | Design |
|---|---|---|
| The matrix | [requirements/matrix.md](requirements/matrix.md) | [design/matrix.md](design/matrix.md) |
