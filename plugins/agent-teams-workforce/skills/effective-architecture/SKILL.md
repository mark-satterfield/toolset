---
name: effective-architecture
description: The one set of criteria that the solutions architect works to and reviews and approves its architecture against, and the spec review checks the specs against, with the level of each.
---

# Architecture criteria

Read [the review standard](review-standard.md) before designing, writing, reviewing or
ruling on architecture, a TRD or a spec. It is the common basis: the solutions architect
develops the architecture, its detailed design and the TRD to exactly these criteria and
reviews and approves them against exactly these and no others; nothing else reviews the
architecture. The spec authors develop the specs to them, and the spec review
(`spec-reviewer`) checks the specs against the specs-and-Tasks level. Each level
of the standard names the agent that reviews and approves it. Criterion P10 requires the proof
that no decision was made by instinct, recorded in the Epic's review log (the
`log-architecture-review` skill). It is the one text of the criteria an agent reads; no brief
hands the criteria as an input. `review-criteria.json` beside it is the pipeline's data, read by
the scripts only: each criterion's id, level, home document and text, and for each level the
agents responsible for it and the agent that reviews and approves it. The standard is written
from that file by `artifact-handoff/scripts/review_criteria.py`, so a criterion is changed in
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
