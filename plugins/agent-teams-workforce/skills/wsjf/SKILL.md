---
name: wsjf
description: >-
  Score work with WSJF at either level — an EPIC, a PRD (a business requirement), or a
  TASK, one agent's work inside it. Cost of Delay is User-Business Value plus Time
  Criticality plus Risk Reduction / Opportunity Enablement, divided by Job Size. RR-OE is
  COMPUTED from transitive reachability over a dependency graph rather than argued from
  prose — the architecture-dependency graph between Epics, where it measures the Epic as an
  Architectural Enabler, or the build graph between Tasks — and `scripts/wsjf.py` owns every band, the size scale and the child-size roll-up.
  Job Size means the same thing at both levels: the relative amount of work to deliver the
  outcome, judged against the agent pipeline, on one Fibonacci scale, with a plausible
  range and a confidence.
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
| What it is | a PRD, a business requirement — it spans repositories, becomes many Tasks, and nobody implements it directly | one agent's work inside one repository |
| UBV, TC | **judged** from the requirements document | **inherited** from the parent Epic, with its confidence |
| RR-OE graph edges | ARCHITECTURE order — a feature both Epics need whose architecture is not approved, its driver first (`epicorder.py`); RR-OE measures the Epic as an Architectural Enabler | BUILD order — one Task must be built before another; RR-OE measures how many sibling Tasks it unblocks |
| Job Size | **judged** as an estimate with a plausible range; once Tasks exist, the plain sum of their sizes | **judged** on the same scale; above 13 is a decomposition fault |

The RR-OE bands differ by level and live in `scripts/wsjf.py`, with the size scale and the
Task decomposition-fault threshold. Read them with `wsjf.py scales --level epic|task`; they are not restated here,
and a number quoted from anywhere else is not the rubric.

## Accept what is known; compute what is missing

The script takes one JSON document and fills in the gaps:

- a supplied `jobSize` is the judged estimate, placed on the Fibonacci scale; supplied
  `childSizes` (Epic only) make the size their plain sum, and the estimate is kept beside it;
- a supplied `sizeLow`, `sizeHigh` and `sizeConfidence` are the estimate's plausible range
  and confidence;
- supplied `edges` are walked to get the reachability count; a supplied `reaches` count is
  banded without walking anything; a supplied `riskReductionOpportunityEnablement` is used
  as given and no graph is needed at all;
- supplied `userBusinessValue` and `timeCriticality` are used as given.

An item whose RR-OE cannot be reached by any of those routes comes back in `unscored`
naming what is missing. Ask for the dependency edges. Where the work genuinely has no
dependency graph, supply RR-OE per item on the caller's own grounds, or report that the
dimension cannot be computed and score nothing — never substitute a judgment of the prose.

## 1. User-Business Value and Time Criticality

### At Epic level — judge them from the full requirements document, one Epic at a time

UBV asks what is lost if this requirement is never delivered:

```
  1-2 : Minimal — internal convenience, no measurable user impact
  3   : Moderate — meaningfully improves an existing capability
  5   : Significant — directly addresses a user pain or a market need
  8   : High — revenue-impacting, or broad customer-facing impact
  13  : Critical — revenue loss, major customer risk, a core capability
  20  : Existential — regulatory mandate, platform failure, contract risk
```

Judge the stated outcome, not the machinery underneath it. An Epic whose requirements
matter mostly because other requirements are designed on the decisions they drive carries
that enabling value in RR-OE, and a low UBV is not a penalty.

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

Each Epic is judged on its own, from its full requirements document, against the rungs
above and the reference jobs. The rungs are the calibration: an Epic is placed on them by
what its own document says, not by where other Epics sit. No condensed version of the
document, no other Epic's document and no other Epic's values are an input, so adding an
Epic never moves another Epic's judged values.

Nothing here is scored from calibration guidance a caller supplies. The rungs above, the
requirements document and the dependency graph are the whole input.

### At Task level — inherit them

The Task's User-Business Value, Time Criticality and value confidence are its parent's, as
recorded on the parent under the metadata keys the schema names (see "Metadata keys" below).
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

**It is a count, not an argument.** What it measures depends on the level:

- **Epic** — the Architectural Enabler measure. An Epic that drives many unapproved features
  other Epics also need scores high; an Epic that waits for others' drivers scores low. The
  edges come from the features the Epics share (`agent-teams-workforce:epic-sequencing`), never
  from build facts.
- **Task** — how many Tasks it unblocks: the edges are ordinary build dependencies between
  Tasks, known once the architecture is settled.

```
reaches(X) = the number of DISTINCT items reachable from X by following edges
             forward, transitively, within the set (X itself excluded)
```

Transitive, because an item reaching one item that reaches six reaches seven. The script
walks it and bands the count.

The walk visits each item once, so a cycle in the graph does not stop scoring; every item
on a cycle counts the others it reaches. `cycle` in the output is always null.

**Do not judge RR-OE from prose in any circumstance, including when the count feels
wrong.** A count that feels wrong is a missing or reversed edge, and the edge is where it
gets fixed. Report the item whose computed RR-OE contradicts its requirements document as a
**graph defect**, naming the edge you believe is missing, and score the count meanwhile.

"No user-visible output" and "unblocks other work" classify nothing; the reachability count
is the test that discriminates.

## 3. Job Size

### One scale, one meaning, both levels

**Job size represents the relative amount of work required to deliver the stated outcome,
considering volume, complexity, available knowledge, and uncertainty, against a consistent
reference capability.** That reference capability is the agent pipeline with its normal
tools, institutional knowledge and established practices — not an imagined human developer,
and not whichever model performs the estimate. It is not calendar time and not a count of
repositories.

The Epic estimate covers delivery of the requirement; the Task estimate covers delivery of
its assigned portion. Both use the same definition of a point. An Epic and a Task can both
be 5: their tracking types do not determine their size.

Four factors guide the comparison, at both levels:

| Factor | Question | What increases size |
|---|---|---|
| Volume | How much distinct work does the outcome require? | More behaviors, cases, transformations, or deliverables |
| Complexity | How intricately do the parts interact? | Interdependent rules, exceptions, state transitions, ordering, concurrency, or precision constraints |
| Knowledge | How much relevant understanding and proven practice is already available? | Required learning, unfamiliar domain rules, or absence of an applicable established approach |
| Uncertainty | What unresolved facts could materially change the required work? | Ambiguous scope, unknown feasibility, or assumptions with substantially different consequences |

Knowledge and uncertainty are different. An unfamiliar but well-documented operation
involves learning. An unresolved question about whether an operation is possible introduces
uncertainty.

At Epic level, answer these from the requirement and institutional knowledge. At Task
level, use the established architecture, design and implementation instructions. **Never
require the Epic estimator to invent a solution.**

The factors guide comparison. They are not independent quantities, and they are never
scored separately, added or multiplied into a score. The numbers express approximate
relative magnitude, not measured ratios or time commitments.

The scale is Fibonacci and continues upward as far as the work needs:

```
1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, ...
```

A judged size between two rungs is placed on the rung above it.

### Reference jobs

Every size is placed by comparison with reference jobs, and its rationale names the
comparison.

- **Reference jobs are the elaborated Epics**: each Epic whose Tasks all carry a size, with
  its original estimate beside its refined size, the sum of its Tasks. They are read from
  the tracker (the Epic's recorded estimate and range, and each of its Tasks' recorded size,
  under the metadata keys the schema names); the set grows as Epics are elaborated.
- **Until any exist**, judge knowledge and uncertainty from what already exists: the
  architecture document, the existing code, and the other artifacts that show what is
  already decided or built and what must be decided or built from scratch.

### Range and confidence

Every judged size carries a **plausible range** — the lowest and highest size the work
could reasonably turn out to be, with the estimate inside it — and a **confidence**, an
integer percent in the estimate. What remains unknown widens the range and lowers the
confidence.

### At Epic level

An Epic is sized before its design exists, from the requirement and institutional
knowledge, without inventing a solution. **Do not automatically enlarge every uncertain
Epic.** Missing implementation design is normal at this stage; it is not itself evidence of
exceptional difficulty, and it shows in the range and the confidence. Uncertainty enlarges
an Epic where the requirement leaves an unresolved fact that could materially change the
work.

There is no "score as-is, it should be decomposed" rung. An Epic IS the thing that gets
decomposed.

### At Task level

A Task is one agent's work in one repository, sized on the same unbounded scale. A Task
above **13** should have been split. It is a **decomposition fault**: say so, and record the
size you judged. Do not reduce it to 13. The script keeps the judged rung as the Task's
size, so the Epic's refined size counts it in full, and returns the Task under `sizeFaults`
with `aboveScale: true`; report it against the decomposition.

### The roll-up — top-down value, bottom-up cost

An Epic's estimate is made before the work is known. Its Tasks are written one by one while
it is elaborated, so until its elaboration is finished (its elaboration state, as the
`agent-teams-workforce:beads-contract` schema defines it) the Epic is
sized by its judged estimate, never by the sum of the Tasks written so far. Once elaboration is
done and every Task carries a size, pass those sizes as `childSizes` with the Epic's estimate
and its range:
the Epic's size becomes the **plain sum** of its distinct Tasks' positive sizes (a
missing or non-positive size is left out of the sum), which need not be a
Fibonacci number, and the score is recomputed from it. Closed Tasks count — the cost is the
whole job, not what is left. The original estimate stays recorded beside the summed size.

A refined size outside the estimate's plausible range is flagged under `outsideRange`, and
the script records the flag in metadata. It is a prompt to examine the Epic — new work, changed scope, or
inconsistent estimation — and never an error.

Value stays top-down: UBV and TC are never re-derived from the children, and RR-OE stays a
function of the Epic graph, never of the Task graph. Once the Epic is done, re-run the
roll-up whenever the child set changes.

## 4. Compute

Hand the script what you have:

```bash
scripts/wsjf.py score --level epic <<'JSON'
{
  "edges": [{"from": "E1", "to": "E2"}],
  "items": [
    {"id": "E1", "userBusinessValue": 13, "timeCriticality": 3, "jobSize": 34,
     "sizeLow": 21, "sizeHigh": 55, "sizeConfidence": 70, "confidence": 88},
    {"id": "E2", "userBusinessValue": 5, "timeCriticality": 2, "jobSize": 21,
     "sizeLow": 13, "sizeHigh": 34, "childSizes": [3, 5, 2, 8], "confidence": 90}
  ]
}
JSON
```

Each scored item comes back with its dimensions, `reaches`, `costOfDelay`, `jobSize`,
`sizeSource`, its estimate's fields, `wsjf`, and a `metadata` object carrying the exact keys
and values to record. Everything the script could not score comes back in `unscored` with a
reason; a Task above 13 keeps its judged size and comes back in `sizeFaults`; an Epic whose summed size falls outside
its estimate's range comes back in `outsideRange`.

`scripts/wsjf.py reach` returns the counts and bands alone, for a caller maintaining a
graph.

## Confidence

A percentage per judged dimension:

```
  98-100% : the source document directly supports this score
  66-97%  : reasonable inference; an assumption was made
  <=65%   : insufficient information — flag it with the reason
```

Two confidences are kept, and never combined:

- **Value confidence** (`confidence`) covers UBV and TC. It is the weighted average of the
  two biased toward the lower, and cannot exceed 70% when either is below 65%. A computed
  RR-OE was counted, not judged, and does not affect it. At Task level it is the Epic's,
  inherited with the value.
- **Size confidence** (`sizeConfidence`) covers the size estimate alone, and stays with it.
  A Task's size confidence is its own.

Pass both; the script records each under its own key and lowers neither.

## Output — the numbers are the deliverable

The judged values are the deliverable, and they go in the judgment file, whose one definition
is artifact-handoff's `schemas/wsjf-judgment.schema.json` (`#/$defs/EpicJudgment` or
`#/$defs/TaskJudgment` for the level scored). Its descriptions define every member: the
rubric name, one score per judged item with the rationale for each judged dimension and the
assumptions that could move it, and `unscored` with the concrete missing input. Every item
appears exactly once, in `scores` or in `unscored`.

The judgment holds judged inputs only. RR-OE, reaches, cost of delay, size source and WSJF are
what `scripts/wsjf.py score` prints from them (section 4); RR-OE carries no rationale — the
count is the reasoning. At Task level the only rationale worth writing is one line on Job
Size, since the rest is arithmetic over it.

Then, for a person, a short prose section per judged dimension. Keep it under a page.

## Metadata keys

Recorded as issue **metadata**, merged rather than replaced, never as a note — a score in
prose is a score no gate can see. The script emits the exact keys and values under
`metadata`.

The keys, their value types and their allowed values are defined in one place: the
`WSJF_KEYS` group of the JSON Schema `schemas/bead-metadata.schema.json` in the
`agent-teams-workforce:beads-contract` skill. Read them there, and read a bead's recorded
values with that skill's `metadata get`; this rubric restates none of them. The
User-Business Value, Time Criticality and value confidence are what a child inherits, and the
size is what a parent's roll-up sums, so all four are recorded on every scored item; every
judged size also records its estimate, plausible range and confidence. Values carry no
character a shell would mis-split: numbers, ISO timestamps, ids and kebab-case words.

## Scoring errors to avoid

- Judging RR-OE from prose when the graph is right there.
- Overriding a computed RR-OE that looks wrong instead of reporting the missing edge.
- Re-deriving UBV or TC from a Task's own description. They are inherited, always.
- Inventing a value for a Task whose parent is unscored.
- Judging an Epic from anything but its own full requirements document: a condensed
  version, an excerpt, or other Epics' values.
- Accepting calibration bands from a caller in place of the ones in this rubric.
- Sizing in calendar time, human effort or repository counts instead of relative work
  against the agent pipeline.
- Adding or multiplying the four size factors instead of weighing them to compare with
  reference jobs.
- Enlarging an Epic's size because its design does not exist yet.
- Inventing a solution in order to size an Epic.
- Sizing an Epic larger than a Task because it is an Epic.
- A size with no plausible range or no confidence.
- Leaving an estimate in place as the size after the Epic's Tasks exist, or snapping the
  summed size onto a rung.
- Treating a refined size outside the estimate's range as an error rather than a flag.
- Reducing a Task above 13 to 13, or scoring it without reporting the decomposition fault.
- Normalizing CoD before dividing.
- Re-deriving UBV or TC from the children. Value is top-down; only cost rolls up.
- Recording the score only in prose.
