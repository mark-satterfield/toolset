# patent

A personal patent prep toolkit for inventors who work with an attorney. The plugin does the ideation, eligibility analysis, prior-art research, draft claim writing, and strategic-worth scoring that helps you arrive at your lawyer's office prepared. The lawyer files, prosecutes, pays, and enforces; the plugin makes you a much more productive client.

Uses only free, public data sources.

## What it produces

The plugin produces artifacts you bring to your lawyer:

- **Invention disclosure document** — the canonical inventor-to-lawyer handoff
- **Eligibility analysis** — Alice/Mayo two-step + EPO technical-effect, cited to controlling cases, so you can answer "why do you think this is patentable?"
- **Prior-art research** — patent and non-patent prior art with source-credibility tiers
- **Draft claims** — independent + dependent, with 35 USC 112 compliance noted, as a starting point your lawyer will refine
- **Strategic-worth scoring** — detectability, designability, evidence path — so you know which ideas are worth your lawyer's billable time
- **Triage ranking** — which idea to bring to your lawyer next

It can also produce USPTO-format drafts (PPA, non-provisional, IDS) and defensive publications, but the primary handoff is the invention disclosure document.

## Architecture

A thin router (`patent`) dispatches on entry intent to one of six specialized sub-skills:

| Entry intent | Routes to |
|---|---|
| Raw idea, open phrasing | `patent-ideation` |
| Eligibility question on a shaped idea | `patent-patentability` |
| Request to draft claims | `patent-claim-drafting` |
| Strategic-worth assessment | `patent-enforceability` |
| Document request | `patent-document-generation` |
| "What should I bring to my lawyer next?" | `patent-triage` |

The router holds no workflow logic of its own. Each sub-skill operates on filesystem state under `patents/` in the working repo — no in-memory cross-session state. The `funnel-stage` field in `idea.md` is the coordination signal.

## State model

```
patents/
  portfolio.md                  — moat thesis + triage ranking
  prior-art-cache/
  ideas/
    {domain-area-slug}/
      idea.md
      qa-log.md
      prior-art.md
      eligibility.md
      claims.md
      enforceability.md
      decision.md
      generated/
```

See `references/state-model.md` for the full schema.

## Slash commands

- `/patent:idea` — start a new idea (routes to `patent-ideation`)
- `/patent:assess` — patentability + prior art
- `/patent:claims` — draft independent + dependent claims
- `/patent:enforce` — strategic-worth scoring
- `/patent:document` — generate an invention disclosure (or other artifact)
- `/patent:triage` — rank ideas; what to bring to your lawyer next

Or just describe what you want — the router skill will pick the right path.

## External integrations

All free, public, no credentials required:

- **PatentsView API** — structured US patent data
- **Google Patents** — global corpus with full text (web + BigQuery public data)
- **EPO Open Patent Services** — European patent data
- **Web search** — non-patent prior art
- **arXiv API** — academic prior art
- **GitHub code search** — open-source prior art

Each integration degrades gracefully: if a source is unavailable, the dependent skill states that prior-art coverage is partial rather than implying a clean search.

## Knowledge base

Bundled in `references/`:

- Alice failure-mode catalog
- Eligibility-saving reframings catalog
- Federal Circuit case summaries (Alice, Bilski, Mayo, DDR Holdings, Enfish, McRO, Berkheimer, Aatrix, Electric Power Group, CyberSource, Affinity Labs, BSG Tech)
- EPO technical-effect heuristics
- 35 USC 112 claim-formalism checklist
- Scoring rubrics (patent strength, strategic-worth tiers, FTO risk)
- Source credibility tiers for prior-art evaluation
- Document templates (invention disclosure, PPA, non-provisional skeleton, IDS, claim chart, defensive publication)

## Scope: what this plugin does and does NOT do

**Does:**
- Ideation, framing, Alice-failure-mode triage
- Eligibility analysis under US Alice/Mayo and EPO technical-effect
- Prior-art research with source-credibility tiers and graceful degradation
- Claim drafting (as a starting point your lawyer will refine)
- Strategic-worth scoring (detectability, designability, evidence path)
- Invention disclosure document generation
- Defensive publication generation (the one self-publishable artifact)
- Triage ranking across ideas

**Does NOT:**
- File anything with the USPTO
- Pay maintenance or filing fees
- Draft prosecution responses to office actions
- Track docket dates or send reminders
- Enforce, send demand letters, or draft licensing agreements
- Substitute for a registered patent attorney

The plugin is a prep tool. Your attorney is the legal actor.

## Accuracy and limits

Eligibility, novelty, non-obviousness, and strategic-worth outputs are estimates produced to support your decision-making and to give your attorney a productive starting point. They are not guarantees of how an examiner would rule. Examiner variance is real; close calls under Alice Step 2 are genuinely uncertain. Every scored output carries an explicit confidence label (HIGH / MEDIUM / LOW / SPECULATIVE).

## Build status

- [x] M1 — State model + router + `patent-ideation`
- [x] M2 — `patent-patentability` + external integrations
- [x] M3 — `patent-claim-drafting`
- [x] M4 — `patent-enforceability`
- [x] M5 — `patent-document-generation`
- [x] M6 — `patent-triage`
