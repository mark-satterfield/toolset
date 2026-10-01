---
name: epic-sequencing
description: >-
  The edge test for Epic-to-Epic dependency edges, and how to apply it to ONE Epic: read its
  full PRD, answer the foundation-layer checklist (drives, rests on or not touched for each
  of nine layers) and name the other architecture decisions it drives and rests on, check
  the effective architecture, find the related Epics by the checklist, read their PRDs in full, and apply the
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

### Only an `effective` view settles anything

An architecture view settles a decision when, and only when, its file's frontmatter carries
`lifecycle_state: effective`. A view at `in-review`, or in any other state, settles NOTHING,
however normatively it is worded and whatever date it carries.

Read the state; never infer it. A dated ruling, a MUST, a table of values and a confident
tone are all properties of the wording, and the wording is what an unreviewed view has most
of. `lifecycle_state` is per file, and the only files marked `effective` are those the
architecture step of a `prd-to-spec` elaboration covered: every architecture file that PRD
relies on (reviewed and approved as it stands, or updated), changes or creates — that step
is the sole writer of the value.

The views of an element are found through the catalog: each view's frontmatter names its
`subject` and every element it `shows`. So when a view that bears on a decision is not
`effective`, the effective architecture does not settle that decision, and the edge test
proceeds as though the view were absent. Record the view you consulted and the state you
read in the edge's `archCheck`, so a later reader can tell a view that settled the question
from one that only sounded like it did. An assessment that drops an edge by citing a view
that is not `effective` has ordered the portfolio on an unchecked claim.

## What an edge decides

- **The dependency graph decides ELIGIBILITY** — what may be elaborated at all. An Epic
  that rests on a decision to be designed from another Epic's requirements waits until
  that one is elaborated. Each edge is stored as a beads `tracks` edge on the dependent Epic.
  `tracks` is non-blocking, so an Epic edge orders elaboration and never holds the
  Stories or Tasks beneath an Epic out of `bd ready`; their build order is their own
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
upstream of every Epic that rests on that layer, unless an `effective` view already
settles the layer. Those Epics are found by the checklist, not by text search: an Epic that
answers "rests on" for a layer has an edge from each Epic that answers "drives" for it.

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

1. Read the Epic's full PRD.
2. Answer the foundation checklist: for each of the nine layers, "drives", "rests on" or
   "not touched", with the requirement that decides the answer. No layer is skipped, and
   every answer goes in the written reasoning. Then name every other architecture decision
   the Epic's requirements should drive or that it rests on.
3. Check each layer and decision against the effective architecture, and drop every one it
   already settles. A view settles a decision only when its file's frontmatter reads
   `lifecycle_state: effective` — read that field on every view you rely on, and treat a
   view in any other state as absent.
4. Find the related Epics by the checklist. For each layer the Epic rests on, the related
   Epics are those whose requirements drive that layer; for each layer it drives, every
   Epic that rests on it. Answer the checklist for those Epics from the index and their
   PRDs. For each other remaining decision, search the other Epics' PRDs — Grep the PRD
   directory, and use the index for titles and section headings — for the PRDs whose
   requirements drive or rest on it.
5. Read in full every related PRD, and the PRD at the other end of every edge standing on
   the Epic.
6. Apply the test in both directions: an edge from another Epic to this one where an
   architecture decision this Epic rests on should be designed from that Epic's
   requirements first, and an edge from this Epic to another where an architecture decision
   that Epic rests on should be designed from this Epic's requirements first.
7. Account for every owned edge standing on the Epic: keep it in the edge file, or withdraw
   it with a reason that answers the reason recorded for it. An edge drawn by hand is never
   withdrawn and appears in neither list.
8. Write the edge file and the reasoning, and validate the file until it passes.

## The worked example

Sign-up / sign-in requirements should drive the identity architecture, so they are
elaborated before password reset. If password reset is elaborated first, its architecture
step finds no identity architecture and designs one from a recovery flow's requirements
alone; sign-up / sign-in then either fits itself onto that minimal design, redesigns it and
invalidates what password reset was elaborated against, or halts for attention. The edge
exists to stop that, and an edge that stops nothing of that kind does not exist. Once the
effective architecture settles the identity architecture, no identity Epic needs an edge for it.

## The edge file

```json
{"edges": [
  {"from": "<blocker epic id>", "to": "<blocked epic id>",
   "reason": "the identity architecture should be designed from sign-up/sign-in requirements, not password reset's",
   "confidence": "high",
   "archCheck": "<the view consulted, the lifecycle_state read there, and why it leaves the decision open>"}
],
 "withdrawn": [
  {"from": "<blocker epic id>", "to": "<blocked epic id>",
   "reason": "the notification delivery decision is designed from this Epic's own requirements; the recorded reason names a runtime call, which is a Task dependency"}
]}
```

`edges` holds every edge to or from the assessed Epic that passes the test — each standing
edge it keeps included — and no edge that does not touch it. `from` must be elaborated
before `to`. `confidence` is `high`, `medium` or `low` and is for the person reading the
proposal. A `low` edge is one to argue about; it is not a reason to leave it out.

`withdrawn` holds every owned edge standing on the assessed Epic that `edges` does not keep,
each with a reason that answers the reason recorded for it. An edge drawn by hand is never
in either list and is never withdrawn. Both ends of every edge are Epics; validation refuses
any other edge.

Alongside the file, write the reasoning in prose: the foundation checklist with an answer
for every layer, the other decisions named, the architecture check on each, the PRDs found related,
and the test applied to each edge and each withdrawal. The
edges are the residue of that reasoning, and the reasoning is what the next assessment
revises.

## Checks before handing it over

- Every id is an open Epic in the index.
- Every edge touches the assessed Epic.
- Every owned standing edge is kept or withdrawn, and every edge and withdrawal carries a
  reason.
- No cycle. A cycle is a wrong edge, not a tie to break — find whose requirements should
  actually drive the decision.
- No edge onto a closed Epic, and none out of one.
- The foundation checklist is complete: every layer has an answer, and every layer the Epic
  rests on has an edge from the Epic that drives it, or cites an `effective` view that
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
- Adding an edge for a decision the effective architecture already settles — one whose view
  reads `lifecycle_state: effective`.
- Dropping an edge by citing a view that is not `effective`. The wording of an
  unreviewed view is not evidence that the decision was made, and this is the error that
  most easily ships as a confident reason nobody re-reads.
- Withdrawing a standing edge without a reason that answers the reason recorded for it.
- Leaving out an edge because you are unsure of it. Draw it at `low` confidence.
- Scoring anything. Value and size belong to the `wsjf` rubric, and RR-OE is computed from
  the edges.
