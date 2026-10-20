---
name: recommendation-ranking
description: How ranked results are built and judged - scoring and ranking functions, deterministic tie-breaking, score normalisation and fusion of several retrievers, two-stage retrieval with re-ranking (including the Amazon Bedrock Rerank API), diversity (maximal marginal relevance, per-attribute caps), freshness and business rules applied after scoring, and the offline metrics that measure a ranking (precision and recall at K, MRR, NDCG, coverage, intra-list diversity). Use when implementing or testing matching, ranking, re-ranking or recommendation components, or when encoding their quality thresholds as tests.
user-invocable: false
---

# Ranking, re-ranking and diversity

A ranked list is built in stages, and each stage has one job. Implement each stage exactly as the
specification states it; this skill gives the method and the checks for each.

```
candidates (retrieval, filters) -> score -> normalise / fuse -> re-rank -> diversify -> rules -> top K
```

## 1. Scoring and ranking functions

- A score is a pure function of the candidate, the query or subject, and the specified weights.
  No clock, no randomness, no I/O inside the function; read features before scoring and pass them in.
- Weighted sums combine features only after each feature is on a known scale (see section 2). A
  feature with no value is handled by the specified rule (default value, exclusion, or penalty),
  never silently as zero unless the specification says zero.
- Sort descending by score with an explicit, total tie-break (for example score, then a stable
  secondary key, then the candidate id). Without a total order the same input can produce two
  orders, and tests become flaky.
- Floating point: compare scores with the tolerance the specification or test states; round only
  where the specification rounds, and only for presentation.
- Hard filters (eligibility, permissions, exclusions) run before scoring and are never expressed
  as a large negative weight.

## 2. Normalisation and fusion of several retrievers

Scores from different retrievers are on different scales (a BM25 score is unbounded; a cosine
similarity lies in [-1, 1]; a k-NN engine may return [0, 1]). Put them on one scale before combining.

| Method | Formula | Use when |
|---|---|---|
| min-max | `(s - min) / (max - min)` over the result set; define the value when `max == min` | Scores are bounded and the spread is meaningful |
| L2 | `s / sqrt(sum(s_i^2))` | Scores are positive and the vector length matters |
| Reciprocal rank fusion (RRF) | `sum over retrievers of 1 / (k + rank)`, commonly `k = 60` | Only ranks are comparable, or scales are unknown |
| Weighted combination | arithmetic, geometric or harmonic mean of normalised scores with weights summing to 1 | The specification gives per-retriever weights |

Amazon OpenSearch Service implements this as the search pipeline normalisation processor
(`min_max`, `l2`; combination `arithmetic_mean`, `geometric_mean`, `harmonic_mean`), run once at the
coordinator over all shards
(https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless-configure-neural-search.html).
In PostgreSQL, fuse a pgvector query and a full-text query in SQL with RRF over their row numbers.
Normalise over the whole candidate set, never per shard, page or batch.

## 3. Re-ranking (two-stage retrieval)

Retrieve a wide candidate set cheaply (vector or hybrid search, top N), then score the top N with a
more precise model and keep the top K (K < N).

- A cross-encoder re-ranker reads query and candidate together, so it is more precise and slower;
  bound N by the latency budget the specification states.
- Amazon Bedrock exposes re-ranker models through the Rerank API on `bedrock-agent-runtime`
  (`rerank`, `rerankingConfiguration.type = BEDROCK_RERANKING_MODEL`, `numberOfResults`), with
  Amazon Rerank 1.0 (`amazon.rerank-v1:0`) and Cohere Rerank 3.5 (`cohere.rerank-v3-5:0`); model
  support differs by Region (https://docs.aws.amazon.com/bedrock/latest/userguide/rerank-supported.html,
  https://docs.aws.amazon.com/bedrock/latest/userguide/rerank-use.html). Results carry the input
  `index` and a `relevanceScore`; map back by index, never by text.
- Knowledge Bases can re-rank inside `Retrieve` and `RetrieveAndGenerate`; check the current
  request shape with the AWS documentation tools before writing it.
- A re-ranker's score replaces the first-stage score for ordering; keep the first-stage score only
  when the specification blends them.

## 4. Diversity

A list of near-duplicates is a poor list even when every item is relevant.

- Maximal marginal relevance (Carbonell and Goldstein, 1998) selects greedily:
  `next = argmax over remaining d of [ lambda * rel(d) - (1 - lambda) * max over selected s of sim(d, s) ]`.
  `lambda = 1` is pure relevance; the specification gives `lambda` and the similarity function
  (usually cosine over the same embeddings). Selection is deterministic when ties break as in section 1.
- Per-attribute caps (for example at most M items per employer, category or source) are applied
  greedily in score order: skip an item whose attribute has reached its cap, and state what happens
  when fewer than K items remain.
- De-duplicate exact and near duplicates (same id, same canonical key, similarity above the
  specified threshold) before diversification.

## 5. Freshness and business rules

- Freshness is a feature (for example exponential decay `exp(-age / half_life * ln 2)`) inside the
  score, or a filter (maximum age); the specification says which, with the half-life or maximum age.
- Business rules that pin, boost or bury items run after scoring and diversity, in the specified
  order, and each rule is recorded in the result's explanation when the specification asks for
  explanations.
- Never let a rule reorder items in a way the tests cannot observe: every rule has a test.

## 6. Measuring a ranking (offline evaluation)

With a labelled set of queries or subjects and their relevant items:

| Metric | Definition | Notes |
|---|---|---|
| Precision@K | relevant items in the top K / K | Ignores order inside K |
| Recall@K | relevant items in the top K / all relevant items | Needs the full relevant set |
| MRR | mean over queries of 1 / rank of the first relevant item | One relevant item matters most |
| NDCG@K (Jarvelin and Kekalainen, 2002) | `DCG@K / IDCG@K`, `DCG@K = sum_i (2^rel_i - 1) / log2(i + 1)` | Graded relevance; state the gain form used |
| Coverage | distinct items recommended across all lists / catalogue size | Detects popularity collapse |
| Intra-list diversity | mean pairwise dissimilarity inside a list | Checks section 4 did its job |

- Take every threshold from the specification; a metric with no threshold is reported, not asserted.
- Report per-segment breakdowns (for example new versus returning subjects) as well as the mean.
- Keep the evaluation set fixed and versioned; never tune on it.
- Popularity bias and position bias inflate offline metrics; when labels come from logged clicks,
  say so beside the result.
