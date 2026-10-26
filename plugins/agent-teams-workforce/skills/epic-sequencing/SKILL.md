---
name: epic-sequencing
description: >-
  The rule that orders Epics, and how to apply it to ONE Epic. Epic order comes from the matrix
  only: an item two or more Epics need (a feature serving their requirements, or an
  architecture entry they reach by the rule of reach) whose architecture is not approved orders
  them by the judgment recorded for it, a drives relationship from the Epic that goes first
  with basis owns or shared; every other Epic that needs the item waits for that Epic. An item
  with no recorded judgment orders nothing. Use when proposing, reviewing or correcting the
  Epic-to-Epic edges of an Epic.
---

# Epic sequencing

The output is an edge file for one Epic and a written account of the reasoning that
produced it.

## The model

- An Epic has requirements. Requirements are served by features. Features are realized by
  architecture entries (services, components, infrastructure, events, stacks, packages,
  layers), which depend on other entries (calls, reads, publishes, imports and the other
  dependency relationships). No Epic relates directly to another Epic.
- An item is **shared** when two or more Epics need it, whatever repository or name it has.
  `shared-` names a thing sharable at enterprise level, but `SkillSpoke-*` things are often
  shared too. Two Epics need an architecture entry when it realizes a feature serving their
  requirements, or is one dependency hop from such an entry (the rule of reach, the `matrix`
  skill).
- Architecture is not fixed: later Epics may change shared architecture. `approved` and
  `verified` are plain yes/no marks, and nothing is approved yet, by design.
- Epic-to-Epic edges exist so that (1) an Epic waits for the Epic that builds and owns
  something it uses, and (2) two Epics never work on the same unapproved shared item at the
  same time.
- There is no fixed answer. For each shared item, either one Epic builds and owns it and the
  others use it, or the Epics share it independently (like two Epics whose Lambdas both need
  the VPC). That is a judgment made from the Epics' requirements and recorded in the matrix; no
  script infers it from counts or names.

## Where Epic order comes from

The owner sets every Epic's dependencies once, before `keeper.py` runs, with
`scripts/portfolio/epicorder.py`. It reads the Epics, the shared items and the judgments from the
matrix only (`matrixshared.py`). It orders one release at a time (`--release`, for example `mvp-1`): the Epics whose PRD is in that release's folder of the vault (`docs/sdlc/<release>/prds/`). An Epic of another release takes no part:
what it needs makes no item shared, a judgment naming it as the Epic that goes first decides
nothing for the release (the item is unjudged), and no edge is computed to or from it. The report
lists those Epics, the standing edges to or from them and those items.

1. The shared items are listed by `atw-matrix shared-items`: each feature that serves a
   requirement of two or more Epics, and each architecture-side entry two or more Epics reach by
   the rule of reach, with the Epics that need it and the requirements through which each does.
2. An item whose architecture is approved makes no edge. A feature is approved when it is
   `realizedBy` at least one architecture-side entry and every one carries the `approved` mark;
   an entry, when it carries the mark.
3. The judgment for an item is the one architecture-side `drives` relationship from an Epic F
   to the item, with `basis` `owns` (F builds and owns the item; the others use it) or `shared`
   (the Epics share it independently; F merely goes first) and a one-sentence `reason`, made
   from the Epics' requirements (see "Recording judgments").
4. The owner's records stay in force: a `drives` with no basis from Epic F to a stack makes F the
   owner of every shared item realized or homed in that stack; `epicDriver: none` on a stack says
   its items make no edge, because the stack is deployed in advance.
5. Every other Epic that needs a decided item waits for F: one edge from F to each. The edges
   several items make between one pair are one edge. An item with no record makes no edge, and
   the report lists it as unjudged.
6. While the edges hold a loop, one edge inside a loop is dropped: first an edge that only
   `shared` items made, then one an `owns` item made, each time the edge made by the fewest
   items, a tie to the lower bead id. The report lists every dropped edge with both Epics and the
   items. The rest is transitively reduced.

## Recording judgments

`atw-matrix shared-items --batches <folder>` writes the unapproved shared items no record
decides, outside every stack deployed in advance, in batches of about 25 items (items whose sets
of Epics are identical stay in one batch), with `index.json`. Each item carries its id, kind,
name, purpose and stack, and for each Epic that needs it the requirements through which it does;
the batch holds each requirement's text once, under `requirements`. A judge writes one judgment
file per batch (artifact-handoff's `schemas/shared-item-judgments.schema.json`), and
`atw-matrix record-judgments --file <file>` (role `script` or `operator`) records every judgment
of the file, or none when one is refused.

## Applying the order

`epicorder.py --release <release> --apply` removes every Epic-to-Epic dependency edge in beads,
whoever made it, those to or from Epics of other releases included, and writes the computed edges
of the release as `tracks` edges; it refuses to write an edge that names an Epic beads
does not hold. No other step of the pipeline sets or changes an Epic-to-Epic edge.

The `dependency-assessment` workflow, which only the owner runs, applies the same rule to one
Epic (see "Assessing one Epic"). The edges it writes are removed and replaced at the next
`epicorder.py --apply`.

## What the matrix records

The chain is `hasRequirement`, `servedBy`, `realizedBy`, `homeIn` and the dependency
relationships (the `matrix` skill holds the model). The Epic-to-Epic edge is a beads `tracks`
edge and never a matrix relationship. The judgment is a `drives` from an Epic to an item, not
to another Epic.

Only the `approved` mark removes the need for an edge: a document at `lifecycle: effective` or
an entry existing does not. A change to an item clears its `approved` mark and leaves its
`drives` judgment as it is.

## What an edge decides

- **The dependency graph decides ELIGIBILITY**: what may be elaborated at all. An Epic waits
  until the Epic that goes first on every unapproved shared item it needs is elaborated. Each edge is stored
  as a beads `tracks` edge on the waiting Epic. `tracks` is non-blocking, so an Epic edge orders
  elaboration and never holds the Stories or Tasks beneath an Epic out of `atw-bd ready`; their
  build order is their own Task-to-Task `blocks` edges.
- **WSJF decides PRIORITY** among what is eligible, and takes these edges as its input (the
  `agent-teams-workforce:wsjf` rubric, RR-OE).

## The test

Set an edge from A to B exactly when the matrix records a shared item that both A and B need,
its architecture is not approved, its stack is not deployed in advance, and A goes first on it
by its recorded judgment or by the owner's decision for its stack. Nowhere else: not for an
item no judgment decides, not for importance, not for something that must exist, be built, be
deployed or be read first (those are Task dependencies), not because a document names both
Epics, and never by a repository's or stack's name.

## Assessing one Epic

An Epic is assessed only when the owner runs the `dependency-assessment` workflow for it. The
assessment covers every edge to or from that Epic, including each one set earlier.

The matrix is read as the `matrix` skill says. When the assessment is handed a context file
(artifact-handoff's `schemas/dependency-assessment.schema.json`, `#/$defs/EpicContext`), that
file is the material it starts from: its `related` list names the Epics that share an entry with
this one, and its `standing` and `withdrawn` lists are the edges on the Epic.

1. List the shared items the Epic needs: `atw-matrix shared-items --epic <beads id>` returns
   each with the Epics that need it, the requirements through which each does, whether it is
   approved, whether its stack is deployed in advance, and its `decision` (the Epic that goes
   first, the basis, the reason, and whether it is a judgment on the item or the owner's decision
   for its stack). When it lists none, say so in the reasoning and write an edge file with no
   edges.
2. Drop every approved item and every item whose stack is deployed in advance.
3. For each item left with a decision, draw the edges that touch this Epic: when this Epic goes
   first, an edge from it to every other Epic that needs the item; otherwise one edge from the
   Epic that goes first to this Epic. The edges several items make between one pair are one edge.
4. List every item left with no decision in the reasoning as unjudged. It draws no edge.
5. Account for every owned edge standing on the Epic: keep it in the edge file when step 3
   draws it, or withdraw it with a reason (no recorded decision draws it). An edge drawn by hand
   (`owned: false`) is never withdrawn and appears in neither list. An edge an earlier assessment
   withdrew is set again only with `answers`, why the recorded reason is wrong by the rule.
6. Write the edge file and the reasoning (see "The edge file"), then check the file with the
   validation command (`depscore.py validate --edges <file> --epic <id>`) and revise it until
   it passes. A loop through an edge with `owned: false` is reported in the reasoning with the
   failed validation and its findings, not forced.

Applying the edges is not part of the assessment: the assessing agent writes nothing to the
tracker or the matrix, and records no judgment.

## The edge file

The edge file's one definition is artifact-handoff's `schemas/epic-edge-proposal.schema.json`:
its descriptions say what `edges` and `withdrawn` hold and what every member means. A reason
names the item, the Epic that goes first, the basis and the recorded reason, for example
"stack:<stack>: <beads id> goes first, owns (the owner's decision for the stack); its
architecture is not approved". A withdrawal's reason says why the rule does not draw
the edge, for example "the only shared item both Epics need has no recorded judgment".

Alongside the file, write the reasoning in prose: the shared items the Epic needs, for each the
Epics that need it, its approval, its decision, and every edge kept, drawn or withdrawn, and the
unjudged items.

## Checks before handing it over

- Every id is an Epic the matrix holds (`atw-matrix epic <id>`).
- Every edge touches the assessed Epic.
- Every edge carries its `archCheck`: the id of the shared item that makes it, the recorded
  decision that names `from` as the Epic that goes first, and that the item's architecture is
  not approved. The item is needed by both Epics.
- Every owned standing edge is kept or withdrawn, and every edge and withdrawal carries a
  reason.
- No edge onto a closed Epic, and none out of one.

## Errors to avoid

- Adding an edge for anything but a decided, unapproved shared item: an unjudged item,
  importance, a total order, a build fact, a data flow, a document both PRDs mention, or a
  repository's or stack's name.
- Choosing who goes first yourself, or from counts of requirements or Epics. Only a recorded
  judgment or the owner's decision for the stack decides it.
- Leaving out an edge a recorded decision draws because the fan-out looks large.
- Reading approval from anything but the `approved` mark: a document at `lifecycle: effective`
  or an entry existing is not approval.
- Scoring anything. Value and size belong to the `wsjf` rubric, and RR-OE is computed from
  the edges.
