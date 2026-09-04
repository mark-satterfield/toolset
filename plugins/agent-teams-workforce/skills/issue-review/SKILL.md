---
name: issue-review
description: Reviews any issue, ticket, story, spec, or bug for completeness before sizing or implementation, scaling what it demands to the size and kind of the work item. Returns COMPLETE or INCOMPLETE with specific findings. Triggers on /issue-review or when user says "review this issue", "is this ready", "check this ticket", "validate this story".
---

# Issue Review

Evaluate any work item — GitHub issue, Beads ticket, Linear issue, user story, spec, or
free-form description — for completeness. This is not a pass/fail gate. It is a
completeness assessment that also determines whether the item has enough information to
be sized and scored, even if it is not yet fully complete.

Completeness is judged **relative to the work**. A one-line constant correction and a
cross-repo schema migration are not held to the same evidence, because the same evidence
does not make them safe. The rubric therefore classifies the item first and only then
decides which dimensions are allowed to refuse it.

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

## Step 2 — Classify the Scope

Before assessing any dimension, classify the item into **exactly one** class. Derive the
class from the item itself — its stated change, its surfaces, its fix if one is already
written down — not from its priority, its age, or who filed it.

- **trivial** — a single-file or single-value correction with a stated or obvious fix, no
  interface change, no new behavior. A version string that disagrees with reality, a
  wrong constant, a corrected path, a `$id` bump.
- **contained** — new or changed behavior inside one service or repo.
- **cross-cutting** — touches more than one service, repo, or deployed surface; **or**
  changes an interface, schema, or an auth / permissions / data-handling path.

When the class is genuinely ambiguous, choose the **more demanding** one and say why in
the findings. Ambiguity resolves upward, never downward.

The class is a statement about blast radius, not importance. A trivial item can be
urgent; a cross-cutting one can be small in lines.

## Step 3 — Completeness Assessment

Evaluate each dimension. Mark each as: ✅ Present | ⚠ Partial | ❌ Missing

### Which dimensions can refuse the item

A dimension is either **blocking** — a ❌ there makes the item INCOMPLETE — or
**advisory** — assessed and reported in full, but never able to change the verdict.

| Dimension | trivial | contained | cross-cutting |
|---|---|---|---|
| Description Quality | blocking | blocking | blocking |
| Acceptance Criteria | blocking | blocking | blocking |
| Dependency Graph 1 — Service / Component Impact | advisory | advisory | blocking |
| Dependency Graph 2 — Deployment Sequence | advisory | advisory | blocking |
| Testing Coverage | advisory | advisory | blocking |
| Standards Compliance | advisory | advisory | advisory |

**Why this split, and not a single universal checklist.** Two of these dimensions ask the
work item to pre-compute analysis that a later phase of the pipeline exists to produce.
The TDD Red phase writes the tests from the acceptance criteria; the deploy mini derives
its own rollout plan from the declared surfaces and the changed paths. Demanding a test
plan and a three-environment deployment sequence on the item itself duplicates phases that
already own that job, and the duplicate is written earlier, with less information, by
whoever filed the ticket. That is the worse of the two artifacts, and requiring it
refuses well-specified work for lacking a document nobody downstream reads.

The exception is where the sequencing genuinely has to be settled **before** anyone
starts: when a change spans repos or deployed surfaces, or moves an interface, schema, or
auth path, the order of operations is a design decision, not an implementation detail. A
downstream phase cannot infer it after the fact from one repo's diff. That is why all
three become blocking at the cross-cutting class and only there.

Standards Compliance is advisory at every class. It is a quality signal about how the
item is written, not evidence about whether the work is understood.

### Description Quality

Is the problem or intent stated clearly enough that an engineer could begin design without
asking questions?

- ✅ Unambiguous scope, clear outcome, context provided
- ⚠ Intent is clear but scope has gaps or assumptions
- ❌ Vague, ambiguous, or too brief to act on

### Acceptance Criteria

Judge **verifiability, not notation.** Criteria are ✅ when they state an unambiguous pass
condition that a test could assert. Prose that names a concrete observable outcome passes.

Serenity BDD (Given / When / Then) is the preferred rendering and is what to suggest in
findings. It is **never** the admission test. An item is not refused for failing to use
it, and using it does not excuse a criterion that asserts nothing checkable.

Serenity BDD format — use this in the "Example of what's needed" output field:

```text
Scenario: [name]
  Given [precondition]
  When [action]
  Then [expected outcome]
```

Marks:

- ✅ At least one unambiguous pass condition a test could assert.
- ⚠ A pass condition is stated but leaves a **material** case open — a named edge case or
  a regression risk a reasonable implementer could plausibly get wrong.
- ❌ There is no verifiable pass condition at all.

Missing edge-case enumeration on a trivial item is **not** ⚠ — it is ✅. A single-value
correction has no edge cases to enumerate, and inventing some to fill the section adds
nothing a test would ever run.

Worked example. For an item whose criterion reads "the `$id` major matches the schema's
actual major; a 2.x elements file does not trip `ELEMENTS_VERSION_MISMATCH`" — that is
✅. It names two concrete observable outcomes, either of which a test can assert directly,
and no Given/When/Then wrapper would make it more checkable.

### Dependency Graph 1 — Service / Component Impact

Identifies:

- Every service, component, or module that is modified or affected
- The issue numbers of the work items covering each impacted area
- Direction of dependency (this issue depends on X / X depends on this issue)

Format when present:

```text
[this issue] → modifies → [component/service]
[this issue] → depends on → [bd-xxxx: issue title]
[bd-yyyy: issue title] → blocked by → [this issue]
```

Mark ⚠ if some dependencies are identified but cross-service or downstream impacts are unclear.
Mark ❌ if no dependency analysis is present.

For a trivial or contained item this is advisory: a ❌ is reported, never a refusal. An
item confined to one file inside one repo has already answered this dimension by saying
so. It becomes blocking only at the cross-cutting class, where the impact set is the
thing a reviewer cannot reconstruct on their own.

### Dependency Graph 2 — Deployment Sequence

Specifies the ordered deployment steps for:

- Local testing (dev environment)
- AWS testing (staging / integration)
- Production release

Format when present:

```text
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

For a trivial or contained item this is advisory. A change with no deployed surface has no
deployment sequence to state, and the deploy phase derives the rollout for everything
else. It becomes blocking only at the cross-cutting class, where the ordering across
repos or surfaces is a decision that must exist before work starts.

### Testing Coverage

Covers all of the following that apply:

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

For a trivial or contained item this is advisory, because the Red phase writes the tests
from the acceptance criteria — a test plan on the ticket is a second, earlier, weaker
version of an artifact the pipeline produces from better information. It becomes blocking
only at the cross-cutting class, where the test surface spans boundaries the Red phase
cannot see from one repo.

### Standards Compliance

Advisory at every class.

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

### What still fails

Scaling the rubric to the work is not a rubber stamp. Two things are exactly what this
gate exists to catch, and neither is excused by a small scope:

1. **No clear intent.** A vague item whose problem, outcome, or scope cannot be
   established from what is written. Description Quality is ❌ and the item is refused, at
   every class.
2. **No verifiable pass condition.** An item nobody can prove finished. Acceptance
   Criteria is ❌ and the item is refused, at every class.

Under-specified work is still refused. What is no longer refused is well-specified
**small** work that lacks ceremony.

## Step 4 — Sufficient to Size

After the completeness assessment, make an independent determination:

**Sufficient to size**: Yes / No / Marginal

Rules:

- Yes: Description is clear enough to estimate relative effort, even if AC or testing
  details are incomplete.
- Marginal: Scope is partially defined. Sizing is possible but confidence will be low.
  State what would improve it.
- No: Too vague to estimate. Sizing would be a guess. State what is needed.

### Consistency rule — sizing and the verdict must agree

If Sufficient to Size is `Yes` **and** the class is `trivial`, the blocking set is
Description Quality and Acceptance Criteria only. A `Yes` sizing verdict with both of
those at ✅ or ⚠ **must** yield COMPLETE.

If you find yourself about to report `Sufficient to Size: Yes` alongside INCOMPLETE,
stop and re-check the blocking dimensions. One of the two judgments is wrong — either the
item is understood well enough to size, in which case find the blocking ❌ that actually
justifies the refusal, or it is not, in which case the sizing verdict is not `Yes`.
Reporting both is a contradiction, not a nuanced position.

## Step 5 — Output

Produce this structure exactly.

---

### Review: [Issue ID or Title]

#### Scope Class

[trivial / contained / cross-cutting]
[One sentence of reasoning. If the class was ambiguous, say so and state why the more
demanding class was chosen.]

#### Completeness Status

```text
COMPLETE  (every blocking dimension is ✅ or ⚠)
— or —
INCOMPLETE  ([n] blocking dimension(s) at ❌)
```

The count is the number of **blocking** dimensions at ❌. It is not the number of
dimensions needing attention.

#### Dimension Summary

```text
Description Quality:      [✅ / ⚠ / ❌]   [blocking / advisory]
Acceptance Criteria:      [✅ / ⚠ / ❌]   [blocking / advisory]
Dependency Graph 1:       [✅ / ⚠ / ❌]   [blocking / advisory]
Dependency Graph 2:       [✅ / ⚠ / ❌]   [blocking / advisory]
Testing Coverage:         [✅ / ⚠ / ❌]   [blocking / advisory]
Standards Compliance:     [✅ / ⚠ / ❌]   [blocking / advisory]
```

#### Blocking Findings

[One section per non-✅ **blocking** dimension. Be specific. Reference what is present and
what is missing. Do not summarize dimensions that are ✅. If there are none, state "None."]

##### [Dimension Name]

Status: ⚠ Partial / ❌ Missing
What's present: [brief]
What's missing: [specific, actionable]
Example of what's needed: [concrete example in correct format where applicable]

#### Advisory Findings — do not affect the verdict

[One section per non-✅ **advisory** dimension, same shape as above. These are reported in
full and are genuinely useful to whoever picks the item up. They did not and cannot change
the Completeness Status. If there are none, state "None."]

#### Sufficient to Size

[Yes / Marginal / No]
[One sentence of reasoning. If Marginal or No, state exactly what would change the answer.]

#### Recommended Next Actions

[Numbered. Each action is specific and directly addresses a finding. Not generic advice.
Order blocking findings first — they are what stands between this item and dispatch.]

---
