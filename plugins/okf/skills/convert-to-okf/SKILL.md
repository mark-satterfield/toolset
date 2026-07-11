---
name: convert-to-okf
description: >-
  Convert existing files, a directory tree, or a foreign format into a
  conformant Open Knowledge Format (OKF) bundle. Use when the user has markdown
  files, an Obsidian vault, a Notion export, a CSV/spreadsheet, database/
  warehouse (e.g. BigQuery) metadata, or an OpenAPI/GraphQL spec and wants it
  turned into OKF, made OKF-conformant, or made interoperable/agent-readable.
  Handles a handful of files inline; delegates a large tree to the
  okf-bundle-builder agent.
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash, Agent]
---

# Convert a source to OKF

Turn existing material into an OKF bundle. The universal move: **one source item
→ one concept file with a `type`**, then group into directories, generate
indexes, cross-link, and validate.

Per-format rules live in
`${CLAUDE_PLUGIN_ROOT}/references/conversion-guides.md` — read the section
matching the source (plain markdown, Obsidian, Notion, CSV, database metadata,
OpenAPI/GraphQL). Field and structure rules:
`${CLAUDE_PLUGIN_ROOT}/references/frontmatter-fields.md` ·
`${CLAUDE_PLUGIN_ROOT}/references/structure-patterns.md`.

## First: size the job

`Glob`/`find` the source and count items to convert.

- **≲ 15 files, or the user wants to make decisions along the way** → convert
  inline with this skill.
- **Large tree / whole vault / whole dataset** → delegate to the
  **`okf-bundle-builder`** agent (spawn via the `Agent` tool with
  `subagent_type: okf-bundle-builder`). Pass it the source path, target bundle
  path, the source format, and any type/host constraints. It converts file by
  file in its own context and reports back.

## Inline conversion workflow

1. **Identify the source/directory type** and open the matching guide section.
   The directory type is a prior, not a guarantee — verify each file's actual
   type as you go and re-dispatch if it doesn't match (a stray `.csv` or Notion
   page inside an Obsidian vault gets its own rules).
2. **Map each item to a concept** — add `type` to every file (the #1 thing that
   makes output conformant); then **fill obvious gaps** for every file
   regardless of format: `title` from a title field / H1 / filename,
   `description` from a summary field / body / one-liner you write. Set
   `resource` when the item is a real asset, and preserve unknown source
   metadata as extension keys. For binary/non-text sources (PDF, DOCX, XLSX,
   images…), extract to Markdown first with the `to-markdown-util` skill, then
   convert the result.
3. **Fix links** — convert wikilinks / Notion / intra-repo links to
   bundle-relative markdown links.
4. **Generate indexes** — `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/okf_tools/index.py <bundle>`
   reindexes every directory in one pass (the root `index.md` gets `okf_version: "0.1"`).
5. **Add a `log.md`** recording the conversion (optional).
6. **Validate** — `${CLAUDE_PLUGIN_ROOT}/scripts/validate-okf.sh <bundle>` — and report the tree, the
   file count, and the conformance result.

## Guardrails

**Never invent data** — missing type/URI/schema → omit or ask, never fabricate.
Preserve unknown metadata keys · one concept per file (split multi-entity docs)
· `type` is the only hard requirement · broken links OK · minimal by default.
Do not query row-level data when converting warehouse metadata — OKF captures
metadata and curated insight, not rows.
