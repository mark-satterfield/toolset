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
| Sync a bundle with its source tree | `sync-okf-bundle` | skill → delegates to sync agent for large diffs |
| Enrich concepts | `enrich-okf-concepts` | skill → delegates to enricher agent for bulk |
| Validate conformance | `validate-okf-bundle` | skill (deterministic) |
| Render a bundle as an interactive graph | `visualize-okf-bundle` | skill (deterministic) |
| Review a tree & recommend changes | `okf-auditor` | agent (read-only report) |
| Build a bundle from a big source | `okf-bundle-builder` | agent (bulk write) |
| Enrich a whole bundle | `okf-enricher` | agent (bulk write) |
| Sync a whole bundle at scale | `okf-sync` | agent (bulk write) |

Skills own the OKF knowledge (the shared `references/`); the agents are lean
workers whose prompts point at the same references, so the rules live in one
place.

## Slash commands

- `/okf:author` — create a new bundle interactively
- `/okf:convert` — convert files / a directory / a foreign format to OKF
- `/okf:audit` — review a tree and get a ranked recommendation report (read-only)
- `/okf:enrich` — add schema, examples, citations, and cross-links to concepts
- `/okf:validate` — check OKF v0.1 conformance
- `/okf:visualize` — render a bundle as a self-contained interactive HTML graph
- `/okf:sync` — reconcile a bundle with its source tree(s) (incremental update)

Or just describe what you want — the `okf` router skill picks the path.

## Scripts

Deterministic tools the skills and agents call:

- [`scripts/validate-okf.sh`](scripts/validate-okf.sh) — v0.1 conformance check
  (`E1`/`E2`/`E3` errors + warnings). Exit `0` pass, `1` fail, `2` bad path.
- [`scripts/okf_tools/`](scripts/okf_tools/) — Python utilities: the OKF
  document model (`document.py`), concept addressing (`paths.py`), the
  whole-bundle index generator (`index.py` — regenerates every `index.md`,
  grouped by `type`, with subdir summaries), the incremental sync engine
  (`sync.py` — diffs a bundle against its source by provenance), and
  `viewer.py`, which renders a bundle as a **self-contained** interactive HTML
  graph (Cytoscape + marked + DOMPurify inlined; no CDN). The document/index/
  viewer portions are adapted from the OKF reference agent (Apache 2.0); see
  [`scripts/okf_tools/NOTICE.md`](scripts/okf_tools/NOTICE.md).

## References (bundled knowledge)

- [`spec-v01.md`](references/spec-v01.md) — the authoritative OKF v0.1 spec
- [`frontmatter-fields.md`](references/frontmatter-fields.md) — field reference
- [`structure-patterns.md`](references/structure-patterns.md) — tree layout,
  indexes, cross-linking
- [`conversion-guides.md`](references/conversion-guides.md) — conversion as a
  directory-setup → per-file recognition → finalize loop (markdown, Obsidian,
  Notion, binary docs, CSV, warehouse metadata, OpenAPI/GraphQL)
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

**Does:** author, convert, audit, enrich, validate, and visualize OKF bundles as
markdown + YAML; generate indexes; run conformance checks; render a
self-contained HTML graph viewer. Small Python utilities back the deterministic
tasks (document model, viewer).

**Does NOT:** ingest live BigQuery/warehouse data, crawl the web to build
bundles from scratch, or run an enterprise catalog — those belong to the
external tools documented in
[`serving-and-tooling.md`](references/serving-and-tooling.md).

## Credits

OKF is an open specification from Google Cloud's Knowledge Catalog project. The
bundled spec and conversion concepts derive from that specification and its
reference implementation; this plugin is an independent toolkit, not affiliated
with Google.

The Python utilities under [`scripts/okf_tools/`](scripts/okf_tools/)
(`document.py`, `paths.py`, `index.py`, `viewer.py`) are adapted from that
reference implementation and remain under the **Apache License 2.0**
([bundled copy](scripts/okf_tools/LICENSE.apache-2.0)); the rest of the plugin
is **MIT** ([`LICENSE`](LICENSE)). The generated viewer inlines Cytoscape.js
(MIT), marked (MIT), and DOMPurify (Apache-2.0 / MPL-2.0). Full attribution and
the list of modifications:
[`scripts/okf_tools/NOTICE.md`](scripts/okf_tools/NOTICE.md).
