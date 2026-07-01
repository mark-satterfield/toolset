---
description: Revise existing FORGE-structured instructions to satisfy a change request, preserving untouched content and re-checking ripple effects. Interactive Q&A by default; pass 'headless' to best-effort silently.
argument-hint: "[path | inline text] + change request"
allowed-tools: Read, Write, Edit, Glob, Grep, Skill, AskUserQuestion
---

# /forge:revise-instructions

Invoke the `revise-instructions` skill.

## Process

1. Resolve `$ARGUMENTS` per `references/operating-rules.md` §2 into two parts:
   - The **existing instructions** — a file path or inline text. Fix an obvious path typo; if not findable in the obvious place, stop and say so. Do not crawl the file system.
   - The **change request** — what to alter, add, remove, or fix.
   - If either part is missing, ask the user for it (interactive).
2. Determine mode: interactive unless `$ARGUMENTS` contains `headless`, `quiet`, `batch`, or `non-interactive`.
3. Load and execute `skills/revise-instructions/SKILL.md`.
