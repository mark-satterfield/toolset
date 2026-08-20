# Section selectors — locating arc42 sections reliably

arc42 is a twelve-section template. This skill targets four of them — **2 Constraints**,
**4 Solution Strategy**, **8 Crosscutting Concepts**, **9 Architecture Decisions**. The challenge is
that arc42 SADs ship in two common physical layouts, and authors rename headings. This file gives a
layered selector cascade that locates each target section robustly across both.

## Step 0 — detect the layout

Do not assume; detect from disk.

- **Single-file layout** — the entire SAD is one document (`architecture.md`, `arc42.adoc`, a single
  `.docx`/`.md`) whose top-level or second-level headings are the twelve arc42 sections. Detect by
  finding three or more arc42 section headings inside one file.
- **One-file-per-section layout** — a directory (often `docs/architecture/`, `arc42/`, `chapters/`)
  with one file per section, conventionally numeric-prefixed: `02-constraints.md`,
  `04-solution-strategy.md`, `08-concepts.md`.

Record the detected layout in the packet's `source.layout`. The selector cascade below is layout-aware.

## The full arc42 section catalog (for disambiguation)

Knowing the neighbors prevents grabbing the wrong block:

| # | Canonical title |
|---|---|
| 1 | Introduction and Goals |
| 2 | Constraints (a.k.a. Architecture Constraints) |
| 3 | Context and Scope |
| 4 | Solution Strategy |
| 5 | Building Block View |
| 6 | Runtime View |
| 7 | Deployment View |
| 8 | Crosscutting Concepts |
| 9 | Architecture Decisions |
| 10 | Quality Requirements |
| 11 | Risks and Technical Debt |
| 12 | Glossary |

Only 2, 4, 8 are in scope. There is no section 9. The rest exist here so a selector never mistakes,
say, section 11's "Technical Debt" for section 4's strategy, or section 10's quality scenarios for
crosscutting concepts.

## Selector cascade (apply per target section, stop at first hit)

For each target section, try selectors in order. The first that resolves wins; record which selector
matched in provenance so a human can audit a fuzzy match.

1. **Numeric prefix (strongest).**
   - One-file-per-section: match a filename whose leading number equals the target (`^0?2[-_. ]` for
     section 2, `^0?4`, `^0?8`, `^0?9`). Tolerate zero-padding and separators.
   - Single-file: match a heading line beginning with the section number — `## 2.`, `## 2 `,
     `# 2 Constraints`, `2. Constraints` — at any heading level.
2. **Canonical title (strong).** Case-insensitive match on the official title: `Constraints` /
   `Architecture Constraints`; `Solution Strategy`; `Crosscutting Concepts` / `Cross-cutting
   Concepts`; `Architecture Decisions` / `Design Decisions`.
3. **Known synonym (medium).** Accept documented aliases (table below). Synonym matches are valid but
   note them in provenance.
4. **Structural fallback (weak — last resort).** If numbering and titles are absent, locate by shape:
   Crosscutting Concepts is the
   section enumerating named concepts each with its own subheading. Use shape only when nothing
   stronger exists, and flag the entry's provenance as `selector: structural` so downstream readers
   know it is heuristic.

If two selectors point at different blocks for the same target, the higher-priority selector wins;
log the conflict in provenance rather than merging.

## Synonym table

| Target | Canonical | Common synonyms seen in the wild |
|---|---|---|
| 2 | Constraints | Architecture Constraints; Boundary Conditions; Constraints & Conventions |
| 4 | Solution Strategy | Solution Approach; Strategy; Technical Strategy; Approach |
| 8 | Crosscutting Concepts | Cross-cutting Concepts; Cross Cutting Concerns; Concepts; Architectural Concepts |

## Sub-structure within a located section

Once a section is located, split it into atomic entries (one per emitted Entry):

- **Section 2 / Constraints** — arc42 groups constraints as Technical, Organizational, and
  Conventions. Each table row or bullet is one entry. Preserve any tag the author gave (`TC-3`) as
  the ID anchor (see `extraction-schema.md`).
- **Section 4 / Solution Strategy** — usually prose plus a decisions-summary table. Each distinct
  strategic statement (chosen pattern, chosen technology, decomposition rationale, quality-goal-to-
  approach mapping row) is one entry.
- **Section 8 / Crosscutting Concepts** — each named concept (its own subheading: Security,
  Persistence, Error Handling, Logging, Internationalization, etc.) is one entry. Do not split a
  single concept's paragraphs into multiple entries unless the author numbered them.

## Provenance to record per located section

For each target, store: the matched file path(s), the heading text and line span (single-file) or
file name (per-file), the selector tier that matched (`numeric` | `title` | `synonym` |
`structural`), and any conflict notes. This provenance is what makes the extraction auditable and is
referenced by `rationaleRef` pointers and by the missing-section signaling in `trd-feed-contract.md`.
