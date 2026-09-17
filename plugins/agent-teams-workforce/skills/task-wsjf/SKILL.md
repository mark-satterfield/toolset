---
name: task-wsjf
description: >-
  Score a TASK with WSJF — arithmetic, not judgement. Value and Time Criticality are
  INHERITED from the parent Epic along with its confidence and are never re-derived from
  the Task's own text, because a Task's description is scoped to one agent's work in one
  repository and cannot carry the value it serves. RR-OE is COMPUTED from how many Tasks
  the Task unblocks in the dependency graph. Job Size in developer-days is the only judged
  input. Use whenever a Task is scored or re-scored. For an Epic, use
  `agent-teams-workforce:epic-wsjf` instead — never this one.
---

# Task WSJF

Three of the four dimensions are computed. **Scoring a Task requires no model call**, and
running this rubric twice over the same inputs must produce the same number.

| Dimension | Where it comes from |
|---|---|
| User-Business Value | **inherited** from the parent Epic's `wsjf_ubv` |
| Time Criticality | **inherited** from the parent Epic's `wsjf_tc` |
| Risk Reduction / Opportunity Enablement | **computed** from the dependency graph |
| Job Size | **judged** — developer-days, the only estimate in the rubric |

`Cost of Delay = UBV + TC + RR-OE`. `WSJF = CoD / Job Size`, two decimal places, raw
sums — never normalize CoD before dividing. `jobSize > 0` always.

## 1. Inherit value and criticality

Read the parent Epic's metadata (`agent-teams-workforce:beads-contract` resolves the
parent; never hand-roll `jq` against `bd`):

```
userBusinessValue := epic.wsjf_ubv
timeCriticality   := epic.wsjf_tc
confidence        := epic.wsjf_confidence
```

Copy them. Do not re-read the Task's description and form a view. **A Task's own text
cannot support these two dimensions**: the decomposer is told each Task is one agent's
work within one repository, so a plumbing Task under a revenue-critical Epic reads as
"minimal user impact" on its own words and scores 1. That is not a low-value Task; it is
the wrong question asked of the wrong document.

Inheriting the Epic's confidence matters as much as inheriting the scores. Judged from
its own text, every Task hits the "insufficient information" rung on two dimensions and
is capped at 70% confidence forever — the confidence protocol correctly detecting that
the input is wrong for the question. Inherited, the Task is exactly as confident as the
Epic it serves.

**A Task whose parent Epic carries no score is UNSCORED.** Say so, name the Epic, and
stop. Do not invent a value, and do not fall back to reading the Task's text. An unscored
Task is a request for the Epic to be scored, not a scoring failure.

Record the Epic the values came from as `wsjf_value_from`. When the Epic is re-scored,
every Task under it is re-scored by re-running this step — no Task is re-judged.

## 2. Compute RR-OE from the dependency graph

The edges already exist: the decomposer emits `edges` as `{from, to}`, meaning *from must
be built before to*, and each bead records `dependsOn`. So "what future work does this
unblock" is a count, not an argument.

```
unblocks(T) = the number of DISTINCT Tasks reachable from T by following edges
              forward, transitively, within this Task set (T itself excluded)
```

Transitive, because a Task that unblocks one Task which unblocks six has unblocked seven.
Band the count:

```
  unblocks = 0      -> RR-OE  1   Nothing waits on this; it is a leaf
  unblocks = 1      -> RR-OE  3   One downstream Task
  unblocks = 2-3    -> RR-OE  5   A small downstream set
  unblocks = 4-6    -> RR-OE  8   A substantial part of the Story waits on this
  unblocks = 7-9    -> RR-OE 13   Most of the Story waits on this
  unblocks >= 10    -> RR-OE 20   Blocking — the Story cannot proceed without it
```

The graph must be acyclic. If it is not, the reachability count is undefined: report the
cycle and score nothing. Do not judge RR-OE from prose in any circumstance, including
when the count feels wrong — a count that feels wrong is a wrong edge, and the edge is
where it gets fixed.

## 3. Judge Job Size — the one estimate

Relative effort, not calendar time. This scale is unchanged and is already correct for a
Task: a Task is one agent's work in one repository.

```
  1   : Trivial — hours, a single isolated change
  2   : Small — less than a day
  3   : Medium-small — 1-2 days, one area of the codebase
  5   : Medium — 3-5 days, multiple components
  8   : Large — 1-2 weeks, cross-cutting within the repository
  13  : X-Large — 2-4 weeks, significant design plus implementation
```

There is no rung above 13. A Task that would score higher is a **decomposition fault**,
not a large Task: report it against the decomposition and score it 13 meanwhile.

Assign a confidence to this dimension on its own (98-100% the Task's contract supports
it; 66-97% inference; ≤65% insufficient information, flagged). The overall confidence is
the inherited Epic confidence, lowered to the Job Size confidence when that is lower.

## 4. Compute

```
costOfDelay = userBusinessValue + timeCriticality + riskReductionOpportunityEnablement
wsjf        = costOfDelay / jobSize          (two decimal places)
```

## Output — the numbers are the deliverable

Emit a fenced `json` block. One object per Task, and nothing in the prose is read by a
program.

```json
{
  "rubric": "task-wsjf",
  "scores": [
    {
      "key": "T3",
      "id": "<bead id, or null>",
      "userBusinessValue": 13,
      "timeCriticality": 5,
      "valueFrom": "<parent Epic bead id>",
      "riskReductionOpportunityEnablement": 8,
      "unblocks": 5,
      "jobSize": 3,
      "costOfDelay": 26,
      "wsjf": 8.67,
      "confidence": 85,
      "rationale": "<one line: what makes this 1-2 days, and what it unblocks>"
    }
  ],
  "unscored": [
    { "key": "T7", "reason": "parent Epic <id> carries no wsjf_ubv" }
  ],
  "notes": "<optional, one line>"
}
```

Every Task in the set appears exactly once, in `scores` or in `unscored`. `jobSize` is
the only value a person argued about; the rest is arithmetic over it.

## Metadata keys

Recorded as bead **metadata**, merged (`--set-metadata`), never as a note — a score in
prose is a score no gate can see, and the bead is never dispatchable. Metadata sits
outside the content fingerprint, so recording a score never makes a bead look stale.

| key | value |
|---|---|
| `wsjf` | the score, two decimal places |
| `wsjf_calculated_at` | ISO 8601 timestamp |
| `wsjf_rubric` | `task-wsjf` |
| `wsjf_ubv` | inherited User-Business Value |
| `wsjf_tc` | inherited Time Criticality |
| `wsjf_value_from` | the parent Epic's bead id |
| `wsjf_rroe` | computed RR-OE |
| `wsjf_unblocks` | the reachability count RR-OE was banded from |
| `wsjf_cod` | Cost of Delay |
| `wsjf_size` | Job Size |
| `wsjf_confidence` | overall confidence, integer percent |

`wsjf_size` is what `epic-wsjf` sums when it rolls Epic size up from its Tasks, so it is
required on every scored Task. Metadata values carry no characters `bd` would mis-split:
numbers, ISO timestamps, bead ids and kebab-case words only.

## Scoring errors to avoid

- Re-deriving UBV or TC from the Task's description. They are inherited, always.
- Judging RR-OE from prose when the graph is right there.
- Inventing a value for a Task whose parent Epic is unscored.
- Scoring a Task above 13 on size instead of reporting the decomposition fault.
- Normalizing CoD before dividing.
- Recording the score only in the notes line.
