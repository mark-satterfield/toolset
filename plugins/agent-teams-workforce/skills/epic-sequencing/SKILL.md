---
name: epic-sequencing
description: >-
  The edge test for Epic-to-Epic dependency edges, and how to apply it in either scope:
  one Epic against the portfolio, or the whole portfolio outside-in. An Epic is a PRD, a
  business requirement, and an edge is a judgment about DESIGN order: it exists exactly
  where an architecture decision one Epic rests on should be designed from another Epic's
  requirements first, and the SAD does not already settle it. Edges decide
  ELIGIBILITY (what may be elaborated at all); WSJF decides PRIORITY among what is
  eligible, and computes RR-OE from these edges. Use when proposing, reviewing or
  correcting the Epic dependency graph.
---

# Epic sequencing

The output is an edge file and a written account of the reasoning that produced it. One
session holds the whole portfolio: the judgment is about how domains relate to each other,
which an agent holding one domain cannot make. It holds the portfolio through each Epic's
stored summary — the architecture decisions its requirements should drive, the decisions it
should be designed on top of, which of those the SAD already settles, and its value and
urgency — and reads a PRD in full where a summary cannot settle an edge.

## What an Epic dependency is

An Epic is a PRD: a business requirement, a WHAT and not a HOW. When an Epic is elaborated,
its architecture is designed, and a decision designed then becomes part of the SAD that
every later Epic is designed against. So the order Epics are elaborated in decides which
requirements each architecture decision is designed from. An Epic dependency answers one
question: **which requirements should this architecture decision be designed from first?**

The judgment is made before the architecture exists. It takes intuition about what the
architecture could be — which decisions a requirement will force, and whose requirements
are the fuller statement of what each decision must serve. One requirement touching a
decision does not make it that decision's driver: a PRD that stores a single value does not
dictate the database schema.

Build facts are Task dependencies, and they never make an Epic edge. That something must
exist, be built, be deployed or be testable first; that one requirement presumes a user or a
record exists; that one reads data from or calls a capability of another — each of those is
settled among Tasks, which are created after the architecture is settled and carry ordinary
build dependencies of their own.

A decision the SAD already settles is designed; no Epic edge is needed for it. As the SAD
accumulates decisions, fewer Epic edges exist.

## Two scopes

- **One Epic** — a new or changed Epic, assessed against the portfolio. Read its full PRD
  and apply the test below in both directions. The edge file holds every edge to or from
  that Epic and no other; every other Epic's edges stand, and validation refuses an edge
  that does not touch the Epic.
- **The whole portfolio** — for re-seeding. Work outside-in, as the rest of this document
  describes, and emit the whole graph.

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

## Outside-in, and revisited — the whole portfolio

Work from the broadest grouping inward, and go back up whenever the detail contradicts the
level above it. Repeat until a pass changes nothing.

### 1. Tiers

Derive the domains from the Epics in the portfolio — their titles, their scope and the
documents they name. The set of Epics is the only description of the domains there is,
and it changes between runs, so the grouping is derived fresh each time.

Order broad tiers by design order: which architecture decisions the rest of the portfolio
will be designed on top of, and whose requirements should drive them. Roughly: the
requirements that drive decisions cutting across every domain, then the requirements that
drive a domain's core decisions — sign-up and sign-in driving identity — then the
requirements designed on top of those decisions, and so on outward. A tier holds
requirements, and nothing about what is built or running decides it.

The grouping is provisional. The detail below it will contradict it — when it does,
redraw it.

### 2. Subdomains within a tier

Same question, one level down. Whose requirements should drive the decisions the other
subdomains are designed on?

### 3. Epic-to-Epic edges — the test

Set an edge from A to B where an architecture decision B rests on should be designed from
A's requirements first, and the SAD does not already settle that decision — and nowhere
else. Not "this feels earlier", not "this is more important", not "this is in an earlier
tier", and never "this must exist or be built first".

**Draw every edge that passes the test, however many that is.** An Epic whose requirements
should drive a cross-cutting decision — the canonical record of a domain, for example — is
upstream of every Epic designed on top of that decision, and each of those edges is true.
How many Epics are designed on decisions one Epic's requirements should drive is a
judgment about the design. An undrawn true edge releases an Epic whose decision would then
be designed from the wrong requirements, and computes its blocker's RR-OE as though nothing
were designed on it.

Never draw an edge that fails the test. Judge each candidate on the test alone and let the
count come out wherever it comes out.

A requirements document's own dependency table names Epics that are related; it does not
say which way. Direction comes from the test.

### 4. Revisit

When a detail at level 3 contradicts the tiering at level 1 — an Epic assumed to be late
turns out to hold the requirements that should drive a decision three others are designed
on — fix level 1 and come back down. Stop when a
pass changes nothing.

## The worked example

Sign-up / sign-in requirements should drive the identity architecture, so they are
elaborated before password reset. If password reset is elaborated first, its architecture
step finds no identity architecture and designs one from a recovery flow's requirements
alone; sign-up / sign-in then either fits itself onto that minimal design, redesigns it and
invalidates what password reset was elaborated against, or halts for attention. The edge
exists to stop that, and an edge that stops nothing of that kind does not exist. Once the
SAD settles the identity architecture, no identity Epic needs an edge for it.

## The edge file

One entry per edge in the scope:

```json
{"edges": [
  {"from": "<blocker epic id>", "to": "<blocked epic id>",
   "reason": "the identity architecture should be designed from sign-up/sign-in requirements, not password reset's",
   "confidence": "high"}
]}
```

`from` must be elaborated before `to`. `confidence` is `high`, `medium` or `low` and is for
the person reading the proposal. A `low` edge is one to argue about; it is not a reason to
leave it out.

Alongside the file, write the reasoning in prose — for the whole portfolio, the tiering and
the subdomain ordering; for one Epic, the test applied to each edge. The edges are the
residue of that reasoning, and the reasoning is what the next assessment revises.

The file is the whole graph of its scope: an edge an earlier assessment created within the
scope and this file omits is withdrawn. An edge drawn by hand is never withdrawn. Both ends
of every edge are Epics; validation refuses any other edge.

## Checks before handing it over

- Every id appears in the portfolio. A bead that does not exist usually means the wrong
  portfolio was read.
- No cycle. A cycle is a wrong edge, not a tie to break — find whose requirements should
  actually drive the decision.
- No edge onto a closed Epic, and none out of one.
- Every edge survives the test stated out loud. If the reason does not name an architecture
  decision that should be designed from the upstream Epic's requirements and that the SAD
  does not already settle, delete the edge. A reason about something existing, being built,
  being deployed, being testable, or being read or called at runtime is a Task dependency;
  delete the edge.

## Errors to avoid

- Adding an edge to express importance. That is WSJF's job, and an edge costs the blocked
  Epic its eligibility until the blocker is elaborated.
- Withholding an edge that passes the test because the fan-out looks excessive.
- Adding an edge to force a total order or to mirror the tiering.
- Adding an edge for a build fact — existence, deployment, testability, data flow — which
  belongs to Tasks.
- Adding an edge for a decision the SAD already settles.
- Scoring anything. Value and size belong to the `wsjf` rubric, and RR-OE is computed from
  the edges.
