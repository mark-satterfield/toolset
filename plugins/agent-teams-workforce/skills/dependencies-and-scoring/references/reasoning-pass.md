# The reasoning pass — outside-in Epic ordering

One agent session, holding the whole portfolio. The output is an edge file and a written
account of the tiering that produced it.

## Why one session, and not a team

The judgment is about how domains relate to each other. An agent holding one domain cannot
make it, and a panel of domain agents produces a set of local opinions nobody reconciled.
Splitting the domains across agents does not help.

## Outside-in, and revisited

Work from the broadest grouping inward, and go back up whenever the detail contradicts the
level above it. Repeat until a pass changes nothing.

### 1. Tiers

Derive the domains yourself from the Epics in the snapshot — their titles, their scope and
the documents they name. The set of Epics is the only description of the domains there is,
and it changes between passes, so the grouping is derived fresh each time.

Then order broad tiers by common sense about what must exist before anything can be built
and TESTED. Roughly: platform foundations, then identity, then everything that presumes a
user exists, then what presumes that user has content, and so on outward.

The grouping is provisional. It is a first reading of the portfolio, not an answer, and
the detail below it will contradict it — when it does, redraw it.

### 2. Subdomains within a tier

Same question, one level down. Which subdomain establishes something the others consume?

### 3. Epic-to-Epic edges

Set an edge where one Epic's architecture must be designed from another Epic's
requirements first, and nowhere else. That is the whole test. Not "this feels earlier",
not "this is more important", not "this is in an earlier tier".

**Draw every edge that passes the test, however many that is.** An Epic that rules a
cross-cutting concern — the service chassis, the event envelope, the canonical record of a
domain — is genuinely upstream of every Epic whose architecture is derived from it, and
each of those edges is true. Do not withhold a true edge because the fan-out looks
excessive or because the result approaches a total order: how many Epics one Epic
establishes the architecture for is a fact about the design, not an aesthetic defect in
the graph.

Never draw an edge that fails the test. Judge each candidate edge on the test alone, and
let the count come out wherever it comes out.

### 4. Revisit

When a detail at level 3 contradicts the tiering at level 1 — an Epic everyone assumed was
late turns out to establish the pattern three others consume — fix level 1 and come back
down. Stop when a pass changes nothing.

## The worked example to honour

Sign-up / sign-in must establish the identity architecture before password reset is
elaborated.

Not because password reset is unimportant, and not because one is "before" the other in a
user's journey. Because if password reset is elaborated first, the identity architecture
gets designed from password-reset requirements alone — a recovery flow's needs become the
canonical identity model, and every later identity Epic inherits a design that was never
meant to carry it. The edge exists to stop that, and edges that do not stop something of
that kind should not exist.

## Emitting

One entry per edge, each carrying a one-line reason and a confidence:

```json
{"edges": [
  {"from": "<blocker epic id>", "to": "<blocked epic id>",
   "reason": "identity architecture is established here and consumed there",
   "confidence": "high"}
]}
```

`confidence` is `high`, `medium` or `low` and is for the person reading the proposal. A
`low` edge is one to argue about before it is applied; it is not a reason to leave it out.

Alongside the file, write the tiering and the subdomain ordering in prose — the edges are
a thin residue of the reasoning, and the reasoning is what the next pass revises.

## Checks before handing it over

- Every id appears in the snapshot. `validate` will catch a typo, but naming a bead that
  does not exist usually means the wrong portfolio was read.
- No cycle. A cycle is a wrong edge, not a tie to break — find which of the two Epics
  actually establishes the pattern.
- No edge onto a closed Epic, and none out of one.
- Every edge survives the test in step 3 stated out loud. If the reason does not name
  something one Epic establishes and the other consumes, delete the edge.
