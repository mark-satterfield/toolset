---
name: architecture-baseline
description: The one set of criteria that the architecture, the TRD and the specs are written to and the reviewers review against, with the level of each.
---

# Architecture criteria

Read [the review standard](review-standard.md) before designing, writing, reviewing or
ruling on architecture, a TRD or a spec. It is the common basis: the architecture, the TRD
and the specs are developed to exactly these criteria, and reviewers apply exactly these and
no others. `review-criteria.json` beside it holds the same criteria as data: each criterion's
id, level, home document and text, the agents responsible for each level with its review
point, and the criteria each reviewer covers. The standard is written from that file by
`artifact-handoff/scripts/review_criteria.py`, so a criterion is changed in
`review-criteria.json` and nowhere else.

Every criterion has a level: architecture (arc42), technical requirement (the TRD) or
implementation (the specs and Tasks). A criterion is satisfied by the document that is its
home. Nobody asks a document for detail below its level.

An effective document is approved design. It is not evidence that anything is built, and it
is not a permanent constraint on a later PRD.

The matrix records what is built and deployed. Python reads it; built state is taken from
the matrix and from nowhere else.
