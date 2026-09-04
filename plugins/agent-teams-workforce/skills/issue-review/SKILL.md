---
name: issue-review
description: Reviews any issue, ticket, story, spec, or bug for completeness before sizing or implementation, scaling what it demands to the size and kind of the work item. Returns COMPLETE or INCOMPLETE with specific findings. Triggers on /issue-review or when user says "review this issue", "is this ready", "check this ticket", "validate this story".
---

# Issue Review

Evaluate any work item — GitHub issue, Beads ticket, Linear issue, user story, spec, or
free-form description — for completeness. This is not a pass/fail gate. It is a
completeness assessment that also determines whether the item has enough information to
be sized and scored, even if it is not yet fully complete.

## What this rubric may demand, and why it is short

Contracts are consumer-defined: a consumer declares the schema it needs, and the producer
produces to it. This review is a producer. It may therefore demand **only** what something
downstream actually reads off the work item, and every dimension below names its consumer.

That test removed four dimensions this rubric used to carry. It demanded two dependency
graphs, a three-environment deployment sequence (Local / AWS staging / Production), a test
plan, and INVEST / IEEE 830 conformance — and nothing anywhere in the pipeline read any of
them off a work item. `workflows/deploy.js` derives its own rollout and deploys to exactly
one environment; `workflows/tdd-red.js` writes the tests from the acceptance criteria. Those
sections were this skill's own invention, they refused well-specified work for lacking a
document nobody read, and they held 106 beads blocked for two months. They are gone — not
demoted to advisory, because advisory ceremony still costs the reader's attention and still
comes back as a finding.

If a future consumer starts reading something new off a work item, add the dimension then,
and name that consumer beside it.

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

## Step 2 — Classify the Scope

Classify the item into **exactly one** class. Derive the class from the item itself — its
stated change, its surfaces, its fix if one is already written down — not from its
priority, its age, or who filed it.

- **trivial** — a single-file or single-value correction with a stated or obvious fix, no
  interface change, no new behavior. A version string that disagrees with reality, a
  wrong constant, a corrected path, a `$id` bump.
- **contained** — new or changed behavior inside one service or repo.
- **cross-cutting** — touches more than one service, repo, or deployed surface; **or**
  changes an interface, schema, or an auth / permissions / data-handling path.

When the class is genuinely ambiguous, choose the **more demanding** one and say why in
the findings. Ambiguity resolves upward, never downward.

The class is a statement about blast radius, not importance. A trivial item can be urgent;
a cross-cutting one can be small in lines.

**The class does not change which dimensions can refuse the item** — both surviving
dimensions are blocking at every class. It calibrates how much Acceptance Criteria demands
(see that dimension), and it tells whoever picks the item up what they are walking into.

Consumed by: this skill's own Acceptance Criteria calibration, and the human reading the
review comment `issue-ready` posts to the tracker.

## Step 3 — Completeness Assessment

Evaluate each dimension. Mark each as: ✅ Present | ⚠ Partial | ❌ Missing

Both dimensions are **blocking** at every class: a ❌ makes the item INCOMPLETE.

### Description Quality

Consumed by: `workflows/route-build.js` and `workflows/route-elaboration.js` — each renders
`bead.description` into the routing prompt that decides which composite the item is
dispatched to; `workflows/bug-triage.js` renders it into the reproduction and root-cause
prompts that produce the bug's implementation contract. A description that does not state
the problem sends those routers into a guess.

Is the problem or intent stated clearly enough that an engineer could begin design without
asking questions?

- ✅ Unambiguous scope, clear outcome, context provided
- ⚠ Intent is clear but scope has gaps or assumptions
- ❌ Vague, ambiguous, or too brief to act on

### Acceptance Criteria

Consumed by: `workflows/tdd-red.js` — it reads `contract.acceptanceCriteria` and derives
the failing tests from it, then an independent coverage reviewer checks the authored tests
back against those same criteria. `workflows/task-to-deploy.js` carries them onto the
contract; `workflows/bug-triage.js` authors the equivalent contract for a bug. An item with
no verifiable pass condition gives the Red phase nothing to encode.

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

### What still fails

A short rubric is not a rubber stamp. Two things are exactly what this gate exists to
catch, and neither is excused by a small scope:

1. **No clear intent.** A vague item whose problem, outcome, or scope cannot be
   established from what is written. Description Quality is ❌ and the item is refused, at
   every class.
2. **No verifiable pass condition.** An item nobody can prove finished. Acceptance
   Criteria is ❌ and the item is refused, at every class.

Under-specified work is still refused. What is no longer refused is well-specified work
that lacks ceremony.

## Step 4 — Sufficient to Size

After the completeness assessment, make an independent determination:

**Sufficient to size**: Yes / No / Marginal

Rules:

- Yes: Description is clear enough to estimate relative effort, even if the acceptance
  criteria are incomplete.
- Marginal: Scope is partially defined. Sizing is possible but confidence will be low.
  State what would improve it.
- No: Too vague to estimate. Sizing would be a guess. State what is needed.

Consumed by: `skills/issue-ready` — a COMPLETE verdict is what releases the item to WSJF
scoring, and the score is stored on the issue as `wsjf`.

### Consistency rule — sizing and the verdict must agree

The blocking set is Description Quality and Acceptance Criteria. A `Yes` sizing verdict
with both of those at ✅ or ⚠ **must** yield COMPLETE.

If you find yourself about to report `Sufficient to Size: Yes` alongside INCOMPLETE,
stop and re-check the two blocking dimensions. One of the two judgments is wrong — either
the item is understood well enough to size, in which case find the blocking ❌ that
actually justifies the refusal, or it is not, in which case the sizing verdict is not
`Yes`. Reporting both is a contradiction, not a nuanced position.

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
COMPLETE  (both dimensions are ✅ or ⚠)
— or —
INCOMPLETE  ([n] dimension(s) at ❌)
```

#### Dimension Summary

```text
Description Quality:      [✅ / ⚠ / ❌]
Acceptance Criteria:      [✅ / ⚠ / ❌]
```

#### Findings

[One section per non-✅ dimension. Be specific. Reference what is present and what is
missing. Do not summarize dimensions that are ✅. If there are none, state "None."]

##### [Dimension Name]

Status: ⚠ Partial / ❌ Missing
What's present: [brief]
What's missing: [specific, actionable]
Example of what's needed: [concrete example in correct format where applicable]

#### Sufficient to Size

[Yes / Marginal / No]
[One sentence of reasoning. If Marginal or No, state exactly what would change the answer.]

#### Recommended Next Actions

[Numbered. Each action is specific and directly addresses a finding. Not generic advice.
If there are no findings, state "None — dispatch it."]

---
