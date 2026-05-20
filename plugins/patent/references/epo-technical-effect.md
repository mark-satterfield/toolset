# EPO further-technical-effect test

The European Patent Office (EPO) takes a different doctrinal approach to software patents than the US. Where the US uses Alice/Mayo two-step under 35 USC 101, the EPO uses Article 52 EPC and the "further technical effect" test established in T 1173/97 (IBM/Computer programs) and refined through the Boards of Appeal.

A US-eligible invention is often EPO-eligible, but the framings can diverge. Including the EPO analysis in `eligibility.md` strengthens international filing strategy.

## The EPO test

### Article 52(2)(c) EPC — what is excluded

The following are excluded from patentability "as such":

- Schemes, rules and methods for performing mental acts, playing games or doing business
- Programs for computers
- Presentations of information

The critical phrase is "as such". An invention that uses a computer program but solves a technical problem is not excluded.

### The two-step EPO analysis

**Step 1 — Is there technical character?**

A claim has technical character if it specifies technical means (e.g., a computer, network, processor). Almost every software invention satisfies Step 1 trivially.

**Step 2 — Does the claim produce a further technical effect?**

This is the substantive step. A "further technical effect" goes beyond the "normal" physical interaction between the program and the computer (i.e., the program executing as software does — that doesn't count).

Examples of acknowledged further technical effects:

- Reduced consumption of memory
- Higher processing speed
- Better security or cryptographic strength
- Improved bandwidth use or network throughput
- More efficient sensor signal processing
- Improved control of an industrial process or device
- Better disk I/O or cache utilization
- More efficient parallelization or distribution of computation
- Reduced power consumption

Examples that do NOT produce a further technical effect:

- Improving the economic outcome of a business process
- Improving the presentation of information (e.g., a clearer chart)
- Improving user experience in non-technical ways (e.g., easier navigation)
- Gameplay rules or fairness
- Aesthetic improvements

### Step 3 — Inventive step assessment (problem-solution approach)

If the claim has further technical effect, the EPO uses the "problem-solution approach":

1. Identify the closest prior art (CPA)
2. Identify the technical features that distinguish the claim from the CPA
3. Identify the technical effect those features produce
4. Formulate the "objective technical problem" as: "how to modify the CPA to produce the technical effect"
5. Ask: would a skilled person, starting from the CPA and facing the objective technical problem, arrive at the claim's solution in an obvious way?

Note: Non-technical features (business outcomes, aesthetic preferences) are NOT considered in inventive step assessment. They appear in the problem statement but cannot contribute to non-obviousness.

This means: a business outcome cannot rescue an otherwise obvious technical invention at the EPO. The technical features alone must be non-obvious.

## Differences from US Alice/Mayo

| Dimension | US | EPO |
|---|---|---|
| Statutory basis | 35 USC 101 | Article 52 EPC |
| Doctrinal test | Two-step Alice/Mayo | "Further technical effect" + problem-solution |
| Sensitive to claim drafting? | Yes, very | Less — focus is on the technical content, not phrasing |
| Treats business outcomes | Can sometimes save with Step 2b inventive concept | Cannot contribute to inventive step at all |
| Treats ML applications | Skeptical under Step 2b | More permissive if the ML contribution has further technical effect (e.g., efficiency, accuracy, speed) |

## Heuristics for `patent-patentability`

When writing the EPO section of `eligibility.md`:

1. **State whether the claim has a further technical effect**, naming the specific effect (memory, speed, etc.) and citing the supporting field of `idea.md`.
2. **Identify the closest prior art** from `prior-art.md`. If not yet searched, defer.
3. **State the objective technical problem** in the form: "How to modify the CPA to produce [the technical effect]".
4. **Assess obviousness from the technical features alone** — explicitly exclude business outcomes from the analysis.

## Common EPO-safer reframings

- Tie every claim limitation to a measurable computational property (memory, latency, throughput, cache, energy, bandwidth)
- Avoid claim language about user experience, business outcomes, or "ease of use"
- For ML inventions: emphasize the training procedure, architecture, or inference optimization rather than the downstream task
- For UI inventions: be cautious — EPO is strict about "presentation of information"; reframe around the underlying state-management or rendering mechanism

## When EPO eligibility is in question

If the EPO analysis is negative, options:

1. Reframe the claim around the technical effect (use `eligibility-reframings.md`)
2. File in the US only — many software inventions that survive Alice/Mayo do not survive EPO Article 52
3. File in JP/KR/CN where the test is closer to Japan's "concrete means" or China's "technical solution" requirement — generally more permissive than EPO but stricter than US
4. Defer EPO filing and watch for further EPO Board of Appeal precedent

## Reference cases (EPO Board of Appeal)

- **T 1173/97 (IBM/Computer programs)** — established the further-technical-effect test
- **T 154/04 (Duns Licensing Associates)** — business methods + computer implementation is not enough
- **T 258/03 (Hitachi)** — every claim with technical means has technical character (Step 1 trivially satisfied)
- **T 641/00 (COMVIK)** — non-technical features cannot contribute to inventive step

These are not binding on US examiners but are useful framing references when drafting for global filing strategy.
