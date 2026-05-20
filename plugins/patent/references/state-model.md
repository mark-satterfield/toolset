# State model

All plugin state lives under `patents/` in the working repository. No sub-skill holds state in memory across sessions. The `funnel stage` field in `idea.md` is the coordination signal.

## Directory layout

```
patents/
  portfolio.md                  — strategic overview, moat map, work-priority ranking
  prior-art-cache/              — cached search results keyed by SHA-256 of canonical query
  ideas/
    {domain-area-slug}/
      idea.md                   — raw + refined description, all structured fields
      qa-log.md                 — append-only Q&A history from ideation sessions
      prior-art.md              — citations, source tiers, relevance scores
      eligibility.md            — Alice/Mayo two-step + EPO technical-effect analysis
      claims.md                 — independent + dependent claim drafts, all variants
      enforceability.md         — detectability, designability, evidence path, strategic score
      decision.md               — file / defer / abandon decision + rationale + filing type + date
      generated/                — finished documents produced by patent-document-generation
        invention-disclosure.md
        ppa-draft.md
        non-provisional-skeleton.md
        ids-summary.md
        claim-chart.md
        defensive-publication.md
```

## Slug naming

Format: `domain-area-feature` in kebab-case.

Examples:
- `database-indexing-adaptive-bloom`
- `api-rate-limiting-token-bucket-variant`
- `ml-training-federated-aggregation`
- `ui-rendering-delta-compression`

If the slug already exists, append `-2`, `-3`, etc. Never overwrite an existing idea directory.

## `idea.md` schema

```yaml
---
title: <one-line title>
slug: <directory slug>
funnel_stage: raw | shaped | assessed | claim-ready | decided
inventors:
  - <name>
conception_date: <YYYY-MM-DD>
reduction_to_practice_date: <YYYY-MM-DD or null>
tier: <S | A | B | C | D | unscored>
---

# {title}

## One-line summary
<one sentence>

## Raw description
<verbatim user input, never paraphrased>

## Technical problem
<the failure that occurs without the invention, in measurable terms>

## Prior approaches and their limitations
- <approach 1>: <limitation>
- <approach 2>: <limitation>

## The approach
<mechanical description of the invention>

## The specific delta versus prior approaches
<what the approach does that prior approaches do not — structural or algorithmic, not outcome>

## The technical effect produced by the delta
<measurable improvement that is an inherent consequence of the delta>

## Non-obviousness argument
<why a skilled engineer looking at prior art would not have found this obvious>

## Alternative embodiments
- <alternative 1>
- <alternative 2>
- <alternative 3>
- ...
```

## Funnel stages

| Stage | Meaning | Reached by |
|---|---|---|
| `raw` | Captured verbatim, not yet structured | `patent-ideation` capture step |
| `shaped` | All structured fields populated, framing survives eligibility triage | `patent-ideation` completion |
| `assessed` | Eligibility analysis complete, prior-art search complete | `patent-patentability` completion |
| `claim-ready` | Independent + dependent claims drafted, 112-compliant | `patent-claim-drafting` completion |
| `decided` | A filing-or-not decision is recorded in `decision.md` | `patent-document-generation` or `patent-triage` |

## `decision.md` schema

```yaml
---
decision: file | defer | abandon | defensive-publish | trade-secret
decision_date: <YYYY-MM-DD>
filing_type: provisional | utility | pct | defensive-publication | none
filing_date: <YYYY-MM-DD or null>
provisional_conversion_deadline: <YYYY-MM-DD or null>
application_number: <USPTO/EPO/WIPO number or null>
---

# Decision rationale
<one paragraph: why this decision over the alternatives, tied to enforceability tier and moat-thesis fit>
```

## `portfolio.md` schema

```markdown
# Portfolio

## Moat thesis
<one to three sentences>

## Ranking
| Rank | slug | Title | Tier | Stage | Filing status | Priority score |

## Action items (in order)
1. <highest priority>

## Coverage gaps
- <gap>: <recommendation>

## Continuation / divisional candidates
## Priority-window flags
## Cost-benefit by idea (tier B+)
## Maintenance windows
## Last updated
<YYYY-MM-DD>
```

## Caching protocol

`patents/prior-art-cache/` stores prior-art search results. Cache key: SHA-256 of the canonicalized query string (lowercase, whitespace-collapsed, JSON-keys-sorted for API queries).

Cache entry format:

```
{cache-key}.json
{
  "query": "<canonical query>",
  "source": "patentsview" | "google-patents" | "epo-ops" | "arxiv" | "github" | "web",
  "fetched_at": "<ISO 8601>",
  "results": [...]
}
```

Treat entries older than 30 days as stale. Refresh if relied on for novelty conclusions.
