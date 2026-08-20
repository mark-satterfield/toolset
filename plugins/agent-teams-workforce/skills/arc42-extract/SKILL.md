---
name: arc42-extract
description: >-
  Reads a Software Architecture Document (SAD) written to the arc42 template and EXTRACTS its
  decision-bearing sections — section 2 Constraints, section 4 Solution Strategy and section 8
  Crosscutting Concepts — into one typed, stably-identified
  packet that the Technical Requirements Document (TRD) author and the spec authors consume
  downstream. This is a pure read: it locates each section reliably across both single-file and
  one-file-per-section arc42 layouts, normalizes every entry to a fixed shape with a stable ID,
  and invents nothing the SAD does not state. Use when extracting constraints, solution strategy,
  crosscutting concepts, or architecture decisions from an arc42 SAD; when building the input
  packet that feeds a TRD or spec; when you need stable IDs for SAD content; or when a downstream
  author asks "what did the architecture document decide" and needs a machine-shaped answer.
triggers:
  - extract from the SAD
  - extract arc42 sections
  - pull constraints and decisions
  - feed the TRD from the architecture doc
  - what did the architecture document decide
  - solution strategy extraction
  - crosscutting concepts packet
  - arc42 extraction
  - SAD to TRD handoff
  - stable IDs for architecture decisions
  - read the architecture document
---

# arc42-extract — SAD reader and decision packet emitter

You read a Software Architecture Document authored to the **arc42** template and emit a single
typed packet of its decision-bearing content. You have exactly one job: **extraction**. You do not
critique the architecture, you do not fill gaps, you do not draft requirements. Every entry you emit
must be traceable to a span of text that already exists in the SAD. If the SAD does not say it, the
packet does not contain it.

The SAD you read is the authoring side; this skill is the reading side. The canonical template,
section catalog, and shape of each section live in the sibling arc42 skill — read
`../arc42/references/` for the section model your selectors target. The three reference files in
**this** skill define what you emit and the contract downstream authors rely on.

## What you extract

The SAD has eleven sections. You pull only the three that carry forward-binding decisions:

| arc42 section | Title | Why it feeds downstream |
|---|---|---|
| 2 | Constraints | Hard limits (technical, organizational, conventions) the TRD and specs must respect. |
| 4 | Solution Strategy | The top-level approach — chosen patterns, tech, decomposition rationale — the specs elaborate. |
| 8 | Crosscutting Concepts | Concept-level rules (security model, persistence, error handling, i18n) that cut across specs. |

Sections 1, 3, 5, 6, 7, 10, 11, 12 (Introduction & Goals, Context & Scope, Building Block View,
Runtime View, Deployment View, Quality Requirements, Risks & Technical Debt, Glossary) are **not**
part of this packet. If a downstream author needs them, that is a separate extraction with a
separate contract — do not smuggle them in.

## How to run

1. **Resolve the layout.** Determine whether the SAD is one file (all eleven sections under one
   document) or one file per section (a directory tree). The selector strategy differs; see
   `references/section-selectors.md`. Never assume the layout — detect it from what is on disk.
2. **Locate the four sections.** Use the layered selector cascade (numeric prefix → canonical
   title → known synonym → structural fallback) from `references/section-selectors.md`. Record for
   each located section the `sourceSection` (canonical arc42 number) and the concrete origin
   (file path plus heading or line span) so every entry stays traceable.
3. **Split each section into atomic entries.** One constraint, one strategy statement, one concept,
   one decision per entry. A bullet list becomes N entries; a decision stated in section 4 becomes
   one entry whose `rationaleRef` points at its rationale span.
4. **Assign stable IDs.** IDs are deterministic and content-anchored, not positional — see the ID
   rules in `references/extraction-schema.md` and `references/trd-feed-contract.md`. The same SAD
   content yields the same ID across re-runs so downstream references do not rot.
5. **Emit the packet.** Produce the typed structure defined in `references/extraction-schema.md`.
   Validate that every entry has all four required fields and that no `id` collides.
6. **Signal completeness.** If a target section is absent from the SAD, emit it as present-but-empty
   with an explicit `missing` marker rather than omitting it silently — the contract requires the
   four section buckets to always exist. See `references/trd-feed-contract.md`.

## The emitted packet (shape sketch)

The packet is three buckets (`constraints`, `solutionStrategy`, `crosscuttingConcepts`), each a
list of entries. Every entry, regardless of bucket, has the same four fields:

- `id` — stable, content-anchored identifier, unique across the whole packet.
- `sourceSection` — the canonical arc42 section number the entry came from (2, 4, or 8).
- `statement` — the extracted text, verbatim or minimally normalized, never paraphrased into new meaning.
- `rationaleRef` — a pointer to the rationale/justification span in the SAD (or `null` when the SAD gives none).

A plain-prose rendering of one decision entry: *id `AD-payments-idempotency`, sourceSection 4,
statement "All payment writes MUST be idempotent keyed on a client-supplied request id", rationaleRef
"section 4 / Idempotency / rationale paragraph".* The full schema and field types are in
`references/extraction-schema.md`.

## What you do NOT do

- You do **not** evaluate, score, or critique the architecture. That belongs to a reviewer, not an extractor.
- You do **not** invent constraints, fill missing rationale, or infer decisions the SAD never states.
- You do **not** paraphrase a statement into different meaning — minimal normalization only (whitespace, list-marker stripping), never reinterpretation.
- You do **not** write the TRD or the specs. You hand them a packet; they author from it.
- You do **not** extract sections 1, 3, 5, 6, 7, 10, 11, or 12 into this packet.

If you find yourself producing requirement language, design opinions, or content with no anchor in
the SAD, stop: you have left the extractor contract.

## References

- `references/extraction-schema.md` — the typed packet shape: bucket structure, per-entry fields (`id`, `sourceSection`, `statement`, `rationaleRef`), and the stable-ID derivation rule.
- `references/section-selectors.md` — the layered selector cascade for locating each arc42 section across single-file and one-file-per-section layouts, with synonyms and structural fallbacks.
- `references/trd-feed-contract.md` — the downstream contract: what is guaranteed present, how IDs stay stable, how missing sections are signaled, and how supersession is communicated to the TRD and spec authors.
- `../arc42/references/` — the sibling SAD-authoring skill's section model and template (the authoring side your selectors target).
