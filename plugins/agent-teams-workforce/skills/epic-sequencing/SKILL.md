---
name: epic-sequencing
description: >-
  The edge test for Epic-to-Epic dependency edges, and the outside-in procedure for
  applying it to a whole Epic portfolio. An edge exists exactly where one Epic's
  architecture must be designed from another Epic's requirements first. Edges decide
  ELIGIBILITY (what may be elaborated at all); WSJF decides PRIORITY among what is
  eligible, and computes RR-OE from these edges. Use when proposing, reviewing or
  correcting the Epic dependency graph.
---

# Epic sequencing

The output is an edge file over the whole Epic portfolio and a written account of the
tiering that produced it. One session holds the whole portfolio: the judgment is about how
domains relate to each other, which an agent holding one domain cannot make.

## What an edge decides

- **The dependency graph decides ELIGIBILITY** — what may be elaborated at all. An Epic
  whose architecture must be designed from another Epic's requirements waits until that
  one is elaborated. Each edge is stored as a beads `tracks` edge on the dependent Epic.
  `tracks` is non-blocking, so an Epic edge orders elaboration and never holds the
  Stories or Tasks beneath an Epic out of `bd ready`; their build order is their own
  Task-to-Task `blocks` edges.
- **WSJF decides PRIORITY** among what is eligible. The `agent-teams-workforce:wsjf`
  rubric computes each Epic's RR-OE from transitive reachability over these edges, so an
  Epic that establishes an architecture many others are designed from outranks one that
  consumes it.

The edge set is therefore the only place either decision is corrected. Draw every edge
that passes the test below, and none that does not.

## Outside-in, and revisited

Work from the broadest grouping inward, and go back up whenever the detail contradicts the
level above it. Repeat until a pass changes nothing.

### 1. Tiers

Derive the domains from the Epics in the snapshot — their titles, their scope and the
documents they name. The set of Epics is the only description of the domains there is,
and it changes between runs, so the grouping is derived fresh each time.

Order broad tiers by what must exist before anything can be built and TESTED. Roughly:
platform foundations, then identity, then everything that presumes a user exists, then
what presumes that user has content, and so on outward.

The grouping is provisional. The detail below it will contradict it — when it does,
redraw it.

### 2. Subdomains within a tier

Same question, one level down. Which subdomain establishes something the others consume?

### 3. Epic-to-Epic edges — the test

Set an edge where one Epic's architecture must be designed from another Epic's
requirements first, and nowhere else. Not "this feels earlier", not "this is more
important", not "this is in an earlier tier".

**Draw every edge that passes the test, however many that is.** An Epic that rules a
cross-cutting concern — the service chassis, the event envelope, the canonical record of a
domain — is upstream of every Epic whose architecture is derived from it, and each of
those edges is true. How many Epics one Epic establishes the architecture for is a fact
about the design. An undrawn true edge releases an Epic that is not ready and computes its
blocker's RR-OE as though nothing were designed from it.

Never draw an edge that fails the test. Judge each candidate on the test alone and let the
count come out wherever it comes out.

A requirements document's own dependency table names Epics that are related; it does not
say which way. Direction comes from the test.

### 4. Revisit

When a detail at level 3 contradicts the tiering at level 1 — an Epic assumed to be late
establishes the pattern three others consume — fix level 1 and come back down. Stop when a
pass changes nothing.

## The worked example

Sign-up / sign-in must establish the identity architecture before password reset is
elaborated. If password reset is elaborated first, the identity architecture is designed
from a recovery flow's requirements alone, and every later identity Epic inherits a model
that was never meant to carry it. The edge exists to stop that, and an edge that stops
nothing of that kind does not exist.

## The edge file

One entry per edge, over the whole portfolio:

```json
{"edges": [
  {"from": "<blocker epic id>", "to": "<blocked epic id>",
   "reason": "identity architecture is established here and consumed there",
   "confidence": "high"}
]}
```

`from` must be elaborated before `to`. `confidence` is `high`, `medium` or `low` and is for
the person reading the proposal. A `low` edge is one to argue about; it is not a reason to
leave it out.

Alongside the file, write the tiering and the subdomain ordering in prose — the edges are
the residue of that reasoning, and the reasoning is what the next run revises.

The file is the whole graph: an edge the sequencing pass created earlier and this file
omits is withdrawn. An edge drawn by hand is never withdrawn. Both ends of every edge are
Epics; validation refuses any other edge.

## Checks before handing it over

- Every id appears in the snapshot. A bead that does not exist usually means the wrong
  portfolio was read.
- No cycle. A cycle is a wrong edge, not a tie to break — find which of the two Epics
  actually establishes the pattern.
- No edge onto a closed Epic, and none out of one.
- Every edge survives the test stated out loud. If the reason does not name something one
  Epic establishes and the other consumes, delete the edge.

## Errors to avoid

- Adding an edge to express importance. That is WSJF's job, and an edge costs the blocked
  Epic its eligibility until the blocker is elaborated.
- Withholding an edge that passes the test because the fan-out looks excessive.
- Adding an edge to force a total order or to mirror the tiering.
- Scoring anything. Value and size belong to the `wsjf` rubric, and RR-OE is computed from
  the edges.
