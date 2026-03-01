---
name: compose
description: Semantically synthesize two or more prompts into a single coherent prompt. Deduplicates overlapping instructions, resolves conflicts, and produces one authoritative result. Does not concatenate — produces an intelligent merge.
argument-hint: "[name1] [name2] ... [--save <new-name>] [--global]"
allowed-tools: Read, Write, Bash
---

If fewer than two prompt names are provided, ask: "Which prompts would you like to compose? Provide at least two names."

Load all specified prompts. Display a brief summary of each: name, description, first 100 chars of body.

Perform semantic synthesis:

1. **Identify shared intent**: Find instructions that both/all prompts express, even if worded differently (e.g. "be concise" appearing in multiple forms).

2. **Identify unique content**: Find instructions that appear in only one prompt and have no counterpart elsewhere.

3. **Identify conflicts**: Find instructions that directly contradict each other (e.g. "respond formally" vs "respond conversationally"). For each conflict, present both versions to the user and ask: "These instructions conflict. Which should take precedence, or would you like to reword?" Wait for the answer before proceeding.

4. **Synthesize**: Produce a single, coherent prompt that:
   - Expresses each shared intent once, in the clearest phrasing
   - Includes all unique content from each source
   - Reflects the conflict resolutions chosen by the user
   - Reads as a single authored document, not a concatenation

5. **Merge variables**: Combine variable lists from all source prompts. Deduplicate variables with identical names. If two prompts define the same variable name with different descriptions, ask the user which definition to keep.

Show the composed result to the user for review.

Ask: "Save this as a new prompt? If yes, what name?" (or use `--save <name>` if provided).

If saving: determine scope (`--global` or project-local default). Write the file. Confirm: "Composed prompt saved as '[name]'."

If not saving: the user can copy the displayed text manually.
