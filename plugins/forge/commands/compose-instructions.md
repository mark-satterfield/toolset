---
description: Compose new FORGE-structured instructions an AI agent can execute without interpretation, from a rough prompt, a form, a file, or inline text. Interactive Q&A by default; pass 'headless' to best-effort silently.
argument-hint: "[inline text | path | 'headless']"
allowed-tools: Read, Write, Edit, Glob, Grep, Skill, AskUserQuestion
---

# /forge:compose-instructions

Invoke the `compose-instructions` skill.

## Process

1. Resolve `$ARGUMENTS` per `references/operating-rules.md` §2:
   - A file path → read it as the source material. Fix an obvious path typo; if not findable in the obvious place, stop and say so. Do not crawl the file system.
   - Inline text → use it as the source material.
   - Empty → ask the user for the source material (interactive), naming the forms accepted.
2. Determine mode: interactive unless `$ARGUMENTS` contains `headless`, `quiet`, `batch`, or `non-interactive`.
3. Load and execute `skills/compose-instructions/SKILL.md`.
