---
description: Enrich OKF concepts — add schema tables, examples, citations, cross-links, and missing recommended frontmatter fields. Inline for a few, delegated for a whole bundle.
argument-hint: "[bundle/concept path]"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent, WebFetch, WebSearch, AskUserQuestion
---

# /okf:enrich

Invoke the `enrich-okf-concepts` skill to deepen existing OKF concepts.

## Process

1. Resolve `$ARGUMENTS` as a bundle directory or a single concept file. If
   missing, ask which bundle/concept to enrich.
2. Load and execute `${CLAUDE_PLUGIN_ROOT}/skills/enrich-okf-concepts/SKILL.md`.
3. Size the job: enrich a few concepts inline; for a whole bundle or dozens of
   files, delegate to the `okf-enricher` agent (pass the bundle path, the
   enrichment moves, allowed hosts, and the paths to
   `${CLAUDE_PLUGIN_ROOT}/references` and `${CLAUDE_PLUGIN_ROOT}/scripts`).
4. Regenerate indexes
   (`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/okf_tools/index.py <bundle>`) and
   validate.

## Notes

- Add depth; do not rewrite author intent. Preserve unknown frontmatter keys.
- Cite, never fabricate. If a fact can't be sourced, leave it out.
