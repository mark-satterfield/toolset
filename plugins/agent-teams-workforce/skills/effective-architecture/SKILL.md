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

Approved design (an `effective` document, as "Lifecycle" below defines it) is not evidence that
anything is built, and it is not a permanent constraint on a later PRD: it iterates.

The matrix records which architecture is approved and which is verified, as plain yes/no marks
that name no Epic. Read it as the `matrix` skill says.

## Lifecycle, the baseline and iteration

This section is the one home of these rules. Every other skill and agent that needs them points
here instead of restating them.

### Lifecycle

An architecture document (arc42 or `detailed/`) is in one of two working states, `in-review` or
`effective`; the other `lifecycle_state` values the vault uses, such as `superseded` or
`withdrawn`, keep their meaning. Approve is an action, not a state between the two.

| From state | Action | To state |
|---|---|---|
| any, or none (a new document) | the architect writes, changes or replaces the document | `in-review` |
| `in-review` | the architect approves it | `effective` |
| any, or none | the architect writes it and approves it in the same step, with no gap between them | `effective` |

A matrix entry or relationship goes through the
same states by the same actions: a changed entry is unapproved until the architect approves it.
The `matrix` skill ("Approved, verified, effective and side") says how its `approved` mark
records that.

### The starting baseline

The arc42 documents are approved in advance as a baseline covering all Epics, so that work goes
faster: they are `effective`. On purpose, the matrix shows none of their entries with the
`approved` mark. Each must be reviewed and approved through an Epic's elaboration, not assumed
correct; any of them may contain mistakes. The matrix's `approved` mark records that the solutions architect has reviewed and approved an
entry through some Epic's elaboration; it names no Epic. Two Epics are never elaborated at the
same time on the same unapproved architecture: the dependency edges `epicorder.py` sets in advance
order them.

### Iteration

For every Epic, every arc42 document and every `detailed/` document may be improved, expanded,
modified, replaced or deleted to fulfil that Epic's needs. The architecture is not complete or
perfect in advance: it improves with each Epic, and an Epic may change it substantially, the
first Epics most of all.

- The architect builds on what is `effective`; it does not derive it again from scratch.
- The architect changes an `effective` document whenever the Epic needs that or it finds a
  defect; the change puts the document in `in-review` until the architect approves it.
- An `in-review` document, such as one in `detailed/` that no architect has approved, is a
  candidate to review. When it already matches what the architect would approve, the architect approves it
  (it becomes `effective`) instead of spending tokens recreating it.
- Nothing is deleted merely for being in `in-review` or for carrying no `approved` mark.

Code and infrastructure iterate the same way, as the `software-engineering` skill says.

## The files the team hands on

Each file an agent of the architecture team writes has one schema, in
`${CLAUDE_PLUGIN_ROOT}/skills/artifact-handoff/schemas/`. A definition names its files by
schema file name, for example `architecture-result.schema.json`; read the schema there before
writing the file. Every shape is defined once, in `architecture-result.schema.json`, and the
other schema files refer to it.
