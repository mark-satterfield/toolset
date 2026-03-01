---
name: clone
description: Duplicate an existing prompt under a new name as a starting point for a new prompt.
argument-hint: "[source] [new-name] [--global]"
allowed-tools: Read, Write, Bash
---

If source is not provided, ask: "Which prompt would you like to clone?"
If new name is not provided, ask: "What should the clone be named?"

Find the source prompt (check project-local first, then global).
If not found, tell the user and suggest `/prompt:search`.

Check the new name does not already exist in the target scope. If it does, tell the user and ask for a different name.

Determine save location:
- Default: same scope as the source
- If `--global` flag: save to global library
- If `--local` flag: save to project-local library

Copy the source prompt file to the new name (creating subdirectories if the new name is namespaced).

Confirm: "Prompt '[source]' cloned as '[new-name]' in [scope] library."
Ask: "Would you like to edit it now?" If yes, proceed as `/prompt:edit [new-name]`.
