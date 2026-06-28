---
name: wsjf
description: Score any job, feature, bug, spec, issue, or description using WSJF (Weighted Shortest Job First). Triggers on /wsjf or when user asks to "score this for WSJF", "WSJF this", "prioritize this with WSJF", or when an unscored issue needs sizing.
---

# WSJF Scoring Engine

Score any input using Weighted Shortest Job First. Never ask clarifying questions.
Score with what you have. Flag uncertainty in confidence and assumptions sections.

## Input Handling

- Text pasted after `/wsjf` — score it directly
- File path — read the file, score its contents
- GitHub issue number — run `gh issue view <n>`, score the output
- No argument — ask once: "Paste or describe the job to score."

## Scoring Scale

Fibonacci only: 1, 2, 3, 5, 8, 13, 20
All scores are relative to each other, not absolute measurements.

## Step 1 — Enabler Detection

Classify as an Enabler if it meets one or more:

- No direct user-visible output
- Unblocks other work items
- Reduces future cost or risk
- Embeds an architectural decision that constrains future work
- "As a user, I want..." does not fit without forcing it

If Enabler, assign exactly one subtype: Architectural | Infrastructure | Exploration (Spike) | Compliance

Enabler scoring rule: do not penalize UBV for no direct user impact. Weight RR-OE on
concrete downstream value. Low UBV + low RR-OE for an Enabler is a scoring error.

## Step 2 — Score Each Dimension

### User-Business Value (UBV)

What is lost if this is never delivered?
  1-2 : Minimal — internal convenience, no measurable user impact
  3   : Moderate — meaningfully improves existing functionality
  5   : Significant — directly addresses user pain or market need
  8   : High — revenue-impacting or broad customer-facing impact
  13  : Critical — revenue loss, major customer risk, core capability
  20  : Existential — regulatory mandate, platform failure, contract risk

### Time Criticality (TC)

How fast does value decay if deferred?
  1   : No decay — timing is irrelevant
  2   : Mild — weeks or months of deferral have little effect
  3   : Moderate — value noticeably diminishes over weeks
  5   : Meaningful drop within this quarter
  8   : Hard deadline this quarter, or competitive window closing
  13  : Fixed external deadline — regulation, event, integration partner
  20  : Imminent or passed — value approaches zero if not done now

### Risk Reduction / Opportunity Enablement (RR-OE)

What future work becomes possible, cheaper, or less risky if done now?
  1   : No dependency or risk impact
  2   : Minor — vague future benefit, no concrete downstream dependency
  3   : Meaningful — reduces systemic risk or enables one downstream job
  5   : Significant — removes a class of risk or unblocks a feature set
  8   : Major — removes an architectural constraint or enables a product line
  13  : Critical — foundational for a platform or regulatory requirement
  20  : Blocking — large portion of planned work cannot proceed without this

### Job Size

Relative effort, not calendar time.
  1   : Trivial — hours, single isolated change
  2   : Small — less than a day
  3   : Medium-small — 1-2 days, one area of the codebase
  5   : Medium — 3-5 days, multiple components
  8   : Large — 1-2 weeks, cross-cutting or multi-service
  13  : X-Large — 2-4 weeks, significant design + implementation
  20  : Epic — score as-is; note it should be decomposed

## Step 3 — Confidence Protocol

Assign a confidence percentage to each dimension:
  98-100% : Input directly supports this score
  66-97%  : Reasonable inference; assumption made
  <=65%   : Insufficient information — flag with explanation

Overall confidence = weighted average, biased toward the lowest individual score.
If any dimension is below 65%, overall confidence cannot exceed 70%.

## Step 4 — Output

Produce this structure exactly. Do not add or remove sections.

---

### Job Classification

[Feature | Bug | Enabler: <subtype> | Spike | Other]

### Understood Scope

One sentence describing the job as parsed from the input.

### WSJF Scoring

#### User-Business Value (UBV)

Score: [Fibonacci]
Confidence: [%]
Reasoning: [1-3 sentences. Reference what in the input drove this score.]
[⚠ LOW CONFIDENCE: reason — include only if confidence < 66%]

#### Time Criticality (TC)

Score: [Fibonacci]
Confidence: [%]
Reasoning: [1-3 sentences.]
[⚠ LOW CONFIDENCE: reason — include only if confidence < 66%]

#### Risk Reduction / Opportunity Enablement (RR-OE)

Score: [Fibonacci]
Confidence: [%]
Reasoning: [1-3 sentences.]
[⚠ LOW CONFIDENCE: reason — include only if confidence < 66%]

#### Job Size

Score: [Fibonacci]
Confidence: [%]
Reasoning: [1-3 sentences.]
[⚠ LOW CONFIDENCE: reason — include only if confidence < 66%]

### Calculation

Cost of Delay = UBV + TC + RR-OE = [n] + [n] + [n] = [n]
Job Size = [n]
WSJF = [CoD] / [Size] = [score to 2 decimal places]

### Overall Confidence

[%] — [One sentence on what is pulling this down, if anything. Omit the dash and
explanation if 90%+.]

### Assumptions and Flags

[Numbered list. One entry per assumption made during scoring. One entry per case where
a different reasonable reading of the input would produce a materially different score.
Omit this section entirely if there are none.]

---

## Common Scoring Errors to Avoid

- Inflating TC because a job feels important — importance is UBV, not TC
- Scoring Enabler RR-OE low because "it's just infrastructure"
- Treating job size as calendar time instead of relative effort
- Assigning false precision — if two jobs both feel like 8s, they're both 8s
- Normalizing CoD before dividing — use raw sums
