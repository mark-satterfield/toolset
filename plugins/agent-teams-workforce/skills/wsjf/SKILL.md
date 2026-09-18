---
name: wsjf
description: >-
  Score work with WSJF at either level — an EPIC, the container for a requirement, or a
  TASK, one agent's work inside it. Cost of Delay is User-Business Value plus Time
  Criticality plus Risk Reduction / Opportunity Enablement, divided by Job Size. RR-OE is
  COMPUTED from transitive reachability over a dependency graph rather than argued from
  prose, and `scripts/wsjf.py` owns every band, the size scale and the child-size roll-up.
  The skill accepts whatever the caller already knows — a job size, the edges, an inherited
  value — and computes only what is missing. Use when scoring or re-scoring an Epic or a
  Task, or ordering a portfolio.
---

# WSJF

`Cost of Delay = UBV + TC + RR-OE`. `WSJF = CoD / Job Size`, two decimal places, raw
sums — never normalize CoD before dividing. `jobSize > 0` always.

Run it twice over the same inputs and it must produce the same number. Adding items to the
portfolio must not move the score of an item whose own inputs did not change.

## Pick the level

| | Epic | Task |
|---|---|---|
| What it is | a container for a requirement — it spans repositories, becomes many Tasks, and nobody implements it directly | one agent's work inside one repository |
| UBV, TC | **judged** from the requirements document | **inherited** from the parent Epic, with its confidence |
| RR-OE graph edges | the order in which architecture must be ESTABLISHED — one Epic's design is drawn from another Epic's requirements first | BUILD order — one Task must be built before another |
| Job Size | **judged** as SPAN, replaced by the roll-up of child sizes once children exist | **judged** in developer-days |

The bands, the size scale and the roll-up mapping differ by level and live in
`scripts/wsjf.py`. Read them with `wsjf.py scales --level epic|task`; they are not restated
here, and a number quoted from anywhere else is not the rubric.

## Accept what is known; compute what is missing

The script takes one JSON document and fills in the gaps:

- a supplied `jobSize` is used as given; supplied `childSizes` replace it by roll-up;
- supplied `edges` are walked to get the reachability count; a supplied `reaches` count is
  banded without walking anything; a supplied `riskReductionOpportunityEnablement` is used
  as given and no graph is needed at all;
- supplied `userBusinessValue` and `timeCriticality` are used as given.

An item whose RR-OE cannot be reached by any of those routes comes back in `unscored`
naming what is missing. Ask for the dependency edges. Where the work genuinely has no
dependency graph, supply RR-OE per item on the caller's own grounds, or report that the
dimension cannot be computed and score nothing — never substitute a judgment of the prose.

## 1. User-Business Value and Time Criticality

### At Epic level — judge them, and judge the whole portfolio in one session

UBV asks what is lost if this requirement is never delivered:

```
  1-2 : Minimal — internal convenience, no measurable user impact
  3   : Moderate — meaningfully improves an existing capability
  5   : Significant — directly addresses a user pain or a market need
  8   : High — revenue-impacting, or broad customer-facing impact
  13  : Critical — revenue loss, major customer risk, a core capability
  20  : Existential — regulatory mandate, platform failure, contract risk
```

Judge the stated outcome, not the machinery underneath it. An Epic whose whole point is
plumbing still carries the value of the capability it exists to deliver; that value is
expressed in RR-OE, and a low UBV is not a penalty.

TC asks how fast that value decays if deferred:

```
  1   : No decay — timing is irrelevant
  2   : Mild — weeks or months of deferral change little
  3   : Moderate — value noticeably diminishes over weeks
  5   : Meaningful drop within this quarter
  8   : Hard deadline this quarter, or a competitive window closing
  13  : Fixed external deadline — regulation, event, integration partner
  20  : Imminent or passed — value approaches zero if not done now
```

Importance is UBV. Do not inflate TC because an item feels important. Work with no launch
date, no customers and no external commitment has little for TC to measure; say so in the
confidence rather than manufacturing urgency.

These two are judged against descriptive rungs, and descriptive rungs drift: one session's
"significant" is another's "high". An agent holding a subset cannot see where it has put
the line, so its 3 and another agent's 2 mean nothing to each other, and the ranking that
results is an artifact of how the work was divided. **Judge the portfolio whole, in one
session, or not at all.** Where it is too large to hold each requirements document in full,
read a digest of every item — title, the feature description, the scope — and open the full
document only for the ones whose UBV or Job Size the digest cannot support.

Nothing here is scored from calibration guidance a caller supplies. The rungs above, the
requirements document and the dependency graph are the whole input.

### At Task level — inherit them

```
userBusinessValue := parent.wsjf_ubv
timeCriticality   := parent.wsjf_tc
confidence        := parent.wsjf_confidence
```

Copy them. Do not read the Task's own description and form a view: a Task is scoped to one
agent's work in one repository, so a plumbing Task under a revenue-critical Epic reads as
"minimal user impact" on its own words and scores 1. That is not a low-value Task; it is
the wrong question asked of the wrong document. Inheriting the confidence matters as much
as inheriting the scores — judged from its own text, every Task hits the "insufficient
information" rung on two dimensions and is capped forever.

**A Task whose parent carries no score is UNSCORED.** Say so, name the parent, and stop.
Do not invent a value and do not fall back to the Task's text. An unscored Task is a
request for its Epic to be scored, not a scoring failure. Record the parent as
`valueFrom`; when the Epic is re-scored, every Task under it is re-scored by re-running
this step, never re-judged.

## 2. RR-OE — a count over the dependency graph

**This is the architectural dimension and it is what orders the portfolio. It is a count,
not an argument.**

```
reaches(X) = the number of DISTINCT items reachable from X by following edges
             forward, transitively, within the set (X itself excluded)
```

Transitive, because something that unblocks one item which unblocks six has unblocked
seven. The script walks it and bands the count.

The graph must be acyclic. When it is not, the count is undefined: the script reports the
cycle and scores nothing.

**Do not judge RR-OE from prose in any circumstance, including when the count feels
wrong.** A count that feels wrong is a missing or reversed edge, and the edge is where it
gets fixed. Report the item whose computed RR-OE contradicts its requirements document as a
**graph defect**, naming the edge you believe is missing, and score the count meanwhile.

"No user-visible output" and "unblocks other work" classify nothing; the reachability count
is the test that discriminates.

## 3. Job Size

### At Epic level — SPAN, not developer-days

How much of the system the requirement moves. Four denominators, judged together:
**repositories** in the ruled span; **child work items** the document implies; **surfaces**
touched; and **new versus extends** — a new service, datastore or external integration, or
a change within material that already exists.

```
  1   : One repo, one child item, one existing surface, extends what is there
  2   : One repo, two or three child items, extends existing patterns
  3   : One repo, several child items, or one new surface on an existing service
  5   : Two repos, or one new surface plus the consumers it forces to change
  8   : Three or four repos, or a new capability established across a surface
  13  : Four-plus repos, or a new service or repository plus its consumers
  20  : A new subsystem — new repositories, a new datastore, new externally
        facing surfaces
  40  : Platform-scale — several new services, a new external integration, and
        migration of material that already ships
```

Removal counts: an item that contradicts shipped material carries the cost of removing it,
and the repositories holding that material are in the span. Where the repository span has
not been ruled, say so in the confidence for this dimension and score from the document's
own reach — do not guess a repository count.

There is no "score as-is, it should be decomposed" rung. An Epic IS the thing that gets
decomposed.

### At Task level — developer-days

Relative effort, not calendar time:

```
  1   : Trivial — hours, a single isolated change
  2   : Small — less than a day
  3   : Medium-small — 1-2 days, one area of the codebase
  5   : Medium — 3-5 days, multiple components
  8   : Large — 1-2 weeks, cross-cutting within the repository
  13  : X-Large — 2-4 weeks, significant design plus implementation
```

A Task that would score above the scale's ceiling is a **decomposition fault**, not a large
Task. The script clamps it to the ceiling and returns it under `sizeFaults`; report it
against the decomposition.

### The roll-up — top-down value, bottom-up cost

An Epic's span size is an estimate made before the work is known. The moment its Tasks
exist, the estimate is replaced: pass every Task's `wsjf_size` as `childSizes` and the
script sums them, maps the sum onto the span scale so every Epic keeps one denominator, and
recomputes the score. Closed Tasks count — the cost is the whole job, not what is left.

Value stays top-down: UBV and TC are never re-derived from the children, and RR-OE stays a
function of the Epic graph, never of the Task graph. Re-run the roll-up whenever the child
set changes.

## 4. Compute

Hand the script what you have:

```bash
scripts/wsjf.py score --level epic <<'JSON'
{
  "edges": [{"from": "E1", "to": "E2"}],
  "items": [
    {"id": "E1", "userBusinessValue": 13, "timeCriticality": 3, "jobSize": 8,
     "confidence": 88},
    {"id": "E2", "userBusinessValue": 5, "timeCriticality": 2, "childSizes": [3, 5, 2],
     "confidence": 90}
  ]
}
JSON
```

Each scored item comes back with its dimensions, `reaches`, `costOfDelay`, `jobSize`,
`sizeSource`, `wsjf`, and a `metadata` object carrying the exact keys and values to record.
Everything the script could not score comes back in `unscored` with a reason.

`scripts/wsjf.py reach` returns the counts and bands alone, for a caller maintaining a
graph. `scripts/wsjf.py selftest` exercises the bands, the roll-up and the graph walk.

## Confidence

A percentage per judged dimension:

```
  98-100% : the source document directly supports this score
  66-97%  : reasonable inference; an assumption was made
  <=65%   : insufficient information — flag it with the reason
```

Overall confidence is the weighted average biased toward the lowest dimension, and cannot
exceed 70% when any dimension is below 65%. A computed RR-OE and a rolled-up Job Size are
98-100% by construction — they were counted, not judged. At Task level, overall confidence
is the inherited confidence, lowered to the Job Size confidence when that is lower; pass
both to the script as `confidence` and `sizeConfidence`.

## Output — the numbers are the deliverable

Emit a fenced `json` block first. This is what a program reads; nothing else in the output
is.

```json
{
  "rubric": "epic-wsjf",
  "scores": [
    {
      "id": "<item id>",
      "userBusinessValue": 13,
      "timeCriticality": 3,
      "riskReductionOpportunityEnablement": 13,
      "reaches": 12,
      "valueFrom": null,
      "costOfDelay": 29,
      "jobSize": 8,
      "sizeSource": "supplied",
      "wsjf": 3.63,
      "confidence": 88,
      "rationale": {
        "userBusinessValue": "<1-3 sentences>",
        "timeCriticality": "<1-3 sentences>",
        "jobSize": "<1-3 sentences, naming the denominators>"
      },
      "assumptions": ["<one entry per assumption that could move a score>"]
    }
  ],
  "graphDefects": [
    { "id": "<item id>", "reaches": 0, "computed": 1,
      "missingEdge": "<blocker> -> <blocked>", "why": "<one line>" }
  ],
  "unscored": [
    { "id": "<item id>", "reason": "<why it could not be scored>" }
  ]
}
```

`rubric` is `epic-wsjf` or `task-wsjf` for the level scored. Every item appears exactly
once, in `scores` or in `unscored`. RR-OE carries no rationale — the count is the
reasoning. `graphDefects` never changes a score. At Task level the only rationale worth
writing is one line on Job Size, since the rest is arithmetic over it.

Then, for a person, a short prose section per judged dimension. Keep it under a page.

## Metadata keys

Recorded as issue **metadata**, merged rather than replaced, never as a note — a score in
prose is a score no gate can see. The script emits the exact values under `metadata`.

| key | value |
|---|---|
| `wsjf` | the score, two decimal places |
| `wsjf_calculated_at` | ISO 8601 timestamp |
| `wsjf_rubric` | the level's rubric name |
| `wsjf_ubv` | User-Business Value |
| `wsjf_tc` | Time Criticality |
| `wsjf_value_from` | the parent the value was inherited from, at Task level |
| `wsjf_rroe` | computed RR-OE |
| `wsjf_reaches` / `wsjf_unblocks` | the reachability count RR-OE was banded from, under the level's key |
| `wsjf_cod` | Cost of Delay |
| `wsjf_size` | Job Size rung |
| `wsjf_size_source` | `supplied` or `child-rollup` |
| `wsjf_size_child_total` | the summed child sizes, on a roll-up only |
| `wsjf_confidence` | overall confidence, integer percent |
| `wsjf_content_hash` | the content fingerprint (`agent-teams-workforce:beads-contract`) of the bead the judged values were judged from — the Epic's PRD or the Task's own content |

`wsjf_ubv`, `wsjf_tc` and `wsjf_confidence` are what a child inherits, and `wsjf_size` is
what a parent's roll-up sums, so all four are required on every scored item. Values carry
no character a shell would mis-split: numbers, ISO timestamps, ids and kebab-case words.

## Scoring errors to avoid

- Judging RR-OE from prose when the graph is right there.
- Overriding a computed RR-OE that looks wrong instead of reporting the missing edge.
- Re-deriving UBV or TC from a Task's own description. They are inherited, always.
- Inventing a value for a Task whose parent is unscored.
- Splitting a portfolio across sessions, or judging one item in isolation against no
  portfolio at all.
- Accepting calibration bands from a caller in place of the ones in this rubric.
- Sizing an Epic in developer-days, or leaving a span estimate in place after its children
  exist.
- Scoring a Task above the size ceiling instead of reporting the decomposition fault.
- Normalizing CoD before dividing.
- Re-deriving UBV or TC from the children. Value is top-down; only cost rolls up.
- Recording the score only in prose.
