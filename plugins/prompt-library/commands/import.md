---
name: import
description: Import prompts from a local file or URL. Supports single .md prompt files and .json collections.
argument-hint: "[path|url] [--global] [--local]"
allowed-tools: Read, Write, Bash
---

If no path or URL is provided, ask: "What would you like to import? Provide a file path or URL."

Determine the source type:
- URL (starts with `http://` or `https://`): fetch the content
- Local `.md` file: read as a single prompt
- Local `.json` file: read as a prompt collection

Determine save location:
- Default: `.claude/prompts/` (project-local)
- `--global` flag: `~/.claude/prompts/`

**For a single `.md` file:**
Parse the YAML frontmatter. If frontmatter is missing or incomplete, ask the user for any missing required fields (name, description).
Check for name conflicts in the target location. If a conflict exists, ask: "A prompt named '[name]' already exists. Overwrite, rename, or skip?"

**For a `.json` collection:**
Expected format:
```json
[
  { "name": "...", "description": "...", "tags": [], "body": "..." },
  ...
]
```
Process each entry. Report conflicts for each and ask for resolution (overwrite / rename / skip).

**For a URL:**
Fetch the content. Detect format (`.md` or `.json`) based on Content-Type or file extension in URL.
Treat as the appropriate format above.

After import, confirm: "Imported [n] prompt(s) to [scope] library." List the names of imported prompts.
