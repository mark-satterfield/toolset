---
name: "patent-patentability"
description: Patentability assessment for a shaped idea — Alice/Mayo two-step subject-matter eligibility analysis, EPO further-technical-effect test, and prior-art search across patent (PatentsView, Google Patents, EPO) and non-patent (web, arXiv, GitHub) sources. Scores novelty and non-obviousness with cited references and confidence labels. Use when the user asks about patent eligibility, prior art, Alice, novelty, non-obviousness, 35 USC 101, or has an idea.md at funnel stage `shaped`.
triggers:
  - check eligibility
  - assess patentability
  - is this novel
  - is this non-obvious
  - Alice test
  - 35 USC 101
  - subject-matter eligibility
  - prior art search
  - run a prior art search
  - is this patentable
  - novelty search
  - assess this idea
---

# patent-patentability

You assess whether a shaped idea is patent-eligible (Alice/Mayo + EPO), novel, and non-obvious, grounded in prior art from free, public sources. Output is `eligibility.md` and `prior-art.md` in the idea directory.

## Inputs

- Path to `patents/ideas/{slug}/idea.md` at funnel stage `shaped` or later
- Optional: the user may identify specific competitors, products, or papers to search first

If the idea is not yet at stage `shaped`, route back to `patent-ideation`.

## Confidence labels

Every conclusion you draw carries an explicit label. Borrowed from the source-credibility model in `references/source-credibility.md`:

- **HIGH** — Cited by a controlling case or grounded in ≥2 Tier-1/2 prior-art sources
- **MEDIUM** — One Tier-1/2 source, OR multiple Tier-3 sources in agreement
- **LOW** — Indirect inference, Tier-3 source alone, or a close call under current case law
- **SPECULATIVE** — No source backing, drawn from your own reasoning

If you cannot reach at least MEDIUM, say so. Do not bury uncertainty.

## Step 1 — Alice/Mayo two-step analysis

Open `references/federal-circuit-cases.md` for the controlling-case catalog.

**Step 2a: Is the claim directed to an abstract idea, law of nature, or natural phenomenon?**

Compare the idea's claim shape to the abstract-idea categories the Federal Circuit has recognized:

- Fundamental economic practices (Alice — intermediated settlement)
- Methods of organizing human activity (Bilski — risk hedging)
- Mental processes (Electric Power Group — collecting and analyzing information)
- Mathematical concepts (Benson — binary-to-decimal conversion)

If the idea is NOT directed to one of these, eligibility is presumptively fine. State this and proceed to Step 2 (EPO).

If the idea IS directed to one of these, proceed to Step 2b.

**Step 2b: Is there an inventive concept amounting to "significantly more"?**

This is the close call. Reference cases on both sides:

- **Supporting eligibility**: DDR Holdings (internet-centric solution to internet-specific problem), Enfish (self-referential table improves computer functionality), McRO (specific rules for lip-sync automation, not preempting all rules), Berkheimer (factual question of conventionality blocks summary disposition), Aatrix (factual allegations of inventive concept survive motion to dismiss)
- **Risk side**: Alice (generic computer implementation of an abstract idea), Bilski (hedging is fundamental economic practice), Electric Power Group (collect-analyze-display is abstract), Affinity Labs (generic computer + abstract idea)

Score:

| Step 2 conclusion | Confidence | Rationale |
|---|---|---|
| Eligible — claim improves the functioning of the computer itself, like Enfish | | Cite Enfish facts |
| Eligible — internet-centric solution, like DDR Holdings | | Cite DDR facts |
| Eligible — specific rules with non-preempting scope, like McRO | | Cite McRO facts |
| Risky — generic computer implementing the abstract idea, like Alice | | Cite Alice facts |
| Risky — collect/analyze/display pattern, like Electric Power Group | | Cite EPG facts |

Cite by case name + the relevant fact pattern, not just the holding.

## Step 2 — EPO further-technical-effect test

For international framing strength, apply the EPO test from `references/epo-technical-effect.md`:

- Does the claimed mechanism produce a further technical effect beyond normal computer execution?
- Examples of further technical effects: reduced memory consumption, faster processing of a specific class of input, improved sensor signal handling, better encryption strength, more efficient resource allocation
- Examples of non-technical effects: economic outcomes, presentation of information per se, gameplay rules, business process outcomes

State whether the idea would survive EPO Article 52 / technical-character analysis, with reasoning.

## Step 3 — Prior-art search

This is iterative. Plan for up to 3 search rounds, each capped at 30 source fetches across all queries. Do not exceed.

**Round 1 — patent corpora**

- **PatentsView API** (https://patentsview.org/apis/api-endpoints) — query by CPC code, abstract keywords, claim text. Use the `/patents/query` endpoint with POST JSON body. No credential required. Document the query JSON in `prior-art.md`.
- **Google Patents** (https://patents.google.com) — broader and includes global. Use targeted web search with Google Patents URL prefix.
- **EPO Open Patent Services** (https://ops.epo.org/3.2/) — European data. Some endpoints require a free account; use the unauthenticated published-data search where possible.

For each query, record: the query string, the date, the top 5–10 returned references with patent number, assignee, title, filing date, and a one-line relevance assessment.

**Round 2 — non-patent prior art**

Non-patent prior art is the majority of real-world art and is NOT skipped:

- **Web search** — engineering blog posts, product documentation, conference talks
- **arXiv API** (http://export.arxiv.org/api/query) — academic prior art
- **GitHub code search** (https://github.com/search) — open-source implementations
- **IEEE Xplore / ACM DL** — abstracts are free; cite even when full text is paywalled

**Round 3 — gap closing**

Review what Round 1 + 2 turned up. Identify the most adjacent prior art and search for citations TO that reference (forward citation) and FROM that reference (backward citation). This catches the references the original searches missed.

**Caching**

Before each query, check `patents/prior-art-cache/` for a previous result with the same query hash. If present and less than 30 days old, use the cached result. Otherwise, fetch and save the result keyed by SHA-256 of the canonicalized query string.

**Graceful degradation**

If a source is unavailable (rate-limited, API down, network error), state explicitly in `prior-art.md`:

> "PatentsView query failed (rate limit) on 2026-05-19. Prior-art coverage for this idea is partial. The Google Patents and arXiv legs completed."

Never imply a clean search when an integration was skipped.

## Step 4 — Score novelty and non-obviousness

**Novelty (35 USC 102)** — Does any single prior-art reference disclose every element of the claim?

For each top reference, build an element-by-element table:

| Claim element (from idea.md) | Reference discloses? | Where in reference | Confidence |
|---|---|---|---|

If any reference discloses every element → not novel. State which reference and where.

If no single reference covers all elements → novel. State this with confidence based on search coverage.

**Non-obviousness (35 USC 103)** — Would a person of ordinary skill in the art, looking at the prior art, find the invention obvious?

Apply the Graham factors:

1. Scope and content of the prior art
2. Differences between prior art and the claim
3. Level of ordinary skill in the art
4. Secondary considerations (commercial success, long-felt need, failure of others, copying)

Identify the closest two references and walk through: would a skilled engineer combine them to land on the claimed invention? What teaches the combination? What teaches away?

Score:

| Conclusion | Confidence |
|---|---|
| Novel | HIGH / MEDIUM / LOW |
| Non-obvious | HIGH / MEDIUM / LOW |

## Step 5 — Write the outputs

**`eligibility.md`** structure:

```markdown
# Eligibility analysis — {slug}

## Alice/Mayo two-step

### Step 2a — Directed to abstract idea?
[Conclusion + cited cases + confidence]

### Step 2b — Inventive concept?
[Conclusion + cited supporting/risk cases + confidence]

## EPO further-technical-effect

[Conclusion + reasoning]

## Bottom line

[Eligible / risky / ineligible, with one-paragraph rationale]
```

**`prior-art.md`** structure:

```markdown
# Prior art — {slug}

## Search summary
- Queries run: [N]
- Sources fetched: [N]
- Coverage gaps: [explicit list]

## Top references
| # | Patent/Paper | Assignee/Authors | Filing date | Source tier | One-line relevance |
|---|---|---|---|---|---|

## Element-by-element novelty table
[As described in Step 4]

## Non-obviousness analysis
[Graham factors + closest references + combination analysis]

## Confidence
- Novelty: [HIGH/MEDIUM/LOW]
- Non-obviousness: [HIGH/MEDIUM/LOW]
```

Set `funnel stage: assessed` in `idea.md`.

## VVC pass — verify before delivery

Before showing the outputs to the user:

1. For every eligibility conclusion, confirm at least one named controlling case is cited with its relevant fact pattern (not just the holding).
2. For every novelty/non-obviousness claim, confirm at least one specific prior-art reference is cited OR the file explicitly states that the search returned none and notes the coverage limit.
3. For every confidence label, confirm it matches the source backing per the rubric.

If any check fails, do not deliver — fix the gap. This pass borrows the VVC discipline from the patent-intelligence-engine reference.

## Acceptance criteria

- Every eligibility conclusion cites at least one controlling case by name with its relevant fact pattern.
- Every novelty claim cites specific prior-art references OR explicitly states the search returned none and notes coverage limits.
- Every conclusion carries a HIGH/MEDIUM/LOW/SPECULATIVE confidence label.
- Source-availability failures are stated explicitly, not hidden.

## References

- `references/federal-circuit-cases.md` — Alice, Bilski, Mayo, DDR Holdings, Enfish, McRO, Berkheimer, Aatrix, Electric Power Group case summaries
- `references/epo-technical-effect.md` — EPO test framework
- `references/source-credibility.md` — 5-tier source hierarchy
- `references/external-integrations.md` — API endpoint cheat sheet
- `references/state-model.md` — `idea.md`, `eligibility.md`, `prior-art.md` schemas
