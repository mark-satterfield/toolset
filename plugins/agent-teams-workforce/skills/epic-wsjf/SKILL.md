---
name: epic-wsjf
description: >-
  Score an EPIC — a PRD-scale container — with WSJF. Job Size is denominated in SPAN
  (repositories, Stories, surfaces, new-vs-extends) with headroom above 20, not in
  developer-days, because an Epic is not a job one agent does. RR-OE is where an Epic that
  ESTABLISHES a canonical pattern outranks one that merely CONSUMES it — that is the
  dimension that puts foundations first. Once the Epic's Tasks exist its size is replaced by
  the roll-up of their sizes and the score is recomputed. Use when scoring or re-scoring an
  Epic, ordering Epics for elaboration, or rolling Task sizes up into an Epic. For a Task,
  use `agent-teams-workforce:task-wsjf` instead — never this one.
---

# Epic WSJF

An Epic is created with its PRD. It is a **container for a requirement**, not a job. It
spans repositories, it becomes many Stories and many Tasks, and no one implements it
directly. Scoring it on a developer-days scale is what made every Epic score the same
size, and a denominator that does not discriminate turns WSJF into a pure
cost-of-delay ranking.

So this rubric changes two things and keeps two.

| Dimension | Epic rubric |
|---|---|
| User-Business Value | kept — what is lost if the PRD is never delivered |
| Time Criticality | kept — how fast that value decays |
| Risk Reduction / Opportunity Enablement | **rewritten** — establish-versus-consume |
| Job Size | **rewritten** — span, with headroom above 20 |

`Cost of Delay = UBV + TC + RR-OE`. `WSJF = CoD / Job Size`, two decimal places, raw
sums — never normalize CoD before dividing.

## Scale

Fibonacci: 1, 2, 3, 5, 8, 13, 20, **40**. The 40 rung exists on the Job Size scale only,
and it exists because two Epics differing five-fold in span must not land on the same
number. All scores are relative to the other Epics in the same portfolio, not absolute
measurements.

There is no "score as-is, it should be decomposed" rung. An Epic IS the thing that gets
decomposed; saying so is not a score.

## User-Business Value (UBV)

What is lost if this PRD is never delivered?

```
  1-2 : Minimal — internal convenience, no measurable user impact
  3   : Moderate — meaningfully improves an existing capability
  5   : Significant — directly addresses a user pain or a market need
  8   : High — revenue-impacting, or broad customer-facing impact
  13  : Critical — revenue loss, major customer risk, a core capability
  20  : Existential — regulatory mandate, platform failure, contract risk
```

Judge the PRD's stated outcome, not the machinery underneath it. An Epic whose whole
point is plumbing still carries the value of the capability it exists to deliver — that
value is expressed in RR-OE below, and a low UBV there is not a penalty.

## Time Criticality (TC)

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

Importance is UBV. Do not inflate TC because an Epic feels important.

## Risk Reduction / Opportunity Enablement (RR-OE)

**This is the architectural dimension, and it is the one that orders the portfolio.**

Ask one question: does this Epic **ESTABLISH** a pattern that later work is designed
from, or does it **CONSUME** a pattern something else already established?

- **Establishes** — this Epic is the first to rule a cross-cutting concern. Its
  architecture decisions constrain every later Epic in that concern. Sign-up and sign-in
  establish identity: the credential store, the session contract, the token shape, the
  error vocabulary. Everything that later touches identity is designed from that ruling.
- **Consumes** — the pattern exists and this Epic uses it. Password reset is an identity
  feature, but it consumes the credential store and the session contract rather than
  ruling them. It enables nothing downstream.

```
  1   : Consumes only — nothing is designed from this; it unblocks nothing
  2   : Minor — vague future benefit, no concrete downstream Epic
  3   : Meaningful — reduces a systemic risk, or unblocks one downstream Epic
  5   : Significant — removes a class of risk, or unblocks a feature set
  8   : Major — establishes a pattern other Epics extend, or removes an
        architectural constraint
  13  : Canonical — establishes THE pattern for a cross-cutting concern
        (identity, persistence, deployment, observability); later Epics in that
        concern cannot be designed until this one is ruled
  20  : Platform foundation — a large portion of the planned portfolio cannot be
        designed or built without this
```

Two rules that follow from establish-versus-consume:

1. **An Epic that establishes is never scored below 8**, whatever its UBV. Scoring the
   foundation low on RR-OE is the error this dimension exists to prevent.
2. **An Epic that consumes is never scored above 5** on the strength of the concern it
   belongs to. Being adjacent to identity is not enabling identity.

There is no separate Enabler classification. "No direct user-visible output" and
"unblocks other work" classify nothing at PRD scale — every Epic unblocks something.
Establish-versus-consume is the test that actually discriminates.

## Job Size — SPAN, not developer-days

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

Removal counts. An Epic that contradicts shipped material carries the cost of removing
it; the repositories holding that material are in the span.

When the repo-scoping ruling is not available, say so in the confidence for this
dimension and score from the PRD's own reach. Do not guess a repository count.

## Size roll-up — top-down value, bottom-up cost

An Epic's span size is an **estimate made before the work is known**. The moment the
Epic's Tasks exist, the estimate is replaced:

1. Sum every open Task's `jobSize` under this Epic. Task sizes are developer-days on the
   `task-wsjf` scale, so the sum is developer-days. Closed Tasks count — the Epic's cost
   is the whole job, not what is left. Record the sum as `wsjf_size_task_days`.
2. Map the sum onto the span scale, so every Epic in the portfolio keeps one denominator
   and stays comparable:

   ```
   <= 2 days -> 1      <= 5 -> 2      <= 10 -> 3     <= 20 -> 5
   <= 40     -> 8      <= 80 -> 13    <= 160 -> 20   > 160 -> 40
   ```

3. Recompute `WSJF = CoD / Job Size` with the mapped rung, and set
   `wsjf_size_source=task-rollup`.

Value stays top-down: UBV, TC and RR-OE are never re-derived from the Tasks. Cost becomes
bottom-up. Re-run the roll-up whenever the Task set changes.

## Confidence

A percentage per dimension:

```
  98-100% : the PRD (or the repo-scoping ruling) directly supports this score
  66-97%  : reasonable inference; an assumption was made
  <=65%   : insufficient information — flag it with the reason
```

Overall confidence is the weighted average biased toward the lowest dimension. If any
dimension is below 65%, overall confidence cannot exceed 70%. A rolled-up Job Size is
98-100% by construction — it was counted, not judged.

## Output — the numbers are the deliverable

Emit a fenced `json` block first. This is what lands in bead metadata, and nothing else
in the output is read by a program.

```json
{
  "rubric": "epic-wsjf",
  "id": "<bead id, or null>",
  "userBusinessValue": 13,
  "timeCriticality": 5,
  "riskReductionOpportunityEnablement": 13,
  "costOfDelay": 31,
  "jobSize": 8,
  "sizeSource": "span-estimate",
  "sizeTaskDays": null,
  "wsjf": 3.88,
  "confidence": 85,
  "posture": "establishes",
  "rationale": {
    "userBusinessValue": "<1-3 sentences>",
    "timeCriticality": "<1-3 sentences>",
    "riskReductionOpportunityEnablement": "<1-3 sentences, naming what is established or consumed>",
    "jobSize": "<1-3 sentences, naming repos / Stories / surfaces / new-vs-extends>"
  },
  "assumptions": ["<one entry per assumption that could move a score>"]
}
```

- `sizeSource` is `span-estimate` or `task-rollup`. `sizeTaskDays` is the raw
  developer-day sum on a roll-up, null on an estimate.
- `posture` is `establishes` or `consumes`.
- `wsjf` is `costOfDelay / jobSize` to two decimal places.

Then, for a person, a short prose section per dimension: score, confidence, reasoning,
and the assumptions list. Keep it under a page.

## Metadata keys

The score is recorded as bead **metadata**, merged (`--set-metadata`), never as a note —
a score that lands only in prose is a score no gate can see. Use the
`agent-teams-workforce:beads-contract` CLI to write it; never hand-roll `jq` against `bd`.

| key | value |
|---|---|
| `wsjf` | the score, two decimal places |
| `wsjf_calculated_at` | ISO 8601 timestamp |
| `wsjf_rubric` | `epic-wsjf` |
| `wsjf_ubv` | User-Business Value |
| `wsjf_tc` | Time Criticality |
| `wsjf_rroe` | Risk Reduction / Opportunity Enablement |
| `wsjf_cod` | Cost of Delay |
| `wsjf_size` | Job Size rung |
| `wsjf_size_source` | `span-estimate` or `task-rollup` |
| `wsjf_size_task_days` | the developer-day sum, on a roll-up only |
| `wsjf_confidence` | overall confidence, integer percent |

`wsjf_ubv`, `wsjf_tc` and `wsjf_confidence` are what `task-wsjf` inherits, so they are
required, not optional colour. Metadata values carry no characters `bd` would mis-split:
numbers, ISO timestamps and kebab-case words only.

## Scoring errors to avoid

- Scoring an Epic's size in developer-days. That is the Task scale, and it does not reach.
- Scoring an establishing Epic low on RR-OE because it has no user-visible output.
- Scoring a consuming Epic high on RR-OE because its concern is important.
- Leaving a span estimate in place after the Tasks exist.
- Normalizing CoD before dividing.
- Re-deriving UBV or TC from the Tasks. Value is top-down; only cost rolls up.
