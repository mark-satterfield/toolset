---
description: Review/lint FORGE-structured instructions against the framework and return only a grade — Score (A–F), Confidence percentage, and an optional Suggestion. Asks no questions, writes no files.
argument-hint: "[path | inline text]"
allowed-tools: Read, Glob, Grep, Skill
---

# /forge:review-instructions

Invoke the `review-instructions` skill.

## Process

1. Resolve `$ARGUMENTS` per `references/operating-rules.md` §2:
   - A file path → read it as the instructions to grade. Fix an obvious path typo; if not findable in the obvious place, stop and say so. Do not crawl the file system.
   - Inline text → use it as the instructions to grade.
   - Empty → ask the user which instructions to review.
2. Load and execute `skills/review-instructions/SKILL.md`.
3. Return only the grade block. Add no preamble, no questions, no narration.
