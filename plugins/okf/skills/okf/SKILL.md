---
name: okf
description: >-
  Router for the Open Knowledge Format (OKF) toolkit. Detects intent on entry
  and dispatches to the right sub-skill or agent. Use when the user mentions
  'OKF', 'Open Knowledge Format', 'knowledge bundle', 'OKF bundle', 'knowledge
  catalog', 'LLM wiki', 'agent-readable knowledge', 'metadata as code', or wants
  to create, convert a directory/files into, review/audit, enrich, validate,
  visualize, or sync a markdown+frontmatter knowledge base for AI agents. Also use when the user has a
  directory of markdown files and wants it made OKF-conformant or interoperable.
allowed-tools: [Read, Grep, Glob, Bash, Agent]
---

# OKF toolkit — router

OKF (Open Knowledge Format) represents knowledge as a directory of markdown
files with YAML frontmatter — no SDK, no registry. Only `type` is required.
Full spec: `${CLAUDE_PLUGIN_ROOT}/references/spec-v01.md`.

This skill routes an incoming request to the right capability. It holds no
workflow logic of its own — detect intent, then hand off.

## Routing table

| The user wants to… | Route to | Kind |
|---|---|---|
| Create a bundle from scratch | `author-okf-bundle` skill | interactive |
| Convert files / a directory / a foreign format to OKF | `convert-to-okf` skill | interactive; delegates to agent for large trees |
| Sync / refresh / update a bundle from its source tree | `sync-okf-bundle` skill | interactive; delegates to agent for large diffs |
| Review a directory tree and get recommendations | `okf-auditor` agent | read-only report |
| Add schema / examples / citations / cross-links to concepts | `enrich-okf-concepts` skill | interactive; delegates to agent for bulk |
| Check conformance | `validate-okf-bundle` skill | deterministic |
| See / explore / visualize a bundle as an interactive graph | `visualize-okf-bundle` skill | deterministic |
| Build a whole bundle autonomously from a big source | `okf-bundle-builder` agent | bulk write |
| Enrich every concept across a bundle | `okf-enricher` agent | bulk write |

## How to decide interactive vs. agent

- **Small / needs decisions in the loop** (a handful of files, scope or type
  choices to make with the user) → use the interactive **skill**.
- **Large / repetitive / read-only fan-out** (dozens+ of files, per-file work,
  a whole-tree review) → delegate to the matching **agent** so each unit gets
  fresh context and the main window does not overflow.

When unsure of the split, size the input first (`Glob`/`find` the tree, count
`.md` files). Under ~15 files: interactive. Over that, or when the user says
"the whole tree/dataset/vault": delegate to the agent.

## Delegating to an agent

Spawn with the `Agent` tool, `subagent_type` set to the agent name
(`okf-auditor`, `okf-bundle-builder`, `okf-enricher`, or `okf-sync`). Give it: the source
path, the target bundle path, and any known constraints (types to use, hosts to
allow, whether to write indexes). The agents already know the OKF rules from the
bundled `references/`.

## Shared knowledge

All capabilities draw on the same bundled references — do not restate the rules,
point at them (bundled paths, resolve via `${CLAUDE_PLUGIN_ROOT}`):

- `${CLAUDE_PLUGIN_ROOT}/references/spec-v01.md` — the authoritative spec
- `${CLAUDE_PLUGIN_ROOT}/references/frontmatter-fields.md` — field reference
- `${CLAUDE_PLUGIN_ROOT}/references/structure-patterns.md` — tree layout, indexes, cross-linking
- `${CLAUDE_PLUGIN_ROOT}/references/conversion-guides.md` — directory- and file-level conversion rules
- `${CLAUDE_PLUGIN_ROOT}/references/examples.md` — concept examples by domain
- `${CLAUDE_PLUGIN_ROOT}/references/serving-and-tooling.md` — okflint, kcmd, Knowledge Catalog

## Guardrails (apply to every route)

1. **Never invent data.** Unknown `type` → ask. No fabricated URIs, columns, or timestamps.
2. **`type` is the only hard requirement.** Everything else is recommended or optional.
3. **Preserve unknown frontmatter keys.** OKF allows extension; never delete fields you don't recognize.
4. **Don't impose taxonomy.** Type values are free-form; suggest, never reject.
5. **Broken links are allowed** — they represent not-yet-written knowledge.
6. **Minimal by default.** Emit `type` plus warranted recommended fields; no padding.
