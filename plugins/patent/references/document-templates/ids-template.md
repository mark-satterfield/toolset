# Information Disclosure Statement — {{TITLE}}

> **Application**: {{APPLICATION_NUMBER}}
> **Inventor(s)**: {{INVENTORS}}
> **Filing date of IDS**: {{TODAY}}
> **Form basis**: USPTO Form PTO/SB/08a (US patent documents), PTO/SB/08b (Foreign patent documents and Non-Patent Literature)

The IDS is the inventor's duty-of-candor disclosure of prior art known to the inventor. Filing an IDS is mandatory under 37 CFR 1.56 — failure to disclose known material prior art can render any resulting patent unenforceable for inequitable conduct.

## US Patent Documents (PTO/SB/08a equivalent)

| Cite No. | Document Number | Pub/Issue Date | Patentee or Applicant | Relevant Pages, Figures |
|---|---|---|---|---|
{{FOR_EACH_US_PATENT_OR_PUBLISHED_APPLICATION_IN_PRIOR_ART_MD}}

Format example:

| 1 | US 8,XXX,XXX B2 | 2022-03-15 | Acme Corp. | Cols. 4–6 |
| 2 | US 2021/0XXXXXX A1 | 2021-08-22 | Smith et al. | ¶¶ 0023–0045 |

## Foreign Patent Documents (PTO/SB/08b — Section 1)

| Cite No. | Foreign Document Number | Country Code | Publication Date | Applicant of Cited Document |
|---|---|---|---|---|
{{FOR_EACH_FOREIGN_PATENT_REFERENCE}}

Format example:

| 1 | EP 3,XXX,XXX A1 | EP | 2022-01-12 | Beta GmbH |
| 2 | WO 2021/XXXXXX A1 | WO | 2021-06-30 | Gamma SA |

## Non-Patent Literature (PTO/SB/08b — Section 2)

Format follows the citation conventions of the field. Include enough detail for an examiner to locate the document.

| Cite No. | Full Citation |
|---|---|
{{FOR_EACH_NON_PATENT_LITERATURE_REFERENCE}}

Format example:

| 1 | Smith, J. and Jones, A., "Adaptive Bloom Filters for High-Throughput Streaming", *Proc. SIGMOD 2021*, pp. 1234–1247, June 2021. |
| 2 | "Apache Kafka Consumer Documentation", v3.0, accessed 2026-05-19, https://kafka.apache.org/30/documentation/. |

## Concise explanation of relevance (optional but recommended)

For each reference, a one-to-three-sentence explanation of how it relates to the claims helps the examiner and demonstrates good-faith candor:

| Cite No. | Relevance |
|---|---|
{{FOR_EACH_REFERENCE: brief explanation}}

Example:

| 1 | US 8,XXX,XXX discloses a counting Bloom filter with periodic decay. The present invention differs in that the decay schedule is adaptive to the input rate, not periodic, providing the inventive technical effect of bounded false-positive rate under variable load. |

---

## Filing notes

1. File the IDS along with the application or within three months of receiving any new reference (37 CFR 1.97). Late filings require a certification and possibly a fee.

2. Use the USPTO electronic filing system. PDF of the form plus copies of each non-US-patent reference (US patents are accessible to the examiner without copies).

3. For non-patent literature, attach a copy. Examiners do not search outside the patent corpus.

4. Maintain a duplicate file in the idea directory's `generated/` folder for the inventor's records.

5. Keep updating the IDS through prosecution. Each new reference learned during prosecution must be disclosed under the continuing duty of candor.

---

**Disclaimer**: Inequitable conduct based on inadequate disclosure is a serious risk. When in doubt about whether to cite a reference, cite it. Over-disclosure has no penalty; under-disclosure can void the patent.
