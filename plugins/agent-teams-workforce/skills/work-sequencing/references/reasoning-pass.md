# The reasoning pass — outside-in Epic ordering

One agent session, holding the whole portfolio. The output is an edge file and a written
account of the tiering that produced it.

## Why one session, and not a team

The judgment is about how domains relate to each other. An agent holding one domain cannot
make it, and a panel of domain agents produces a set of local opinions nobody reconciled.
Mark was explicit: splitting the domains across agents does not help.

## Outside-in, and revisited

Work from the broadest grouping inward, and go back up whenever the detail contradicts the
level above it. Repeat until a pass changes nothing.

### 1. Tiers

Order broad tiers by common sense about what must exist before anything can be built and
TESTED. Roughly: platform foundations, then identity, then everything that presumes a user
exists, then what presumes that user has content, and so on outward.

The domain table in `domain-table.md` is a starting grouping, not an answer. It was derived
from PRD file names and **its errors are to be corrected rather than trusted** — `shell` and
`mobile/shell`, for instance, probably belong under platform.

### 2. Subdomains within a tier

Same question, one level down. Which subdomain establishes something the others consume?

### 3. Epic-to-Epic edges — the narrow part

Set an edge ONLY where one Epic's architecture must be designed from another Epic's
requirements first. That is the whole test. Not "this feels earlier", not "this is more
important", not "this is in an earlier tier".

**Do not add edges to force a total order.** WSJF orders everything an edge does not, and
an edge costs the blocked Epic its eligibility until the blocker's Tasks are written.

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

In WSJF terms the same fact shows up as RR-OE: sign-up scores high because it ESTABLISHES
the pattern, password reset low because it CONSUMES it. The edge and the score agree, and
when they disagree, one of the two is wrong and it is worth finding out which.

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
