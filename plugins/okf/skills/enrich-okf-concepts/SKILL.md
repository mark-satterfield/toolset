---
name: enrich-okf-concepts
description: >-
  Enrich existing Open Knowledge Format (OKF) concept documents — add schema
  tables, examples, citations, cross-links, and missing recommended frontmatter
  fields. Use when the user has OKF concepts (or a bundle) that are thin,
  metadata-only, or missing structure and wants them fleshed out, enriched, or
  improved. Handles a few concepts inline; delegates whole-bundle enrichment to
  the okf-enricher agent.
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash, Agent, WebFetch, WebSearch]
---

# Enrich OKF concepts

Deepen existing concepts. The enrichment moves, in the order the reference
enrichment agent applies them:

1. **Fill recommended fields** — add `title`, `description`, `tags`,
   `timestamp` where missing; derive values from body content when possible.
2. **Add `# Schema`** — for data assets, a Column / Type / Description table;
   link FK columns to their target concept.
3. **Add `# Examples`** — for APIs, queries, tools: fenced code blocks showing
   real usage.
4. **Add `# Citations`** — numbered external sources backing claims; may be
   URLs, bundle-relative paths, or paths into `references/`.
5. **Weave cross-links** — into prose, based on discovered relationships (FKs,
   shared tags, join paths). No standalone "links" section.

Shapes to copy: `${CLAUDE_PLUGIN_ROOT}/references/examples.md`. Field rules:
`${CLAUDE_PLUGIN_ROOT}/references/frontmatter-fields.md`.

## First: size the job

- **A few concepts** → enrich inline with this skill.
- **A whole bundle / dozens of concepts** → delegate to the **`okf-enricher`**
  agent (`Agent` tool, `subagent_type: okf-enricher`). Pass the bundle path,
  which enrichment moves to apply, and any allowed hosts for citation lookups.
  It processes each concept in fresh context and reports what it changed.

## Sourcing citations

When adding citations or schema you don't already have, you may use `WebFetch`/
`WebSearch` to find authoritative sources — but **cite, don't fabricate**. If a
fact can't be sourced, leave it out. Prefer the source system's own docs.

## Guardrails

**Never invent data** — no fabricated columns, URLs, or schema. Preserve
existing and unknown frontmatter keys. Don't overwrite author intent — add,
don't rewrite. `type` stays as the author set it unless it is clearly wrong (ask
first). Minimal by default — only add sections that are warranted.

After enriching, optionally regenerate indexes
(`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/okf_tools/index.py <bundle>`) since
descriptions may have changed, and validate
(`${CLAUDE_PLUGIN_ROOT}/scripts/validate-okf.sh`).
