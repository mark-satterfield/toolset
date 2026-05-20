---
description: Start shaping a raw invention idea — Socratic clarification, Alice-failure-mode triage, alternative-embodiment exploration, and a populated idea.md.
argument-hint: "[free-text idea, or path to existing idea.md]"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, WebFetch, WebSearch, AskUserQuestion
---

# /patent:idea

Invoke the `patent-ideation` skill on the provided idea text or `idea.md` path.

## Process

1. If `$ARGUMENTS` is empty, ask the user: "Describe your idea — what is the invention you want to shape? A sentence is fine; I'll ask the questions to flesh it out."
2. If `$ARGUMENTS` is a path to an existing `idea.md`, read it and resume from the current `funnel stage`. If the stage is `raw`, continue shaping. If it is past `raw`, redirect to the appropriate next skill.
3. Otherwise, treat `$ARGUMENTS` as the raw idea text.
4. Load and execute `skills/patent-ideation/SKILL.md`.
5. On completion (funnel stage `shaped`), recommend `/patent:assess` as the next step.

## Notes

- This command and the router skill `patent` overlap. Use the slash command for explicit start; let the router handle implicit phrasing in normal conversation.
