# Defensive Publication — {{TITLE}}

> **Publication date**: {{TODAY}}
> **Author(s)**: {{INVENTORS_OR_ANONYMOUS}}
> **Type**: Public disclosure for prior-art purposes
> **DOI / URL / Repository** (to be filled after publishing): {{PUBLISHED_URL}}

A defensive publication is a public, timestamped disclosure of an invention. It creates prior art that blocks subsequent patent filings by anyone — including the discloser. The discloser sacrifices the patent option in exchange for cheap, fast prior-art creation.

**Use when**: the strategic-value tier is C or D and the inventor prefers to deny competitors the patent over filing it themselves.

---

## Title

{{TITLE}}

## Abstract

{{ONE_PARAGRAPH_ABSTRACT — derived from idea.md, broader-worded than a patent abstract since the goal is wide prior-art coverage}}

## Field

This disclosure relates to {{TECHNICAL_FIELD}}.

## Background

{{TECHNICAL_PROBLEM_FROM_IDEA_MD: the problem being solved}}

### Prior approaches and their limitations

{{LIST_FROM_IDEA_MD}}

## Disclosure

{{FROM_IDEA_MD: the approach, expanded for clarity. This must be ENABLING — a person of ordinary skill must be able to practice the invention from this disclosure alone.}}

### Specific embodiment

{{ONE_CONCRETE_EMBODIMENT_FROM_IDEA_MD: complete enough to reproduce}}

### Worked example

{{NUMERICAL_OR_PSEUDOCODE_WALKTHROUGH_IF_AVAILABLE}}

### Alternative embodiments

The disclosed approach may be implemented in numerous alternative ways:

{{LIST_FROM_IDEA_MD: each alternative described with enabling detail. The broader this list, the broader the prior-art block.}}

### Variations and configurability

{{LIST_DIMENSIONS_OF_VARIATION}}

## Technical effects

{{FROM_IDEA_MD: measurable improvements produced by the approach}}

## Possible applications

{{ENUMERATE_APPLICATION_DOMAINS — broader is better for defensive purposes}}

## Disclaimer of patent rights

The author(s) hereby disclose this invention publicly and irrevocably. The author(s) make no claim of patent rights to the subject matter described herein. This publication is intended as prior art under 35 USC 102 and equivalent provisions in other jurisdictions, blocking subsequent patent filings by any party.

This disclosure does not waive copyright in the textual presentation of this document, only patent rights in the underlying invention.

---

## Publication venue recommendations

Defensive value depends on:
1. **Timestamp authenticity** — must be verifiable by third parties
2. **Search-engine findability** — examiners must be able to discover it
3. **Permanence** — the disclosure must remain accessible

### Recommended venues (in rough order of defensive strength)

1. **arXiv.org** (https://arxiv.org)
   - Free, fast (typically 1–2 day moderation), archival
   - Submit to the cs.* category matching the invention's domain
   - Receives a DOI and permanent URL
   - Indexed by Google Scholar and patent examiners

2. **IP.com Prior Art Database** (https://priorart.ip.com)
   - Free tier exists for inventors
   - Explicit prior-art purpose (signals intent to examiners)
   - Searchable by examiners worldwide

3. **Personal blog + arXiv combo**
   - Blog provides discoverability and human-readable framing
   - arXiv provides the formal timestamp and DOI

4. **GitHub repository with tagged release**
   - Strong for software/code-centric inventions
   - The tagged release timestamp is cryptographically verifiable
   - Combine with a written description for the algorithmic content

5. **Research Disclosure** (https://www.researchdisclosure.com)
   - Established defensive publication venue
   - Subscription-only for the publication itself (cost a few hundred USD)
   - Strong industry recognition

### Steps after publishing

1. Capture the published URL and the SHA-256 hash of the canonical published document
2. Archive the URL via the Wayback Machine: https://web.archive.org/save/
3. Capture a screenshot of the published page (date-stamped by the publisher's UI)
4. Update the idea's `decision.md`:
   ```yaml
   decision: defensive-publish
   decision_date: YYYY-MM-DD
   filing_type: defensive-publication
   published_url: <full URL>
   published_doi: <DOI if any>
   published_sha256: <hash of canonical document>
   wayback_url: <web.archive.org snapshot URL>
   ```
5. Update `portfolio.md` to mark the idea's filing status as `defensive-published`

---

**Disclaimer**: Once published as defensive material, the patent option is forfeit. Provisional and non-provisional patent applications cannot be filed for the same invention after public disclosure (in the US, you have a 12-month grace period under 35 USC 102(b) but lose foreign filing options in absolute-novelty jurisdictions immediately). Defensive publication is a deliberate, irreversible choice.
