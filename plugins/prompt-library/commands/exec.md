---
name: exec
description: Run two or more prompts either sequentially (one after another) or in parallel (as independent tasks). Default is sequential.
argument-hint: "[name1] [name2] ... [--sequential|--parallel]"
allowed-tools: Read, Write, Bash
---

If fewer than two prompt names are provided, ask: "Which prompts would you like to run? Provide at least two names."

Determine execution mode:
- `--parallel`: run all prompts as independent tasks simultaneously using sub-agents
- `--sequential` or no flag: run prompts one after another

For each prompt:
- Find the file (project-local first, then global)
- Parse variables from the body
- If variables exist, ask for values interactively (show prompt name first so user knows which prompt's variables are being filled)

**Sequential mode:**
Run each prompt in order. After each completes, proceed to the next. Show a divider between results: `--- [prompt-name] complete ---`.

**Parallel mode:**
Dispatch all prompts as concurrent sub-agent tasks. Each sub-agent receives the assembled prompt text and runs independently. Collect and present all results when complete, labeled by prompt name.

Record each run in history.

After all prompts complete, summarize: "Executed [n] prompts [sequentially|in parallel]: [name1], [name2], ..."
