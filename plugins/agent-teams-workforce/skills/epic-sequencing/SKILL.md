---
name: epic-sequencing
description: >-
  The edge test for Epic-to-Epic dependency edges, and how to apply it to ONE Epic: read its
  full PRD, answer the foundation-layer checklist (drives, rests on or not touched for each
  of nine layers) and name the other architecture decisions it drives and rests on, the shared
  capabilities it uses among them, check which of them the matrix holds approved, find the
  related Epics through the matrix, read the requirements of theirs that bear on each decision,
  and apply the test to every related Epic in both directions. An Epic is a PRD, a business requirement, and an edge is an ARCHITECTURE
  dependency, a judgment about the order in which architecture is established: it exists
  exactly where an architecture decision one Epic rests on should be designed from another
  Epic's requirements first, and the matrix does not hold that decision approved. Edges decide
  ELIGIBILITY (what may be elaborated at all); WSJF decides PRIORITY among what is
  eligible, and computes RR-OE from these edges. Use when proposing, reviewing or
  correcting the architecture dependencies of an Epic.
---

# Epic sequencing

The output is an edge file for one Epic and a written account of the reasoning that
produced it.

## Where Epic order comes from

The owner sets every Epic's dependencies once, before `keeper.py` runs, with
`scripts/portfolio/epicorder.py`. It reads the Epics and the chain the matrix records (Epic,
requirement, feature, `realizedBy`, `homeIn`, and one dependency hop) from the matrix only and
applies this skill's edge test to shared foundations alone:

1. Only shared foundations order Epics. A foundation is a stack named `shared-*`, `*-lib` or
   `*-infra` with every entry homed in it, and a layer or package homed in no such stack.
   Product services, components, events and app stacks make no Epic edge: who builds them first
   is build order, settled among Tasks.
2. A foundation the matrix holds approved (its own entry and every architecture-side entry homed
   in it carry the `approved` flag) makes no edge.
3. The owner's driver decision, recorded in the matrix, comes first: a `drives` relationship
   (architecture side) from an Epic to the stack names its driving Epic, and the stack attribute
   `epicDriver: none` says no Epic drives it ("A shared capability no Epic drives").
4. Otherwise the driving Epic is the one with strictly the most features serving its
   requirements that are `realizedBy` anything in the foundation; a tie means no Epic drives it.
   A foundation no Epic drives makes no edge.
5. Every other Epic that realizes part of the foundation, or reaches one of its realized entries
   as the far end of a dependency one hop away, waits for the driving Epic. Two users get no edge
   between them.
6. While the edges hold a cycle, the edge inside a cycle whose driving Epic has the fewest
   features in the foundations that make it is dropped (a tie to the lower bead id), and the
   report lists every dropped edge.

With `--apply` it removes every Epic-to-Epic dependency edge in beads, whoever made it, and
writes the computed edges as `tracks` edges; it refuses to write while a cycle is left or an edge
names an Epic beads does not hold. WSJF is scored once, also before `keeper.py` runs, by the
owner's own `wsjf-scoring` run. Nothing in the keeper, the supervisor, its lanes, elaboration,
build or deploy assesses an Epic's dependencies or scores anything.

This skill's edge test is the judgment the owner applies when reviewing one Epic's edges with
the `dependency-assessment` workflow, which only the owner runs. The edges that workflow
writes are removed and replaced at the next `epicorder.py --apply`.

## What an Epic dependency is

An Epic is a PRD: a business requirement, a WHAT and not a HOW. When an Epic is elaborated,
its architecture is designed and approved, and the approved design is what every later
Epic is designed against. So the order Epics are elaborated in decides which
requirements each architecture decision is designed from. An edge between two Epics is an
architecture dependency, and it answers one question: **which requirements should this
architecture decision be designed from first?**

The judgment is made before the architecture exists. It takes intuition about what the
architecture could be — which decisions a requirement will force, and whose requirements
are the fuller statement of what each decision must serve. An Epic rests on a decision as
soon as its design will be built on it, however little of the decision it uses.

Build facts are Task dependencies, and they never make an Epic edge. That something must
exist, be built, be deployed or be testable first; that one requirement presumes a user or a
record exists; that one reads a value another Epic's design keeps — each of those is settled
among Tasks, which are created after the architecture is settled and carry ordinary build
dependencies of their own. "Data flow, so no edge" holds only when no design decision of the
other Epic shapes how this Epic works.

### Shared capabilities come first

Everything shared is designed first. An Epic that uses a shared capability — sending its
messages through notification delivery, publishing or consuming events on the event
backbone, signing people in through shared identity, keeping files in shared storage, and
every other capability more than one Epic uses — rests on the design of that capability. Using
another Epic's mechanism is resting on its design, not a data flow. When the matrix does not
hold the capability's design approved, the Epic rests on the Epic whose requirements drive that
design, and that Epic is elaborated first. Without the edge, the using Epic's architecture step
finds no design and invents a bespoke one of its own: a private notification service beside
the shared one, its own event path, its own sign-in.

Two Epics that both only use a capability share no decision with each other: each rests on the
Epic that drives it, and no edge runs between the two users.

A decision the matrix holds approved is designed; no Epic edge is needed for it. As
elaboration approves more of the architecture, fewer Epic edges exist.

The first Epic elaborated that needs a decision not yet approved designs and approves it,
and later Epics design against it; the edges decide which Epic that is: the one whose
requirements should drive the decision.

### A shared capability no Epic drives

There are no platform Epics. When the matrix does not hold a shared capability's design
approved and no open Epic's requirements drive it (every Epic that reaches it only uses it,
as the event bus, the chassis and the API front door are used), it makes no edge, as it makes
none in `epicorder.py` (a tie for most features, or the owner's `epicDriver: none` on the
stack): the first Epic elaborated that uses it reviews and approves its
architecture, and every later user designs against that. No edge runs between two users, as
"Shared capabilities come first" states. Name the capability and its users in the reasoning.

### What removes the need for an edge

An `effective` document is approved content, and every architecture document still iterates
with each Epic (the `effective-architecture` skill, "Lifecycle, the baseline and iteration", is
the one home of both rules). The `effective` baseline is approved in advance, but no Epic's
elaboration has reviewed it yet, and the Epic that does may change it. So a document being
`effective`, or a matrix entry existing, does not remove the need to order the Epics: the
decision is still to be reviewed and shaped by one Epic's requirements, and the edge decides
which.

What removes the need is the matrix's `approved` mark on the entry or relationship that states
the decision: the solutions architect has reviewed and approved it (the `matrix` skill,
"Approved, verified, effective and side", says what sets it). A later Epic designs against
that decision, and changes it if it must, without an edge.

The effective documents and the matrix entries without the flag are still the starting point:
they say which decisions exist, what each is designed as, and which Epics share them.

Take the flag from the matrix; never infer it. What states a decision is found through the
matrix, with `atw-matrix`:

```
atw-matrix find --kinds document,constraint,feature --text "<the decision in words>"
atw-matrix node <id>
atw-matrix approval --epic <beads id>
```

`find` ranks the documents, constraints and features that match the words, and an empty
result means nothing states the decision. `node` returns one entry with its relationships;
an entry or relationship without an `approved` member is not approved. `approval --epic`
shows which content of an Epic's approval scope is approved. Read the heading the matrix
names, in that document and no other, when the entry alone does not say what the decision
is. The arc42 folders, their front matter and section 2 are not searched for this.

So when the entry that states a decision carries no `approved` flag, the decision is open
for ordering, and the edge test proceeds on it. Record the entry id (and the document heading,
for a document) you consulted and whether the matrix holds it approved in the edge's
`archCheck`, so a later reader can tell a decision an Epic has approved from one no Epic has
reviewed yet. An assessment that drops an edge by citing anything but the `approved` flag has
ordered the Epics on an unchecked claim.

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
A's requirements first, and the matrix does not hold that decision approved — and nowhere
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

**When the two Epics share a decision and you are unsure of the direction or the strength,
draw the edge at `low` confidence.** Never draw an edge between Epics that share no open
decision: unrelated Epics elaborate concurrently, and an edge between them delays one for
nothing. Over-serializing is as wrong as a missing edge.

### Foundation Epics

A foundation Epic is one whose requirements drive a foundation layer — networking, the
chassis, identity, the event platform, or any other layer on the checklist below. It is
upstream of every Epic that rests on that layer, unless the matrix holds the layer's
decisions approved. Those Epics are ruled by the checklist: an Epic that answers "rests on"
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

An Epic is assessed only when the owner runs the `dependency-assessment` workflow for it
(see "Where Epic order comes from"). The assessment judges every edge to or from that Epic,
including each one an earlier assessment of another Epic set.

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
   the Epic's requirements should drive or that it rests on. Among them name every shared
   capability the Epic uses, including one its PRD states only as an outcome: a message or
   email is sent, a person is notified, an event is published or reacted to, a file is kept,
   someone is signed in. Each is a decision the Epic rests on, unless its requirements are
   the fuller statement of what the capability must serve, and then it drives it (see "Shared
   capabilities come first"). An Epic is a PRD, a WHAT, and its architecture does not exist
   yet: this takes intuition about what the architecture could be.
3. Check each layer and decision against the matrix's `approved` flag, and drop every one
   the matrix holds approved. Find what states each one with `atw-matrix find --kinds
   document,constraint,feature --text "<the decision in words>"`, then `atw-matrix node <id>`
   for each match that bears on it (see "What removes the need for an edge").
   Record, for each decision you keep, the entry id (and the document heading, for a
   document) you consulted and that the matrix does not hold it approved, or that the lookup
   returned nothing: that record goes on every edge as `archCheck`, and an edge without one
   is refused. As elaboration approves more of the architecture this becomes the answer for
   most decisions: the check is the step's purpose, not a formality.
4. Find the related Epics through the matrix: the context's `related` and `similar`, or
   `atw-matrix related --epic <beads id>` without a context, which returns the Epics that
   reach a feature, document, stack, service, component or infrastructure this Epic reaches,
   each with what is shared and through which relationship. For an Epic no feature serves
   yet, and for a layer or decision those do not reach, `atw-matrix find --kinds
   requirement,feature --text "<the layer or decision in words>"` returns the requirements and
   features that match: a requirement's id names its Epic, and a feature is returned with the
   Epics it serves. For each layer or shared capability the Epic rests on, the related Epics
   are those whose requirements drive it; find them by the capability in words (for example
   "deliver a notification"), since the matrix may record no entry both Epics reach yet. For
   each layer it drives, every Epic that rests on it. The context lists first the related
   Epics that share the most features and documents with this one; one with an empty
   `shared` list shares no decision the matrix records. The matrix names the candidates; it
   does not say which way an edge runs.
5. For every related Epic, and the Epic at the other end of every edge standing on the Epic,
   read the requirements that bear on the layer or decision in question: `atw-matrix epic
   <its id>` names its requirements by their PRD headings. Read those headings and no other
   part, in the file at the `prdPath` the context gives or, for an Epic it does not list, at
   that `prd` path under the vault root. No other PRD is opened and no folder of PRDs is
   searched.
6. Apply the test to every related Epic, in both directions, and answer both questions
   explicitly for each:
   - (a) Does the other Epic rest on a decision this Epic drives? Then the edge runs from
     this Epic to the other.
   - (b) Does this Epic rest on a decision the other Epic drives, including a shared
     capability this Epic uses whose design the other Epic's requirements drive? Then the
     edge runs from the other Epic to this one.

   Answering (a) and leaving (b) unasked is the error this step exists to stop: an Epic
   that only reads or receives something from this one at run time may still drive the
   design of a capability this one sends through. "Data flow, so no edge" is the answer only
   when neither question finds a decision. Say each edge's reason in one line, naming the
   decision and whose requirements should drive it, and write both answers for every related
   Epic you judged in the reasoning.
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

Applying the edges is not part of the assessment: the assessing agent writes nothing to the
tracker or the matrix.

### What the matrix holds of an assessment

Nothing. Each edge's `archCheck` names the matrix entry that states the decision it orders (a
feature id, or a document id with its heading), and the reasoning names every decision judged.
The Epic-to-Epic edge
is a beads `tracks` edge and is never a matrix relationship. The order across every Epic is
derived from the chain the matrix records (Epic, requirement, feature, `realizedBy`, `homeIn`)
by `scripts/portfolio/epicorder.py`, never from a relationship stated between Epics.

## The worked example

Sign-up / sign-in requirements should drive the identity architecture, so they are
elaborated before password reset. If password reset is elaborated first, its architecture
step finds no identity architecture and designs one from a recovery flow's requirements
alone; sign-up / sign-in then either fits itself onto that minimal design, redesigns it and
invalidates what password reset was elaborated against, or halts for attention. The edge
exists to stop that, and an edge that stops nothing of that kind does not exist. Once the
matrix holds the identity architecture approved, no identity Epic needs an edge for it.

The shared-capability case runs the same way in the other direction. Email Channel Proof and
Self-Serve Address Correction (ssbd-guuuz) drives the account's email-address aggregate, and
Multi-Channel Notification Delivery (ssbd-hdqid) reads that address at run time to deliver
notifications. Asking only question (a) finds that read and calls it a data flow, so no edge.
Question (b) finds the decision that matters: ssbd-guuuz's own proof-of-control emails are
messages the product sends, and every message is sent through the notification service, with
events on the bus and EventBridge rules routing them. Notification delivery is a shared
capability ssbd-guuuz uses, ssbd-hdqid's requirements drive its design, and the matrix does
not hold that design approved. So the edge runs from ssbd-hdqid to ssbd-guuuz. Without it,
ssbd-guuuz's architecture step designs its own way to send its emails, which is how a bespoke
`securityNotifications-service` appeared in the architecture.

## The edge file

The edge file's one definition is artifact-handoff's `schemas/epic-edge-proposal.schema.json`:
its descriptions say what `edges` and `withdrawn` hold and what every member means. A reason in it reads like this one: "the identity architecture should be designed from
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
  rests on has an edge from the Epic that drives it, or cites the matrix entry that holds it
  approved.
- Every edge survives the test stated out loud. If the reason does not name an architecture
  decision that should be designed from the upstream Epic's requirements and that the
  matrix does not hold approved, delete the edge. A reason about something existing, being built,
  being deployed, being testable, or being read at runtime, with no design decision of the
  other Epic shaping how this one works, is a Task dependency; delete the edge.
- Every related Epic judged has both answers written: (a) whether it rests on a decision this
  Epic drives, and (b) whether this Epic rests on a decision it drives, shared capabilities
  this Epic uses included.

## Errors to avoid

- Adding an edge to express importance. That is WSJF's job, and an edge costs the blocked
  Epic its eligibility until the blocker is elaborated. WSJF never enters an edge.
- Withholding an edge that passes the test because the fan-out looks excessive.
- Adding an edge to force a total order.
- Adding an edge for a build fact — existence, deployment, testability, data flow — which
  belongs to Tasks.
- Calling a dependency a data flow after asking only whether the other Epic rests on this
  one. Using another Epic's mechanism, such as sending messages through the notification
  delivery it drives, is resting on its design, and the edge runs from that Epic.
- Adding an edge for a decision the matrix holds approved.
- Dropping an edge by citing anything but the matrix's `approved` flag: a matrix entry that
  exists, a document at `lifecycle: effective`, or the wording of a document. None of them
  shows that an Epic's elaboration has reviewed the decision, and this is the error that most
  easily ships as a confident reason nobody re-reads.
- Adding an edge between Epics that share no open decision. Unrelated Epics elaborate
  concurrently.
- Searching the arc42 folders, their front matter or section 2, or a folder of PRDs, for
  what the matrix returns.
- Withdrawing a standing edge without a reason that answers the reason recorded for it.
- Leaving out an edge on a shared open decision because you are unsure of it. Draw it at
  `low` confidence.
- Scoring anything. Value and size belong to the `wsjf` rubric, and RR-OE is computed from
  the edges.
