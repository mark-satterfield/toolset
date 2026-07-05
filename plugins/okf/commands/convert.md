---
description: Convert files, a directory tree, or a foreign format (Obsidian, Notion, CSV, warehouse metadata, OpenAPI) into a conformant OKF bundle.
argument-hint: "[source path] [target bundle dir]"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent, AskUserQuestion
---

# /okf:convert

Invoke the `convert-to-okf` skill to turn an existing source into an OKF bundle.

## Process

1. Resolve `$ARGUMENTS` — first token is the source path, second (optional) is
   the target bundle dir. If the source is missing, ask for it and the format.
2. Load and execute `${CLAUDE_PLUGIN_ROOT}/skills/convert-to-okf/SKILL.md`.
3. Size the source: convert a small set inline; for a large tree/vault/dataset,
   delegate to the `okf-bundle-builder` agent (pass it the source, target,
   format, and the paths to `${CLAUDE_PLUGIN_ROOT}/references` and
   `${CLAUDE_PLUGIN_ROOT}/scripts`).
4. Validate the result with
   `${CLAUDE_PLUGIN_ROOT}/scripts/validate-okf.sh <bundle>` and report.

## Notes

- The universal move: one source item → one concept file with a `type`.
- Never invent data; never query row-level warehouse data (metadata only).
