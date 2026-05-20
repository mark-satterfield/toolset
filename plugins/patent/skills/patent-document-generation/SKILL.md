---
name: "patent-document-generation"
description: Generates artifacts from an idea directory for handoff to a patent attorney. Primary artifact is the invention disclosure document — the canonical inventor-to-lawyer record. Secondary artifacts (USPTO PPA draft, non-provisional skeleton, IDS) are starting drafts the lawyer will revise. Defensive publication is the one document the inventor can self-publish to create blocking prior art. Claim chart is for the inventor's own analysis. Writes markdown source and renders PDF when a renderer is available. Use when the user asks to generate, draft, or produce any of these artifacts.
triggers:
  - generate document
  - draft document
  - invention disclosure
  - invention record
  - for my lawyer
  - artifact for the lawyer
  - PPA
  - provisional patent
  - non-provisional
  - utility application
  - IDS
  - information disclosure statement
  - claim chart
  - defensive publication
  - finished document
---

# patent-document-generation

You assemble artifacts from the content accumulated in an idea directory. The audience is an inventor preparing to meet with a patent attorney. The invention disclosure document is the primary deliverable; everything else is secondary.

Every fact in every output traces to `idea.md`, `eligibility.md`, `prior-art.md`, `claims.md`, `enforceability.md`, or `qa-log.md`. If a required field is missing, you stop and tell the user which earlier skill to run first. You do not invent content.

## Inputs

- `patents/ideas/{slug}/` — the full idea directory
- Document type the user wants — if not specified, ask

## Step 1 — Determine document type

Ask the user (one question, one menu):

> "Which artifact do you want?
>
> **Primary (the things you actually take to your lawyer)**
> 1. **Invention disclosure** — the canonical inventor-to-lawyer record. Recommended for almost every meeting.
> 2. **Defensive publication** — self-publishable prior art for ideas you've decided not to file. Done by the inventor; no lawyer needed.
> 3. **Claim chart** — element-by-element analysis for your own thinking (novelty mapping, "does my product practice this", competitor comparison)
>
> **Secondary (useful for context; your lawyer will redraft)**
> 4. **Provisional patent application (PPA) draft** — USPTO-format starting point. Your lawyer will rewrite in their own style; this is for your understanding or for solo lawyers who appreciate the head-start.
> 5. **Non-provisional skeleton** — full spec + claims + abstract in USPTO format. Same caveat: your lawyer will redraft.
> 6. **IDS prior-art summary** — USPTO PTO/SB/08-format prior-art list. Your lawyer files the actual IDS in their own format; this is the underlying data."

If the user picks options 4, 5, or 6, mention before generating: "This is a USPTO-format draft. Your lawyer will rewrite it in their own style — but it captures the substance for them to work from."

## Step 2 — Verify the directory is ready for the chosen type

| Document type | Required files |
|---|---|
| Invention disclosure | `idea.md` at stage `shaped` or later |
| Defensive publication | `idea.md` at stage `shaped` or later, with a `decision.md` recording the choice not to file |
| Claim chart | `claims.md` + `prior-art.md` |
| PPA draft | `idea.md` at `claim-ready` (claims optional in PPA but recommended) |
| Non-provisional skeleton | `idea.md` + `claims.md` at stage `claim-ready` |
| IDS prior-art summary | `prior-art.md` |

If a required file is missing, do not proceed. State exactly which earlier skill to run.

## Step 3 — Assemble the document

Open the matching template in `references/document-templates/`. Each template has placeholder sections; fill them from the directory contents.

### Invention disclosure document (PRIMARY)

Template: `references/document-templates/invention-disclosure.md`

This is the canonical handoff artifact. The lawyer reads this, asks the inventor questions, and from there decides what to file and how to claim it.

Structure:
- Inventor(s) — from `idea.md`
- Title — from `idea.md`
- Conception date — from `idea.md`
- Reduction-to-practice date — from `idea.md`
- Technical field
- Background — the problem and prior approaches
- Summary of the invention
- Detailed description — the approach, all alternative embodiments
- Drawings (placeholder for the inventor to attach)
- Possible variations
- Advantages and technical effects
- Eligibility note — one paragraph summarizing your eligibility reasoning from `eligibility.md`, so the lawyer can see the case-law analogies you're relying on
- Draft claims (if `claims.md` exists, embed all — flag clearly as "inventor's draft, lawyer will revise")
- Prior art known to the inventor (from `prior-art.md`)

The acceptance criterion is that someone reading only this document — including a busy attorney with no other context — understands the invention end-to-end and has the inputs they need to start prosecution-planning.

### Defensive publication (PRIMARY — inventor-direct action)

Template: `references/document-templates/defensive-publication.md`

A defensive publication is a public, timestamped disclosure that creates prior art blocking subsequent filings by anyone else. It does NOT confer rights to the inventor — it sacrifices the patent option in exchange for cheap, fast prior-art creation.

This is the one document type the inventor publishes themselves; no lawyer required.

Structure:
- Title
- Publication date (must be verifiable)
- Inventor(s) — optional; can be anonymous
- Field of the invention
- Background
- Detailed description — must be enabling
- Possible variations and alternative embodiments (the broader, the better — broader disclosure blocks broader future claims)

Publication venues:
- **arXiv** (cs.* category) — fast, free, archival, recognized prior art
- **IP.com Prior Art Database** — free tier; explicit prior-art purpose
- **GitHub repository with a public release** — adequate if the venue is reputable
- **Personal blog + Wayback Machine snapshot** — weakest but acceptable

After publishing: archive via web.archive.org, capture SHA-256 of the canonical document, record both in `decision.md`.

### Claim chart (PRIMARY — inventor's own analysis)

Template: `references/document-templates/claim-chart-template.md`

Element-by-element table. One row per claim element, one column per target (prior-art reference, competitor product, inventor's own implementation).

This is for the inventor's analysis: novelty mapping, "does my product practice this claim", competitor comparison. Bring to the lawyer as supporting context. Not a litigation exhibit — those are produced under attorney supervision.

### Provisional Patent Application (PPA) draft (SECONDARY)

Template: `references/document-templates/ppa-template.md`

USPTO-format starting draft. Your lawyer will not file this as-is — they will rewrite in their house style. Generating this is useful when:
- You want to understand the USPTO PPA format
- Your lawyer is willing to use the draft as input rather than starting from blank
- You are working with a solo practitioner who appreciates the head-start

Structure:
- Title
- Cross-references to related applications
- Federally sponsored research statement
- Background
- Summary
- Brief description of drawings (if any)
- Detailed description (largest section — must enable practice)
- Optional claims (recommended for stronger priority support)
- Abstract

Mark the output clearly: "This is an inventor-prepared draft. Filing should be done by your attorney."

### Non-provisional application skeleton (SECONDARY)

Template: `references/document-templates/non-provisional-skeleton.md`

Same caveat as the PPA draft: USPTO-format starting point, lawyer will redraft. Generated only when the inventor specifically requests it.

Structure follows 37 CFR 1.77(b) — see the template for the section order.

### IDS prior-art summary (SECONDARY)

Template: `references/document-templates/ids-template.md`

USPTO PTO/SB/08-format prior-art listing. Your lawyer files the actual IDS in their own format; this captures the substance for them.

Mark the output: "This is a substance-only IDS summary. Your lawyer files the formal IDS in their own format with their own filing process."

## Step 4 — Write the document file

Write to `patents/ideas/{slug}/generated/{document-type}.md`. Create the directory if needed. The markdown file is the source of truth.

## Step 5 — Render to PDF (best-effort)

Try, in order:

1. **pandoc** — `pandoc {file}.md -o {file}.pdf --pdf-engine=xelatex` (or `wkhtmltopdf` as fallback)
2. **md-to-pdf** — if Node.js + `md-to-pdf` is installed
3. **weasyprint** — if Python + `weasyprint` is installed
4. **Skip with a note** — if no renderer is available, write the markdown only and tell the user: "PDF renderer not found. Install pandoc with `brew install pandoc` (macOS) and re-run, or open the markdown directly."

Never claim PDF generation succeeded if it did not.

## Step 6 — Confirm and recommend next step

Tell the user:
- Which file was written (path)
- Whether PDF was rendered
- For the invention disclosure: "This is ready to send to your lawyer. Recommend running `/patent:enforce` first if not done, so the lawyer sees the strategic-worth scoring alongside the disclosure."
- For the defensive publication: "Publish to your chosen venue and update decision.md with the published URL, timestamp, and SHA-256 hash. The plugin does not publish for you."
- For PPA / non-prov / IDS drafts: "This is a starting draft. Send to your lawyer with a note that you generated it as a head-start; they will redraft."

## Acceptance criteria

- The invention disclosure is self-contained, lawyer-ready, and includes an eligibility-reasoning summary so the attorney can see the case-law analogies you're relying on
- The defensive publication is enabling and broadly worded with alternative embodiments, suitable to constitute prior art on publication
- USPTO-format secondary drafts are clearly marked as "inventor draft; lawyer will redraft" — never framed as ready-to-file
- Every fact in every document traces to an existing file in the idea directory; no invention happens here

## What this skill does NOT do

- It does NOT file with the USPTO
- It does NOT compute or recommend filing fees
- It does NOT submit to defensive-publication venues (the inventor publishes themselves)
- It does NOT replace an attorney's drafting work on USPTO filings

## References

- `references/document-templates/invention-disclosure.md`
- `references/document-templates/defensive-publication.md`
- `references/document-templates/claim-chart-template.md`
- `references/document-templates/ppa-template.md`
- `references/document-templates/non-provisional-skeleton.md`
- `references/document-templates/ids-template.md`
- `references/state-model.md`
