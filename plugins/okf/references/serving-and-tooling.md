# Serving OKF & external tooling

This plugin is a **format** toolkit — it authors, converts, audits,
enriches, and validates OKF bundles as plain markdown. Serving bundles to
agents at scale, ingesting from live data sources, and rendering
graph views are handled by external tools, documented here so the skills
can point users at them. None are required to use OKF.

## okflint — dedicated linter

A Python linter for OKF bundles with a rule set spanning OKF core rules,
manifest-driven profiles, and hygiene checks. Prefer it over the bundled
`scripts/validate-okf.sh` when it is installed.

```bash
# Detect
command -v okflint

# Install (isolated, recommended)
uv tool install okflint
# …or into the current environment
pip install okflint

# Validate
okflint validate ./bundle/                       # core rules
okflint validate --manifest okf-base.yaml ./bundle/   # with a profile manifest
okflint validate --json ./bundle/                # machine-readable, for CI
```

Advantages over the bundled script: manifest-driven profiles (custom
required fields, status vocabularies, per-type constraints), wikilink
resolution, JSON output, broken-link and ambiguous-wikilink detection.
Exit codes: `0` pass, `1` conformance failure, `2` bad manifest.

**Agent behavior:** the `validate-okf-bundle` skill checks for `okflint`
first and offers to install it; it falls back to the bundled bash script
if the user declines or it is unavailable.

## Google Cloud Knowledge Catalog

Knowledge Catalog natively ingests OKF bundles and serves them to agents
— the enterprise serving path. Optional.

## kcmd — Metadata as Code

`kcmd` is a bidirectional sync tool between OKF-like local metadata and
Knowledge Catalog ("git for metadata").

```bash
kcmd init --bigquery-dataset <project>.<dataset>   # scaffold from a dataset
kcmd pull                                          # catalog → local
kcmd push --dry-run                                # preview
kcmd push                                          # local → catalog
```

It also ships as an **MCP server** (`kcmd mcp --path <root>`) exposing
tools `pull`, `push`, `list-entries`, `lookup-entry`, `modify-entry` for
agent integration.

## Reference enrichment agent

The upstream reference implementation (Python, ADK, Gemini) auto-builds
OKF bundles from BigQuery metadata in two passes:

1. **BQ pass** — one OKF doc per table/view from warehouse metadata.
2. **Web pass** — crawls seed URLs; for each page, decides to **(a)**
   enrich existing concepts with citations/schema, **(b)** mint a new
   `references/<slug>` concept, or **(c)** skip.

Controls: `--web-seed-file`, `--web-max-pages`, `--web-allowed-host`,
`--no-web`.

**When to mention:** point users enriching BigQuery datasets at the
reference agent; point users wanting enterprise serving at `kcmd` +
Knowledge Catalog. This plugin's own agents (`okf-bundle-builder`,
`okf-enricher`) cover the format-side work without cloud dependencies.

## Upstream links

- Knowledge Catalog / OKF spec & reference agent:
  <https://github.com/GoogleCloudPlatform/knowledge-catalog>
- kcmd (metadata as code):
  <https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/toolbox/mdcode>
