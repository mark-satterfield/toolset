# Scoring rubrics

Rubrics used by `patent-enforceability` and `patent-triage`. Adapted from the `ip-portfolio` reference directory's patent valuation framework, with adjustments for personal-portfolio context (pre-filing decision-making rather than granted-patent valuation).

---

## Patent strength scorecard

For each granted patent or claim-ready idea, score on six dimensions (1–5 each, weighted). Used by `patent-triage` Step 6.

| Dimension | Weight | Score (1–5) basis |
|---|---|---|
| Claim scope | 20% | Broader = higher. Score 5 if the independent claim reads on all alternative embodiments; 1 if it covers only a narrow single embodiment. |
| Design-around difficulty | 20% | More difficult = higher. See `patent-enforceability` Step 2 for the 1–5 scale. |
| Technical importance | 15% | More critical to the field = higher. Score 5 if the invention is foundational; 1 if the invention is a minor improvement to a corner case. |
| Citation frequency (for granted patents) | 15% | More cited = higher. Score 5 if >50 forward citations; 1 if 0. (Use 0 for ungranted ideas.) |
| Remaining term | 15% | Longer = higher. Score 5 for fresh grant (~20 years remaining); 1 for last year. |
| Market relevance | 15% | Greater applicability to commercially active fields = higher. Score 5 if directly applicable to top-3 market segments in the field; 1 if niche. |

**Composite**: Sum of (score × weight). Range: 1.0 to 5.0.

| Composite | Tier |
|---|---|
| ≥ 4.0 | S — strategic asset |
| 3.0 – 3.99 | A — important |
| 2.0 – 2.99 | B — defensive |
| 1.0 – 1.99 | C — marginal |

---

## IP value assessment framework

A second scoring lens used by `patent-triage`. Reframes the "is this idea worth filing" question in terms of strategic position.

| Dimension | Weight |
|---|---|
| Business relevance | 30% |
| Technical superiority | 25% |
| Market coverage | 20% |
| Defensive strength | 15% |
| Revenue potential | 10% |

Score each 1–5. Composite = weighted average. Map to tier:

| Composite | Tier | Meaning |
|---|---|---|
| ≥ 4.0 | S | Essential to the moat thesis; irreplaceable |
| 3.0 – 3.99 | A | Important; contributes to competitive advantage |
| 2.0 – 2.99 | B | Complementary; defensible value |
| 1.0 – 1.99 | C | Low utilization; candidate for retention review or abandonment |

---

## Freedom-to-operate (FTO) risk matrix

| Risk level | Infringement likelihood | Impact | Recommended response |
|---|---|---|---|
| High | Literal infringement possible against a known reference | Core to commercialization | Design-around or license |
| Medium | Doctrine-of-equivalents infringement possible | Some functionality affected | Design-around review |
| Low | No reference reads on the planned product | Non-core | Routine monitoring |

Used by `patent-enforceability` Step 4 as a sidebar separate from the owner's own enforceability of their patent.

---

## Industry royalty rate benchmarks

Reference table for `patent-triage` when discussing licensing potential of granted patents. Source: ip-portfolio reference, consistent with widely-cited industry surveys.

| Industry | Royalty rate range | Median |
|---|---|---|
| Pharmaceutical / Biotech | 3–10% | 5% |
| Semiconductor / Electronics | 1–5% | 3% |
| Software | 5–25% | 10% |
| Chemical / Materials | 2–5% | 3% |
| Machinery / Equipment | 1–5% | 3% |
| Consumer Goods | 2–8% | 4% |
| Automotive | 1–3% | 2% |

State as informational. Do not estimate revenue without revenue data from the user.

### 25% rule (quick estimate)

```
Royalty ≈ Licensee Operating Profit × 25%
```

The 25% rule estimates that 25% of patent-contributed profit flows to the patent holder. Used by courts only as a starting reference, never as an absolute standard. Useful for back-of-envelope discussions in `patent-triage`.

---

## License structure types

Reference table for `patent-document-generation` when discussing licensing options. Lifted from ip-portfolio reference.

| Type | Description | Typical structure |
|---|---|---|
| Exclusive | Only licensee may practice | High upfront + royalty |
| Non-exclusive | Multiple licensees | Lower upfront + royalty |
| Sublicensable | Relicensing permitted | Royalty sharing |
| Cross-license | Mutual practice rights | Royalty-free or balancing payment |

### Payment structures

- **Lump-sum**: One-time payment at agreement
- **Running royalty**: Periodic payment based on sales or volume
- **Minimum royalty**: Annual minimum guarantee
- **Milestone**: Stage-based payments (development, commercialization, sales thresholds)
- **Hybrid**: Lump-sum + running combination

---

## Maintenance fee schedule (granted patents)

Used by `patent-triage` Step 8.

| Country | Schedule | Cost trend |
|---|---|---|
| United States | At 3.5 / 7.5 / 11.5 years from grant | Three steps, increasing |
| Europe (EP designation) | Annual from year 3 | Increases annually |
| Japan | Annual from year 4 | Increases annually |
| Korea | Annual from year 4 | Increases annually |

US maintenance fees are entity-dependent (large entity / small entity / micro entity).

---

## Retention / pruning criteria

For `patent-triage` when reviewing the existing portfolio.

### Retention criteria

| Score | Meaning |
|---|---|
| 3 stars | Core: directly business-related, high value, keep regardless of cost |
| 2 stars | Important: defensive value, revenue potential, keep if cost is reasonable |
| 1 star | Moderate: review value versus maintenance cost annually |

### Pruning criteria

Recommend abandonment if any:

- No business relevance + no licensing demand
- Annual maintenance cost > likely annual licensing value
- Patent expires within 3 years AND no active enforcement plan AND no licensing pipeline
- Strategic tier has dropped from A or B at filing to C or D currently

### Conversion options

When a granted patent's tier drops, consider:

1. **Let lapse** — stop paying maintenance, patent enters public domain. Cheapest option.
2. **Sell** — assign to a third party (patent broker, defensive aggregator). Some recovery.
3. **License non-exclusively at low rates** — extract residual value without active enforcement
4. **Defensive publication of related claims** — voluntarily disclose continuation/divisional material to block competitors without spending more on prosecution

---

## Strategic-value tier mapping (used by `patent-enforceability`)

Composite from `patent-enforceability` Step 5: Claim scope × Detectability × Designability difficulty (then multiplied by evidence-path score as tiebreaker).

| Composite range | Tier | Action |
|---|---|---|
| 80–125 | S — Strategic | File priority; consider continuation strategy |
| 50–79 | A — Important | File; budget for international |
| 25–49 | B — Defensive | Provisional only, then re-evaluate |
| 10–24 | C — Marginal | Consider defensive publication instead |
| < 10 | D — Abandon or trade-secret | Filing cost likely exceeds value |

The tier from `patent-enforceability` is the primary input to `patent-triage`'s ranking.
