---
name: epic-sequencing
description: >-
  The edge test for Epic-to-Epic dependency edges, and how to apply it to ONE Epic: read its
  full PRD, answer the foundation-layer checklist (drives, rests on or not touched for each
  of nine layers) and name the other architecture decisions it drives and rests on, check
  the effective architecture, find the related Epics through the matrix, read the requirements of theirs that bear on each decision, and apply the
  test in both directions. An Epic is a PRD, a business requirement, and an edge is an ARCHITECTURE
  dependency, a judgment about the order in which architecture is established: it exists
  exactly where an architecture decision one Epic rests on should be designed from another
  Epic's requirements first, and the effective architecture does not already settle it. Edges decide
  ELIGIBILITY (what may be elaborated at all); WSJF decides PRIORITY among what is
  eligible, and computes RR-OE from these edges. Use when proposing, reviewing or
  correcting the architecture dependencies of an Epic.
---

# Epic sequencing

The output is an edge file for one Epic and a written account of the reasoning that
produced it.

## What an Epic dependency is

An Epic is a PRD: a business requirement, a WHAT and not a HOW. When an Epic is elaborated,
its architecture is designed, and the design made then becomes part of the effective
architecture that every later Epic is designed against. So the order Epics are elaborated in decides which
requirements each architecture decision is designed from. An edge between two Epics is an
architecture dependency, and it answers one question: **which requirements should this
architecture decision be designed from first?**

The judgment is made before the architecture exists. It takes intuition about what the
architecture could be — which decisions a requirement will force, and whose requirements
are the fuller statement of what each decision must serve. An Epic rests on a decision as
soon as its design will be built on it, however little of the decision it uses.

Build facts are Task dependencies, and they never make an Epic edge. That something must
exist, be built, be deployed or be testable first; that one requirement presumes a user or a
record exists; that one reads data from or calls a capability of another — each of those is
settled among Tasks, which are created after the architecture is settled and carry ordinary
build dependencies of their own.

A decision the effective architecture already settles is designed; no Epic edge is needed
for it. As the effective architecture grows, fewer Epic edges exist.

### Only an `effective` document settles anything

An arc42 document settles a decision when, and only when, the matrix returns its entry with
`lifecycle: effective`. A document at `in-review`, or in any other state, settles NOTHING,
however normatively it is worded and whatever date it carries.

Take the state from the matrix; never infer it. A dated ruling, a MUST, a table of values
and a confident tone are all properties of the wording, and the wording is what an
unreviewed document has most of. The matrix's `lifecycle` mirrors the document's own front
matter, and a document becomes `effective` only through the architecture step of a
`prd-to-spec` elaboration.

What states a decision is found through the matrix, with `atw-matrix`:

```
atw-matrix find --kinds document,constraint,feature --text "<the decision in words>"
atw-matrix node <id>
```

`find` ranks the documents, constraints and features that match the words, and an empty
result means nothing states the decision. `node` returns one entry with its relationships:
a document with its `lifecycle` and headings, a constraint with the document and heading it
is `statedIn`, a feature with the documents and headings it is `describedBy`. Read the
heading the matrix names, in that document and no other, when the entry alone does not say
whether the decision is settled. The arc42 folders, their front matter and section 2 are
not searched for this.

So when a document that bears on a decision is not `effective`, the effective architecture
does not settle that decision, and the edge test proceeds as though the document were
absent. Record the document id and heading you consulted and the `lifecycle` the matrix
returned in the edge's `archCheck`, so a later reader can tell a document that settled the
question from one that only sounded like it did. An assessment that drops an edge by citing
a document that is not `effective` has ordered the Epics on an unchecked claim.

## What an edge decides

- **The dependency graph decides ELIGIBILITY** — what may be elaborated at all. An Epic
  that rests on a decision to be designed from another Epic's requirements waits until
  that one is elaborated. Each edge is stored as a beads `tracks` edge on the dependent Epic.
  `tracks` is non-blocking, so an Epic edge orders elaboration and never holds the
  Stories or Tasks beneath an Epic out of `atw-bd ready`; their build order is their own
  Task-to-Task `blocks` edges.
- **WSJF decides PRIORITY** among what is eligible. The `agent-teams-workforce:wsjf`
  rubric computes each Epic's RR-OE — the Architectural Enabler measure — from transitive
  reachability over these edges, so an Epic whose requirements should drive decisions many
  others are designed on outranks one designed on top of a decision it does not drive.

The edge set is therefore the only place either decision is corrected. Draw every edge
that passes the test below, and none that does not.

## The test

Set an edge from A to B where an architecture decision B rests on should be designed from
A's requirements first, and the effective architecture does not already settle that decision — and nowhere
else. Not "this feels earlier", not "this is more important", and never "this must exist or
be built first".

**Draw every edge that passes the test, however many that is.** An Epic whose requirements
should drive a cross-cutting decision — the canonical record of a domain, for example — is
upstream of every Epic designed on top of that decision, and each of those edges is true.
How many Epics are designed on decisions one Epic's requirements should drive is a
judgment about the design. An undrawn true edge releases an Epic whose decision would then
be designed from the wrong requirements, and computes its blocker's RR-OE as though nothing
were designed on it.

Never draw an edge that fails the test. Judge each candidate on the test alone and let the
count come out wherever it comes out.

**When unsure, draw the edge at `low` confidence.** A missing edge costs more than an extra
one: a missing edge lets an Epic's architecture be designed from the wrong requirements,
while an extra one only delays an Epic until its blocker is elaborated.

### Foundation Epics

A foundation Epic is one whose requirements drive a foundation layer — networking, the
chassis, identity, the event platform, or any other layer on the checklist below. It is
upstream of every Epic that rests on that layer, unless an `effective` document already
settles the layer. Those Epics are ruled by the checklist: an Epic that answers "rests on"
for a layer has an edge from each Epic that answers "drives" for it. The matrix names the
Epics to answer it for (step 4 below).

### The foundation checklist

Every Epic is answered against each of these layers, and every layer gets one answer:
**drives** (its requirements are the fuller statement of what the layer must serve),
**rests on** (its design will be built on the layer), or **not touched**.

1. Network and egress
2. Identity and authorization
3. Data stores and data residency
4. Event platform
5. API shape
6. Chassis and runtime
7. Configuration and secrets
8. Observability
9. Environments

A requirements document's own dependency table names Epics that are related; it does not
say which way. Direction comes from the test.

## Assessing one Epic

An Epic is assessed when it is new or has changed, and seeding assesses every open Epic
this same way, one after another. The Epic's assessment is the only judgment of its edges:
it decides every edge to or from that Epic, including each one an earlier assessment of
another Epic set.

The matrix is read as the `matrix` skill says. `atw-matrix epic <beads id>` returns an Epic's
PRD path (`prd`, relative to the vault root), its requirements, each named by its PRD heading,
and the features each is served by.
When the assessment is handed a context file (artifact-handoff's
`schemas/dependency-assessment.schema.json`, `#/$defs/EpicContext`), that file is the material
it starts from: its descriptions say what each member holds, its `prdPath` values are absolute,
and its `standing` and `withdrawn` lists are the edges on the Epic.

1. Read the Epic's full PRD, at the context's `epic.prdPath` or the path `atw-matrix epic
   <beads id>` returns as `prd`. When the matrix names no PRD for the Epic, say so in the
   reasoning and write no edge file.
2. Answer the foundation checklist: for each of the nine layers, "drives", "rests on" or
   "not touched", with the requirement that decides the answer. No layer is skipped, and
   every answer goes in the written reasoning. Then name every other architecture decision
   the Epic's requirements should drive or that it rests on. An Epic is a PRD, a WHAT, and
   its architecture does not exist yet: this takes intuition about what the architecture
   could be.
3. Check each layer and decision against the effective architecture, and drop every one it
   already settles. Find what states each one with `atw-matrix find --kinds
   document,constraint,feature --text "<the decision in words>"`, then `atw-matrix node <id>`
   for each match that bears on it (see "Only an `effective` document settles anything").
   Record, for each decision you keep, the document id and heading you consulted, the
   `lifecycle` the matrix returned for it and why it leaves the decision open, or that the
   lookup returned nothing: that record goes on every edge as `archCheck`, and an edge without
   one is refused. As the effective architecture grows this becomes the answer for most
   decisions: the check is the step's purpose, not a formality.
4. Find the related Epics through the matrix: the context's `related` and `similar`, or
   `atw-matrix related --epic <beads id>` without a context, which returns the Epics that
   reach a feature, document, stack, service, component or infrastructure this Epic reaches,
   each with what is shared and through which relationship. For an Epic no feature serves
   yet, and for a layer or decision those do not reach, `atw-matrix find --kinds
   requirement,feature --text "<the layer or decision in words>"` returns the requirements and
   features that match: a requirement's id names its Epic, and a feature is returned with the
   Epics it serves. For each layer the Epic rests on, the related Epics are those whose
   requirements drive that layer; for each layer it drives, every Epic that rests on it. The
   matrix names the candidates; it does not say which way an edge runs.
5. For every related Epic, and the Epic at the other end of every edge standing on the Epic,
   read the requirements that bear on the layer or decision in question: `atw-matrix epic
   <its id>` names its requirements by their PRD headings. Read those headings and no other
   part, in the file at the `prdPath` the context gives or, for an Epic it does not list, at
   that `prd` path under the vault root. No other PRD is opened and no folder of PRDs is
   searched.
6. Apply the test in both directions: an edge from another Epic to this one where an
   architecture decision this Epic rests on should be designed from that Epic's
   requirements first, and an edge from this Epic to another where an architecture decision
   that Epic rests on should be designed from this Epic's requirements first. Say the reason
   in one line, naming the decision and whose requirements should drive it.
7. Account for every owned edge standing on the Epic: keep it in the edge file, or withdraw
   it with a reason that answers the reason recorded for it. An edge drawn by hand
   (`owned: false`) is never withdrawn and appears in neither list. An edge an earlier
   assessment withdrew is set again only with `answers`, why that recorded reason is wrong on
   the architecture; one you cannot answer is not set, and the earlier judgment stands.
8. Write the edge file and the reasoning (see "The edge file"), then check the file with the
   validation command (`depscore.py validate --edges <file> --epic <id>`) and revise it until
   it passes, keeping to the test: an edge that fails the test is dropped, never kept to
   satisfy the validator. A cycle you cannot remove by dropping one of your own edges that
   fails the test, one through an edge with `owned: false`, is reported in the reasoning with
   the failed validation and its findings, not forced.

Applying the edges and recording the matrix rows is not part of the assessment: the assessing
agent writes nothing to the tracker or the matrix.

### What the matrix records from an assessment

For each decision judged, the assessment names the matrix entry the Epic drives or rests
on: a feature id, or a document id with its heading. The dispatching workflow records each
as a `drives` or `restsOn` relationship from the Epic, with `side: architecture`; the
assessing agent runs no `put` and no `link`. A decision no matrix entry states gets no row
in the edge file; the reasoning names it, and nothing is recorded for it. The Epic-to-Epic edge is a beads `tracks` edge
and is never a matrix relationship.

## The worked example

Sign-up / sign-in requirements should drive the identity architecture, so they are
elaborated before password reset. If password reset is elaborated first, its architecture
step finds no identity architecture and designs one from a recovery flow's requirements
alone; sign-up / sign-in then either fits itself onto that minimal design, redesigns it and
invalidates what password reset was elaborated against, or halts for attention. The edge
exists to stop that, and an edge that stops nothing of that kind does not exist. Once the
effective architecture settles the identity architecture, no identity Epic needs an edge for it.

## The edge file

The edge file's one definition is artifact-handoff's `schemas/epic-edge-proposal.schema.json`:
its descriptions say what `edges`, `withdrawn` and `decisions` hold and what every member
means. A reason in it reads like this one: "the identity architecture should be designed from
sign-up/sign-in requirements, not password reset's". A withdrawal's reason answers the one
recorded: "the notification delivery decision is designed from this Epic's own requirements;
the recorded reason names a runtime call, which is a Task dependency".

Alongside the file, write the reasoning in prose: the foundation checklist with an answer
for every layer, the other decisions named, the architecture check on each, the Epics found
related and the requirement headings read, the test applied to each edge and each
withdrawal, the validation findings, and every edge you were unsure of with what would
settle it. The edges are the residue of that reasoning, and the reasoning is what the next assessment
revises.

## Checks before handing it over

- Every id is an open Epic the matrix holds (`atw-matrix epic <id>`).
- Every edge touches the assessed Epic.
- Every owned standing edge is kept or withdrawn, and every edge and withdrawal carries a
  reason; every edge carries its `archCheck`.
- No cycle. A cycle is a wrong edge, not a tie to break — find whose requirements should
  actually drive the decision.
- No edge onto a closed Epic, and none out of one.
- The foundation checklist is complete: every layer has an answer, and every layer the Epic
  rests on has an edge from the Epic that drives it, or cites an `effective` document that
  settles it.
- Every edge survives the test stated out loud. If the reason does not name an architecture
  decision that should be designed from the upstream Epic's requirements and that the
  effective architecture does not already settle, delete the edge. A reason about something existing, being built,
  being deployed, being testable, or being read or called at runtime is a Task dependency;
  delete the edge.

## Errors to avoid

- Adding an edge to express importance. That is WSJF's job, and an edge costs the blocked
  Epic its eligibility until the blocker is elaborated.
- Withholding an edge that passes the test because the fan-out looks excessive.
- Adding an edge to force a total order.
- Adding an edge for a build fact — existence, deployment, testability, data flow — which
  belongs to Tasks.
- Adding an edge for a decision the effective architecture already settles — one whose
  document the matrix returns with `lifecycle: effective`.
- Dropping an edge by citing a document that is not `effective`. The wording of an
  unreviewed document is not evidence that the decision was made, and this is the error that
  most easily ships as a confident reason nobody re-reads.
- Searching the arc42 folders, their front matter or section 2, or a folder of PRDs, for
  what the matrix returns.
- Withdrawing a standing edge without a reason that answers the reason recorded for it.
- Leaving out an edge because you are unsure of it. Draw it at `low` confidence.
- Scoring anything. Value and size belong to the `wsjf` rubric, and RR-OE is computed from
  the edges.
