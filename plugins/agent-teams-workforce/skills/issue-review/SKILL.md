---
name: issue-review
description: Reviews any issue, ticket, story, spec, or bug for completeness before sizing or implementation. Returns COMPLETE or INCOMPLETE with specific findings. Triggers on /issue-review or when user says "review this issue", "is this ready", "check this ticket", "validate this story".
---

# Issue Review

Evaluate any work item — GitHub issue, Beads ticket, Linear issue, user story, spec, or
free-form description — for completeness. This is not a pass/fail gate. It is a
completeness assessment that also determines whether the item has enough information to
be sized and scored, even if it is not yet fully complete.

Never ask clarifying questions. Assess with what you have. Flag gaps explicitly.

## Input Handling

- Beads issue ID (ssbd-xxxx) — run `bd show <id> --json`, use all fields
- GitHub issue number — run `gh issue view <n>`
- File path — read and assess
- Inline text — assess directly
- No argument — ask once: "Paste or describe the issue to review."

## Step 1 — Parse the Item

Extract and identify:
- Title / summary
- Description / body
- Type (feature, bug, enabler, spike, chore)
- Acceptance criteria (if present)
- Dependencies (explicit or implied)
- Testing notes (if present)
- UI impact (yes / no / unclear)
- Related tickets (if referenced)

## Step 2 — Completeness Assessment

Evaluate each dimension. Mark each as: ✅ Present | ⚠ Partial | ❌ Missing

### Description Quality
Is the problem or intent stated clearly enough that an engineer could begin design without
asking questions?
- ✅ Unambiguous scope, clear outcome, context provided
- ⚠ Intent is clear but scope has gaps or assumptions
- ❌ Vague, ambiguous, or too brief to act on

### Acceptance Criteria
Must be present, in Serenity BDD notation (Given / When / Then), and must cover:
- Primary scenario (the happy path)
- Secondary scenarios (alternate valid flows)
- Edge cases (boundary conditions, nulls, empty states, concurrency)
- Regression coverage (any existing behavior that must not break)

Serenity BDD format:
```
Scenario: [name]
  Given [precondition]
  When [action]
  Then [expected outcome]
```

Mark ⚠ if criteria exist but miss edge cases or regression coverage.
Mark ❌ if criteria are absent or not in BDD notation.

### Dependency Graph 1 — Service / Component Impact
Must identify:
- Every service, component, or module that is modified or affected
- The issue numbers of the work items covering each impacted area
- Direction of dependency (this issue depends on X / X depends on this issue)

Format when present:
```
[this issue] → modifies → [component/service]
[this issue] → depends on → [bd-xxxx: issue title]
[bd-yyyy: issue title] → blocked by → [this issue]
```

Mark ⚠ if some dependencies are identified but cross-service or downstream impacts are unclear.
Mark ❌ if no dependency analysis is present.

### Dependency Graph 2 — Deployment Sequence
Must specify the ordered deployment steps for:
- Local testing (dev environment)
- AWS testing (staging / integration)
- Production release

Format when present:
```
Local:
  1. [step]
  2. [step]

AWS (staging):
  1. [step]
  2. [step]

Production:
  1. [step]
  2. [step]
```

Mark ⚠ if some environments are covered but not all three.
Mark ❌ if absent entirely.

### Testing Coverage
Must include all of the following that apply:

Unit tests — specific functions, classes, or modules under test
Integration tests — service boundaries, API contracts, DB interactions
End-to-end tests — full user flow from entry point to outcome
UI / Browser tests — required if this issue has any UI impact (functional + regression)
Performance tests — required if latency, throughput, or load is affected
Security tests — required if auth, permissions, or data handling is affected

If testing of this issue is consolidated under a related ticket, that ticket number must be
explicitly stated: "Testing covered under bd-xxxx".

Mark ⚠ if some test types are present but UI testing is missing despite UI impact, or
consolidated coverage is implied but not cited.
Mark ❌ if no testing plan is present.

### Standards Compliance

INVEST criteria (for user stories):
- Independent — can be developed without depending on another incomplete story
- Negotiable — not a rigid contract, leaves room for conversation
- Valuable — delivers value to user or business
- Estimable — enough detail to size it
- Small — fits within a sprint
- Testable — acceptance criteria exist and are verifiable

IEEE 830 alignment (for specs/requirements):
- Correct, Unambiguous, Complete, Consistent, Ranked, Verifiable, Modifiable, Traceable

Flag specific violations. Do not just state "non-compliant."

## Step 3 — Sufficient to Size

After completeness assessment, make an independent determination:

**Sufficient to size**: Yes / No / Marginal

Rules:
- Yes: Description is clear enough to estimate relative effort, even if AC or testing
  details are incomplete.
- Marginal: Scope is partially defined. Sizing is possible but confidence will be low.
  State what would improve it.
- No: Too vague to estimate. Sizing would be a guess. State what is needed.

## Step 4 — Output

Produce this structure exactly.

---

### Review: [Issue ID or Title]

#### Completeness Status
COMPLETE  (all dimensions ✅)
— or —
INCOMPLETE  ([n] dimensions need attention)

#### Dimension Summary
Description Quality:      [✅ / ⚠ / ❌]
Acceptance Criteria:      [✅ / ⚠ / ❌]
Dependency Graph 1:       [✅ / ⚠ / ❌]
Dependency Graph 2:       [✅ / ⚠ / ❌]
Testing Coverage:         [✅ / ⚠ / ❌]
Standards Compliance:     [✅ / ⚠ / ❌]

#### Findings
[One section per non-✅ dimension. Be specific. Reference what is present and what is
missing. Do not summarize dimensions that are ✅.]

##### [Dimension Name]
Status: ⚠ Partial / ❌ Missing
What's present: [brief]
What's missing: [specific, actionable]
Example of what's needed: [concrete example in correct format where applicable]

#### Sufficient to Size
[Yes / Marginal / No]
[One sentence of reasoning. If Marginal or No, state exactly what would change the answer.]

#### Recommended Next Actions
[Numbered. Each action is specific and directly addresses a finding. Not generic advice.]

---
