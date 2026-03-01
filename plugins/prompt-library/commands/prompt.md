---
description: Prompt library — list available commands or run a stored prompt by name.
argument-hint: "[name | command]"
allowed-tools: Read
---

If an argument was provided:
- If it matches a stored prompt name (check `~/.claude/prompts/` and `.claude/prompts/`), run that prompt as if `/prompt:run [name]` was called.
- Otherwise, treat the argument as the name and suggest `/prompt:search [argument]`.

If no argument was provided, display this menu:

```
Prompt Library — available commands:

  /prompt:list               List all stored prompts
  /prompt:run [name]         Run a prompt with variable substitution
  /prompt:search [query]     Search prompts by name or tag
  /prompt:create [name]      Create a new prompt
  /prompt:edit [name]        Edit an existing prompt
  /prompt:show [name]        Show a prompt's content
  /prompt:clone [name]       Copy a prompt under a new name
  /prompt:delete [name]      Delete a prompt
  /prompt:import [file]      Import prompts from a file
  /prompt:export [name]      Export a prompt to a file
  /prompt:compose [a] [b]    Merge two prompts into one
  /prompt:exec [names...]    Run multiple prompts sequentially or in parallel
  /prompt:history            Show recent prompt runs
  /prompt:diff [a] [b]       Diff two prompt versions
```
