---
description: Distill a READY, step-by-step implementation plan out of a multi-purpose document — steps in, everything else (decisions, history, notes, open questions) stays out. The plan carries per-step execution state so any session can resume it. Interactive Q&A by default; pass 'headless' to best-effort silently.
argument-hint: "[path | inline text | 'headless']"
allowed-tools: Read, Write, Edit, Glob, Grep, Skill, AskUserQuestion
---

# /forge:distill-plan

Invoke the `distill-plan` skill.

## Process

1. Resolve `$ARGUMENTS` per `${CLAUDE_PLUGIN_ROOT}/references/operating-rules.md` §2:
   - A file path → read it as the source document. Fix an obvious path typo; if not findable in the obvious place, stop and say so. Do not crawl the file system.
   - Inline text → use it as the source material.
   - Empty → ask the user for the source document (interactive), naming the forms accepted.
2. Determine mode: interactive unless `$ARGUMENTS` contains `headless`, `quiet`, `batch`, or `non-interactive`.
3. Load and execute `${CLAUDE_PLUGIN_ROOT}/skills/distill-plan/SKILL.md`.
