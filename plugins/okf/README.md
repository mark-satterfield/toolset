# okf

A toolkit for the **Open Knowledge Format (OKF)** — the open spec for
representing knowledge as a directory of markdown files with YAML frontmatter,
readable by humans without tooling and parseable by agents without an SDK. If you
can `cat` a file, you can read OKF; if you can `git clone` a repo, you can ship
it.

This plugin lets you **author, convert, audit, enrich, and validate** OKF
bundles. It is a *format* toolkit — it works on the markdown, and points you at
external tools (`okflint`, `kcmd`, Google Cloud Knowledge Catalog) for linting
profiles and enterprise serving.

## What OKF is

- **Bundle** — a directory tree of `.md` files; the unit of distribution.
- **Concept** — one markdown file = one unit of knowledge (a table, a metric, an
  API, a playbook…). The frontmatter's `type` field is the only hard
  requirement.
- **Index / log** — reserved files (`index.md`, `log.md`) for progressive
  disclosure and change history.

Full spec: [`references/spec-v01.md`](references/spec-v01.md).

## Architecture

A thin router skill (`okf`) dispatches on entry intent. The work splits by
whether it needs you in the loop (a **skill**) or runs as bulk / read-only
fan-out in its own context (an **agent**):

| Capability | Component | Kind |
|---|---|---|
| Route intent on entry | `okf` | skill (router) |
| Create a bundle from scratch | `author-okf-bundle` | skill (interactive) |
| Convert files / a tree / a foreign format | `convert-to-okf` | skill → delegates to builder agent for large trees |
| Enrich concepts | `enrich-okf-concepts` | skill → delegates to enricher agent for bulk |
| Validate conformance | `validate-okf-bundle` | skill (deterministic) |
| Review a tree & recommend changes | `okf-auditor` | agent (read-only report) |
| Build a bundle from a big source | `okf-bundle-builder` | agent (bulk write) |
| Enrich a whole bundle | `okf-enricher` | agent (bulk write) |

Skills own the OKF knowledge (the shared `references/`); the agents are lean
workers whose prompts point at the same references, so the rules live in one
place.

## Slash commands

- `/okf:author` — create a new bundle interactively
- `/okf:convert` — convert files / a directory / a foreign format to OKF
- `/okf:audit` — review a tree and get a ranked recommendation report (read-only)
- `/okf:enrich` — add schema, examples, citations, and cross-links to concepts
- `/okf:validate` — check OKF v0.1 conformance

Or just describe what you want — the `okf` router skill picks the path.

## Scripts

Deterministic tools the skills and agents call:

- [`scripts/validate-okf.sh`](scripts/validate-okf.sh) — v0.1 conformance check
  (`E1`/`E2`/`E3` errors + warnings). Exit `0` pass, `1` fail, `2` bad path.
- [`scripts/gen-index.sh`](scripts/gen-index.sh) — generate a conformant
  `index.md` for a directory from its children's frontmatter.

## References (bundled knowledge)

- [`spec-v01.md`](references/spec-v01.md) — the authoritative OKF v0.1 spec
- [`frontmatter-fields.md`](references/frontmatter-fields.md) — field reference
- [`structure-patterns.md`](references/structure-patterns.md) — tree layout,
  indexes, cross-linking
- [`conversion-guides.md`](references/conversion-guides.md) — per-format
  conversion rules (markdown, Obsidian, Notion, CSV, warehouse metadata,
  OpenAPI/GraphQL)
- [`examples.md`](references/examples.md) — concept examples by domain
- [`serving-and-tooling.md`](references/serving-and-tooling.md) — `okflint`,
  `kcmd`, Knowledge Catalog, the reference enrichment agent

## Conformance rules (the whole bar)

A bundle is OKF v0.1 conformant when:

1. Every non-reserved `.md` file has a parseable YAML frontmatter block.
2. Every frontmatter block has a non-empty `type` field.
3. Reserved files (`index.md`, `log.md`) follow their structure rules.

Everything else is soft guidance. A bundle is **never** rejected for missing
optional fields, unknown `type` values, unknown frontmatter keys, broken links,
or missing indexes.

## Guardrails

1. **Never invent data** — unknown `type`/URI/schema → ask or omit; never
   fabricate.
2. **`type` is the only hard requirement.**
3. **Preserve unknown frontmatter keys** — OKF allows extension.
4. **Don't impose taxonomy** — type values are free-form; suggest, never reject.
5. **Broken links are allowed** — they represent not-yet-written knowledge.
6. **Minimal by default** — emit `type` plus warranted recommended fields; no
   padding.

## Scope: what this plugin does and does NOT do

**Does:** author, convert, audit, enrich, and validate OKF bundles as markdown +
YAML; generate indexes; run conformance checks.

**Does NOT:** ingest live BigQuery/warehouse data, crawl the web to build
bundles from scratch, run an enterprise catalog, or render the graph viewer —
those belong to the external tools documented in
[`serving-and-tooling.md`](references/serving-and-tooling.md). This plugin stays
markdown/YAML-only, matching the rest of the marketplace.

## Credits

OKF is an open specification from Google Cloud's Knowledge Catalog project. The
bundled spec and conversion concepts derive from that specification and its
reference implementation; this plugin is an independent toolkit, not affiliated
with Google.
