---
name: author-okf-bundle
description: >-
  Create an Open Knowledge Format (OKF) knowledge bundle from scratch — an
  interactive, in-the-loop workflow for greenfield authoring. Use when the user
  wants to build a new OKF bundle, start a knowledge base for agents, capture
  knowledge as markdown+frontmatter concepts, or structure tables/metrics/APIs/
  playbooks into an agent-readable catalog. For converting existing files use
  convert-to-okf; for reviewing an existing tree use the okf-auditor agent.
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash]
---

# Author an OKF bundle

Greenfield authoring. The scope and structure decisions need the user in the
loop — this is an interactive skill, not a bulk job. (For building a bundle
autonomously from a large existing source, hand off to the `okf-bundle-builder`
agent instead.)

Rules live in the bundled references — read them, don't restate them
(resolve via `${CLAUDE_PLUGIN_ROOT}`):
`references/spec-v01.md` · `references/frontmatter-fields.md` ·
`references/structure-patterns.md` · `references/examples.md`.

## Workflow

### 1. Determine scope and structure

Ask what knowledge is being captured (tables, metrics, APIs, playbooks, …) and
who consumes it. Propose a directory tree grouped by kind or subject area. Keep
depth shallow. Confirm the tree before writing files.

### 2. Write concept documents

One concept = one `.md` file. Every file needs frontmatter with a non-empty
`type`; add the recommended fields that are warranted (`title`, `description`,
and `resource` for resource-bound concepts). Favor structural body markdown —
`# Schema` tables, `# Examples` code blocks — over prose. See
`${CLAUDE_PLUGIN_ROOT}/references/examples.md` for shapes by domain.

**Never invent data.** If you don't know a `type`, a column, or a URI, ask or
omit — do not fabricate.

### 3. Cross-link

Weave bundle-relative links (`/tables/customers.md`) into prose where a real
relationship exists — FKs, metric inputs, join partners, playbook triggers. No
standalone "links" section. Broken links are allowed.

### 4. Generate indexes

Run `${CLAUDE_PLUGIN_ROOT}/scripts/gen-index.sh <dir> > <dir>/index.md` for each directory to produce
progressive-disclosure listings from child frontmatter. Optionally add a
bundle-root `index.md` with `okf_version: "0.1"` frontmatter (the only index
that may carry frontmatter).

### 5. Log (optional)

Add a `log.md` recording creation, newest first, ISO 8601 date headings.

### 6. Validate and report

Run `${CLAUDE_PLUGIN_ROOT}/scripts/validate-okf.sh <bundle>`. Then present:

1. The directory tree.
2. Conformance result (aim for `PASS`; explain any warnings).

## Guardrails

Never invent data · `type` is the only hard requirement · preserve unknown
keys · don't impose taxonomy · broken links OK · minimal by default.
