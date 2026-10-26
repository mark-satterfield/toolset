---
name: epic-sequencing
description: >-
  The rule that orders Epics, and how to apply it to ONE Epic. Epic order comes from the matrix
  only: a feature that two or more Epics need (a requirement of each is servedBy it) and whose
  architecture is not approved orders those Epics, and the Epic with the most requirements
  served by it goes first (a tie to the lower bead id); loops are broken automatically. Use
  when proposing, reviewing or correcting the Epic-to-Epic edges of an Epic.
---

# Epic sequencing

The output is an edge file for one Epic and a written account of the reasoning that
produced it.

## Where Epic order comes from

The owner sets every Epic's dependencies once, before `keeper.py` runs, with
`scripts/portfolio/epicorder.py`. It reads the Epics and the chain the matrix records (Epic,
`hasRequirement`, requirement, `servedBy`, feature, `realizedBy`, architecture entry) from the
matrix only. The unit that orders Epics is the feature: no two Epics are elaborated at once on
the unapproved architecture of a feature they both need. Repository names play no part.

1. The Epics that need a feature are the Epics with a requirement `servedBy` it.
2. A feature's architecture is approved when the feature is `realizedBy` at least one
   architecture-side entry and every architecture-side entry it is `realizedBy` carries the
   `approved` mark. A feature realized by nothing is not approved.
3. A feature two or more Epics need whose architecture is not approved makes edges. An approved
   feature makes none, and a feature one Epic needs makes none.
4. The feature's driver is the Epic with the most of its requirements `servedBy` the feature, a
   tie to the lower bead id. The owner's decisions recorded in the matrix come first: a `drives`
   relationship (architecture side) from an Epic to a stack makes that Epic the driver of every
   feature whose realizers are all in that stack, and the stack attribute `epicDriver: none` says
   that no feature whose realizers are all in that stack makes an edge.
5. The driver goes first: one edge from the driver to every other Epic that needs the feature.
6. While the edges hold a loop, the edge inside a loop whose driver has the fewest requirements
   served by the feature that made it is dropped (a tie to the lower bead id), and the report
   lists every dropped edge with both Epics and the feature. The rest is transitively reduced.

With `--apply` it removes every Epic-to-Epic dependency edge in beads, whoever made it, and
writes the computed edges as `tracks` edges; it refuses to write an edge that names an Epic beads
does not hold. No other step of the pipeline sets or changes an Epic-to-Epic edge.

The `dependency-assessment` workflow, which only the owner runs, applies the same rule to one
Epic (see "Assessing one Epic"). The edges it writes are removed and replaced at the next
`epicorder.py --apply`.

## What the matrix records

The rule walks the chain `hasRequirement`, `servedBy`, `realizedBy` (the `matrix` skill holds
the model). No Epic is related directly to another Epic: the Epic-to-Epic edge is a beads
`tracks` edge and never a matrix relationship.

The rule reads one mark: the `approved` mark on a feature's architecture-side realizers (the
`matrix` skill, "Approved, verified, effective and side", says what it means and what clears
it). Only that mark removes the need for an edge: a document at `lifecycle: effective` or an
entry existing does not.

## What an edge decides

- **The dependency graph decides ELIGIBILITY**: what may be elaborated at all. An Epic waits
  until the driver of every unapproved feature it shares is elaborated. Each edge is stored as
  a beads `tracks` edge on the waiting Epic. `tracks` is non-blocking, so an Epic edge orders
  elaboration and never holds the Stories or Tasks beneath an Epic out of `atw-bd ready`; their
  build order is their own Task-to-Task `blocks` edges.
- **WSJF decides PRIORITY** among what is eligible, and takes these edges as its input (the
  `agent-teams-workforce:wsjf` rubric, RR-OE).

## The test

Set an edge from A to B exactly when the matrix records a feature that both A and B need, the
feature's architecture is not approved, and A is its driver by the rule above. Nowhere else:
not for importance, not for something that must exist, be built, be deployed or be read first
(those are Task dependencies), not because a document names both Epics, and never by a
repository's or stack's name.

## Assessing one Epic

An Epic is assessed only when the owner runs the `dependency-assessment` workflow for it. The
assessment covers every edge to or from that Epic, including each one set earlier.

The matrix is read as the `matrix` skill says. When the assessment is handed a context file
(artifact-handoff's `schemas/dependency-assessment.schema.json`, `#/$defs/EpicContext`), that
file is the material it starts from: its `related` list names the Epics that share an entry with
this one, and its `standing` and `withdrawn` lists are the edges on the Epic.

1. List the features the Epic needs: `atw-matrix epic <beads id>` returns its requirements and
   the features each is served by. Count, for each feature, the Epic's requirements served by it.
   When the matrix records no requirement or no feature for the Epic, say so in the reasoning
   and write an edge file with no edges.
2. For each feature, `atw-matrix node <feature id>` returns the requirements that are `servedBy`
   it (a requirement's id names its Epic) and the entries it is `realizedBy`. Count each other
   Epic's requirements served by the feature. Drop every feature only this Epic needs.
3. For each feature left, read the `approved` mark of every architecture-side entry it is
   `realizedBy` (`atw-matrix node <entry id>`). A feature with no realizer, or with one realizer
   without the mark, is not approved. Drop every approved feature.
4. For each feature left, name its driver by the rule in "Where Epic order comes from", step 4,
   the owner's `drives` and `epicDriver: none` decisions on the one stack that holds all its
   realizers included.
5. Draw the edges that touch this Epic: when this Epic is the driver, an edge from it to every
   other Epic that needs the feature; otherwise one edge from the driver to this Epic. The
   edges several features make between one pair are one edge.
6. Account for every owned edge standing on the Epic: keep it in the edge file when step 5
   draws it, or withdraw it with a reason (the feature rule does not draw it). An edge drawn by
   hand (`owned: false`) is never withdrawn and appears in neither list. An edge an earlier
   assessment withdrew is set again only with `answers`, why the recorded reason is wrong by
   the rule.
7. Write the edge file and the reasoning (see "The edge file"), then check the file with the
   validation command (`depscore.py validate --edges <file> --epic <id>`) and revise it until
   it passes. A loop through an edge with `owned: false` is reported in the reasoning with the
   failed validation and its findings, not forced.

Applying the edges is not part of the assessment: the assessing agent writes nothing to the
tracker or the matrix.

## The edge file

The edge file's one definition is artifact-handoff's `schemas/epic-edge-proposal.schema.json`:
its descriptions say what `edges` and `withdrawn` hold and what every member means. A reason
names the feature and the requirement counts, for example "feature:sign-in-identifier-first-on-a-new-device:
ssbd-b41b has 3 requirements served by it, ssbd-guuuz 1; its architecture is not approved". A
withdrawal's reason says why the rule does not draw the edge, for example "the only feature both
Epics need has every realizer approved".

Alongside the file, write the reasoning in prose: the features the Epic needs, for each shared
feature the Epics that need it with their requirement counts, its realizers and their
`approved` marks, its driver and how the driver was decided, and every edge kept, drawn or
withdrawn.

## Checks before handing it over

- Every id is an Epic the matrix holds (`atw-matrix epic <id>`).
- Every edge touches the assessed Epic.
- Every edge carries its `archCheck`: the id of the feature that makes it, and that the feature's
  architecture is not approved (the realizer without the `approved` mark, or that it has no
  realizer). That feature is needed by both Epics and has the edge's `from` as its driver.
- Every owned standing edge is kept or withdrawn, and every edge and withdrawal carries a
  reason.
- No edge onto a closed Epic, and none out of one.

## Errors to avoid

- Adding an edge for anything but a shared feature whose architecture is not approved:
  importance, a total order, a build fact, a data flow, a document both PRDs mention, or a
  repository's or stack's name.
- Leaving out an edge the rule draws because the fan-out looks large.
- Reading approval from anything but the `approved` mark on the feature's realizers: a document
  at `lifecycle: effective` or an entry existing is not approval.
- Choosing a driver by judgment. The driver is the Epic with the most requirements served by
  the feature, a tie to the lower bead id, unless a `drives` relationship or `epicDriver: none`
  on the stack that holds all its realizers decides it.
- Scoring anything. Value and size belong to the `wsjf` rubric, and RR-OE is computed from
  the edges.
