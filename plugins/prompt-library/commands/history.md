---
name: history
description: Show recently run prompts with timestamps, variable values used, and quick re-run option.
argument-hint: "[--limit <n>] [--clear]"
allowed-tools: Read, Write, Bash
---

Read run history from `~/.claude/prompts/.history.json`. This file is maintained by `/prompt:run` and `/prompt:exec`.

Expected format:
```json
[
  {
    "name": "coding/review",
    "timestamp": "2025-03-01T14:32:00Z",
    "scope": "global",
    "variables": { "language": "Python", "context": "API handler" }
  }
]
```

If `--clear` flag: ask "Clear all run history? (yes/no)". If confirmed, truncate the history file to `[]` and confirm.

If the file does not exist or is empty, tell the user: "No run history yet. History is recorded when you use `/prompt:run` or `/prompt:exec`."

Default limit: 20 entries. Override with `--limit <n>`.

Display entries in reverse chronological order (most recent first). For each entry show:
- Timestamp (formatted as relative time: "2 hours ago", "yesterday", etc.)
- Prompt name and scope badge
- Variables used (if any), formatted as `key=value` pairs

After displaying history, ask: "Would you like to re-run any of these?" If yes, ask which one, then proceed as `/prompt:run` with the same variable values pre-filled.
