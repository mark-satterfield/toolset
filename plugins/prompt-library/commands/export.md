---
name: export
description: Export one or all prompts to a .md or .json file.
argument-hint: "[name|--all] [--format md|json] [--output <path>]"
allowed-tools: Read, Write, Bash
---

Determine what to export:
- If a prompt name is provided: export that single prompt
- If `--all` flag: export all prompts from both global and project-local libraries

Determine format:
- `--format md`: export as a single `.md` file (for single prompts) or a zip/directory of `.md` files (for --all)
- `--format json`: export as a `.json` collection file
- If no format specified, ask: "Export as .md or .json?"

Determine output path:
- If `--output <path>` is provided, use that path
- Otherwise, use the current working directory with a default filename:
  - Single: `[name].md` or `[name].json`
  - All: `prompts-export.json` or `prompts/` directory

**Single `.md` export:**
Write the prompt file as-is (frontmatter + body).

**Single `.json` export:**
Write: `{ "name": "...", "description": "...", "tags": [], "variables": [], "body": "..." }`

**All prompts `.json` export:**
Write an array of all prompt objects from both libraries. Include a `scope` field (`"global"` or `"local"`) for each.

**All prompts `.md` export:**
Create the output directory. Write each prompt as a separate `.md` file, preserving category subdirectory structure.

Confirm: "Exported [n] prompt(s) to [output path]."
