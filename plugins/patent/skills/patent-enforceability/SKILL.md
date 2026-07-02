---
name: "patent-enforceability"
description: Strategic-worth assessment for a claim-ready idea — detectability (can infringement be observed?), designability (how hard is it to design around?), evidence-path (what would have to be shown to prove infringement?), and a composite strategic-value score. Scored independently of patentability. Use when the user asks how enforceable a patent would be, whether infringement is detectable, how easy a claim is to design around, or the strategic value of an idea.
triggers:
  - is this enforceable
  - can I detect infringement
  - design around
  - designability
  - strategic value
  - how valuable is this patent
  - is it worth filing
  - infringement evidence
  - hard to detect
  - FTO
  - freedom to operate
---

# patent-enforceability

You assess the strategic worth of a claim-ready idea. A patent is only as valuable as it is enforceable. An idea can be perfectly eligible and novel but worthless if infringement happens server-side and is invisible from outside the product, or if a competitor can design around the claim in a weekend. Output is `enforceability.md`.

## Inputs

- `patents/ideas/{slug}/idea.md`
- `patents/ideas/{slug}/claims.md` if present (preferred)
- `patents/ideas/{slug}/eligibility.md` — context, not gating

If claims are not yet drafted, you can score the idea-level concept, but flag that the score is provisional and will shift once claims pin scope.

## Step 1 — Detectability analysis

Detectability is the probability that infringement is observable from outside the alleged infringer's product. This dominates strategic value for software patents.

Ask:

- Does the claimed mechanism produce an observable output a third party can capture? (UI behavior, network traffic, file format, API response shape, latency profile)
- Or does it execute internally with no observable trace? (server-side optimization, batch-job decision, internal data structure)

Score:

| Score | Observation pathway |
|---|---|
| 5 — Easy | Visible in the product UI or public API; can be confirmed by black-box testing |
| 4 — Moderate | Visible in network traffic, file output, or instrumented behavior |
| 3 — Difficult | Inferable from performance characteristics or output statistics |
| 2 — Very difficult | Only observable with insider knowledge or whistleblower |
| 1 — Effectively undetectable | Server-side method with no observable signature |

Server-side and back-end methods with no observable output score low. Client-observable behavior scores high. Be honest. A common failure mode is overstating detectability.

## Step 2 — Designability-around analysis

Designability is the minimum change a competitor needs to escape the claim while still solving the same problem. The narrower the claim, the easier the design-around.

Ask:

- What is the smallest change to the mechanism that still achieves the technical effect but no longer reads on the claim's wherein clause?
- How many such design-arounds exist? (One? Five? Effectively unlimited?)
- How much engineering effort does each cost?

Score:

| Score | Design-around effort |
|---|---|
| 5 — Locked | No alternative achieves the technical effect; the inventive limitation is essential to the result |
| 4 — Hard | One or two alternatives exist, each requiring significant engineering or sacrificing the technical effect |
| 3 — Moderate | Three to five alternatives exist, each costing weeks of engineering |
| 2 — Easy | Many alternatives exist, each costing days of engineering |
| 1 — Trivial | The claim limitation is incidental; the same result is reachable by countless paths |

Probe the dependent claims too — if the independent claim is easy to design around but a dependent claim covers a structurally locked-in approach, the dependent is more valuable than the parent. Flag this for portfolio-review.

## Step 3 — Evidence-path analysis

Even if infringement is detectable, the evidence must be admissible and producible.

For each observable signal identified in Step 1, document:

- What artifact would have to be collected (network capture, decompiled binary, public document, deposition testimony)
- Who could collect it (the patent holder, a third-party expert, only through discovery)
- What test or analysis would convert the artifact into proof of every claim element
- What ambiguities the alleged infringer could raise

If the only path to proof requires discovery — meaning a lawsuit has already begun — that is a real cost. Patents enforceable only after filing suit are weaker than patents enforceable through pre-suit demand letters backed by public evidence.

Score the evidence path:

| Score | Evidence path |
|---|---|
| 5 — Pre-suit demonstrable | Black-box testing from public artifacts proves every element |
| 4 — Expert analysis sufficient | An expert with public artifacts can demonstrate infringement |
| 3 — Discovery-light | Limited discovery (one or two depositions) closes the gap |
| 2 — Full discovery required | All elements require internal documents or insider testimony |
| 1 — Impossible to prove | No realistic path to admissible proof |

## Step 4 — Freedom-to-operate (FTO) sidebar

Reference `${CLAUDE_PLUGIN_ROOT}/references/scoring-rubrics.md` for the FTO risk matrix. This is NOT enforceability of your patent — it's risk that practicing your invention infringes someone else's patent. Important context but scored separately.

| FTO risk | Infringement likelihood | Impact | Recommended response |
|---|---|---|---|
| High | Literal infringement possible on a top prior-art reference | Core to commercialization | Design-around or license |
| Medium | Doctrine-of-equivalents infringement possible | Some functionality affected | Design-around review |
| Low | No reference reads on the planned product | Non-core | Routine monitoring |

State the FTO risk level based on the top references in `prior-art.md`. Flag if any reference is owned by a known assertive licensor.

## Step 5 — Composite strategic value score

Compute:

```
Strategic value = Claim scope × Detectability × Designability difficulty
```

Where:

- **Claim scope** is a 1–5 estimate from the breadth of the independent claim's `wherein` clause (broader = higher; pin to dependent claims if the parent is too narrow to be useful)
- **Detectability** is the Step 1 score
- **Designability difficulty** is the Step 2 score (note: HIGHER difficulty = HIGHER value, because it means a design-around is HARDER)

Then multiply by the evidence-path score (Step 3) as a tiebreaker.

Map the final composite to a strategic tier (adapted from the IP value framework in ip-portfolio reference):

| Composite range | Tier | Action |
|---|---|---|
| 80–125 | S — Strategic | File priority; consider continuation strategy |
| 50–79 | A — Important | File; budget for international filings |
| 25–49 | B — Defensive | File provisional and monitor; convert if landscape shifts |
| 10–24 | C — Marginal | Consider defensive publication instead of filing |
| <10 | D — Abandon or trade-secret | Filing cost likely exceeds value |

Do not paper over a low score. The plan's acceptance criterion is explicit: an idea that is eligible and novel but undetectable in practice gets a LOW strategic score and is flagged.

## Step 6 — Write `enforceability.md`

Structure:

```markdown
# Enforceability — {slug}

## Detectability
Score: [N/5]
Pathway: [description]
Rationale: [why this score]

## Designability
Score: [N/5]
Known design-arounds: [list]
Rationale: [why this score]

## Evidence path
Score: [N/5]
Required artifacts: [list]
Required testimony: [list, if any]

## FTO sidebar
Risk: [High / Medium / Low]
Trigger references: [list]
Recommended response: [Design-around / License / Monitor]

## Strategic value
Claim scope: [N/5]
Detectability: [N/5]
Designability difficulty: [N/5]
Evidence path: [N/5]
Composite: [N]
Tier: [S / A / B / C / D]

## Bottom line
[One-paragraph recommendation: file priority, file with budget, defer, defensive publication, trade-secret, or abandon]
```

Set the `tier` field in `idea.md` to the computed tier.

## Acceptance criteria

- An idea that is eligible and novel but undetectable in practice scores low and is flagged with reasoning.
- Patentability and enforceability are scored independently — never re-litigate eligibility here.
- FTO risk is stated separately from enforceability of the owner's own patent.
- The composite score and tier are both stated; the tier maps to a specific recommended action.

## References

- `${CLAUDE_PLUGIN_ROOT}/references/scoring-rubrics.md` — FTO risk matrix, strategic-value tiers
- `${CLAUDE_PLUGIN_ROOT}/references/state-model.md` — `enforceability.md` schema
