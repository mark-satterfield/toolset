---
name: epic-wsjf
description: >-
  Score an EPIC — a PRD-scale container — with WSJF. RR-OE is COMPUTED from the Epic
  dependency graph, which records the order in which architecture must be established, so
  an Epic that establishes a canonical pattern outranks one that consumes it by
  arithmetic rather than argument. Value and Time Criticality are judged from the PRD, and
  the whole portfolio is judged in one session so those two stay calibrated. Job Size is
  denominated in SPAN with headroom above 20, and is replaced by the roll-up of Task sizes
  once the Tasks exist. Use when scoring or re-scoring an Epic or
  ordering Epics for elaboration. For a Task, use `agent-teams-workforce:task-wsjf`
  instead — never this one.
---

# Epic WSJF

An Epic is a **container for a requirement**, not a job. It spans repositories, it becomes
many Stories and many Tasks, and no one implements it directly.

| Dimension | Where it comes from |
|---|---|
| User-Business Value | **judged** from the PRD |
| Time Criticality | **judged** from the PRD |
| Risk Reduction / Opportunity Enablement | **computed** from the dependency graph |
| Job Size | **judged** — span, until the Tasks exist |

`Cost of Delay = UBV + TC + RR-OE`. `WSJF = CoD / Job Size`, two decimal places, raw
sums — never normalize CoD before dividing. `jobSize > 0` always.

Every band in this rubric is an absolute threshold. Running it twice over the same PRD and
the same graph must produce the same number, and adding Epics to the portfolio must not
move the score of an Epic whose own inputs did not change.

## Scale

Fibonacci: 1, 2, 3, 5, 8, 13, 20, **40**. The 40 rung exists on the Job Size scale only,
so that two Epics differing five-fold in span do not land on the same number.

There is no "score as-is, it should be decomposed" rung. An Epic IS the thing that gets
decomposed.

## Score the whole portfolio in one session

RR-OE and the size roll-up are counted, so they are the same whoever runs them. UBV and TC
are judged against descriptive rungs, and those drift: one session's "significant" is
another's "high". An agent holding a subset cannot see where it has put the line, so its 3
and another agent's 2 mean nothing to each other and the ranking that results is an
artifact of how the work was divided.

So the portfolio is judged whole, in one session, or not at all. Where the Epic set is too
large for one session to hold each PRD in full, read a digest — title plus the PRD's
Feature Description and Feature Scope — for every Epic, and read the full PRD only for the
ones whose UBV or Job Size the digest cannot support. Never split the portfolio across
sessions to make it fit.

Nothing in this rubric is scored from another agent's calibration guidance. The bands
below, the PRD, and the dependency graph are the whole input.

## 1. Judge User-Business Value (UBV)

What is lost if this PRD is never delivered?

```
  1-2 : Minimal — internal convenience, no measurable user impact
  3   : Moderate — meaningfully improves an existing capability
  5   : Significant — directly addresses a user pain or a market need
  8   : High — revenue-impacting, or broad customer-facing impact
  13  : Critical — revenue loss, major customer risk, a core capability
  20  : Existential — regulatory mandate, platform failure, contract risk
```

Judge the PRD's stated outcome, not the machinery underneath it. An Epic whose whole point
is plumbing still carries the value of the capability it exists to deliver; that value is
expressed in RR-OE, and a low UBV is not a penalty.

## 2. Judge Time Criticality (TC)

How fast does that value decay if deferred?

```
  1   : No decay — timing is irrelevant
  2   : Mild — weeks or months of deferral change little
  3   : Moderate — value noticeably diminishes over weeks
  5   : Meaningful drop within this quarter
  8   : Hard deadline this quarter, or a competitive window closing
  13  : Fixed external deadline — regulation, event, integration partner
  20  : Imminent or passed — value approaches zero if not done now
```

Importance is UBV. Do not inflate TC because an Epic feels important. A project with no
launch date, no customers and no external commitment has little for TC to measure; say so
in the confidence rather than manufacturing urgency.

## 3. Compute RR-OE from the dependency graph

**This is the architectural dimension, and it is the one that orders the portfolio. It is
a count, not an argument.**

An Epic edge records that one Epic's architecture must be designed from another Epic's
requirements first. That is the same question RR-OE asks — does this Epic ESTABLISH a
pattern later work is designed from, or CONSUME one already established — so the edges
answer it directly.

```
reaches(E) = the number of DISTINCT Epics reachable from E by following edges
             forward, transitively, within the portfolio (E itself excluded)
```

Transitive, because an Epic that unblocks one Epic which unblocks six has unblocked seven.
Band the count:

```
  reaches = 0       -> RR-OE  1   Nothing is designed from this
  reaches = 1       -> RR-OE  3   One downstream Epic
  reaches = 2-3     -> RR-OE  5   A small downstream set
  reaches = 4-9     -> RR-OE  8   Establishes a pattern other Epics extend
  reaches = 10-19   -> RR-OE 13   Canonical for a cross-cutting concern
  reaches >= 20     -> RR-OE 20   Platform foundation
```

Record `reaches(E)` as `wsjf_reaches` alongside the score, so the number behind the band is
visible.

The graph must be acyclic. If it is not, the reachability count is undefined: report the
cycle and score nothing.

**Do not judge RR-OE from prose in any circumstance, including when the count feels
wrong.** A count that feels wrong is a missing or reversed edge, and the edge is where it
gets fixed. This is load-bearing for Epics in a way it is not for Tasks: an Epic graph
built to stay sparse — one that withholds `service chassis -> the services designed from
it` because the result looks like a total order — will compute a foundation at rung 1. The
remedy is to draw the edge that is true, not to override the band. Report any Epic whose
computed RR-OE contradicts its PRD as a **graph defect**, naming the edge you believe is
missing, and score the count meanwhile.

There is no separate Enabler classification and no posture field. "No user-visible output"
and "unblocks other work" classify nothing at PRD scale; the reachability count is the test
that discriminates.

## 4. Judge Job Size — SPAN, not developer-days

An Epic's size is how much of the system it moves. Four denominators, judged together:

- **repositories** in the ruled span (the repo-scoping ruling, when it exists);
- **Stories** the PRD implies — one per repository per coherent slice;
- **surfaces** touched: `api-contract`, `event-chain`, `auth`, `web-ui`, `ios`,
  `android`, `cross-platform-mobile`, `ml`, `performance`, `data-pipeline`;
- **new versus extends** — new service, new datastore, new external integration, or a
  change within material that already exists.

```
  1   : One repo, one Story, one existing surface, extends what is there
  2   : One repo, two or three Stories, extends existing patterns
  3   : One repo, several Stories, or one new surface on an existing service
  5   : Two repos, or one new surface plus the consumers it forces to change
  8   : Three or four repos, or a new capability established across a surface
  13  : Four-plus repos, or a new service or repository plus its consumers
  20  : A new subsystem — new repositories, a new datastore, new externally
        facing surfaces
  40  : Platform-scale — several new services, a new external integration, and
        migration of material that already ships
```

Removal counts. An Epic that contradicts shipped material carries the cost of removing it;
the repositories holding that material are in the span.

When the repo-scoping ruling is not available, say so in the confidence for this dimension
and score from the PRD's own reach. Do not guess a repository count.

## 5. Compute

```
costOfDelay = userBusinessValue + timeCriticality + riskReductionOpportunityEnablement
wsjf        = costOfDelay / jobSize          (two decimal places)
```

## Size roll-up — top-down value, bottom-up cost

An Epic's span size is an estimate made before the work is known. The moment the Epic's
Tasks exist, the estimate is replaced:

1. Sum every Task's `wsjf_size` under this Epic. Task sizes are developer-days, so the sum
   is developer-days. Closed Tasks count — the Epic's cost is the whole job, not what is
   left. Record the sum as `wsjf_size_task_days`.
2. Map the sum onto the span scale, so every Epic in the portfolio keeps one denominator
   and stays comparable:

   ```
   <= 2 days -> 1      <= 5 -> 2      <= 10 -> 3     <= 20 -> 5
   <= 40     -> 8      <= 80 -> 13    <= 160 -> 20   > 160 -> 40
   ```

3. Recompute `WSJF = CoD / Job Size` with the mapped rung, and set
   `wsjf_size_source=task-rollup`.

Value stays top-down: UBV and TC are never re-derived from the Tasks, and RR-OE stays a
function of the Epic graph, never of the Task graph. Cost becomes bottom-up. Re-run the
roll-up whenever the Task set changes.

## Confidence

A percentage per judged dimension — UBV, TC and Job Size:

```
  98-100% : the PRD (or the repo-scoping ruling) directly supports this score
  66-97%  : reasonable inference; an assumption was made
  <=65%   : insufficient information — flag it with the reason
```

Overall confidence is the weighted average biased toward the lowest dimension. If any
dimension is below 65%, overall confidence cannot exceed 70%. A computed RR-OE and a
rolled-up Job Size are 98-100% by construction — they were counted, not judged.

## Output — the numbers are the deliverable

Emit a fenced `json` block first. This is what lands in bead metadata, and nothing else in
the output is read by a program.

```json
{
  "rubric": "epic-wsjf",
  "scores": [
    {
      "id": "<bead id>",
      "userBusinessValue": 13,
      "timeCriticality": 3,
      "riskReductionOpportunityEnablement": 13,
      "reaches": 12,
      "costOfDelay": 29,
      "jobSize": 8,
      "sizeSource": "span-estimate",
      "sizeTaskDays": null,
      "wsjf": 3.63,
      "confidence": 88,
      "rationale": {
        "userBusinessValue": "<1-3 sentences>",
        "timeCriticality": "<1-3 sentences>",
        "jobSize": "<1-3 sentences, naming repos / Stories / surfaces / new-vs-extends>"
      },
      "assumptions": ["<one entry per assumption that could move a score>"]
    }
  ],
  "graphDefects": [
    { "id": "<bead id>", "reaches": 0, "computed": 1,
      "missingEdge": "<blocker> -> <blocked>", "why": "<one line>" }
  ],
  "unscored": [
    { "id": "<bead id>", "reason": "<why it could not be scored>" }
  ]
}
```

Every Epic in the portfolio appears exactly once, in `scores` or in `unscored`. RR-OE
carries no rationale — the count is the reasoning. `graphDefects` is where an Epic whose
computed RR-OE contradicts its PRD is reported; it never changes the score.

Then, for a person, a short prose section per judged dimension. Keep it under a page.

## Metadata keys

Recorded as bead **metadata**, merged (`--set-metadata`), never as a note — a score in
prose is a score no gate can see. Use the `agent-teams-workforce:beads-contract` CLI to
write it; never hand-roll `jq` against `bd`.

| key | value |
|---|---|
| `wsjf` | the score, two decimal places |
| `wsjf_calculated_at` | ISO 8601 timestamp |
| `wsjf_rubric` | `epic-wsjf` |
| `wsjf_ubv` | User-Business Value |
| `wsjf_tc` | Time Criticality |
| `wsjf_rroe` | computed RR-OE |
| `wsjf_reaches` | the reachability count RR-OE was banded from |
| `wsjf_cod` | Cost of Delay |
| `wsjf_size` | Job Size rung |
| `wsjf_size_source` | `span-estimate` or `task-rollup` |
| `wsjf_size_task_days` | the developer-day sum, on a roll-up only |
| `wsjf_confidence` | overall confidence, integer percent |

`wsjf_ubv`, `wsjf_tc` and `wsjf_confidence` are what `task-wsjf` inherits, so they are
required, not optional colour. Metadata values carry no characters `bd` would mis-split:
numbers, ISO timestamps and kebab-case words only.

## Scoring errors to avoid

- Judging RR-OE from prose when the graph is right there.
- Overriding a computed RR-OE that looks wrong instead of reporting the missing edge.
- Splitting the portfolio across sessions, or scoring one Epic in isolation against no
  portfolio at all.
- Accepting calibration bands from a caller in place of the ones in this rubric.
- Scoring an Epic's size in developer-days. That is the Task scale.
- Leaving a span estimate in place after the Tasks exist.
- Normalizing CoD before dividing.
- Re-deriving UBV or TC from the Tasks. Value is top-down; only cost rolls up.
