---
name: effective-architecture
description: The one set of criteria that the solutions architect works to and the reviewers review against, with the level of each.
---

# Architecture criteria

Read [the review standard](review-standard.md) before designing, writing, reviewing or
ruling on architecture, a TRD or a spec. It is the common basis: the solutions architect
develops the architecture, its detailed design and the TRD to exactly these criteria, the spec authors develop the
specs to them, and reviewers apply exactly these and no others. It is the one text of the
criteria an agent reads; no brief hands the criteria as an input. `review-criteria.json` beside
it is the pipeline's data, read by the scripts only: each criterion's id, level, home document
and text, the agents responsible for each level, and for each reviewer group its reviewer, the
criteria it covers and the rule that selects it. A reviewer's review scope names the criterion
ids it reviews against. The standard is written from that file by
`artifact-handoff/scripts/review_criteria.py`, so a criterion is changed in
`review-criteria.json` and nowhere else.

Every criterion has a level: architecture and design (arc42 and the detailed architecture
under `detailed/`), technical requirement (the TRD), or the specs and Tasks. A criterion is
satisfied by the document that is its home. All of the design, from the system context to the
classes, data models, routes and names of one component, is done during architecture and
recorded in the architecture documents and in the matrix; the specs and Tasks carry it and
decide none of it.

An effective document is approved design. It is not evidence that anything is built, and it
is not a permanent constraint on a later PRD.

The matrix records what is approved and what code is trusted. Read it through `atw-matrix`.

## The files the team hands on

Each file an agent of the architecture team writes has one schema, in
`${CLAUDE_PLUGIN_ROOT}/skills/artifact-handoff/schemas/`. A definition names its files by
schema file name, for example `architecture-result.schema.json`; read the schema there before
writing the file. Every shape is defined once, in `architecture-result.schema.json`, and the
other schema files refer to it.
