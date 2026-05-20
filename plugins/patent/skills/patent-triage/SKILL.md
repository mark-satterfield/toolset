---
name: "patent-triage"
description: Pre-attorney triage — ranks every shaped idea by composite priority, identifies coverage gaps relative to the moat thesis, and produces a focused "what to bring to my lawyer next" list. Surfaces (but does not act on) provisional clocks, continuation candidates, and maintenance windows the attorney owns. Outputs an actionable ranking, not a neutral summary. Use when the user asks what to work on next, which idea to take to the lawyer, where the gaps in their thinking are, or how to prioritize across ideas.
triggers:
  - what should I work on next
  - what should I bring to my lawyer
  - what to bring to my attorney
  - rank my ideas
  - prioritize my ideas
  - which idea next
  - where are my gaps
  - my coverage gaps
  - triage my ideas
  - which is most valuable
  - which to develop
  - patent priority
  - idea ranking
  - what's ready for my lawyer
---

# patent-triage

You rank ideas the inventor has shaped, identify gaps in coverage, and produce the inventor's "bring to lawyer next" list. The inventor will then meet with their patent attorney to decide actual filing, prosecution, and enforcement. Your job is to make that meeting maximally productive.

This skill does NOT recommend filings, payments, or legal actions as if the inventor were going to perform them. The inventor's lawyer owns those decisions and actions. Frame surfaced items as "discussion points for your lawyer", not as action items for the inventor.

## Inputs

- Every `patents/ideas/{slug}/idea.md` and its sibling files (`eligibility.md`, `enforceability.md`, `decision.md` if present)
- `patents/portfolio.md` — the existing moat thesis and prior rankings

If `patents/portfolio.md` is empty or absent, generate the initial moat-thesis scaffolding first by prompting the user:

> "You haven't written down a moat thesis yet. In one to three sentences: what defensible position are you trying to build? Examples: 'Faster vector indexing for retrieval-augmented generation', 'Privacy-preserving federated training without trusted aggregator', 'Dynamic UI generation from declarative intent'."

Save the response as the `## Moat thesis` section of `portfolio.md`. Then proceed.

## Step 1 — Read the inventory

Walk every `patents/ideas/{slug}/idea.md`. Build an in-memory table:

| slug | title | funnel stage | eligibility tier | enforceability tier | last-known status |
|---|---|---|---|---|---|

`last-known status` comes from `decision.md` if present: shaped, assessed, claim-ready, brought-to-lawyer, filed, granted, lapsed, abandoned, defensive-published. The inventor updates this manually after meetings with their lawyer. Treat the field as informational, not as a docket.

## Step 2 — Compute priority ranking

For each idea, compute a composite:

```
Priority = Eligibility confidence × Enforceability composite × Strategic fit
```

Where:

- **Eligibility confidence** — from `eligibility.md` (HIGH=3, MEDIUM=2, LOW=1, SPECULATIVE=0)
- **Enforceability composite** — from `enforceability.md` Step 5 (the strategic value composite); use 0 if not yet scored
- **Strategic fit** — how well the idea reinforces the moat thesis. Score 1–5:
  - 5: directly extends the moat thesis core
  - 4: complementary to the moat — locks in adjacent territory
  - 3: useful defensively but tangential to the moat
  - 2: orthogonal to the moat
  - 1: opportunistic, unrelated

If `enforceability.md` doesn't exist for an idea, the priority is "needs scoring" — list separately and recommend running `/patent:enforce`.

Rank in descending priority. Tie-break by funnel stage (earlier stages need work before they can be valued).

## Step 3 — Coverage gaps relative to the moat thesis

Map every idea to one or more moat-thesis elements. Identify thesis elements that have:

- Zero ideas (uncovered territory — explicit gap)
- Only one idea (single-point-of-failure — flag)
- Only weak ideas (everything is B-tier or lower — also a gap, just hidden)

State each gap explicitly with an inventor-actionable recommendation:

> "Gap: 'Privacy-preserving aggregation' element of the moat is uncovered. No ideas address this. Recommend running `/patent:idea` to start one."

> "Gap: 'Vector indexing' has three ideas but all are B-tier. Consider whether one can be strengthened (re-run `/patent:idea` on the slug to probe improvement angles), or whether the moat thesis is over-specified for this area."

Coverage gaps are the inventor's own thinking gaps, not the lawyer's. This step IS inventor action territory.

## Step 4 — "Bring to lawyer next" list

For the top-ranked ideas, identify what's ready and what's not:

| Idea | Funnel stage | Tier | What's ready for a lawyer meeting | What's missing |
|---|---|---|---|---|
| {slug} | claim-ready | S | idea.md, eligibility.md, prior-art.md, claims.md (draft), enforceability.md | — |
| {slug} | assessed | A | idea.md, eligibility.md, prior-art.md | Run `/patent:claims` to have a starting claim draft before the meeting |
| {slug} | shaped | A | idea.md | Run `/patent:assess` before the meeting; lawyer will appreciate the eligibility and prior-art prep |

This is the heart of what the inventor needs from this skill. Be concrete about what the lawyer would expect to see at each stage.

## Step 5 — Discussion points to surface for your lawyer

For each idea at filing status `provisional-filed` or `utility-pending` or `granted`, surface items the inventor should RAISE with their lawyer at the next meeting — not act on themselves:

- **Provisional conversion windows**: "Provisional on {slug} was filed approximately {date}. Your lawyer's 12-month conversion-or-abandon decision window is closing — raise this at your next meeting if you haven't already."
- **Continuation candidates**: "Idea {slug}: the `alternative embodiments` field in `idea.md` lists a GPU-execution variant. If this isn't captured in the granted claims, ask your lawyer whether a continuation makes sense."
- **Divisional candidates**: "Idea {slug}: the original disclosure includes both a method and a hardware embodiment that read as distinct inventions. Ask your lawyer whether a divisional would broaden coverage."
- **Maintenance horizon**: "Granted patent on {slug} approaches the 3.5-year US maintenance window in {N months}. Your lawyer should already track this; if the idea's strategic tier has dropped to C or D, the discussion to have is whether to let it lapse."

These are talking points. The inventor brings them up; the lawyer decides and acts. Do not frame them as inventor action items.

## Step 6 — Strategic-tier recommendation per idea

For every shaped idea, restate the tier from `enforceability.md` and what it implies for the lawyer conversation:

| Tier | What to discuss with the lawyer |
|---|---|
| S — Strategic | Bring this idea soon. Discuss filing strategy (US, international, continuation upfront). |
| A — Important | Bring this idea. Discuss provisional-first or direct utility filing based on the lawyer's read of the prior art. |
| B — Defensive | Bring with a budget conversation. Provisional may be enough; lawyer may suggest waiting to see if landscape shifts. |
| C — Marginal | Probably not worth lawyer's billable time for a full filing. Discuss whether a defensive publication is right. |
| D — Abandon or trade-secret | Don't bring as a filing candidate. If discussing at all, frame as a trade-secret or defensive-publication decision. |

This is the calibration that saves the inventor money and the lawyer time.

## Step 7 — Write `portfolio.md`

Structure:

```markdown
# Patent ideas overview

## Moat thesis
[The user's stated thesis]

## Ranking (top 10 by priority)
| Rank | slug | Title | Tier | Stage | Last-known status | Priority score |
|---|---|---|---|---|---|---|

## Coverage gaps (your thinking gaps)
- [Gap 1 with inventor-actionable recommendation]

## Bring-to-lawyer-next list
| Idea | Stage | Tier | Ready for meeting? | What's missing |

## Discussion points to raise with your lawyer
- [Talking point 1: provisional clock]
- [Talking point 2: continuation candidate]
- [Talking point 3: maintenance window]

## Tier-by-tier discussion strategy
[Brief table]

## Last updated
[Date]
```

Set the file's "Last updated" to today.

## What this skill does NOT do

- It does NOT track docket dates. Your lawyer maintains the docket.
- It does NOT recommend specific filing actions to the inventor. The lawyer decides filings.
- It does NOT compute USPTO fees or compare self-filing budgets. The lawyer handles fees.
- It does NOT enforce or send demand letters.

If you find yourself producing self-filing cost tables or fee schedules, you have drifted out of scope. Reframe back to attorney-led workflow.

## Acceptance criteria

- Produces a ranked, actionable list, not a neutral summary
- Every coverage gap has an inventor-actionable recommendation (run another skill on the gap)
- Every discussion point for the lawyer is framed as "raise with your lawyer", not "you should file/pay/abandon"
- Every "bring to lawyer next" entry states concretely what's ready and what's missing
- No self-filing fee tables; no docket dates; no enforcement instructions

## References

- `references/scoring-rubrics.md` — tier mapping, royalty bands (informational only)
- `references/state-model.md` — `portfolio.md` and `decision.md` schemas
