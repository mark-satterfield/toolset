# Source credibility tiers

Every prior-art reference, case citation, or eligibility-supporting source carries a tier label. Tiers reflect the rigor with which the source can be relied upon and the strength of the conclusion it supports.

Adapted from the 5-tier credibility model in the patent-intelligence-engine reference.

## Tiers

### Tier 1 — Authoritative primary sources

- USPTO patent grants and published applications (with full prosecution history available via Public PAIR)
- EPO published patents and opposition records
- WIPO PCT publications
- Federal Circuit decisions, Supreme Court patent decisions
- PTAB IPR / PGR / CBM decisions
- 37 CFR sections, 35 USC sections, MPEP sections

These are the gold standard. A claim grounded in a Tier 1 source carries HIGH confidence by default.

### Tier 2 — Adjacent primary sources

- Foreign patent offices (KIPO, JPO, CNIPA, IP Australia)
- Patent classification systems (CPC, IPC) and their official definitions
- USPTO and EPO examiner-cited prior art (when published with rejections)
- USPTO Patent Eligibility Guidance and updates
- EPO Guidelines for Examination
- Patent attorney-authored treatises (Chisum on Patents, Nimmer on Copyright equivalent for patent law)

Reliable but require cross-referencing for strong claims. Use to confirm Tier 1 findings.

### Tier 3 — Technical literature

- arXiv preprints (when peer-reviewed equivalents exist)
- IEEE Xplore and ACM Digital Library papers
- Conference proceedings (peer-reviewed)
- Books from established technical publishers (O'Reilly, Manning, Springer)
- Standards documents (RFCs, ISO, IEEE standards)
- Open-source project source code with version control history

Useful as prior art. Citation must include the version or revision date. A claim grounded in Tier 3 sources requires multiple in agreement for HIGH confidence.

### Tier 4 — Industry sources

- Engineering blog posts from established companies (Google, Meta, Netflix tech blogs)
- Conference talks (video or slides) with named presenters and dates
- Trade publications (IEEE Spectrum, Communications of the ACM)
- Patent analytics services' free content (Patent Public Search, Google Patents Scholar)
- Reputable industry analyst reports (with author and date)

Useful for context and pattern-confirmation. Insufficient alone for HIGH confidence. Always identify and label as Tier 4 when cited.

### Tier 5 — Unreliable / noise

- Anonymous forum posts (Reddit, Hacker News)
- Wikipedia (use as a starting point but cite the underlying source)
- Social media posts
- Press releases without technical detail
- Marketing material
- Articles by unnamed authors on low-reputation sites

Do not cite as prior art unless re-grounded in a higher tier. Use only as a discovery aid.

## Confidence labels

Every conclusion in `eligibility.md`, `prior-art.md`, and `enforceability.md` carries one of these labels:

| Label | Source backing required |
|---|---|
| HIGH | Cited by a controlling case OR ≥2 Tier 1/2 sources OR ≥3 Tier 3 sources in agreement |
| MEDIUM | One Tier 1/2 source OR multiple Tier 3 sources in agreement |
| LOW | Indirect inference OR single Tier 3 source OR a close call under current law |
| SPECULATIVE | No source backing, drawn from reasoning alone |

A conclusion at SPECULATIVE confidence must be flagged in the output, never buried.

## Tier-tagging in `prior-art.md`

Every reference table row in `prior-art.md` includes a `Source tier` column with one of: T1, T2, T3, T4. Do not cite T5 sources directly.
