---
name: delete
description: Delete a prompt from the library. Confirms before removing.
argument-hint: "[name] [--force]"
allowed-tools: Read, Bash
---

If no name is provided, ask: "Which prompt would you like to delete?"

Find the prompt file (check project-local first, then global). If not found, tell the user.

If the prompt exists in both scopes (same name in local and global), ask: "Found this prompt in both local and global libraries. Which should be deleted?" Present both options.

Unless `--force` is passed, confirm with the user: "Delete '[name]' from [scope] library? This cannot be undone. (yes/no)"

If confirmed (or --force), delete the file. If the file was in a namespaced subdirectory and that directory is now empty, remove the empty directory.

Confirm deletion: "Prompt '[name]' deleted from [scope] library."

If the user says no, cancel and say "Deletion cancelled."
