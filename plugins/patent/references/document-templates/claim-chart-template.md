# Claim Chart — {{TITLE}}

> **Purpose**: Element-by-element analysis of the claims against {{TARGET}} — used for {{novelty mapping / licensing comparison / own-implementation read-out}}
> **Prepared by**: {{INVENTORS}}
> **Date**: {{TODAY}}

A claim chart maps each element of each claim to whether and where it appears in a target reference, product, or implementation. Used by the inventor for analysis. Litigation-grade claim charts require attorney involvement; this is a working file.

---

## Subject claim — Independent Claim 1

> {{FULL_TEXT_OF_CLAIM_1_FROM_CLAIMS_MD}}

### Element-by-element table

| Element | Element text | Target 1: {{TARGET_1_NAME}} | Target 2: {{TARGET_2_NAME}} | Target N: {{TARGET_N_NAME}} |
|---|---|---|---|---|
| 1a | {{Preamble: "A method of..."}} | {{Yes / No / Partial + citation}} | {{...}} | {{...}} |
| 1b | {{First step: "comprising: [step 1]"}} | {{Yes / No / Partial + citation}} | {{...}} | {{...}} |
| 1c | {{Second step}} | {{...}} | {{...}} | {{...}} |
| 1d | {{wherein clause: "wherein [limitation]"}} | {{...}} | {{...}} | {{...}} |
| 1e | {{such-that clause: "such that [effect]"}} | {{...}} | {{...}} | {{...}} |

**Conclusion for Target 1**: {{All elements present / Element 1d not present / Element 1d only partially present}}.

---

## Dependent Claim 2

> {{FULL_TEXT_OF_CLAIM_2}}

### Element-by-element table

| Element | Element text | Target 1 | Target 2 | Target N |
|---|---|---|---|---|
| 2a (inherits 1a–1e) | (referenced from claim 1) | {{See claim 1}} | {{...}} | {{...}} |
| 2b | {{Additional limitation}} | {{Yes / No / Partial + citation}} | {{...}} | {{...}} |

{{REPEAT_FOR_EACH_DEPENDENT_CLAIM}}

---

## Citation format

For each "Yes" or "Partial" cell, include a citation:

- For a patent: column and line number, e.g., "Col. 4, lines 23–37"
- For a publication: page and paragraph, e.g., "p. 12, ¶ 2"
- For a product: URL and access date + specific feature, e.g., "https://example.com/docs/api#rate-limit, accessed 2026-05-19, parameter `burst_size`"
- For source code: file path + line range, e.g., "src/ratelimit/bucket.go:142-178"

Each citation must be reproducible — someone reading the chart should be able to verify the cell independently.

---

## Cell labels

| Label | Meaning |
|---|---|
| Yes | Element is fully present in the target |
| Partial | Element is partially present; specific gap is noted in citation |
| No | Element is absent from the target |
| Unknown | Could not verify from available evidence (note what evidence would be needed) |
| N/A | Element does not apply to this target context |

---

## Summary table

| Target | Independent claims fully read upon? | Dependent claims fully read upon? | Notes |
|---|---|---|---|
| {{TARGET_1_NAME}} | {{Yes / No / Partial}} | {{enumerate}} | {{infringement / no infringement / inconclusive}} |
| {{TARGET_2_NAME}} | {{...}} | {{...}} | {{...}} |

---

## Use of this chart

- **Novelty mapping** — if every element of an independent claim is found in a single prior-art target, the claim is not novel under 35 USC 102 over that target. Time to narrow the claim in `patent-claim-drafting`.
- **Licensing comparison** — if a competitor's product reads on the granted claims, this is the basis for a licensing discussion. Confirm with counsel before sending a demand.
- **Own-implementation read-out** — confirms that the inventor's own product actually practices the claimed invention. Important for marking under 35 USC 287.

---

**Disclaimer**: A working claim chart is not a legal opinion. Any decision to send a demand letter, file suit, or rely on the chart for litigation purposes requires attorney review.
