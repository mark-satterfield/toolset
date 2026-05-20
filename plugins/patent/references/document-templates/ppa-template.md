# Provisional Patent Application (PPA) — {{TITLE}}

> **Type**: USPTO Provisional Patent Application draft
> **Applicant**: {{INVENTORS}}
> **Filing date** (target): {{PLANNED_FILING_DATE}}
> **Cover sheet**: USPTO Form SB/16 — see https://www.uspto.gov/sites/default/files/documents/sb0016.pdf
> **Filing portal**: USPTO EFS-Web at https://efs.uspto.gov/

A PPA does not require formal claims and is not examined. To preserve a priority date for later non-provisional filing, the PPA must disclose the invention sufficiently to satisfy 35 USC 112(a) (written description + enablement) when relied upon.

---

## Title of the invention

{{TITLE}}

## Cross-references to related applications

{{NONE — for a first filing. Otherwise list parent applications.}}

## Statement regarding federally sponsored research

Not applicable.

## Background of the invention

### Field of the invention

The present invention relates to {{TECHNICAL_FIELD}}.

### Description of related art

{{PRIOR_APPROACHES_FROM_IDEA_MD: each known approach + its limitation}}

## Brief summary of the invention

{{ONE_TO_THREE_PARAGRAPHS — derived from idea.md approach + delta + technical effect}}

## Brief description of the drawings

- **Fig. 1** illustrates {{SUGGESTED_FIGURE_1}}.
- **Fig. 2** illustrates {{SUGGESTED_FIGURE_2}}.
- ...

(Drawings to be supplied separately if filed with figures. PPAs may be filed without drawings if drawings are not needed to understand the subject matter.)

## Detailed description of the invention

This is the largest and most important section. It must enable a person of ordinary skill in the art to practice the invention without undue experimentation.

### Overview

{{ONE_PARAGRAPH_OVERVIEW}}

### Detailed mechanism

{{FROM_IDEA_MD: the approach, expanded with worked examples from qa-log.md}}

### Alternative embodiments

{{LIST_FROM_IDEA_MD: each alternative embodiment described with sufficient detail to be practiced}}

### Worked example

{{IF_AVAILABLE: numerical or pseudocode walkthrough}}

### Variations

{{LIST: dimensions along which the invention can vary while preserving the technical effect}}

## Optional claims

A PPA may include claims to strengthen the priority-support argument for the later non-provisional. Recommended for stronger priority.

{{IF_CLAIMS_MD_EXISTS: embed all independent claims}}

## Abstract

{{150_WORD_OR_FEWER_ABSTRACT — single paragraph, states what the invention is}}

---

## Filing notes

1. Complete USPTO Form SB/16 (cover sheet) with:
   - Inventor name(s), residence(s)
   - Title of the invention
   - Correspondence address
   - Entity status (large / small / micro)

2. Pay the appropriate fee. As of the plan reference date (verify current fees at https://www.uspto.gov/learning-and-resources/fees-and-payment):
   - Large entity: ~$320
   - Small entity: ~$160
   - Micro entity: ~$65 (qualify if: gross income < 3× US median household; named on ≤4 prior US applications)

3. File electronically via EFS-Web. Receive an electronic acknowledgment with the application number and filing date.

4. Record the filing details in the idea directory's `decision.md`:
   ```
   filing_type: provisional
   filing_date: YYYY-MM-DD
   application_number: 63/XXX,XXX
   provisional_conversion_deadline: YYYY-MM-DD (filing_date + 12 months)
   ```

5. Set a calendar reminder for the conversion deadline. A provisional cannot be extended. If you do not file a non-provisional within 12 months, the priority date is lost.

---

**Disclaimer**: This template is a working draft. It is NOT legal advice. Filing decisions, claim drafting, and prosecution strategy in real cases benefit from review by a registered patent practitioner. The inventor proceeding self-filed bears all risk.
